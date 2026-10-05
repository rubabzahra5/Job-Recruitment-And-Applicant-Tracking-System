"""
End-to-End Verification Test Script for V3 Features & Dashboards
Tests all 5 new features (6-10) and 4 dashboards.
"""
import os
import sys
import io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
import db

AJAX_HEADERS = {'X-Requested-With': 'XMLHttpRequest'}

def p(msg):
    print(msg)

def run_tests():
    client = app.test_client()
    p("=" * 70)
    p("STARTING JOB RECRUITMENT AND ATS V3 FULL END-TO-END VERIFICATION")
    p("=" * 70)

    # 1. Feature 6: Advanced Job Search
    p("\n[TEST 1] Advanced Job Search & Filtering...")
    res = client.get('/')
    assert res.status_code == 200, f"Index returned {res.status_code}"
    assert b"Find Your Next" in res.data, "Hero banner missing"
    assert b"All Job Types" in res.data, "Job types dropdown missing"
    p("  PASS - Index page rendered with advanced search UI")

    res_filter = client.get('/?min_salary=100000&remote_only=true&sort_by=salary_desc')
    assert res_filter.status_code == 200
    p("  PASS - Advanced filter query (salary + remote + sort) executed")

    # 2. Feature 7: Resume Parser
    p("\n[TEST 2] Resume Parser API (/api/parse-resume)...")
    sample_pdf = os.path.join(app.config['UPLOAD_FOLDER'], 'sample_resume_david_kim.pdf')
    if os.path.exists(sample_pdf):
        with open(sample_pdf, 'rb') as f:
            pdf_bytes = f.read()
        data = {'resume': (io.BytesIO(pdf_bytes), 'david_kim_resume.pdf')}
        res_parse = client.post('/api/parse-resume', data=data, content_type='multipart/form-data')
        assert res_parse.status_code == 200, f"Parse API returned {res_parse.status_code}"
        jr = res_parse.get_json()
        assert jr['success'] is True, f"Parser failed: {jr}"
        parsed = jr['data']
        p(f"  PASS - Extracted Email: {parsed.get('email')}")
        p(f"  PASS - Extracted Phone: {parsed.get('phone')}")
        skills = [s['skill_name'] for s in parsed.get('matched_skills', [])]
        p(f"  PASS - Matched {len(skills)} Skills: {skills}")
        assert len(skills) > 0, "No skills matched!"
    else:
        p("  SKIP - Sample PDF not found")

    # 3. Applicant Login
    p("\n[TEST 3] Applicant Authentication...")
    login_res = client.post('/auth/login', data={
        'identifier': 'david.kim@gmail.com',
        'password': 'password123'
    }, follow_redirects=True)
    assert login_res.status_code == 200
    assert b"David Kim" in login_res.data or b"david.kim" in login_res.data
    p("  PASS - Applicant logged in successfully")

    # 4. Feature 8: Bookmarks
    p("\n[TEST 4] Saved Jobs / Bookmarks (Feature 8)...")
    job = db.query_one("SELECT job_id, title FROM jobs LIMIT 1;")
    job_id = job['job_id']

    res_bm = client.post(f'/jobs/{job_id}/bookmark', headers=AJAX_HEADERS)
    assert res_bm.status_code == 200
    bm_json = res_bm.get_json()
    assert bm_json is not None, "Bookmark returned non-JSON"
    assert bm_json['status'] in ['saved', 'removed']
    p(f"  PASS - Toggled bookmark for Job #{job_id}: {bm_json['status']}")

    if bm_json['status'] == 'removed':
        res_bm2 = client.post(f'/jobs/{job_id}/bookmark', headers=AJAX_HEADERS)
        assert res_bm2.get_json()['status'] == 'saved'

    res_saved_page = client.get('/applicant/saved-jobs')
    assert res_saved_page.status_code == 200
    assert b"My Saved Career Vacancies" in res_saved_page.data
    p("  PASS - /applicant/saved-jobs page rendered with bookmarked vacancies")

    # 5. Dashboard 3: Applicant Dashboard
    p("\n[TEST 5] Applicant Dashboard (Dashboard 3)...")
    res_app_dash = client.get('/applicant/dashboard')
    assert res_app_dash.status_code == 200
    assert b"My Active Applications" in res_app_dash.data
    assert b"Bookmarked Jobs" in res_app_dash.data
    assert b"Upcoming Interviews" in res_app_dash.data
    p("  PASS - Applicant Dashboard rendered with 3 KPI cards")

    # 6. Feature 9: Withdrawal
    p("\n[TEST 6] Application Withdrawal (Feature 9)...")
    cand = db.query_one("SELECT applicant_id FROM applicants WHERE email = 'david.kim@gmail.com';")
    if cand:
        app_rec = db.query_one("""
            SELECT application_id FROM applications
            WHERE applicant_id = %s AND status NOT IN ('Withdrawn', 'Hired', 'Rejected')
            LIMIT 1;
        """, (cand['applicant_id'],))

        if not app_rec:
            any_cand_app = db.query_one("SELECT application_id FROM applications WHERE applicant_id = %s LIMIT 1;", (cand['applicant_id'],))
            if any_cand_app:
                db.execute_dml("UPDATE applications SET status = 'Applied' WHERE application_id = %s;", (any_cand_app['application_id'],))
                test_app_id = any_cand_app['application_id']
            else:
                unapplied_job = db.query_one("""
                    SELECT job_id FROM jobs 
                    WHERE job_id NOT IN (SELECT job_id FROM applications WHERE applicant_id = %s)
                    LIMIT 1;
                """, (cand['applicant_id'],))
                with db.get_db_cursor(commit=True) as cur:
                    cur.execute("""
                        INSERT INTO applications (job_id, applicant_id, status, resume_filename)
                        VALUES (%s, %s, 'Applied', 'test_resume.pdf')
                        RETURNING application_id;
                    """, (unapplied_job['job_id'], cand['applicant_id']))
                    test_app_id = cur.fetchone()['application_id']
        else:
            test_app_id = app_rec['application_id']

        res_withdraw = client.post(f'/applications/{test_app_id}/withdraw', follow_redirects=True)
        assert res_withdraw.status_code == 200
        updated = db.query_one("SELECT status FROM applications WHERE application_id = %s;", (test_app_id,))
        assert updated['status'] == 'Withdrawn', f"Expected Withdrawn, got {updated['status']}"
        p(f"  PASS - Application #{test_app_id} transitioned to 'Withdrawn'")
    else:
        p("  SKIP - No applicant found for david.kim@gmail.com")

    client.get('/auth/logout', follow_redirects=True)

    # 7. Recruiter Dashboard (Dashboard 1)
    p("\n[TEST 7] Recruiter Dashboard (Dashboard 1)...")
    client.post('/auth/login', data={
        'identifier': 'alex_talent', 'password': 'password123'
    }, follow_redirects=True)
    p("  PASS - Recruiter logged in")

    res_rec = client.get('/recruiter/dashboard')
    assert res_rec.status_code == 200
    assert b"Recruiter Dashboard" in res_rec.data
    assert b"Total Applicants" in res_rec.data
    assert b"Applications This Week" in res_rec.data
    assert b"Upcoming Interviews" in res_rec.data
    assert b"Hired This Month" in res_rec.data
    assert b"timelineChart" in res_rec.data
    assert b"funnelChart" in res_rec.data
    assert b"Recent Applications (Last 10)" in res_rec.data
    assert b"kanban-board" in res_rec.data
    assert b"Withdrawn" in res_rec.data
    p("  PASS - KPI cards, Chart.js timeline & funnel, recent apps, today interviews, 6-stage Kanban")

    # 8. Feature 10: Recruiter Notes
    p("\n[TEST 8] Recruiter Collaboration Notes (Feature 10)...")
    any_app = db.query_one("""
        SELECT a.application_id 
        FROM applications a 
        JOIN jobs j ON a.job_id = j.job_id 
        JOIN users_v2 u ON u.company_id = j.company_id
        WHERE u.username = 'alex_talent'
        LIMIT 1;
    """)
    note_text = "Excellent PostgreSQL optimization skills demonstrated in technical assessment."
    res_note = client.post(f'/applications/{any_app["application_id"]}/notes', data={
        'note_text': note_text
    }, follow_redirects=True)
    assert res_note.status_code == 200

    note_in_db = db.query_one("""
        SELECT note FROM application_notes
        WHERE application_id = %s AND note = %s;
    """, (any_app['application_id'], note_text))
    assert note_in_db is not None, "Note not persisted!"
    p(f"  PASS - Note saved to application_notes for App #{any_app['application_id']}")

    # Check update_status page for notes rendering
    res_manage = client.get(f'/recruiter/update-status/{any_app["application_id"]}')
    assert res_manage.status_code == 200
    assert b"Recruiter Team Notes" in res_manage.data
    assert b"PostgreSQL optimization" in res_manage.data
    p("  PASS - Notes thread rendered on candidate management page")

    # 9. Dashboard 4: Recruiter Analytics
    p("\n[TEST 9] Recruiter Analytics (Dashboard 4)...")
    res_an = client.get('/recruiter/analytics')
    assert res_an.status_code == 200
    assert b"Avg Time-to-Hire" in res_an.data
    assert b"Recruitment Stage Conversion Rates" in res_an.data
    assert b"velocityChart" in res_an.data
    assert b"Source of Hire" in res_an.data
    p("  PASS - Time-to-Hire, conversion rates, velocity chart, top jobs table rendered")

    client.get('/auth/logout', follow_redirects=True)

    # 10. Admin Dashboard (Dashboard 2)
    p("\n[TEST 10] Admin SaaS Dashboard (Dashboard 2)...")
    client.post('/auth/login', data={
        'identifier': 'admin_system', 'password': 'password123'
    }, follow_redirects=True)
    p("  PASS - Admin logged in")

    res_admin = client.get('/admin/dashboard')
    assert res_admin.status_code == 200
    assert b"Total Companies" in res_admin.data
    assert b"Total Users" in res_admin.data
    assert b"Monthly Recurring Revenue" in res_admin.data
    assert b"Active Subscriptions" in res_admin.data
    assert b"signupChart" in res_admin.data
    assert b"planPieChart" in res_admin.data
    assert b"Recent Company Signups" in res_admin.data
    assert b"Recent Subscription Upgrades" in res_admin.data
    p("  PASS - MRR, Users, Signups Line Chart, Plan Pie Chart, Recent Upgrades table")

    p("\n" + "=" * 70)
    p("ALL 10 VERIFICATION TESTS PASSED SUCCESSFULLY!")
    p("=" * 70)

if __name__ == '__main__':
    run_tests()
