-- ==============================================================================
-- University DBMS Project: Job Recruitment and Applicant Tracking System (ATS)
-- File: queries.sql
-- Description: 10 Advanced SQL Queries Demonstrating INNER JOIN, LEFT JOIN,
--              GROUP BY, HAVING, Aggregate Functions, and Subqueries
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- QUERY 1: Active Job Postings with Company Details
-- Concepts: INNER JOIN, WHERE, ORDER BY, String Formatting
-- Description: Fetches all active job openings enriched with company profile data
-- ------------------------------------------------------------------------------
SELECT 
    j.job_id,
    j.title AS job_title,
    c.name AS company_name,
    c.location AS company_headquarters,
    j.location AS job_location,
    j.job_type,
    j.salary_min,
    j.salary_max,
    TO_CHAR(j.created_at, 'YYYY-MM-DD') AS date_posted
FROM jobs j
INNER JOIN companies c ON j.company_id = c.company_id
WHERE j.status = 'Open'
ORDER BY j.created_at DESC;


-- ------------------------------------------------------------------------------
-- QUERY 2: Comprehensive Candidate Application Pipeline
-- Concepts: LEFT OUTER JOIN (Multi-table), COALESCE
-- Description: Lists all applicants and any active applications, including candidates
--              who have registered but not yet applied.
-- ------------------------------------------------------------------------------
SELECT 
    cand.applicant_id,
    cand.first_name || ' ' || cand.last_name AS full_name,
    cand.email,
    cand.location AS applicant_city,
    COALESCE(j.title, 'No Active Applications') AS applied_job,
    COALESCE(c.name, 'N/A') AS company,
    COALESCE(app.status, 'Registered') AS current_stage,
    app.applied_at
FROM applicants cand
LEFT JOIN applications app ON cand.applicant_id = app.applicant_id
LEFT JOIN jobs j ON app.job_id = j.job_id
LEFT JOIN companies c ON j.company_id = c.company_id
ORDER BY cand.applicant_id, app.applied_at DESC;


-- ------------------------------------------------------------------------------
-- QUERY 3: Application Funnel Distribution Across Statuses
-- Concepts: GROUP BY, Aggregate Functions (COUNT, SUM), Window Function (OVER)
-- Description: Computes applicant count and percentage share for each pipeline stage.
-- ------------------------------------------------------------------------------
SELECT 
    status AS pipeline_stage,
    COUNT(*) AS total_applications,
    ROUND(
        (COUNT(*)::DECIMAL / SUM(COUNT(*)) OVER ()) * 100, 
        2
    ) AS percentage_of_total
FROM applications
GROUP BY status
ORDER BY total_applications DESC;


-- ------------------------------------------------------------------------------
-- QUERY 4: Departmental Hiring Budget & Compensation Analysis
-- Concepts: GROUP BY, HAVING, Aggregates (COUNT, MIN, MAX, AVG)
-- Description: Identifies departments with multiple openings and calculates salary brackets.
-- ------------------------------------------------------------------------------
SELECT 
    department,
    COUNT(job_id) AS total_openings,
    ROUND(MIN(salary_min), 2) AS lowest_salary_min,
    ROUND(AVG((salary_min + salary_max) / 2.0), 2) AS avg_midpoint_salary,
    ROUND(MAX(salary_max), 2) AS highest_salary_max
FROM jobs
WHERE status = 'Open'
GROUP BY department
HAVING COUNT(job_id) >= 1
ORDER BY avg_midpoint_salary DESC;


-- ------------------------------------------------------------------------------
-- QUERY 5: Top In-Demand Applicant Skills and Average Experience
-- Concepts: INNER JOIN, GROUP BY, Aggregate Functions (COUNT, AVG, MAX)
-- Description: Aggregates candidate skills to determine market talent pool density.
-- ------------------------------------------------------------------------------
SELECT 
    s.skill_id,
    s.skill_name,
    s.category,
    COUNT(ask.applicant_id) AS candidate_count,
    ROUND(AVG(ask.years_of_experience), 1) AS avg_experience_years,
    MAX(ask.years_of_experience) AS max_experience_years
FROM skills s
INNER JOIN applicant_skills ask ON s.skill_id = ask.skill_id
GROUP BY s.skill_id, s.skill_name, s.category
ORDER BY candidate_count DESC, avg_experience_years DESC;


-- ------------------------------------------------------------------------------
-- QUERY 6: Recruiter Performance & Placement Efficiency
-- Concepts: INNER JOIN, LEFT JOIN, GROUP BY, Conditional Aggregation (COUNT CASE)
-- Description: Measures how many jobs each recruiter has posted and their conversion to hires.
-- ------------------------------------------------------------------------------
SELECT 
    u.user_id AS recruiter_id,
    u.username AS recruiter_name,
    u.email AS recruiter_email,
    COUNT(DISTINCT j.job_id) AS total_jobs_posted,
    COUNT(app.application_id) AS total_applicants_received,
    COUNT(CASE WHEN app.status = 'Interview' THEN 1 END) AS candidates_in_interview,
    COUNT(CASE WHEN app.status = 'Hired' THEN 1 END) AS successful_hires
FROM users u
INNER JOIN jobs j ON u.user_id = j.recruiter_id
LEFT JOIN applications app ON j.job_id = app.job_id
WHERE u.role = 'recruiter'
GROUP BY u.user_id, u.username, u.email
ORDER BY successful_hires DESC, total_applicants_received DESC;


-- ------------------------------------------------------------------------------
-- QUERY 7: Top-Rated Candidates Across Interview Rounds
-- Concepts: INNER JOIN, GROUP BY, Aggregate Functions (AVG, COUNT), Subqueries
-- Description: Identifies candidates whose average interview score is 4.0 or above.
-- ------------------------------------------------------------------------------
SELECT 
    cand.applicant_id,
    cand.first_name || ' ' || cand.last_name AS candidate_name,
    j.title AS job_position,
    c.name AS company_name,
    COUNT(iv.interview_id) AS total_interview_rounds,
    ROUND(AVG(iv.rating), 2) AS overall_avg_score
FROM applicants cand
INNER JOIN applications app ON cand.applicant_id = app.applicant_id
INNER JOIN jobs j ON app.job_id = j.job_id
INNER JOIN companies c ON j.company_id = c.company_id
INNER JOIN interviews iv ON app.application_id = iv.application_id
WHERE iv.rating IS NOT NULL
GROUP BY cand.applicant_id, cand.first_name, cand.last_name, j.title, c.name
HAVING AVG(iv.rating) >= 3.5
ORDER BY overall_avg_score DESC;


-- ------------------------------------------------------------------------------
-- QUERY 8: Vacancies with Zero Applications (Recruitment Gaps)
-- Concepts: LEFT JOIN, WHERE IS NULL
-- Description: Detects published jobs that have received zero submissions so recruiters
--              can update descriptions or boost marketing.
-- ------------------------------------------------------------------------------
SELECT 
    j.job_id,
    j.title,
    c.name AS company_name,
    j.department,
    j.job_type,
    j.created_at AS posted_on
FROM jobs j
INNER JOIN companies c ON j.company_id = c.company_id
LEFT JOIN applications app ON j.job_id = app.job_id
WHERE app.application_id IS NULL
  AND j.status = 'Open'
ORDER BY j.created_at ASC;


-- ------------------------------------------------------------------------------
-- QUERY 9: Candidate Multi-Skill Match Density
-- Concepts: INNER JOIN, GROUP BY, Aggregate Functions (COUNT, STRING_AGG)
-- Description: Lists applicants possessing multiple technical skills with concatenated proficiencies.
-- ------------------------------------------------------------------------------
SELECT 
    cand.applicant_id,
    cand.first_name || ' ' || cand.last_name AS applicant_name,
    cand.email,
    COUNT(ask.skill_id) AS total_verified_skills,
    STRING_AGG(s.skill_name || ' (' || ask.proficiency_level || ')', ', ' ORDER BY s.skill_name) AS skill_inventory
FROM applicants cand
INNER JOIN applicant_skills ask ON cand.applicant_id = ask.applicant_id
INNER JOIN skills s ON ask.skill_id = s.skill_id
GROUP BY cand.applicant_id, cand.first_name, cand.last_name, cand.email
HAVING COUNT(ask.skill_id) >= 2
ORDER BY total_verified_skills DESC;


-- ------------------------------------------------------------------------------
-- QUERY 10: Time-to-Interview Operational Velocity
-- Concepts: INNER JOIN, Date/Time Functions (AGE / EXTRACT), Aggregates (MIN, AVG)
-- Description: Measures days elapsed between initial candidate application and
--              their first scheduled interview round.
-- ------------------------------------------------------------------------------
SELECT 
    j.title AS job_title,
    c.name AS company_name,
    COUNT(DISTINCT app.application_id) AS applications_interviewed,
    ROUND(
        AVG(EXTRACT(EPOCH FROM (iv.scheduled_at - app.applied_at)) / 86400.0), 
        1
    ) AS avg_days_to_interview
FROM applications app
INNER JOIN jobs j ON app.job_id = j.job_id
INNER JOIN companies c ON j.company_id = c.company_id
INNER JOIN interviews iv ON app.application_id = iv.application_id
GROUP BY j.job_id, j.title, c.name
ORDER BY avg_days_to_interview ASC;
