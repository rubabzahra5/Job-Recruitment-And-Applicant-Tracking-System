-- ==============================================================================
-- University DBMS Project: Job Recruitment and Applicant Tracking System (ATS)
-- Database: PostgreSQL (Normalized to 3NF)
-- Component: Schema Definition (DDL), Constraints, Indexes, Triggers, Views & Procedures
-- ==============================================================================

-- Drop existing views, procedures, triggers, and tables if they exist (clean slate)
DROP VIEW IF EXISTS v_applicant_pipeline_overview CASCADE;
DROP VIEW IF EXISTS v_job_applications_summary CASCADE;

DROP PROCEDURE IF EXISTS sp_schedule_interview CASCADE;
DROP FUNCTION IF EXISTS fn_get_applicants_for_job CASCADE;
DROP FUNCTION IF EXISTS fn_advance_application_on_interview CASCADE;
DROP FUNCTION IF EXISTS fn_update_timestamp CASCADE;
DROP FUNCTION IF EXISTS fn_validate_application_submission CASCADE;

DROP TABLE IF EXISTS interviews CASCADE;
DROP TABLE IF EXISTS applications CASCADE;
DROP TABLE IF EXISTS applicant_skills CASCADE;
DROP TABLE IF EXISTS skills CASCADE;
DROP TABLE IF EXISTS applicants CASCADE;
DROP TABLE IF EXISTS jobs CASCADE;
DROP TABLE IF EXISTS companies CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- ==============================================================================
-- 1. TABLE DEFINITIONS (Normalized to 3NF)
-- ==============================================================================

-- Table 1: users
-- Represents authenticated actors in the system (Recruiters, Applicants, Admins)
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('recruiter', 'applicant', 'admin')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE users IS 'Core authentication table holding credentials and system roles';
COMMENT ON COLUMN users.role IS 'Role of the user: recruiter, applicant, or admin';

-- Table 2: companies
-- Stores enterprise employer details (Eliminates transitive dependencies from jobs)
CREATE TABLE companies (
    company_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    website VARCHAR(150),
    location VARCHAR(100) NOT NULL,
    industry VARCHAR(60),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE companies IS 'Employer organizations offering job vacancies';

-- Table 3: jobs
-- Stores individual job openings posted by recruiters for specific companies
CREATE TABLE jobs (
    job_id SERIAL PRIMARY KEY,
    company_id INT NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    recruiter_id INT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    title VARCHAR(120) NOT NULL,
    department VARCHAR(80) NOT NULL,
    location VARCHAR(100) NOT NULL,
    job_type VARCHAR(30) NOT NULL CHECK (job_type IN ('Full-Time', 'Part-Time', 'Contract', 'Remote', 'Internship')),
    salary_min NUMERIC(12, 2) CHECK (salary_min >= 0),
    salary_max NUMERIC(12, 2) CHECK (salary_max >= salary_min),
    description TEXT NOT NULL,
    requirements TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Open' CHECK (status IN ('Open', 'Closed', 'Draft', 'Archived')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE jobs IS 'Job postings linked to companies and recruiter users';

-- Table 4: applicants
-- Candidate profiles containing demographic and contact information
CREATE TABLE applicants (
    applicant_id SERIAL PRIMARY KEY,
    user_id INT UNIQUE REFERENCES users(user_id) ON DELETE SET NULL,
    first_name VARCHAR(60) NOT NULL,
    last_name VARCHAR(60) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    phone VARCHAR(25),
    location VARCHAR(100),
    linkedin_url VARCHAR(200),
    portfolio_url VARCHAR(200),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE applicants IS 'Candidate profile records normalized from users table';

-- Table 5: skills
-- Master lookup catalog of industry skills
CREATE TABLE skills (
    skill_id SERIAL PRIMARY KEY,
    skill_name VARCHAR(60) NOT NULL UNIQUE,
    category VARCHAR(50) NOT NULL -- e.g., 'Languages', 'Database', 'Cloud', 'Frameworks'
);

COMMENT ON TABLE skills IS 'Standardized skill taxonomy';

-- Table 6: applicant_skills (Junction Table for M:N Relationship)
-- Links applicants with skills, capturing proficiency and experience
CREATE TABLE applicant_skills (
    applicant_id INT NOT NULL REFERENCES applicants(applicant_id) ON DELETE CASCADE,
    skill_id INT NOT NULL REFERENCES skills(skill_id) ON DELETE CASCADE,
    years_of_experience NUMERIC(4, 1) DEFAULT 1.0 CHECK (years_of_experience >= 0),
    proficiency_level VARCHAR(20) DEFAULT 'Intermediate' CHECK (proficiency_level IN ('Beginner', 'Intermediate', 'Advanced', 'Expert')),
    PRIMARY KEY (applicant_id, skill_id)
);

COMMENT ON TABLE applicant_skills IS 'Junction table linking applicants to their competencies with proficiency levels';

-- Table 7: applications
-- Tracks candidate applications for specific jobs through the hiring pipeline
CREATE TABLE applications (
    application_id SERIAL PRIMARY KEY,
    job_id INT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    applicant_id INT NOT NULL REFERENCES applicants(applicant_id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'Applied' CHECK (status IN ('Applied', 'Screening', 'Interview', 'Hired', 'Rejected')),
    resume_filename VARCHAR(255) NOT NULL,
    cover_letter TEXT,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_job_applicant UNIQUE (job_id, applicant_id)
);

COMMENT ON TABLE applications IS 'Core workflow table tracking candidate lifecycle per job';

-- Table 8: interviews
-- Tracks scheduled, completed, and evaluated interview rounds for applications
CREATE TABLE interviews (
    interview_id SERIAL PRIMARY KEY,
    application_id INT NOT NULL REFERENCES applications(application_id) ON DELETE CASCADE,
    interviewer_id INT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    interview_type VARCHAR(40) NOT NULL CHECK (interview_type IN ('Phone Screening', 'Technical Assessment', 'System Design', 'Behavioral', 'Executive Final')),
    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_minutes INT NOT NULL DEFAULT 45 CHECK (duration_minutes > 0),
    feedback TEXT,
    rating INT CHECK (rating BETWEEN 1 AND 5),
    status VARCHAR(20) NOT NULL DEFAULT 'Scheduled' CHECK (status IN ('Scheduled', 'Completed', 'Cancelled', 'No Show')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE interviews IS 'Interview rounds associated with an application';


-- ==============================================================================
-- 2. INDEXES (Optimized for Foreign Keys, Searches, and Analytical Queries)
-- ==============================================================================

-- Index for high-throughput public job search
CREATE INDEX idx_jobs_status_created ON jobs(status, created_at DESC);
CREATE INDEX idx_jobs_company ON jobs(company_id);
CREATE INDEX idx_jobs_department ON jobs(department);

-- Index for applicant lookups by email and user
CREATE INDEX idx_applicants_email ON applicants(email);
CREATE INDEX idx_applicants_user ON applicants(user_id);

-- Index for recruiter Kanban board performance (job + status)
CREATE INDEX idx_applications_job_status ON applications(job_id, status);
CREATE INDEX idx_applications_applicant ON applications(applicant_id);

-- Index for candidate skills querying
CREATE INDEX idx_applicant_skills_skill ON applicant_skills(skill_id);

-- Index for interview scheduling by date and application
CREATE INDEX idx_interviews_application ON interviews(application_id);
CREATE INDEX idx_interviews_scheduled_at ON interviews(scheduled_at);


-- ==============================================================================
-- 3. TRIGGERS (Automated Business Logic & Audit Trails)
-- ==============================================================================

-- Trigger Function 1: Automatically updates 'updated_at' column on row modification
CREATE OR REPLACE FUNCTION fn_update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply Trigger 1 to jobs and applications
CREATE TRIGGER trg_jobs_update_timestamp
    BEFORE UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION fn_update_timestamp();

CREATE TRIGGER trg_applications_update_timestamp
    BEFORE UPDATE ON applications
    FOR EACH ROW
    EXECUTE FUNCTION fn_update_timestamp();


-- Trigger Function 2: Automatically advances application status to 'Interview'
-- when an interview round is scheduled if the application is in 'Applied' or 'Screening'
CREATE OR REPLACE FUNCTION fn_advance_application_on_interview()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'Scheduled' THEN
        UPDATE applications
        SET status = 'Interview',
            updated_at = CURRENT_TIMESTAMP
        WHERE application_id = NEW.application_id
          AND status IN ('Applied', 'Screening');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply Trigger 2 to interviews table
CREATE TRIGGER trg_interviews_auto_advance_status
    AFTER INSERT ON interviews
    FOR EACH ROW
    EXECUTE FUNCTION fn_advance_application_on_interview();


-- Trigger Function 3 (Guard): Prevents applications to non-open jobs
CREATE OR REPLACE FUNCTION fn_validate_application_submission()
RETURNS TRIGGER AS $$
DECLARE
    v_job_status VARCHAR(20);
BEGIN
    SELECT status INTO v_job_status FROM jobs WHERE job_id = NEW.job_id;
    
    IF v_job_status IS NULL THEN
        RAISE EXCEPTION 'Target job id % does not exist.', NEW.job_id;
    ELSIF v_job_status <> 'Open' THEN
        RAISE EXCEPTION 'Cannot apply to job %: current status is "%". Only "Open" jobs accept applications.', NEW.job_id, v_job_status;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_job_application
    BEFORE INSERT ON applications
    FOR EACH ROW
    EXECUTE FUNCTION fn_validate_application_submission();


-- ==============================================================================
-- 4. VIEWS (Analytical and Operational Reporting)
-- ==============================================================================

-- View 1: v_job_applications_summary
-- Executive overview of job posts with aggregated recruitment pipeline metrics
CREATE OR REPLACE VIEW v_job_applications_summary AS
SELECT 
    j.job_id,
    j.title AS job_title,
    j.department,
    c.name AS company_name,
    c.location AS company_location,
    j.job_type,
    j.status AS job_status,
    j.salary_min,
    j.salary_max,
    u.username AS posted_by_recruiter,
    COUNT(a.application_id) AS total_applicants,
    COUNT(CASE WHEN a.status = 'Applied' THEN 1 END) AS applied_count,
    COUNT(CASE WHEN a.status = 'Screening' THEN 1 END) AS screening_count,
    COUNT(CASE WHEN a.status = 'Interview' THEN 1 END) AS interview_count,
    COUNT(CASE WHEN a.status = 'Hired' THEN 1 END) AS hired_count,
    COUNT(CASE WHEN a.status = 'Rejected' THEN 1 END) AS rejected_count,
    ROUND(AVG(iv.rating), 2) AS avg_candidate_rating,
    j.created_at AS posted_date
FROM jobs j
JOIN companies c ON j.company_id = c.company_id
JOIN users u ON j.recruiter_id = u.user_id
LEFT JOIN applications a ON j.job_id = a.job_id
LEFT JOIN interviews iv ON a.application_id = iv.application_id
GROUP BY j.job_id, c.name, c.location, u.username;

COMMENT ON VIEW v_job_applications_summary IS 'Analytical view consolidating job listings with candidate conversion metrics and interview ratings';


-- View 2: v_applicant_pipeline_overview
-- Powers the recruiter Kanban board with candidate demographics, skills, and application progress
CREATE OR REPLACE VIEW v_applicant_pipeline_overview AS
SELECT 
    app.application_id,
    app.job_id,
    j.title AS job_title,
    c.name AS company_name,
    j.department,
    cand.applicant_id,
    cand.first_name || ' ' || cand.last_name AS candidate_name,
    cand.email AS candidate_email,
    cand.phone AS candidate_phone,
    cand.location AS candidate_location,
    cand.linkedin_url,
    cand.portfolio_url,
    app.status AS application_status,
    app.resume_filename,
    app.cover_letter,
    app.applied_at,
    app.updated_at,
    COALESCE(
        (SELECT string_agg(s.skill_name || ' (' || ask.proficiency_level || ')', ', ' ORDER BY s.skill_name)
         FROM applicant_skills ask
         JOIN skills s ON ask.skill_id = s.skill_id
         WHERE ask.applicant_id = cand.applicant_id),
        'None Recorded'
    ) AS candidate_skills,
    (SELECT COUNT(*) FROM interviews i WHERE i.application_id = app.application_id) AS total_interviews,
    (SELECT ROUND(AVG(rating), 1) FROM interviews i WHERE i.application_id = app.application_id AND rating IS NOT NULL) AS avg_interview_rating
FROM applications app
JOIN applicants cand ON app.applicant_id = cand.applicant_id
JOIN jobs j ON app.job_id = j.job_id
JOIN companies c ON j.company_id = c.company_id;

COMMENT ON VIEW v_applicant_pipeline_overview IS 'Operational view feeding the recruiter Kanban board and candidate profile summaries';


-- ==============================================================================
-- 5. STORED PROCEDURES & FUNCTIONS
-- ==============================================================================

-- Stored Function 1: fn_get_applicants_for_job
-- Fetches candidate details for a specific job, with optional status filter
CREATE OR REPLACE FUNCTION fn_get_applicants_for_job(
    p_job_id INT,
    p_status VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    application_id INT,
    applicant_id INT,
    candidate_name TEXT,
    email VARCHAR,
    phone VARCHAR,
    current_status VARCHAR,
    applied_at TIMESTAMP WITH TIME ZONE,
    skills_list TEXT,
    interview_count BIGINT,
    avg_rating NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        v.application_id,
        v.applicant_id,
        v.candidate_name,
        v.candidate_email,
        v.candidate_phone,
        v.application_status,
        v.applied_at,
        v.candidate_skills,
        v.total_interviews,
        v.avg_interview_rating
    FROM v_applicant_pipeline_overview v
    WHERE v.job_id = p_job_id
      AND (p_status IS NULL OR v.application_status = p_status)
    ORDER BY v.applied_at DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fn_get_applicants_for_job IS 'Returns detailed applicant pipeline for a given job, optionally filtered by status';


-- Stored Procedure 2: sp_schedule_interview
-- Transactional procedure to schedule an interview, validate recruiter/interviewer,
-- advance application status, and write an interview audit record
CREATE OR REPLACE PROCEDURE sp_schedule_interview(
    p_application_id INT,
    p_interviewer_id INT,
    p_interview_type VARCHAR,
    p_scheduled_at TIMESTAMP WITH TIME ZONE,
    p_duration_minutes INT,
    p_feedback TEXT DEFAULT NULL,
    p_rating INT DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_app_exists INT;
    v_user_role VARCHAR(20);
BEGIN
    -- 1. Check if application exists
    SELECT COUNT(*) INTO v_app_exists 
    FROM applications 
    WHERE application_id = p_application_id;

    IF v_app_exists = 0 THEN
        RAISE EXCEPTION 'Application with ID % does not exist.', p_application_id;
    END IF;

    -- 2. Verify interviewer has recruiter or admin role
    SELECT role INTO v_user_role 
    FROM users 
    WHERE user_id = p_interviewer_id;

    IF v_user_role IS NULL OR v_user_role NOT IN ('recruiter', 'admin') THEN
        RAISE EXCEPTION 'User % is not authorized to conduct or schedule interviews.', p_interviewer_id;
    END IF;

    -- 3. Insert the interview round (Trigger trg_interviews_auto_advance_status will advance application status)
    INSERT INTO interviews (
        application_id,
        interviewer_id,
        interview_type,
        scheduled_at,
        duration_minutes,
        feedback,
        rating,
        status
    ) VALUES (
        p_application_id,
        p_interviewer_id,
        p_interview_type,
        p_scheduled_at,
        p_duration_minutes,
        p_feedback,
        p_rating,
        'Scheduled'
    );

    -- 4. Explicitly ensure application timestamp is updated
    UPDATE applications 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE application_id = p_application_id;
    
END;
$$;

COMMENT ON PROCEDURE sp_schedule_interview IS 'Schedules an interview round and coordinates atomic workflow updates';
