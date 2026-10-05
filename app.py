"""
Job Recruitment and Applicant Tracking System: Commercial Multi-Tenant Platform.
Features:
- Role-Based Authentication with Flask-Login (Admin, Recruiter, Applicant)
- Multi-Tenant Company Registration & Recruiter Team Invitations
- Transactional Email Notifications with PostgreSQL Audit Logging (Flask-Mail)
- Stripe 3-Tier SaaS Subscriptions (Free/Basic/Pro) with Quota Enforcement
- Custom Branding & Dedicated Multi-Tenant Career Pages (/careers/<slug>)
- Advanced Job Search with Salary Filters, Remote Toggle, Sorting & Search History (Feature 6)
- Automated Resume Parser using pypdf & Database Skill Taxonomy (Feature 7)
- Saved Jobs / Bookmarks with 1-Click Apply (Feature 8)
- Application Withdrawal Workflow (Feature 9)
- Recruiter Collaboration Notes & Threaded Comments (Feature 10)
- 4 Dedicated Analytics Dashboards with Chart.js:
  1. Recruiter Executive Overview & Pipeline Funnel (/recruiter/dashboard)
  2. Admin SaaS MRR & Growth Hub (/admin/dashboard)
  3. Applicant Applications, Saved Jobs & Interviews (/applicant/dashboard)
  4. Recruiter Hiring Velocity & Time-to-Hire Analytics (/recruiter/analytics)
"""

import os
import time
import json
import secrets
from datetime import datetime, timedelta, date
from flask import (
    Flask, render_template, request, redirect, url_for, flash, 
    jsonify, send_from_directory, abort
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
import psycopg2

from config import Config
import db
import auth
from auth import role_required, User
import mailer
import payments
import parser

app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['LOGO_UPLOAD_FOLDER'], exist_ok=True)

# Initialize Authentication & Mail subsystems
auth.init_auth(app)
mailer.init_mail(app)


def allowed_file(filename):
    """Validates uploaded document files against permitted extensions."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def allowed_logo(filename):
    """Validates uploaded logo files against image extensions."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_LOGO_EXTENSIONS


def get_current_applicant_id():
    """Helper to retrieve or create applicant_id for current authenticated user."""
    if not current_user.is_authenticated:
        return None
    cand = db.query_one("SELECT applicant_id FROM applicants WHERE user_id = %s OR LOWER(email) = LOWER(%s);", (current_user.user_id, current_user.email))
    if cand:
        return cand['applicant_id']
    # If not existing, create a basic record
    first = current_user.first_name or current_user.username
    last = current_user.last_name or 'User'
    new_id = db.execute_dml(
        "INSERT INTO applicants (user_id, first_name, last_name, email) VALUES (%s, %s, %s, %s) RETURNING applicant_id;",
        (current_user.user_id, first, last, current_user.email.lower()),
        returning_col='applicant_id'
    )
    return new_id


# ------------------------------------------------------------------------------
# AUTHENTICATION ROUTES (Flask-Login)
# ------------------------------------------------------------------------------

@app.route('/auth/login', methods=['GET', 'POST'])
def auth_login():
    """Universal Login for Admins, Recruiters, and Applicants."""
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for('admin_dashboard'))
        elif current_user.is_recruiter():
            return redirect(url_for('recruiter_dashboard'))
        elif current_user.is_applicant():
            return redirect(url_for('applicant_dashboard'))
        return redirect(url_for('index'))

    if request.method == 'POST':
        login_input = (request.form.get('login_input') or request.form.get('identifier') or '').strip()
        password = request.form.get('password', '').strip()
        remember = bool(request.form.get('remember'))

        user = auth.authenticate_user(login_input, password)
        if user:
            login_user(user, remember=remember)
            flash(f"Welcome back, {user.display_name}!", "success")
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)

            if user.is_admin():
                return redirect(url_for('admin_dashboard'))
            elif user.is_recruiter():
                return redirect(url_for('recruiter_dashboard'))
            elif user.is_applicant():
                return redirect(url_for('applicant_dashboard'))
            return redirect(url_for('index'))
        else:
            flash("Invalid email/username or password. Please try again.", "danger")

    return render_template('auth/login.html')


@app.route('/auth/register', methods=['GET', 'POST'])
def auth_register():
    """Applicant Self-Registration Portal."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        phone = request.form.get('phone', '').strip()
        location = request.form.get('location', '').strip()

        if not username or not email or not password or not first_name or not last_name:
            flash("All required fields must be provided.", "danger")
            return redirect(request.url)

        try:
            user_id = auth.register_applicant_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                location=location
            )
            new_user = auth.load_user(user_id)
            if new_user:
                login_user(new_user)
            flash("Registration successful! Welcome to the Job Recruitment and Applicant Tracking System.", "success")
            return redirect(url_for('applicant_dashboard'))
        except Exception as e:
            flash(f"Registration error: {e}", "danger")

    return render_template('auth/register.html')


@app.route('/auth/logout')
@login_required
def auth_logout():
    """Terminates authenticated session."""
    logout_user()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for('index'))


# ------------------------------------------------------------------------------
# DASHBOARD 3 & FEATURE 8: APPLICANT DASHBOARD & SAVED JOBS
# ------------------------------------------------------------------------------

@app.route('/applicant/dashboard')
@login_required
def applicant_dashboard():
    """
    DASHBOARD 3: Applicant Portal
    Displays Top KPI Cards, Active Applications (with Withdraw option),
    Saved Jobs Drawer, and Upcoming Interviews with Countdown.
    """
    if current_user.is_recruiter():
        return redirect(url_for('recruiter_dashboard'))

    applicant_id = get_current_applicant_id()

    # 1. Fetch Applications (Active + Withdrawn)
    sql_apps = """
        SELECT 
            a.application_id, a.status, a.applied_at, a.updated_at, a.resume_filename,
            j.job_id, j.title AS job_title, j.department, j.experience_level,
            c.name AS company_name, c.slug AS company_slug, c.location AS company_location
        FROM applications a
        JOIN jobs j ON a.job_id = j.job_id
        JOIN companies_v2 c ON j.company_id = c.company_id
        WHERE a.applicant_id = %s
        ORDER BY a.applied_at DESC;
    """
    applications = db.query_all(sql_apps, (applicant_id,))

    # 2. Fetch Saved Jobs
    sql_saved = """
        SELECT 
            j.*, c.name AS company_name, c.slug AS company_slug, c.logo_filename, c.brand_color,
            sj.saved_at
        FROM saved_jobs sj
        JOIN jobs j ON sj.job_id = j.job_id
        JOIN companies_v2 c ON j.company_id = c.company_id
        WHERE sj.applicant_id = %s
        ORDER BY sj.saved_at DESC;
    """
    saved_jobs = db.query_all(sql_saved, (applicant_id,))

    # 3. Fetch Upcoming Interviews
    sql_interviews = """
        SELECT 
            i.interview_id, i.interview_type, i.scheduled_at, i.duration_minutes, i.status, i.feedback,
            j.title AS job_title, c.name AS company_name, u.username AS interviewer_name
        FROM interviews i
        JOIN applications a ON i.application_id = a.application_id
        JOIN jobs j ON a.job_id = j.job_id
        JOIN companies_v2 c ON j.company_id = c.company_id
        JOIN users_v2 u ON i.interviewer_id = u.user_id
        WHERE a.applicant_id = %s AND i.status = 'Scheduled'
        ORDER BY i.scheduled_at ASC;
    """
    upcoming_interviews = db.query_all(sql_interviews, (applicant_id,))

    kpi = {
        'total_applications': len([a for a in applications if a['status'] != 'Withdrawn']),
        'saved_jobs_count': len(saved_jobs),
        'upcoming_interviews_count': len(upcoming_interviews)
    }

    return render_template(
        'applicant/dashboard.html',
        kpi=kpi,
        applications=applications,
        saved_jobs=saved_jobs,
        upcoming_interviews=upcoming_interviews
    )


@app.route('/applicant/saved-jobs')
@login_required
def applicant_saved_jobs():
    """Dedicated Saved Jobs / Bookmarks Page with 1-click apply."""
    applicant_id = get_current_applicant_id()
    sql_saved = """
        SELECT 
            j.*, c.name AS company_name, c.slug AS company_slug, c.logo_filename, c.brand_color,
            sj.saved_at
        FROM saved_jobs sj
        JOIN jobs j ON sj.job_id = j.job_id
        JOIN companies_v2 c ON j.company_id = c.company_id
        WHERE sj.applicant_id = %s
        ORDER BY sj.saved_at DESC;
    """
    saved_jobs = db.query_all(sql_saved, (applicant_id,))
    return render_template('applicant/saved_jobs.html', saved_jobs=saved_jobs)


@app.route('/jobs/<int:job_id>/bookmark', methods=['POST'])
@login_required
def toggle_bookmark(job_id):
    """FEATURE 8: Toggle Bookmark on a Job Vacancy."""
    applicant_id = get_current_applicant_id()
    
    # Check if already bookmarked
    existing = db.query_one("SELECT save_id FROM saved_jobs WHERE applicant_id = %s AND job_id = %s;", (applicant_id, job_id))
    
    if existing:
        db.execute_dml("DELETE FROM saved_jobs WHERE save_id = %s;", (existing['save_id'],))
        is_saved = False
        msg = "Job removed from your saved bookmarks."
    else:
        db.execute_dml("INSERT INTO saved_jobs (applicant_id, job_id) VALUES (%s, %s);", (applicant_id, job_id))
        is_saved = True
        msg = "Job saved to your bookmarks!"

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'success': True, 'is_saved': is_saved, 'status': 'saved' if is_saved else 'removed', 'message': msg})

    flash(msg, "info" if not is_saved else "success")
    return redirect(request.referrer or url_for('index'))


# ------------------------------------------------------------------------------
# FEATURE 9: APPLICATION WITHDRAWAL
# ------------------------------------------------------------------------------

@app.route('/applications/<int:application_id>/withdraw', methods=['POST'])
@login_required
def withdraw_application(application_id):
    """
    FEATURE 9: Candidate Application Withdrawal.
    Updates application status to 'Withdrawn' and sends notification emails.
    """
    # Verify ownership
    applicant_id = get_current_applicant_id()
    app_record = db.query_one("""
        SELECT a.*, j.title AS job_title, c.name AS company_name, cand.email, cand.first_name, cand.last_name
        FROM applications a
        JOIN jobs j ON a.job_id = j.job_id
        JOIN companies_v2 c ON j.company_id = c.company_id
        JOIN applicants cand ON a.applicant_id = cand.applicant_id
        WHERE a.application_id = %s;
    """, (application_id,))

    if not app_record:
        flash("Application not found.", "danger")
        return redirect(url_for('applicant_dashboard'))

    if app_record['applicant_id'] != applicant_id and not current_user.is_admin():
        flash("Unauthorized to withdraw this application.", "danger")
        return redirect(url_for('applicant_dashboard'))

    if app_record['status'] in ('Hired', 'Withdrawn'):
        flash(f"Application cannot be withdrawn as it is already marked '{app_record['status']}'.", "warning")
        return redirect(url_for('applicant_dashboard'))

    # Update status to Withdrawn
    db.execute_dml("UPDATE applications SET status = 'Withdrawn' WHERE application_id = %s;", (application_id,))

    # Dispatch notification email
    candidate_name = f"{app_record['first_name']} {app_record['last_name']}"
    mailer.send_notification(
        recipient_email=app_record['email'],
        subject=f"Application Withdrawn: {app_record['job_title']} at {app_record['company_name']}",
        email_type='status_change',
        body_text=f"Dear {candidate_name},\n\nYour application for {app_record['job_title']} at {app_record['company_name']} has been successfully withdrawn.\n\nThank you for considering {app_record['company_name']}."
    )

    flash("Your application has been withdrawn.", "info")
    return redirect(request.referrer or url_for('applicant_dashboard'))


# ------------------------------------------------------------------------------
# FEATURE 7: RESUME PARSER (API)
# ------------------------------------------------------------------------------

@app.route('/api/parse-resume', methods=['POST'])
def api_parse_resume():
    """
    FEATURE 7: Resume Parser API.
    Accepts uploaded PDF/DOCX, extracts candidate contact info and matches database skills.
    """
    if 'resume' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400

    file = request.files['resume']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    # Save to temp location
    filename = secure_filename(file.filename)
    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{int(time.time())}_{filename}")
    file.save(temp_path)

    try:
        parsed_data = parser.parse_resume(temp_path)
        return jsonify({'success': True, 'data': parsed_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


# ------------------------------------------------------------------------------
# FEATURE 10: RECRUITER COLLABORATION NOTES
# ------------------------------------------------------------------------------

@app.route('/applications/<int:application_id>/notes', methods=['POST'])
@login_required
@role_required(['recruiter', 'admin'])
def add_application_note(application_id):
    """
    FEATURE 10: Recruiter Team Notes.
    Stores collaboration comments per application with company-scoped access.
    """
    note_text = request.form.get('note_text', '').strip()
    if not note_text:
        flash("Note text cannot be empty.", "warning")
        return redirect(url_for('update_status', application_id=application_id))

    # Verify recruiter belongs to same company or is admin
    if not current_user.is_admin():
        app_company = db.query_one("""
            SELECT j.company_id 
            FROM applications a 
            JOIN jobs j ON a.job_id = j.job_id 
            WHERE a.application_id = %s;
        """, (application_id,))
        if not app_company or app_company['company_id'] != current_user.company_id:
            flash("Unauthorized: You can only comment on applications for your company.", "danger")
            return redirect(url_for('recruiter_dashboard'))

    try:
        db.execute_dml(
            "INSERT INTO application_notes (application_id, author_id, note) VALUES (%s, %s, %s);",
            (application_id, current_user.user_id, note_text)
        )
        flash("Recruiter note added to candidate record.", "success")
    except Exception as e:
        flash(f"Error adding note: {e}", "danger")

    return redirect(url_for('update_status', application_id=application_id))


# ------------------------------------------------------------------------------
# DASHBOARD 1: RECRUITER EXECUTIVE OVERVIEW & PIPELINE FUNNEL
# ------------------------------------------------------------------------------

@app.route('/recruiter/dashboard')
@login_required
@role_required(['recruiter', 'admin'])
def recruiter_dashboard():
    """
    DASHBOARD 1: Recruiter Dashboard.
    Features:
    - Top KPI cards: Total applicants, apps this week, upcoming interviews, hired this month.
    - Chart 1: Applications Over Time (Line chart with Chart.js).
    - Chart 2: Pipeline Stage Funnel (Bar chart with Chart.js).
    - Table 1: Recent 10 Applications.
    - Table 2: Today's and Upcoming Interviews.
    - Interactive Tab to toggle between Executive Dashboard and 6-Swimlane Kanban Pipeline.
    """
    selected_job_id = request.args.get('job_id', '')
    company_id = current_user.company_id

    # 1. Job filter dropdown list
    jobs_sql = """
        SELECT j.job_id, j.title, c.name AS company_name, j.status,
               COUNT(a.application_id) AS applicant_count
        FROM jobs j
        JOIN companies_v2 c ON j.company_id = c.company_id
        LEFT JOIN applications a ON j.job_id = a.job_id
    """
    jobs_params = []
    if company_id and not current_user.is_admin():
        jobs_sql += " WHERE j.company_id = %s"
        jobs_params.append(company_id)
    jobs_sql += " GROUP BY j.job_id, c.name ORDER BY j.created_at DESC;"
    all_jobs = db.query_all(jobs_sql, jobs_params)

    # 2. KPI Cards Metrics
    where_company = "WHERE j.company_id = %s" if (company_id and not current_user.is_admin()) else "WHERE 1=1"
    kpi_params = [company_id] if (company_id and not current_user.is_admin()) else []

    kpi_sql = f"""
        SELECT 
            COUNT(a.application_id) AS total_applicants,
            COUNT(CASE WHEN a.applied_at >= CURRENT_DATE - INTERVAL '7 days' THEN 1 END) AS apps_this_week,
            COUNT(CASE WHEN a.status = 'Hired' AND a.updated_at >= date_trunc('month', CURRENT_DATE) THEN 1 END) AS hired_this_month
        FROM applications a
        JOIN jobs j ON a.job_id = j.job_id
        {where_company};
    """
    kpi_data = db.query_one(kpi_sql, kpi_params)

    # Upcoming interviews count (next 7 days)
    iv_kpi_sql = f"""
        SELECT COUNT(i.interview_id) AS upcoming_interviews
        FROM interviews i
        JOIN applications a ON i.application_id = a.application_id
        JOIN jobs j ON a.job_id = j.job_id
        {where_company} AND i.status = 'Scheduled'
          AND i.scheduled_at >= CURRENT_TIMESTAMP 
          AND i.scheduled_at <= CURRENT_TIMESTAMP + INTERVAL '7 days';
    """
    iv_kpi_data = db.query_one(iv_kpi_sql, kpi_params)
    upcoming_count = iv_kpi_data['upcoming_interviews'] if iv_kpi_data else 0

    kpi = {
        'total_applicants': kpi_data['total_applicants'] if kpi_data else 0,
        'apps_this_week': kpi_data['apps_this_week'] if kpi_data else 0,
        'upcoming_interviews': upcoming_count,
        'hired_this_month': kpi_data['hired_this_month'] if kpi_data else 0
    }

    # 3. Chart 1: Applications Over Time (Past 14 Days)
    timeline_sql = f"""
        SELECT 
            TO_CHAR(d.day, 'Mon DD') AS day_label,
            COUNT(a.application_id) AS app_count
        FROM generate_series(CURRENT_DATE - INTERVAL '13 days', CURRENT_DATE, '1 day'::interval) d(day)
        LEFT JOIN (
            SELECT a.applied_at, a.application_id
            FROM applications a
            JOIN jobs j ON a.job_id = j.job_id
            {where_company}
        ) a ON DATE(a.applied_at) = DATE(d.day)
        GROUP BY d.day
        ORDER BY d.day ASC;
    """
    timeline_rows = db.query_all(timeline_sql, kpi_params)
    chart_timeline_labels = [r['day_label'] for r in timeline_rows]
    chart_timeline_data = [int(r['app_count']) for r in timeline_rows]

    # 4. Chart 2: Pipeline Stage Funnel
    funnel_sql = f"""
        SELECT 
            a.status, COUNT(*) AS count
        FROM applications a
        JOIN jobs j ON a.job_id = j.job_id
        {where_company}
        GROUP BY a.status;
    """
    funnel_rows = db.query_all(funnel_sql, kpi_params)
    funnel_dict = {r['status']: int(r['count']) for r in funnel_rows}
    funnel_stages = ['Applied', 'Screening', 'Interview', 'Hired', 'Rejected', 'Withdrawn']
    chart_funnel_labels = funnel_stages
    chart_funnel_data = [funnel_dict.get(s, 0) for s in funnel_stages]

    # 5. Table 1: Recent Applications (Last 10)
    recent_apps_sql = f"""
        SELECT 
            a.application_id, a.status, a.applied_at, a.resume_filename,
            j.job_id, j.title AS job_title, j.department,
            c.name AS company_name,
            cand.first_name || ' ' || cand.last_name AS candidate_name,
            cand.email AS candidate_email
        FROM applications a
        JOIN jobs j ON a.job_id = j.job_id
        JOIN companies_v2 c ON j.company_id = c.company_id
        JOIN applicants cand ON a.applicant_id = cand.applicant_id
        {where_company}
        ORDER BY a.applied_at DESC
        LIMIT 10;
    """
    recent_applications = db.query_all(recent_apps_sql, kpi_params)

    # 6. Table 2: Today's & Upcoming Interviews
    today_iv_sql = f"""
        SELECT 
            i.interview_id, i.interview_type, i.scheduled_at, i.duration_minutes, i.status,
            a.application_id, j.title AS job_title,
            cand.first_name || ' ' || cand.last_name AS candidate_name,
            u.username AS interviewer_name
        FROM interviews i
        JOIN applications a ON i.application_id = a.application_id
        JOIN jobs j ON a.job_id = j.job_id
        JOIN applicants cand ON a.applicant_id = cand.applicant_id
        JOIN users_v2 u ON i.interviewer_id = u.user_id
        {where_company} AND i.scheduled_at >= CURRENT_DATE
        ORDER BY i.scheduled_at ASC
        LIMIT 8;
    """
    today_interviews = db.query_all(today_iv_sql, kpi_params)

    # 7. Kanban Board Pipeline (Including 'Withdrawn')
    view_sql = """
        SELECT 
            app.application_id, app.job_id, j.title AS job_title, c.name AS company_name, j.department,
            cand.applicant_id, cand.first_name || ' ' || cand.last_name AS candidate_name,
            cand.email AS candidate_email, cand.phone AS candidate_phone,
            app.status AS application_status, app.resume_filename, app.applied_at,
            COALESCE(
                (SELECT string_agg(s.skill_name || ' (' || ask.proficiency_level || ')', ', ' ORDER BY s.skill_name)
                 FROM applicant_skills ask
                 JOIN skills s ON ask.skill_id = s.skill_id
                 WHERE ask.applicant_id = cand.applicant_id),
                'None Recorded'
            ) AS candidate_skills,
            (SELECT COUNT(*) FROM interviews i WHERE i.application_id = app.application_id) AS total_interviews,
            (SELECT ROUND(AVG(rating), 1) FROM interviews i WHERE i.application_id = app.application_id AND rating IS NOT NULL) AS avg_interview_rating,
            (SELECT COUNT(*) FROM application_notes an WHERE an.application_id = app.application_id) AS notes_count
        FROM applications app
        JOIN applicants cand ON app.applicant_id = cand.applicant_id
        JOIN jobs j ON app.job_id = j.job_id
        JOIN companies_v2 c ON j.company_id = c.company_id
    """
    view_conditions = []
    view_params = []

    if company_id and not current_user.is_admin():
        view_conditions.append("j.company_id = %s")
        view_params.append(company_id)

    if selected_job_id and selected_job_id.isdigit():
        view_conditions.append("app.job_id = %s")
        view_params.append(int(selected_job_id))

    if view_conditions:
        view_sql += " WHERE " + " AND ".join(view_conditions)
    view_sql += " ORDER BY app.applied_at DESC;"

    pipeline_candidates = db.query_all(view_sql, view_params)

    kanban = {'Applied': [], 'Screening': [], 'Interview': [], 'Hired': [], 'Rejected': [], 'Withdrawn': []}
    for cand in pipeline_candidates:
        stage = cand['application_status']
        if stage in kanban:
            kanban[stage].append(cand)

    subscription = payments.get_company_subscription(company_id) if company_id else None

    return render_template(
        'recruiter_dashboard.html',
        kpi=kpi,
        chart_timeline_labels=json.dumps(chart_timeline_labels),
        chart_timeline_data=json.dumps(chart_timeline_data),
        chart_funnel_labels=json.dumps(chart_funnel_labels),
        chart_funnel_data=json.dumps(chart_funnel_data),
        recent_applications=recent_applications,
        today_interviews=today_interviews,
        kanban=kanban,
        all_jobs=all_jobs,
        selected_job_id=selected_job_id,
        subscription=subscription,
        total_candidates=len(pipeline_candidates)
    )


# ------------------------------------------------------------------------------
# DASHBOARD 2: ADMIN PLATFORM HUB (MRR & GROWTH)
# ------------------------------------------------------------------------------

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    """
    DASHBOARD 2: Platform Administrator SaaS Hub.
    Displays:
    - Top Cards: Total Companies, Total Users, MRR (Monthly Recurring Revenue), Active Subscriptions.
    - Chart 1: User Signups Over Time (Line Chart with Chart.js).
    - Chart 2: Subscription Distribution (Doughnut Chart: Free / Basic / Pro).
    - Table 1: Recent Company Registrations.
    - Table 2: Recent Subscriptions & Upgrades.
    """
    # 1. KPI Cards
    total_companies = db.query_one("SELECT COUNT(*) AS c FROM companies_v2;")['c']
    total_users = db.query_one("SELECT COUNT(*) AS c FROM users_v2;")['c']
    
    # Calculate MRR from active subscriptions ($49 for Basic, $149 for Pro)
    mrr_sql = """
        SELECT 
            COALESCE(SUM(
                CASE 
                    WHEN plan_name = 'Basic' THEN 49
                    WHEN plan_name = 'Pro' THEN 149
                    ELSE 0
                END
            ), 0) AS mrr,
            COUNT(CASE WHEN plan_name IN ('Basic', 'Pro') THEN 1 END) AS paying_subs,
            COUNT(*) AS total_subs
        FROM subscriptions
        WHERE status = 'active';
    """
    mrr_data = db.query_one(mrr_sql)
    mrr = float(mrr_data['mrr'])
    paying_subs = mrr_data['paying_subs']
    total_subs = mrr_data['total_subs']

    kpi = {
        'total_companies': total_companies,
        'total_users': total_users,
        'mrr': mrr,
        'paying_subs': paying_subs,
        'total_subs': total_subs
    }

    # 2. Chart 1: Signups Over Time (Past 8 Weeks)
    signups_sql = """
        SELECT 
            TO_CHAR(date_trunc('week', created_at), 'Mon DD') AS week_label,
            COUNT(*) AS signup_count
        FROM users_v2
        WHERE created_at >= CURRENT_DATE - INTERVAL '8 weeks'
        GROUP BY date_trunc('week', created_at)
        ORDER BY date_trunc('week', created_at) ASC;
    """
    signup_rows = db.query_all(signups_sql)
    chart_signup_labels = [r['week_label'] for r in signup_rows]
    chart_signup_data = [int(r['signup_count']) for r in signup_rows]

    # 3. Chart 2: Subscription Distribution (Pie/Doughnut)
    plan_sql = "SELECT plan_name, COUNT(*) AS count FROM subscriptions GROUP BY plan_name;"
    plan_rows = db.query_all(plan_sql)
    plan_dict = {r['plan_name']: int(r['count']) for r in plan_rows}
    chart_plan_labels = ['Free', 'Basic', 'Pro']
    chart_plan_data = [plan_dict.get('Free', 0), plan_dict.get('Basic', 0), plan_dict.get('Pro', 0)]

    # 4. Table 1: Recent Company Registrations
    recent_companies = db.query_all("""
        SELECT c.*, s.plan_name, s.status AS sub_status,
               (SELECT COUNT(*) FROM users_v2 u WHERE u.company_id = c.company_id) AS recruiter_count,
               (SELECT COUNT(*) FROM jobs j WHERE j.company_id = c.company_id) AS job_count
        FROM companies_v2 c
        LEFT JOIN subscriptions s ON c.company_id = s.company_id
        ORDER BY c.created_at DESC
        LIMIT 8;
    """)

    # 5. Table 2: Recent Subscriptions / Subscriptions List
    recent_subscriptions = db.query_all("""
        SELECT s.*, c.name AS company_name, c.slug AS company_slug
        FROM subscriptions s
        JOIN companies_v2 c ON s.company_id = c.company_id
        ORDER BY s.created_at DESC;
    """)

    return render_template(
        'admin/dashboard.html',
        kpi=kpi,
        chart_signup_labels=json.dumps(chart_signup_labels),
        chart_signup_data=json.dumps(chart_signup_data),
        chart_plan_labels=json.dumps(chart_plan_labels),
        chart_plan_data=json.dumps(chart_plan_data),
        recent_companies=recent_companies,
        recent_subscriptions=recent_subscriptions
    )


# ------------------------------------------------------------------------------
# DASHBOARD 4: RECRUITER HIRING ANALYTICS (/recruiter/analytics)
# ------------------------------------------------------------------------------

@app.route('/recruiter/analytics')
@login_required
@role_required(['recruiter', 'admin'])
def recruiter_analytics():
    """
    DASHBOARD 4: Recruiter Hiring Analytics.
    Metrics:
    - Time-to-Hire (average days from applied to hired)
    - Source of Hire (which job postings brought the most hires)
    - Stage Conversion Rates (% Applied -> Screening -> Interview -> Hired)
    - Hiring Velocity (Monthly hires over last 6 months)
    - Top performing jobs
    """
    company_id = current_user.company_id
    where_company = "WHERE j.company_id = %s" if (company_id and not current_user.is_admin()) else "WHERE 1=1"
    params = [company_id] if (company_id and not current_user.is_admin()) else []

    # 1. Time-to-Hire (Days elapsed between applied_at and updated_at for Hired candidates)
    tth_sql = f"""
        SELECT 
            ROUND(AVG(EXTRACT(EPOCH FROM (a.updated_at - a.applied_at)) / 86400.0), 1) AS avg_time_to_hire,
            MIN(ROUND(EXTRACT(EPOCH FROM (a.updated_at - a.applied_at)) / 86400.0, 1)) AS min_time_to_hire,
            MAX(ROUND(EXTRACT(EPOCH FROM (a.updated_at - a.applied_at)) / 86400.0, 1)) AS max_time_to_hire,
            COUNT(*) AS total_hires
        FROM applications a
        JOIN jobs j ON a.job_id = j.job_id
        {where_company} AND a.status = 'Hired';
    """
    tth_data = db.query_one(tth_sql, params)
    avg_tth = tth_data['avg_time_to_hire'] if tth_data and tth_data['avg_time_to_hire'] else 12.5
    total_hires = tth_data['total_hires'] if tth_data else 0

    # 2. Stage Conversion Rates
    conv_sql = f"""
        SELECT 
            COUNT(*) AS total_applied,
            COUNT(CASE WHEN a.status IN ('Screening', 'Interview', 'Hired') THEN 1 END) AS reached_screening,
            COUNT(CASE WHEN a.status IN ('Interview', 'Hired') THEN 1 END) AS reached_interview,
            COUNT(CASE WHEN a.status = 'Hired' THEN 1 END) AS reached_hired,
            COUNT(CASE WHEN a.status = 'Withdrawn' THEN 1 END) AS withdrawn_count
        FROM applications a
        JOIN jobs j ON a.job_id = j.job_id
        {where_company};
    """
    conv = db.query_one(conv_sql, params)
    total_app = conv['total_applied'] or 1
    scr_pct = round((conv['reached_screening'] / total_app) * 100, 1)
    iv_pct = round((conv['reached_interview'] / total_app) * 100, 1)
    hire_pct = round((conv['reached_hired'] / total_app) * 100, 1)

    # 3. Source of Hire (Jobs bringing the most hires)
    soh_sql = f"""
        SELECT 
            j.job_id, j.title, j.title AS job_title, c.name AS company_name, j.department,
            COUNT(a.application_id) AS total_applicants,
            COUNT(a.application_id) AS total_apps,
            COUNT(CASE WHEN a.status = 'Hired' THEN 1 END) AS total_hires,
            COUNT(CASE WHEN a.status = 'Hired' THEN 1 END) AS total_hired,
            ROUND(AVG(iv.rating), 2) AS avg_candidate_rating,
            ROUND(AVG(iv.rating), 2) AS avg_rating
        FROM jobs j
        JOIN companies_v2 c ON j.company_id = c.company_id
        LEFT JOIN applications a ON j.job_id = a.job_id
        LEFT JOIN interviews iv ON a.application_id = iv.application_id
        {where_company}
        GROUP BY j.job_id, j.title, c.name, j.department
        ORDER BY total_hires DESC, total_applicants DESC
        LIMIT 6;
    """
    top_jobs = db.query_all(soh_sql, params)

    # 4. Hiring Velocity (Hires per month for past 6 months)
    velocity_sql = f"""
        SELECT 
            TO_CHAR(d.month, 'Mon YYYY') AS month_label,
            COUNT(a.application_id) AS hire_count
        FROM generate_series(date_trunc('month', CURRENT_DATE - INTERVAL '5 months'), date_trunc('month', CURRENT_DATE), '1 month'::interval) d(month)
        LEFT JOIN (
            SELECT a.updated_at, a.application_id
            FROM applications a
            JOIN jobs j ON a.job_id = j.job_id
            {where_company} AND a.status = 'Hired'
        ) a ON date_trunc('month', a.updated_at) = date_trunc('month', d.month)
        GROUP BY d.month
        ORDER BY d.month ASC;
    """
    velocity_rows = db.query_all(velocity_sql, params)
    chart_velocity_labels = [r['month_label'] for r in velocity_rows]
    chart_velocity_data = [int(r['hire_count']) for r in velocity_rows]

    return render_template(
        'recruiter_analytics.html',
        avg_tth=avg_tth,
        total_hires=total_hires,
        conv=conv,
        scr_pct=scr_pct,
        iv_pct=iv_pct,
        hire_pct=hire_pct,
        top_jobs=top_jobs,
        chart_velocity_labels=json.dumps(chart_velocity_labels),
        chart_velocity_data=json.dumps(chart_velocity_data)
    )


# ------------------------------------------------------------------------------
# FEATURE 6: ADVANCED JOB SEARCH & HOME BOARD
# ------------------------------------------------------------------------------

@app.route('/')
def index():
    """
    FEATURE 6: Advanced Job Search & Filters.
    Filters: salary range, location, remote-only toggle, experience level, department.
    Sort by: newest, salary high-to-low, application deadline.
    Saves search history per user in user_search_history.
    """
    search_query = request.args.get('q', '').strip()
    department = request.args.get('department', '').strip()
    location = request.args.get('location', '').strip()
    job_type = request.args.get('job_type', '').strip()
    remote_only = request.args.get('remote_only') in ['1', 'true', 'on']
    min_salary = request.args.get('min_salary', '').strip()
    max_salary = request.args.get('max_salary', '').strip()
    experience_level = request.args.get('experience_level', '').strip()
    sort_by = request.args.get('sort_by', 'newest').strip()

    sql = """
        SELECT 
            j.job_id,
            j.title AS job_title,
            c.name AS company_name,
            c.slug AS company_slug,
            c.logo_filename,
            c.brand_color,
            c.location AS company_location,
            j.department,
            j.location AS job_location,
            j.job_type,
            j.experience_level,
            j.application_deadline,
            j.salary_min,
            j.salary_max,
            j.status AS job_status,
            TO_CHAR(j.created_at, 'Mon DD, YYYY') AS posted_date,
            (SELECT COUNT(*) FROM applications a WHERE a.job_id = j.job_id) AS applicant_count
        FROM jobs j
        INNER JOIN companies_v2 c ON j.company_id = c.company_id
        WHERE j.status = 'Open'
    """
    params = []

    if search_query:
        sql += " AND (j.title ILIKE %s OR c.name ILIKE %s OR j.description ILIKE %s OR j.department ILIKE %s)"
        like_term = f"%{search_query}%"
        params.extend([like_term, like_term, like_term, like_term])

    if department:
        sql += " AND j.department = %s"
        params.append(department)

    if location:
        sql += " AND (j.location ILIKE %s OR c.location ILIKE %s)"
        params.extend([f"%{location}%", f"%{location}%"])

    if remote_only:
        sql += " AND j.job_type = 'Remote'"
    elif job_type:
        sql += " AND j.job_type = %s"
        params.append(job_type)

    if min_salary and min_salary.isdigit():
        sql += " AND (j.salary_max >= %s OR j.salary_min >= %s)"
        params.extend([float(min_salary), float(min_salary)])

    if max_salary and max_salary.isdigit():
        sql += " AND (j.salary_min <= %s)"
        params.append(float(max_salary))

    if experience_level:
        sql += " AND j.experience_level = %s"
        params.append(experience_level)

    # Sorting
    if sort_by == 'salary_high':
        sql += " ORDER BY COALESCE(j.salary_max, j.salary_min, 0) DESC, j.created_at DESC;"
    elif sort_by == 'deadline':
        sql += " ORDER BY j.application_deadline ASC NULLS LAST, j.created_at DESC;"
    else:
        sql += " ORDER BY j.created_at DESC;"

    try:
        jobs = db.query_all(sql, params)
        departments = db.query_all("SELECT DISTINCT department FROM jobs WHERE status = 'Open' ORDER BY department;")
    except Exception as e:
        flash(f"Database error loading jobs: {str(e)}", "danger")
        jobs = []
        departments = []

    # Save Search History if user is authenticated and filters applied
    recent_searches = []
    if current_user.is_authenticated:
        if search_query or department or location or remote_only or min_salary or experience_level:
            label_parts = [p for p in [search_query, department, location, "Remote" if remote_only else None, experience_level] if p]
            label = " &bull; ".join(label_parts) if label_parts else "Filtered Search"
            filter_dict = {
                'q': search_query, 'department': department, 'location': location,
                'remote_only': remote_only, 'min_salary': min_salary, 'max_salary': max_salary,
                'experience_level': experience_level, 'sort_by': sort_by
            }
            try:
                db.execute_dml(
                    "INSERT INTO user_search_history (user_id, search_label, search_filters) VALUES (%s, %s, %s);",
                    (current_user.user_id, label[:150], json.dumps(filter_dict))
                )
            except Exception as e:
                print(f"Error saving search history: {e}")

        # Fetch recent searches
        recent_searches = db.query_all(
            "SELECT * FROM user_search_history WHERE user_id = %s ORDER BY created_at DESC LIMIT 5;",
            (current_user.user_id,)
        )

    # Check bookmarks for logged in applicant
    saved_job_ids = set()
    if current_user.is_authenticated:
        applicant_id = get_current_applicant_id()
        if applicant_id:
            saved_rows = db.query_all("SELECT job_id FROM saved_jobs WHERE applicant_id = %s;", (applicant_id,))
            saved_job_ids = set(r['job_id'] for r in saved_rows)

    return render_template(
        'index.html', 
        jobs=jobs, 
        departments=departments,
        search_query=search_query,
        selected_department=department,
        selected_location=location,
        selected_job_type=job_type,
        remote_only=remote_only,
        min_salary=min_salary,
        max_salary=max_salary,
        experience_level=experience_level,
        sort_by=sort_by,
        recent_searches=recent_searches,
        saved_job_ids=saved_job_ids
    )


# ------------------------------------------------------------------------------
# JOB DETAILS & APPLICATION FORM (Enhanced with Resume Parser)
# ------------------------------------------------------------------------------

@app.route('/jobs/<int:job_id>')
def job_detail(job_id):
    """Displays individual job requirements and company profile."""
    sql = """
        SELECT 
            j.*,
            c.name AS company_name,
            c.slug AS company_slug,
            c.logo_filename,
            c.brand_color,
            c.website AS company_website,
            c.location AS company_location,
            c.description AS company_description,
            u.username AS recruiter_name,
            u.email AS recruiter_email
        FROM jobs j
        JOIN companies_v2 c ON j.company_id = c.company_id
        JOIN users u ON j.recruiter_id = u.user_id
        WHERE j.job_id = %s;
    """
    job = db.query_one(sql, (job_id,))
    if not job:
        flash("The requested job posting was not found.", "warning")
        return redirect(url_for('index'))

    # Check if bookmarked
    is_saved = False
    if current_user.is_authenticated:
        applicant_id = get_current_applicant_id()
        if applicant_id:
            row = db.query_one("SELECT save_id FROM saved_jobs WHERE applicant_id = %s AND job_id = %s;", (applicant_id, job_id))
            is_saved = bool(row)

    return render_template('job_detail.html', job=job, is_saved=is_saved)


@app.route('/apply/<int:job_id>', methods=['GET', 'POST'])
def apply(job_id):
    """
    Application submission with auto-parser capability and confirmation email.
    """
    job = db.query_one("""
        SELECT j.job_id, j.title, j.status, c.name AS company_name
        FROM jobs j
        JOIN companies_v2 c ON j.company_id = c.company_id
        WHERE j.job_id = %s;
    """, (job_id,))

    if not job:
        flash("Job not found.", "danger")
        return redirect(url_for('index'))

    if job['status'] != 'Open':
        flash(f"Applications are currently closed for '{job['title']}'.", "warning")
        return redirect(url_for('job_detail', job_id=job_id))

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        location = request.form.get('location', '').strip()
        linkedin_url = request.form.get('linkedin_url', '').strip()
        portfolio_url = request.form.get('portfolio_url', '').strip()
        cover_letter = request.form.get('cover_letter', '').strip()
        selected_skills = request.form.getlist('skills')

        if not first_name or not last_name or not email:
            flash("First name, last name, and email are required.", "danger")
            return redirect(request.url)

        if 'resume' not in request.files:
            flash("Please upload your resume document.", "danger")
            return redirect(request.url)

        file = request.files['resume']
        if file.filename == '' or not allowed_file(file.filename):
            flash("Please upload a valid document (.pdf, .docx, .doc).", "danger")
            return redirect(request.url)

        filename_clean = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{email.replace('@', '_at_')}_{filename_clean}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)

        try:
            with db.get_db_cursor(commit=True) as cur:
                # Upsert applicant
                cur.execute("SELECT applicant_id FROM applicants WHERE email = %s;", (email,))
                existing_cand = cur.fetchone()
                logged_in_uid = current_user.user_id if current_user.is_authenticated else None

                if existing_cand:
                    applicant_id = existing_cand['applicant_id']
                    cur.execute("""
                        UPDATE applicants 
                        SET first_name = %s, last_name = %s, phone = %s, location = %s, 
                            linkedin_url = %s, portfolio_url = %s,
                            user_id = COALESCE(user_id, %s)
                        WHERE applicant_id = %s;
                    """, (first_name, last_name, phone, location, linkedin_url, portfolio_url, logged_in_uid, applicant_id))
                else:
                    cur.execute("""
                        INSERT INTO applicants (user_id, first_name, last_name, email, phone, location, linkedin_url, portfolio_url)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING applicant_id;
                    """, (logged_in_uid, first_name, last_name, email, phone, location, linkedin_url, portfolio_url))
                    applicant_id = cur.fetchone()['applicant_id']

                # Associate skills
                if selected_skills:
                    for skill_id in selected_skills:
                        cur.execute("""
                            INSERT INTO applicant_skills (applicant_id, skill_id, years_of_experience, proficiency_level)
                            VALUES (%s, %s, 2.0, 'Intermediate')
                            ON CONFLICT (applicant_id, skill_id) DO NOTHING;
                        """, (applicant_id, int(skill_id)))

                # Insert application
                cur.execute("""
                    INSERT INTO applications (job_id, applicant_id, status, resume_filename, cover_letter)
                    VALUES (%s, %s, 'Applied', %s, %s)
                    RETURNING application_id;
                """, (job_id, applicant_id, unique_filename, cover_letter))
                application_id = cur.fetchone()['application_id']

            # Trigger Confirmation Email Notification
            candidate_full_name = f"{first_name} {last_name}"
            mailer.send_application_confirmation(
                recipient_email=email,
                candidate_name=candidate_full_name,
                job_title=job['title'],
                company_name=job['company_name'],
                application_id=application_id
            )

            flash(f"Application submitted successfully! Your tracking ID is #{application_id}. A confirmation email has been dispatched.", "success")
            return redirect(url_for('view_status', app_id=application_id, email=email))

        except psycopg2.Error as err:
            err_msg = str(err)
            if 'uq_job_applicant' in err_msg:
                flash("You have already submitted an active application for this job posting.", "warning")
            elif 'Only "Open" jobs accept applications' in err_msg:
                flash("This job is no longer accepting new applications.", "danger")
            else:
                flash(f"Database error during application submission: {err_msg}", "danger")
            return redirect(url_for('job_detail', job_id=job_id))

    skills = db.query_all("SELECT * FROM skills ORDER BY category, skill_name;")
    return render_template('apply.html', job=job, skills=skills)


@app.route('/status', methods=['GET', 'POST'])
def view_status():
    """Applicant Status Tracking Portal with Withdrawal Option."""
    app_id_param = request.args.get('app_id', '').strip()
    email_param = request.args.get('email', '').strip()
    search_query = request.form.get('identifier', app_id_param or email_param).strip()
    applications = []

    if search_query:
        if search_query.isdigit():
            sql = """
                SELECT 
                    a.application_id, a.status, a.applied_at, a.updated_at, a.resume_filename,
                    j.job_id, j.title AS job_title, j.department,
                    c.name AS company_name, c.location AS company_location,
                    cand.first_name || ' ' || cand.last_name AS candidate_name, cand.email AS candidate_email
                FROM applications a
                JOIN jobs j ON a.job_id = j.job_id
                JOIN companies_v2 c ON j.company_id = c.company_id
                JOIN applicants cand ON a.applicant_id = cand.applicant_id
                WHERE a.application_id = %s;
            """
            params = (int(search_query),)
        else:
            sql = """
                SELECT 
                    a.application_id, a.status, a.applied_at, a.updated_at, a.resume_filename,
                    j.job_id, j.title AS job_title, j.department,
                    c.name AS company_name, c.location AS company_location,
                    cand.first_name || ' ' || cand.last_name AS candidate_name, cand.email AS candidate_email
                FROM applications a
                JOIN jobs j ON a.job_id = j.job_id
                JOIN companies_v2 c ON j.company_id = c.company_id
                JOIN applicants cand ON a.applicant_id = cand.applicant_id
                WHERE LOWER(cand.email) = LOWER(%s)
                ORDER BY a.applied_at DESC;
            """
            params = (search_query,)

        try:
            applications = db.query_all(sql, params)
            for app_rec in applications:
                interviews = db.query_all("""
                    SELECT interview_type, scheduled_at, duration_minutes, status, feedback
                    FROM interviews
                    WHERE application_id = %s
                    ORDER BY scheduled_at ASC;
                """, (app_rec['application_id'],))
                app_rec['interviews'] = interviews

            if not applications:
                flash(f"No applications found for '{search_query}'.", "info")
        except Exception as e:
            flash(f"Error checking status: {e}", "danger")

    return render_template('view_status.html', applications=applications, identifier=search_query)


# ------------------------------------------------------------------------------
# RECRUITER ACTIONS (Status Updates, Interviews & Notes)
# ------------------------------------------------------------------------------

@app.route('/recruiter/update-status/<int:application_id>', methods=['GET', 'POST'])
@login_required
@role_required(['recruiter', 'admin'])
def update_status(application_id):
    """
    Candidate Management: Update status, schedule interviews, and collaborate via Recruiter Notes.
    """
    sql = """
        SELECT 
            app.*,
            cand.first_name || ' ' || cand.last_name AS candidate_name,
            cand.email AS candidate_email,
            cand.phone AS candidate_phone,
            j.title AS job_title,
            c.name AS company_name,
            c.company_id
        FROM applications app
        JOIN applicants cand ON app.applicant_id = cand.applicant_id
        JOIN jobs j ON app.job_id = j.job_id
        JOIN companies_v2 c ON j.company_id = c.company_id
        WHERE app.application_id = %s;
    """
    application = db.query_one(sql, (application_id,))
    if not application:
        flash("Application not found.", "danger")
        return redirect(url_for('recruiter_dashboard'))

    interviews = db.query_all("""
        SELECT i.*, u.username AS interviewer_name
        FROM interviews i
        JOIN users u ON i.interviewer_id = u.user_id
        WHERE i.application_id = %s
        ORDER BY i.scheduled_at DESC;
    """, (application_id,))

    # FEATURE 10: Fetch Chronological Recruiter Notes
    notes_list = db.query_all("""
        SELECT n.*, u.username AS author_username, u.first_name, u.last_name, u.role
        FROM application_notes n
        JOIN users_v2 u ON n.author_id = u.user_id
        WHERE n.application_id = %s
        ORDER BY n.created_at DESC;
    """, (application_id,))

    recruiters = db.query_all("SELECT user_id, username FROM users_v2 WHERE role IN ('recruiter', 'admin');")

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_stage':
            new_status = request.form.get('status')
            if new_status in ['Applied', 'Screening', 'Interview', 'Hired', 'Rejected', 'Withdrawn']:
                db.execute_dml("UPDATE applications SET status = %s WHERE application_id = %s;", (new_status, application_id))
                
                mailer.send_status_update_notification(
                    recipient_email=application['candidate_email'],
                    candidate_name=application['candidate_name'],
                    job_title=application['job_title'],
                    company_name=application['company_name'],
                    new_status=new_status
                )
                flash(f"Application status updated to '{new_status}' and email dispatched to candidate.", "success")
            return redirect(url_for('update_status', application_id=application_id))

        elif action == 'schedule_interview':
            interviewer_id = request.form.get('interviewer_id')
            interview_type = request.form.get('interview_type')
            scheduled_date = request.form.get('scheduled_date')
            duration = int(request.form.get('duration', 45))
            notes = request.form.get('notes', '')

            try:
                db.call_procedure(
                    'sp_schedule_interview',
                    [application_id, int(interviewer_id), interview_type, scheduled_date, duration, notes, None]
                )
                mailer.send_interview_invitation(
                    recipient_email=application['candidate_email'],
                    candidate_name=application['candidate_name'],
                    job_title=application['job_title'],
                    company_name=application['company_name'],
                    interview_type=interview_type,
                    scheduled_at=scheduled_date,
                    duration_minutes=duration,
                    notes=notes
                )
                flash("Interview scheduled successfully! Status automatically advanced to 'Interview' and invitation email dispatched.", "success")
            except Exception as e:
                flash(f"Failed to schedule interview: {e}", "danger")

            return redirect(url_for('update_status', application_id=application_id))

    return render_template(
        'update_status.html',
        app_record=application,
        interviews=interviews,
        notes_list=notes_list,
        recruiters=recruiters
    )


@app.route('/api/applications/update-status', methods=['POST'])
@login_required
@role_required(['recruiter', 'admin'])
def api_update_status():
    """AJAX endpoint for instant Kanban drag-and-drop or select dropdown."""
    data = request.get_json() or {}
    application_id = data.get('application_id')
    new_status = data.get('status')

    if not application_id or new_status not in ['Applied', 'Screening', 'Interview', 'Hired', 'Rejected', 'Withdrawn']:
        return jsonify({'success': False, 'message': 'Invalid parameters'}), 400

    try:
        updated = db.execute_dml("UPDATE applications SET status = %s WHERE application_id = %s;", (new_status, int(application_id)))
        
        cand_info = db.query_one("""
            SELECT cand.email, cand.first_name || ' ' || cand.last_name AS name, j.title, c.name AS company_name
            FROM applications a
            JOIN applicants cand ON a.applicant_id = cand.applicant_id
            JOIN jobs j ON a.job_id = j.job_id
            JOIN companies_v2 c ON j.company_id = c.company_id
            WHERE a.application_id = %s;
        """, (int(application_id),))

        if cand_info:
            mailer.send_status_update_notification(
                recipient_email=cand_info['email'],
                candidate_name=cand_info['name'],
                job_title=cand_info['title'],
                company_name=cand_info['company_name'],
                new_status=new_status
            )

        return jsonify({'success': True, 'application_id': application_id, 'new_status': new_status, 'updated': updated})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/recruiter/jobs/new', methods=['GET', 'POST'])
@login_required
@role_required(['recruiter', 'admin'])
def post_job():
    """Recruiter page to publish a new job vacancy with Plan Quota Enforcement."""
    company_id = current_user.company_id

    if company_id:
        can_post, current_count, limit = payments.check_job_quota(company_id)
        if not can_post and request.method == 'POST':
            flash(f"You have reached your subscription limit of {limit} active job(s). Please upgrade to publish more.", "warning")
            return redirect(url_for('pricing'))
    else:
        can_post, current_count, limit = True, 0, 9999

    companies = db.query_all("SELECT company_id, name FROM companies_v2 ORDER BY name;")
    recruiters = db.query_all("SELECT user_id, username FROM users_v2 WHERE role IN ('recruiter', 'admin') ORDER BY username;")

    if request.method == 'POST':
        target_company_id = company_id or request.form.get('company_id')
        recruiter_id = current_user.user_id if not current_user.is_admin() else request.form.get('recruiter_id')
        title = request.form.get('title', '').strip()
        department = request.form.get('department', '').strip()
        location = request.form.get('location', '').strip()
        job_type = request.form.get('job_type')
        experience_level = request.form.get('experience_level', 'Mid-Level')
        salary_min = request.form.get('salary_min') or None
        salary_max = request.form.get('salary_max') or None
        deadline_input = request.form.get('deadline') or None
        description = request.form.get('description', '').strip()
        requirements = request.form.get('requirements', '').strip()
        status = request.form.get('status', 'Open')

        if not title or not department or not location or not description:
            flash("All required fields must be filled.", "danger")
            return redirect(request.url)

        try:
            sql = """
                INSERT INTO jobs (
                    company_id, recruiter_id, title, department, location, 
                    job_type, experience_level, application_deadline,
                    salary_min, salary_max, description, requirements, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING job_id;
            """
            new_job_id = db.execute_dml(sql, (
                int(target_company_id), int(recruiter_id), title, department, location,
                job_type, experience_level, deadline_input,
                salary_min, salary_max, description, requirements, status
            ), returning_col='job_id')

            flash(f"Job posting '{title}' published successfully! (ID #{new_job_id})", "success")
            return redirect(url_for('job_detail', job_id=new_job_id))
        except Exception as e:
            flash(f"Database error creating job: {e}", "danger")

    subscription = payments.get_company_subscription(company_id) if company_id else None
    return render_template(
        'post_job.html',
        companies=companies,
        recruiters=recruiters,
        can_post=can_post,
        current_count=current_count,
        limit=limit,
        subscription=subscription
    )


# ------------------------------------------------------------------------------
# COMPANY ONBOARDING, TEAM & BRANDING ROUTES
# ------------------------------------------------------------------------------

@app.route('/company/register', methods=['GET', 'POST'])
def company_register():
    """SaaS Employer Registration."""
    if request.method == 'POST':
        company_name = request.form.get('company_name', '').strip()
        website = request.form.get('website', '').strip()
        location = request.form.get('location', '').strip()
        industry = request.form.get('industry', '').strip()
        description = request.form.get('description', '').strip()
        brand_color = request.form.get('brand_color', '#2563eb').strip()

        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()

        if not company_name or not location or not username or not email or not password:
            flash("Please complete all required company and recruiter fields.", "danger")
            return redirect(request.url)

        logo_filename = None
        if 'logo' in request.files:
            logo_file = request.files['logo']
            if logo_file.filename and allowed_logo(logo_file.filename):
                clean_name = secure_filename(logo_file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                logo_filename = f"logo_{timestamp}_{clean_name}"
                logo_path = os.path.join(app.config['LOGO_UPLOAD_FOLDER'], logo_filename)
                logo_file.save(logo_path)

        slug_base = company_name.lower().replace(' ', '-').replace('&', 'and')
        slug = ''.join(c for c in slug_base if c.isalnum() or c == '-')

        try:
            with db.get_db_cursor(commit=True) as cur:
                cur.execute("""
                    INSERT INTO companies_v2 (name, slug, website, location, industry, description, logo_filename, brand_color)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING company_id;
                """, (company_name, slug, website, location, industry, description, logo_filename, brand_color))
                company_id = cur.fetchone()['company_id']

                cur.execute("""
                    INSERT INTO companies (company_id, name, website, location, industry, description)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (company_id) DO NOTHING;
                """, (company_id, company_name, website, location, industry, description))

                cur.execute("""
                    INSERT INTO subscriptions (company_id, plan_name, status, job_limit, recruiter_limit, custom_branding_enabled)
                    VALUES (%s, 'Free', 'active', 1, 1, FALSE);
                """, (company_id,))

                password_hash = generate_password_hash(password)
                cur.execute("""
                    INSERT INTO users_v2 (company_id, username, email, password_hash, role, first_name, last_name)
                    VALUES (%s, %s, %s, %s, 'recruiter', %s, %s)
                    RETURNING user_id;
                """, (company_id, username, email, password_hash, first_name, last_name))
                user_id = cur.fetchone()['user_id']

                cur.execute("""
                    INSERT INTO users (user_id, username, email, password_hash, role)
                    VALUES (%s, %s, %s, %s, 'recruiter')
                    ON CONFLICT (user_id) DO NOTHING;
                """, (user_id, username, email, password_hash))

            new_user = auth.load_user(user_id)
            if new_user:
                login_user(new_user)

            flash(f"Company '{company_name}' registered successfully! Welcome to your recruiter dashboard.", "success")
            return redirect(url_for('recruiter_dashboard'))

        except psycopg2.Error as err:
            err_msg = str(err)
            if 'companies_v2_name_key' in err_msg:
                flash("A company with that name is already registered.", "warning")
            elif 'users_v2_email_key' in err_msg or 'users_v2_username_key' in err_msg:
                flash("A user account with that email or username already exists.", "warning")
            else:
                flash(f"Database error during registration: {err_msg}", "danger")
            return redirect(request.url)

    return render_template('company/register.html')


@app.route('/company/team')
@login_required
@role_required(['recruiter', 'admin'])
def company_team():
    """Recruiter Team Seats & Invitations."""
    company_id = current_user.company_id
    if not company_id:
        flash("You are not associated with a company organization.", "warning")
        return redirect(url_for('index'))

    team_members = db.query_all("""
        SELECT user_id, username, email, first_name, last_name, role, created_at
        FROM users_v2
        WHERE company_id = %s
        ORDER BY created_at ASC;
    """, (company_id,))

    invitations = db.query_all("""
        SELECT invitation_id, email, role, status, expires_at, created_at, token
        FROM recruiter_invitations
        WHERE company_id = %s
        ORDER BY created_at DESC;
    """, (company_id,))

    can_invite, current_count, limit = payments.check_recruiter_quota(company_id)
    subscription = payments.get_company_subscription(company_id)

    return render_template(
        'company/team.html',
        team_members=team_members,
        invitations=invitations,
        can_invite=can_invite,
        current_count=current_count,
        limit=limit,
        subscription=subscription
    )


@app.route('/company/team/invite', methods=['POST'])
@login_required
@role_required(['recruiter', 'admin'])
def company_team_invite():
    """Invite Recruiter."""
    company_id = current_user.company_id
    invite_email = request.form.get('email', '').strip().lower()

    if not invite_email:
        flash("Please enter a valid email address.", "warning")
        return redirect(url_for('company_team'))

    can_invite, current_count, limit = payments.check_recruiter_quota(company_id)
    if not can_invite:
        flash(f"Recruiter seat limit reached ({current_count}/{limit}). Please upgrade your plan to add more team members.", "warning")
        return redirect(url_for('pricing'))

    existing = db.query_one("SELECT user_id FROM users_v2 WHERE LOWER(email) = LOWER(%s);", (invite_email,))
    if existing:
        flash("That user is already registered in the system.", "info")
        return redirect(url_for('company_team'))

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(days=7)

    sql = """
        INSERT INTO recruiter_invitations (company_id, email, token, expires_at)
        VALUES (%s, %s, %s, %s)
        RETURNING invitation_id;
    """
    try:
        db.execute_dml(sql, (company_id, invite_email, token, expires_at))
        mailer.send_recruiter_invitation(invite_email, current_user.company_name or 'our company', token)
        flash(f"Invitation sent to {invite_email}! (Logged in email audit table)", "success")
    except Exception as e:
        flash(f"Error creating invitation: {e}", "danger")

    return redirect(url_for('company_team'))


@app.route('/invite/accept/<token>', methods=['GET', 'POST'])
def accept_invitation(token):
    """Invited Recruiter Onboarding."""
    invitation = db.query_one("""
        SELECT inv.*, c.name AS company_name
        FROM recruiter_invitations inv
        JOIN companies_v2 c ON inv.company_id = c.company_id
        WHERE inv.token = %s AND inv.status = 'pending' AND inv.expires_at > CURRENT_TIMESTAMP;
    """, (token,))

    if not invitation:
        flash("This invitation is invalid or has expired.", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()

        if not username or not password:
            flash("Username and password are required.", "danger")
            return redirect(request.url)

        try:
            password_hash = generate_password_hash(password)
            with db.get_db_cursor(commit=True) as cur:
                cur.execute("""
                    INSERT INTO users_v2 (company_id, username, email, password_hash, role, first_name, last_name)
                    VALUES (%s, %s, %s, %s, 'recruiter', %s, %s)
                    RETURNING user_id;
                """, (invitation['company_id'], username, invitation['email'], password_hash, first_name, last_name))
                user_id = cur.fetchone()['user_id']

                cur.execute("""
                    INSERT INTO users (user_id, username, email, password_hash, role)
                    VALUES (%s, %s, %s, %s, 'recruiter')
                    ON CONFLICT (user_id) DO NOTHING;
                """, (user_id, username, invitation['email'], password_hash))

                cur.execute("UPDATE recruiter_invitations SET status = 'accepted' WHERE invitation_id = %s;", (invitation['invitation_id'],))

            new_user = auth.load_user(user_id)
            if new_user:
                login_user(new_user)

            flash(f"Welcome to the {invitation['company_name']} recruitment team!", "success")
            return redirect(url_for('recruiter_dashboard'))
        except Exception as e:
            flash(f"Error activating account: {e}", "danger")

    return render_template('company/accept_invitation.html', invitation=invitation)


@app.route('/company/branding', methods=['GET', 'POST'])
@login_required
@role_required(['recruiter', 'admin'])
def company_branding():
    """Custom Branding Settings."""
    company_id = current_user.company_id
    if not company_id:
        flash("You are not affiliated with a company.", "warning")
        return redirect(url_for('index'))

    company = db.query_one("SELECT * FROM companies_v2 WHERE company_id = %s;", (company_id,))
    subscription = payments.get_company_subscription(company_id)
    can_brand = payments.check_custom_branding_allowed(company_id)

    if request.method == 'POST':
        if not can_brand:
            flash("Custom branding is exclusive to Pro tier subscribers. Please upgrade your plan.", "warning")
            return redirect(url_for('pricing'))

        brand_color = request.form.get('brand_color', '#2563eb').strip()
        brand_text_color = request.form.get('brand_text_color', '#ffffff').strip()

        logo_filename = company['logo_filename']
        if 'logo' in request.files:
            logo_file = request.files['logo']
            if logo_file.filename and allowed_logo(logo_file.filename):
                clean_name = secure_filename(logo_file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                logo_filename = f"logo_{company_id}_{timestamp}_{clean_name}"
                logo_file.save(os.path.join(app.config['LOGO_UPLOAD_FOLDER'], logo_filename))

        try:
            db.execute_dml("""
                UPDATE companies_v2
                SET brand_color = %s, brand_text_color = %s, logo_filename = %s
                WHERE company_id = %s;
            """, (brand_color, brand_text_color, logo_filename, company_id))
            flash("Company branding updated successfully! Check your branded career page.", "success")
            return redirect(url_for('company_branding'))
        except Exception as e:
            flash(f"Error updating branding: {e}", "danger")

    return render_template(
        'company/branding.html',
        company=company,
        subscription=subscription,
        can_brand=can_brand
    )


@app.route('/careers/<slug>')
def company_career_page(slug):
    """Dedicated Multi-Tenant Branded Career Portal."""
    company = db.query_one("SELECT * FROM companies_v2 WHERE slug = %s;", (slug,))
    if not company:
        flash("Career page not found.", "warning")
        return redirect(url_for('index'))

    jobs = db.query_all("""
        SELECT 
            j.*,
            (SELECT COUNT(*) FROM applications a WHERE a.job_id = j.job_id) AS applicant_count
        FROM jobs j
        WHERE j.company_id = %s AND j.status = 'Open'
        ORDER BY j.created_at DESC;
    """, (company['company_id'],))

    subscription = payments.get_company_subscription(company['company_id'])

    return render_template(
        'company/career_page.html',
        company=company,
        jobs=jobs,
        subscription=subscription
    )


@app.route('/uploads/logos/<filename>')
def download_logo(filename):
    """Serves uploaded company logos safely."""
    return send_from_directory(app.config['LOGO_UPLOAD_FOLDER'], filename)


# ------------------------------------------------------------------------------
# STRIPE PAYMENTS & SUBSCRIPTIONS
# ------------------------------------------------------------------------------

@app.route('/pricing')
def pricing():
    """3-Tier SaaS Pricing Table: Free / Basic / Pro comparison."""
    current_sub = None
    if current_user.is_authenticated and current_user.company_id:
        current_sub = payments.get_company_subscription(current_user.company_id)

    return render_template(
        'pricing.html',
        plans=Config.SUBSCRIPTION_PLANS,
        current_sub=current_sub,
        stripe_key=Config.STRIPE_PUBLISHABLE_KEY
    )


@app.route('/subscription/checkout/<plan_name>', methods=['POST'])
@login_required
@role_required(['recruiter', 'admin'])
def subscription_checkout(plan_name):
    """Initiates Stripe Checkout session or simulated upgrade."""
    company_id = current_user.company_id
    if not company_id:
        flash("You must be affiliated with a company to upgrade subscriptions.", "warning")
        return redirect(url_for('index'))

    success_url = url_for('subscription_success', plan=plan_name, _external=True)
    cancel_url = url_for('pricing', _external=True)

    try:
        session_info = payments.create_stripe_checkout_session(company_id, plan_name, success_url, cancel_url)
        return redirect(session_info['url'])
    except Exception as e:
        flash(f"Stripe checkout error: {e}", "danger")
        return redirect(url_for('pricing'))


@app.route('/subscription/success')
@login_required
@role_required(['recruiter', 'admin'])
def subscription_success():
    """Callback after completing Stripe checkout."""
    plan_name = request.args.get('plan')
    session_id = request.args.get('session_id')
    company_id = current_user.company_id

    if plan_name and company_id:
        try:
            payments.apply_subscription_upgrade(company_id, plan_name, stripe_session_id=session_id)
            flash(f"Subscription successfully upgraded to the {plan_name} plan! New limits and features are now active.", "success")
        except Exception as e:
            flash(f"Error finalizing subscription: {e}", "danger")

    return redirect(url_for('company_branding' if plan_name == 'Pro' else 'recruiter_dashboard'))


# ------------------------------------------------------------------------------
# AUDIT & DBMS ANALYTICS (Email Logs & Legacy SQL Showcase)
# ------------------------------------------------------------------------------

@app.route('/admin/email-logs')
@login_required
@role_required(['admin', 'recruiter'])
def admin_email_logs():
    """Audit Trail Viewer: Displays all transactional notifications and statuses."""
    logs = db.query_all("SELECT * FROM email_logs ORDER BY sent_at DESC LIMIT 50;")
    return render_template('admin/email_logs.html', logs=logs)


@app.route('/analytics')
def analytics():
    """DBMS Query & View Showcase Page."""
    query_catalog = [
        {
            "id": 1,
            "title": "Query 1: Active Job Postings with Company Details",
            "concept": "INNER JOIN, String Formatting, Temporal Sorting",
            "description": "Enriches open job vacancies with company profile and location metadata.",
            "sql": """
                SELECT 
                    j.job_id, j.title AS job_title, c.name AS company_name,
                    c.location AS company_headquarters, j.location AS job_location,
                    j.job_type, j.salary_min, j.salary_max,
                    TO_CHAR(j.created_at, 'YYYY-MM-DD') AS date_posted
                FROM jobs j
                INNER JOIN companies_v2 c ON j.company_id = c.company_id
                WHERE j.status = 'Open'
                ORDER BY j.created_at DESC;
            """
        },
        {
            "id": 2,
            "title": "Query 2: Comprehensive Candidate Pipeline",
            "concept": "LEFT OUTER JOIN (Multi-table), COALESCE",
            "description": "Lists all candidate profiles and their active applications, including registered applicants without submissions.",
            "sql": """
                SELECT 
                    cand.applicant_id, cand.first_name || ' ' || cand.last_name AS full_name,
                    cand.email, cand.location AS applicant_city,
                    COALESCE(j.title, 'No Active Applications') AS applied_job,
                    COALESCE(c.name, 'N/A') AS company,
                    COALESCE(app.status, 'Registered') AS current_stage,
                    app.applied_at
                FROM applicants cand
                LEFT JOIN applications app ON cand.applicant_id = app.applicant_id
                LEFT JOIN jobs j ON app.job_id = j.job_id
                LEFT JOIN companies_v2 c ON j.company_id = c.company_id
                ORDER BY cand.applicant_id, app.applied_at DESC;
            """
        },
        {
            "id": 3,
            "title": "Query 3: Pipeline Stage Distribution Funnel",
            "concept": "GROUP BY, Aggregate Functions (COUNT), Window Function (OVER)",
            "description": "Calculates total candidate count and percentage share for each recruitment pipeline stage.",
            "sql": """
                SELECT 
                    status AS pipeline_stage, COUNT(*) AS total_applications,
                    ROUND((COUNT(*)::DECIMAL / SUM(COUNT(*)) OVER ()) * 100, 2) AS percentage_share
                FROM applications
                GROUP BY status
                ORDER BY total_applications DESC;
            """
        },
        {
            "id": 4,
            "title": "Query 4: Departmental Hiring Budget & Compensation Analysis",
            "concept": "GROUP BY, HAVING, Aggregates (COUNT, MIN, MAX, AVG)",
            "description": "Analyzes salary ranges and midpoint compensation across company departments.",
            "sql": """
                SELECT 
                    department, COUNT(job_id) AS total_openings,
                    ROUND(MIN(salary_min), 2) AS lowest_salary_min,
                    ROUND(AVG((salary_min + salary_max) / 2.0), 2) AS avg_midpoint_salary,
                    ROUND(MAX(salary_max), 2) AS highest_salary_max
                FROM jobs
                WHERE status = 'Open'
                GROUP BY department
                HAVING COUNT(job_id) >= 1
                ORDER BY avg_midpoint_salary DESC;
            """
        },
        {
            "id": 5,
            "title": "Query 5: Top In-Demand Applicant Skills and Experience",
            "concept": "INNER JOIN, GROUP BY, Aggregate Functions (COUNT, AVG, MAX)",
            "description": "Identifies the most frequent technical skills possessed by applicants and their average years of experience.",
            "sql": """
                SELECT 
                    s.skill_id, s.skill_name, s.category,
                    COUNT(ask.applicant_id) AS candidate_count,
                    ROUND(AVG(ask.years_of_experience), 1) AS avg_experience_years,
                    MAX(ask.years_of_experience) AS max_experience_years
                FROM skills s
                INNER JOIN applicant_skills ask ON s.skill_id = ask.skill_id
                GROUP BY s.skill_id, s.skill_name, s.category
                ORDER BY candidate_count DESC, avg_experience_years DESC;
            """
        },
        {
            "id": 6,
            "title": "Query 6: Recruiter Performance & Placement Efficiency",
            "concept": "INNER JOIN, LEFT JOIN, GROUP BY, Conditional Aggregation (CASE)",
            "description": "Assesses recruiter productivity: total jobs posted, candidate submissions, interviews, and final hires.",
            "sql": """
                SELECT 
                    u.user_id AS recruiter_id, u.username AS recruiter_name, u.email AS recruiter_email,
                    COUNT(DISTINCT j.job_id) AS total_jobs_posted,
                    COUNT(app.application_id) AS total_applicants_received,
                    COUNT(CASE WHEN app.status = 'Interview' THEN 1 END) AS candidates_in_interview,
                    COUNT(CASE WHEN app.status = 'Hired' THEN 1 END) AS successful_hires
                FROM users_v2 u
                INNER JOIN jobs j ON u.user_id = j.recruiter_id
                LEFT JOIN applications app ON j.job_id = app.job_id
                WHERE u.role = 'recruiter'
                GROUP BY u.user_id, u.username, u.email
                ORDER BY successful_hires DESC, total_applicants_received DESC;
            """
        },
        {
            "id": 7,
            "title": "Query 7: High-Performing Interviewed Candidates",
            "concept": "INNER JOIN, GROUP BY, Aggregate Functions (AVG, COUNT), HAVING Filter",
            "description": "Extracts candidate profiles with average interview ratings of 3.5 or above across rounds.",
            "sql": """
                SELECT 
                    cand.applicant_id, cand.first_name || ' ' || cand.last_name AS candidate_name,
                    j.title AS job_position, c.name AS company_name,
                    COUNT(iv.interview_id) AS total_interview_rounds,
                    ROUND(AVG(iv.rating), 2) AS overall_avg_score
                FROM applicants cand
                INNER JOIN applications app ON cand.applicant_id = app.applicant_id
                INNER JOIN jobs j ON app.job_id = j.job_id
                INNER JOIN companies_v2 c ON j.company_id = c.company_id
                INNER JOIN interviews iv ON app.application_id = iv.application_id
                WHERE iv.rating IS NOT NULL
                GROUP BY cand.applicant_id, cand.first_name, cand.last_name, j.title, c.name
                HAVING AVG(iv.rating) >= 3.5
                ORDER BY overall_avg_score DESC;
            """
        },
        {
            "id": 8,
            "title": "Query 8: Vacancies with Zero Applications",
            "concept": "LEFT JOIN with IS NULL Filtering",
            "description": "Finds published positions that have not received any candidate submissions.",
            "sql": """
                SELECT 
                    j.job_id, j.title, c.name AS company_name,
                    j.department, j.job_type, j.created_at AS posted_on
                FROM jobs j
                INNER JOIN companies_v2 c ON j.company_id = c.company_id
                LEFT JOIN applications app ON j.job_id = app.job_id
                WHERE app.application_id IS NULL AND j.status = 'Open'
                ORDER BY j.created_at ASC;
            """
        },
        {
            "id": 9,
            "title": "Query 9: Candidate Multi-Skill Match Density",
            "concept": "INNER JOIN, GROUP BY, Aggregate Functions (COUNT, STRING_AGG)",
            "description": "Consolidates applicant technical profiles with concatenated verified skills and proficiencies.",
            "sql": """
                SELECT 
                    cand.applicant_id, cand.first_name || ' ' || cand.last_name AS applicant_name, cand.email,
                    COUNT(ask.skill_id) AS total_verified_skills,
                    STRING_AGG(s.skill_name || ' (' || ask.proficiency_level || ')', ', ' ORDER BY s.skill_name) AS skill_inventory
                FROM applicants cand
                INNER JOIN applicant_skills ask ON cand.applicant_id = ask.applicant_id
                INNER JOIN skills s ON ask.skill_id = s.skill_id
                GROUP BY cand.applicant_id, cand.first_name, cand.last_name, cand.email
                HAVING COUNT(ask.skill_id) >= 2
                ORDER BY total_verified_skills DESC;
            """
        },
        {
            "id": 10,
            "title": "Query 10: Time-to-Interview Operational Velocity",
            "concept": "INNER JOIN, Date Difference (EPOCH), Aggregate AVG",
            "description": "Measures average business days taken between application submission and first interview round.",
            "sql": """
                SELECT 
                    j.title AS job_title, c.name AS company_name,
                    COUNT(DISTINCT app.application_id) AS applications_interviewed,
                    ROUND(AVG(EXTRACT(EPOCH FROM (iv.scheduled_at - app.applied_at)) / 86400.0), 1) AS avg_days_to_interview
                FROM applications app
                INNER JOIN jobs j ON app.job_id = j.job_id
                INNER JOIN companies_v2 c ON j.company_id = c.company_id
                INNER JOIN interviews iv ON app.application_id = iv.application_id
                GROUP BY j.job_id, j.title, c.name
                ORDER BY avg_days_to_interview ASC;
            """
        }
    ]

    query_results = []
    for item in query_catalog:
        start_time = time.time()
        try:
            rows = db.query_all(item['sql'])
            duration_ms = round((time.time() - start_time) * 1000, 2)
            headers = list(rows[0].keys()) if rows else []
            query_results.append({
                **item,
                'headers': headers,
                'rows': rows,
                'row_count': len(rows),
                'duration_ms': duration_ms,
                'status': 'Success'
            })
        except Exception as e:
            query_results.append({
                **item,
                'headers': [],
                'rows': [],
                'row_count': 0,
                'duration_ms': 0,
                'status': f"Error: {e}"
            })

    try:
        view1_rows = db.query_all("SELECT * FROM v_job_applications_summary ORDER BY total_applicants DESC;")
        view1_headers = list(view1_rows[0].keys()) if view1_rows else []
    except Exception as e:
        view1_rows, view1_headers = [], []

    try:
        view2_rows = db.query_all("SELECT * FROM v_applicant_pipeline_overview LIMIT 15;")
        view2_headers = list(view2_rows[0].keys()) if view2_rows else []
    except Exception as e:
        view2_rows, view2_headers = [], []

    return render_template(
        'analytics.html',
        query_results=query_results,
        view1_rows=view1_rows,
        view1_headers=view1_headers,
        view2_rows=view2_rows,
        view2_headers=view2_headers
    )


@app.route('/admin/reset-db', methods=['POST'])
def admin_reset_db():
    """Administrative reset re-running schema.sql, seed.sql, schema_v2.sql, and schema_v3.sql."""
    try:
        db.init_db()
        db.seed_db()
        db.execute_sql_file('sql/schema_v2.sql')
        db.execute_sql_file('sql/schema_v3.sql')
        flash("Database successfully reset and re-seeded with demo records and SaaS V3 extensions!", "success")
    except Exception as e:
        flash(f"Error resetting database: {e}", "danger")
    return redirect(url_for('analytics'))


@app.route('/uploads/resumes/<filename>')
def download_resume(filename):
    """Serves candidate resume files securely."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() in ['true', '1']
    try:
        db.ensure_database_exists()
    except Exception as exc:
        print(f"PostgreSQL connection notice: {exc}")
    
    # use_reloader=False avoids ValueError: signal only works in main thread
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=False)
