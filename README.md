# Job Recruitment and Applicant Tracking System (ATS)

**Job Recruitment and Applicant Tracking System (ATS)** is a complete, multi-tenant B2B **Applicant Tracking System (ATS)** and recruitment software platform built with **Python (Flask)**, **PostgreSQL** (via `psycopg2`), and **HTML5 + Bootstrap 5**.

It combines a 3NF normalized relational DBMS engine (views, triggers, stored procedures, indexes) with commercial SaaS features: **Role-Based Authentication (RBAC)**, **Company Workspaces & Recruiter Team Seats**, **Automated Email Notifications with DB Audits**, **Stripe 3-Tier Subscriptions with Quota Gating**, and **Custom Brand Identity with Multi-Tenant Career Portals**.

---

## 1. Tech Stack

- **Backend:** Python 3 + Flask 3.1
- **Database:** PostgreSQL 18 with `psycopg2` driver (`RealDictCursor`)
- **Authentication:** `Flask-Login` + secure password hashing with `Werkzeug`
- **Email Notifications:** `Flask-Mail` with dual-mode delivery (SMTP or graceful DB logging fallback)
- **Payments & Subscriptions:** `stripe` Python SDK (Checkout Sessions, feature gating, 3-tier limits)
- **Frontend:** HTML5 + Bootstrap 5.3 CDN + Bootstrap Icons (Responsive, modern, clean)
- **Document & Asset Storage:** Resumes (`static/uploads/resumes/`) and Company Logos (`static/uploads/logos/`)

---

## 2. Commercial SaaS Features Added

### 1. Authentication & Role-Based Access Control (RBAC)
- Unified login (`/auth/login`) supporting Admins, Recruiters, and Applicants.
- Applicant self-registration (`/auth/register`) creating accounts and candidate profiles.
- Route guards using `@role_required(['recruiter', 'admin'])`, `@role_required('applicant')`, `@login_required`.
- Quick-fill demo buttons on the login screen for testing all 3 user roles with 1 click.

### 2. Multi-Tenant Company Registration & Recruiter Team Management
- Company registration (`/company/register`):
  - Company profile, website, industry, headquarters, description.
  - Logo image upload (`.png`, `.jpg`, `.svg`, `.webp`).
  - Primary brand color picker (`brand_color`) and header text contrast picker.
  - Auto-provisions the primary Recruiter Admin account and activates the **Free** subscription tier.
- Team Management (`/company/team`):
  - View all team recruiters and seat allocation.
  - Generates secure tokenized invitations (`recruiter_invitations` table) and dispatches onboarding emails.
  - Enforces `recruiter_limit` quota based on subscription plan.
  - Invited recruiter acceptance flow (`/invite/accept/<token>`).

### 3. Transactional Email Notifications & Audit Logging
- Integrated via `mailer.py` and persisted in PostgreSQL `email_logs`.
- Dual-mode delivery:
  - Connects to SMTP if configured in `.env`.
  - Automatically falls back to mock logging if SMTP credentials are dummy/offline, ensuring applications and workflows never crash.
- Automated triggers:
  1. **Application Confirmation:** Dispatched on submission with Application ID and tracking link.
  2. **Stage Progression Notice:** Dispatched when a candidate is moved to `Screening`, `Interview`, `Hired`, or `Rejected`.
  3. **Interview Schedule Invitation:** Dispatched when an interview is scheduled via `sp_schedule_interview`.
  4. **Recruiter Team Invitation:** Dispatched when a recruiter invites a colleague.
- Audit table viewer (`/admin/email-logs`) for reviewing outbound communication.

### 4. Stripe Payments & 3-Tier Subscription Model
- Dedicated pricing comparison page (`/pricing`).
- **3 Tiers & Limits:**

| Tier | Price | Active Job Limit | Recruiter Seats | Custom Branding | Dedicated Career Portal |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Free** | $0/mo | 1 Job | 1 Seat | Standard | Shared Job Board |
| **Basic** | $49/mo | 5 Jobs | 3 Seats | Standard | Shared Job Board |
| **Pro** | $149/mo | Unlimited | Unlimited | Custom Logo & Colors | Dedicated `/careers/:slug` |

- Stripe Checkout integration (`stripe.checkout.Session.create`) with simulated instant test checkout for offline evaluation.
- Quota enforcement in `/recruiter/jobs/new` and `/company/team/invite` with upgrade prompts.

### 5. Custom Branding & Multi-Tenant Career Pages
- Company branding settings (`/company/branding`) for Pro tier subscribers:
  - Upload company logo.
  - Live brand primary color swatch picker.
- Dedicated multi-tenant public career pages (`/careers/<slug>`):
  - E.g.: `/careers/stripe-global`, `/careers/datadog-systems`, `/careers/snowflake-computing`.
  - Injects dynamic CSS variables (`--company-brand: {{ company.brand_color }}`).
  - Branded header displaying company logo and custom colors.
  - Displays exclusively active jobs for that specific employer with direct apply links.

---

## 3. Database Architecture (3NF Schema)

### Tables Summary

| Table | Description |
|:---|:---|
| **`companies_v2`** | Multi-tenant organization profile with `slug`, `logo_filename`, `brand_color`, `brand_text_color`. |
| **`subscriptions`** | Tier monetization ledger (`Free`, `Basic`, `Pro`), quotas (`job_limit`, `recruiter_limit`), `custom_branding_enabled`. |
| **`users_v2`** | Tenant-scoped user credentials, `role` (`admin`, `recruiter`, `applicant`), Werkzeug `password_hash`. |
| **`recruiter_invitations`** | Secure tokenized invitation records for onboarding colleagues. |
| **`email_logs`** | Notification audit trail (`recipient_email`, `subject`, `email_type`, `body`, `status`). |
| **`jobs`** | Job openings linked to `companies_v2` and `users_v2`, `salary_min <= salary_max`. |
| **`applicants`** | Candidate contact info, LinkedIn, and portfolio URLs. |
| **`skills`** | Taxonomy catalog of technical skills. |
| **`applicant_skills`** | M:N Junction table linking applicants and skills with proficiency and experience years. |
| **`applications`** | Candidate application lifecycle per job (`Applied`, `Screening`, `Interview`, `Hired`, `Rejected`). |
| **`interviews`** | Interview rounds, ratings (1–5), duration, feedback, and interviewer links. |

### PostgreSQL Triggers, Views & Stored Procedures
- **Trigger 1 (`trg_applications_update_timestamp`):** Auto-updates `updated_at` on row modifications.
- **Trigger 2 (`trg_interviews_auto_advance_status`):** Promotes application status to `'Interview'` when an interview round is scheduled.
- **Trigger 3 (`trg_validate_job_application`):** Prevents submissions to non-open jobs.
- **View 1 (`v_job_applications_summary`):** Aggregated metrics per job (total, screening, interview, hired, rejected, avg rating).
- **View 2 (`v_applicant_pipeline_overview`):** Multi-table join powering the Kanban board with concatenated skills (`string_agg`).
- **Stored Procedure (`sp_schedule_interview`):** Transactional interview scheduling and pipeline advancement.
- **Table Function (`fn_get_applicants_for_job`):** Retrieves candidate rows for a job.

---

## 4. Quickstart Guide

### 1. Configure Environment
Credentials are pre-configured in `.env`:
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ats_db
DB_USER=postgres
DB_PASSWORD=your_postgres_password
```

### 2. Run the Application
```bash
python app.py
```
Access the application at: **`http://localhost:5000`**

### 3. Demo Login Credentials
All demo accounts use password: `password123`

- **Recruiter (Stripe Global - Pro Plan):** `alex_talent` / `password123`
- **Recruiter (Datadog Systems - Basic Plan):** `elena_hr` / `password123`
- **Recruiter (Snowflake Computing - Pro Plan):** `sarah_recruiter` / `password123`
- **Applicant (Candidate Profile):** `david.kim@gmail.com` / `password123`
- **Platform Administrator:** `admin_system` / `password123`

*(Note: The login page includes 1-click Quick-Fill buttons for instant role switching during evaluation.)*

---

## 5. Verification Suite

Run the automated end-to-end verification script:
```bash
python "C:\Users\amc\.gemini\antigravity\brain\43b0f8ec-0c6c-4503-84ac-ccb022fe051b\scratch\verify_v2_saas.py"
```
Verifies authentication, company registration, email audit logging, Stripe tier upgrades, branded career pages, and all route HTTP 200 responses.
