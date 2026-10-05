"""
Transactional Email Notifications & Audit Logging Module.
Integrates with Flask-Mail and persists all outbound notifications into PostgreSQL email_logs.
Features dual-mode delivery: attempts live SMTP if configured, with automatic graceful fallback
to mock-logging so application workflows never crash on email outages.
"""

from flask import current_app, render_template_string
from flask_mail import Mail, Message
from config import Config
import db

mail = Mail()


def init_mail(app):
    """Initializes Flask-Mail with application configuration."""
    mail.init_app(app)


def log_email_to_db(recipient_email, subject, email_type, body, status='sent'):
    """Records the email dispatch event to PostgreSQL email_logs table."""
    sql = """
        INSERT INTO email_logs (recipient_email, subject, email_type, body, status)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING log_id;
    """
    try:
        log_id = db.execute_dml(sql, (recipient_email, subject, email_type, body, status), returning_col='log_id')
        return log_id
    except Exception as e:
        print(f"Warning: Failed to persist email log to database: {e}")
        return None


def send_notification(recipient_email, subject, email_type, body_text):
    """
    Core dispatcher sending email via Flask-Mail and writing audit log to DB.
    Guaranteed not to raise an exception: gracefully falls back to mock logging.
    """
    try:
        sender = current_app.config.get('MAIL_DEFAULT_SENDER', Config.MAIL_DEFAULT_SENDER)
        suppress_send = current_app.config.get('MAIL_SUPPRESS_SEND', False) or not current_app.config.get('MAIL_USERNAME')
    except RuntimeError:
        sender = Config.MAIL_DEFAULT_SENDER
        suppress_send = Config.MAIL_SUPPRESS_SEND or not Config.MAIL_USERNAME

    status = 'sent'

    # Check if real SMTP sending is disabled/mocked
    if suppress_send:
        status = 'mock_logged'
        print(f"\n[EMAIL NOTIFICATION - MOCK LOGGED]\nTo: {recipient_email}\nSubject: {subject}\nType: {email_type}\n{body_text}\n" + "-"*50)
    else:
        try:
            msg = Message(
                subject=subject,
                sender=sender,
                recipients=[recipient_email],
                body=body_text
            )
            mail.send(msg)
            print(f"[EMAIL NOTIFICATION - SENT VIA SMTP] To: {recipient_email} | Subject: {subject}")
        except Exception as e:
            print(f"[EMAIL NOTIFICATION - SMTP FAILED, FALLING BACK TO LOG] {e}")
            status = 'mock_logged'

    # Always persist in PostgreSQL email_logs
    log_email_to_db(recipient_email, subject, email_type, body_text, status=status)
    return status


def send_application_confirmation(recipient_email, candidate_name, job_title, company_name, application_id):
    """Dispatched when a candidate applies to a job vacancy."""
    subject = f"Application Received: {job_title} at {company_name} (#{application_id})"
    body = f"""Dear {candidate_name},

Thank you for applying for the position of {job_title} at {company_name}!

We have successfully received your application. Your reference tracking number is:
Application ID: #{application_id}

You can track your recruitment pipeline progress at any time through our portal:
http://localhost:5000/status?app_id={application_id}

Our hiring team will review your qualifications and update your status shortly.

Best regards,
The Talent Acquisition Team at {company_name}
Powered by Job Recruitment and Applicant Tracking System (ATS)
"""
    return send_notification(recipient_email, subject, 'application_confirmation', body)


def send_status_update_notification(recipient_email, candidate_name, job_title, company_name, new_status):
    """Dispatched when a recruiter advances or updates an applicant's stage."""
    subject = f"Update on Your Application for {job_title} at {company_name}"
    
    stage_messages = {
        'Screening': 'Your resume and qualifications are currently undergoing recruiter screening.',
        'Interview': 'Congratulations! You have been selected to move forward to the interview stage.',
        'Hired': 'Congratulations! We are delighted to inform you that an offer has been extended or finalized.',
        'Rejected': 'Thank you for your interest. While this role has progressed with other candidates, we will keep your profile on file for future opportunities.'
    }
    stage_desc = stage_messages.get(new_status, f"Your application status has been updated to: {new_status}.")

    body = f"""Dear {candidate_name},

We have an update regarding your application for {job_title} at {company_name}.

Current Status: {new_status}

{stage_desc}

To view detailed status history and any scheduled appointments, please visit:
http://localhost:5000/status

Sincerely,
{company_name} Hiring Team
"""
    return send_notification(recipient_email, subject, 'status_change', body)


def send_interview_invitation(recipient_email, candidate_name, job_title, company_name, interview_type, scheduled_at, duration_minutes, notes=None):
    """Dispatched when an interview is scheduled via sp_schedule_interview."""
    subject = f"Interview Scheduled: {interview_type} - {job_title} at {company_name}"
    formatted_date = str(scheduled_at)
    
    body = f"""Dear {candidate_name},

You have been scheduled for an upcoming interview round for the position of {job_title} at {company_name}.

Interview Details:
- Round Type: {interview_type}
- Scheduled Date & Time: {formatted_date}
- Estimated Duration: {duration_minutes} minutes
- Organization: {company_name}

{f"Interviewer Notes / Instructions:\n{notes}\n" if notes else ""}
Please make sure you are available at the scheduled time. To view all your interview appointments and application details, visit:
http://localhost:5000/status

Best of luck!
The Hiring Team at {company_name}
"""
    return send_notification(recipient_email, subject, 'interview_scheduled', body)


def send_recruiter_invitation(recipient_email, company_name, invite_token):
    """Dispatched when a company admin invites a recruiter to join their hiring workspace."""
    subject = f"Invitation to join the {company_name} Recruitment Team on ATS"
    invite_url = f"http://localhost:5000/invite/accept/{invite_token}"
    
    body = f"""Hello,

You have been invited to join the hiring team for {company_name} on Job Recruitment and Applicant Tracking System (ATS).

As a team member, you will be able to review candidate pipelines, manage Kanban stages, schedule interviews, and publish job vacancies.

To activate your recruiter account and set your password, please click the secure link below:
{invite_url}

This invitation link is valid for 7 days.

Welcome aboard!
Job Recruitment and Applicant Tracking System
"""
    return send_notification(recipient_email, subject, 'recruiter_invitation', body)
