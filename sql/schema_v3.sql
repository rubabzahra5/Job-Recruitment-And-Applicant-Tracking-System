-- ==============================================================================
-- University DBMS Project / SaaS Upgrade: Job Recruitment and Applicant Tracking System (Phase 3)
-- File: schema_v3.sql
-- Description: Adds tables for Saved Jobs, Application Notes, User Search History,
--              enhances Job schema with experience level & deadline, and enables
--              the 'Withdrawn' application status.
-- ==============================================================================

-- 1. UPDATE applications.status CONSTRAINT TO INCLUDE 'Withdrawn'
ALTER TABLE applications DROP CONSTRAINT IF EXISTS applications_status_check;
ALTER TABLE applications ADD CONSTRAINT applications_status_check 
    CHECK (status IN ('Applied', 'Screening', 'Interview', 'Hired', 'Rejected', 'Withdrawn'));

-- 2. ENHANCE jobs TABLE WITH EXPERIENCE LEVEL & DEADLINE
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'jobs' AND column_name = 'experience_level'
    ) THEN
        ALTER TABLE jobs ADD COLUMN experience_level VARCHAR(30) DEFAULT 'Mid-Level' 
            CHECK (experience_level IN ('Entry-Level', 'Mid-Level', 'Senior', 'Lead', 'Executive'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'jobs' AND column_name = 'application_deadline'
    ) THEN
        ALTER TABLE jobs ADD COLUMN application_deadline TIMESTAMP WITH TIME ZONE 
            DEFAULT (CURRENT_TIMESTAMP + INTERVAL '30 days');
    END IF;
END $$;

-- Populate realistic experience levels and deadlines for existing jobs
UPDATE jobs SET experience_level = 'Senior', application_deadline = CURRENT_TIMESTAMP + INTERVAL '21 days' WHERE job_id = 1;
UPDATE jobs SET experience_level = 'Mid-Level', application_deadline = CURRENT_TIMESTAMP + INTERVAL '14 days' WHERE job_id = 2;
UPDATE jobs SET experience_level = 'Lead', application_deadline = CURRENT_TIMESTAMP + INTERVAL '28 days' WHERE job_id = 3;
UPDATE jobs SET experience_level = 'Senior', application_deadline = CURRENT_TIMESTAMP + INTERVAL '18 days' WHERE job_id = 4;
UPDATE jobs SET experience_level = 'Entry-Level', application_deadline = CURRENT_TIMESTAMP + INTERVAL '10 days' WHERE job_id = 5;
UPDATE jobs SET experience_level = 'Mid-Level', application_deadline = CURRENT_TIMESTAMP + INTERVAL '25 days' WHERE job_id = 6;


-- 3. CREATE TABLE: saved_jobs (Candidate Bookmarks)
CREATE TABLE IF NOT EXISTS saved_jobs (
    save_id SERIAL PRIMARY KEY,
    applicant_id INT NOT NULL REFERENCES applicants(applicant_id) ON DELETE CASCADE,
    job_id INT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    saved_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_applicant_saved_job UNIQUE (applicant_id, job_id)
);

COMMENT ON TABLE saved_jobs IS 'Stores candidate bookmarked jobs for 1-click application review';

CREATE INDEX IF NOT EXISTS idx_saved_jobs_applicant ON saved_jobs(applicant_id);
CREATE INDEX IF NOT EXISTS idx_saved_jobs_job ON saved_jobs(job_id);


-- 4. CREATE TABLE: application_notes (Recruiter Collaboration Thread)
CREATE TABLE IF NOT EXISTS application_notes (
    note_id SERIAL PRIMARY KEY,
    application_id INT NOT NULL REFERENCES applications(application_id) ON DELETE CASCADE,
    author_id INT NOT NULL REFERENCES users_v2(user_id) ON DELETE CASCADE,
    note TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE application_notes IS 'Recruiter internal comments and evaluation notes per application';

CREATE INDEX IF NOT EXISTS idx_app_notes_application ON application_notes(application_id);
CREATE INDEX IF NOT EXISTS idx_app_notes_author ON application_notes(author_id);


-- 5. CREATE TABLE: user_search_history (Saved Job Searches)
CREATE TABLE IF NOT EXISTS user_search_history (
    search_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users_v2(user_id) ON DELETE CASCADE,
    search_label VARCHAR(150) NOT NULL,
    search_filters JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE user_search_history IS 'Saved filter criteria for candidates and recruiters';

CREATE INDEX IF NOT EXISTS idx_search_history_user ON user_search_history(user_id);


-- 6. SEED SAMPLE SAVED JOBS & RECRUITER NOTES
-- Sample bookmarks for David Kim (applicant 1) and Maya Patel (applicant 2)
INSERT INTO saved_jobs (applicant_id, job_id) VALUES
(1, 2), -- David saved Datadog SRE
(1, 3), -- David saved Snowflake Data Platform
(2, 1)  -- Maya saved Stripe Backend
ON CONFLICT (applicant_id, job_id) DO NOTHING;

-- Sample Recruiter Notes for Application 1 (David Kim at Stripe) and Application 2 (Maya Patel at Datadog)
INSERT INTO application_notes (application_id, author_id, note, created_at) VALUES
(1, 2, 'Candidate demonstrated deep mastery of Postgres write-ahead logs and MVCC concurrency during the technical interview.', CURRENT_TIMESTAMP - INTERVAL '8 days'),
(1, 2, 'Leadership team approved offer package. Extending offer letter with equity component.', CURRENT_TIMESTAMP - INTERVAL '6 days'),
(2, 3, 'Solid Kubernetes experience. Needs slight ramp up on multi-cluster mesh architecture.', CURRENT_TIMESTAMP - INTERVAL '5 days'),
(3, 2, 'Strong academic background in relational algebra. Scheduled for initial phone screening.', CURRENT_TIMESTAMP - INTERVAL '2 days')
ON CONFLICT DO NOTHING;
