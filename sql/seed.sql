-- ==============================================================================
-- University DBMS Project: Job Recruitment and Applicant Tracking System (ATS)
-- File: seed.sql
-- Description: Realistic Sample Dataset for University Evaluation & Testing
-- ==============================================================================

-- 1. SEED USERS
-- Password hashes represented as standard dummy scrypt/argon hashes for testing
INSERT INTO users (user_id, username, email, password_hash, role) VALUES
(1, 'sarah_recruiter', 'sarah.miller@techcorp.com', 'scrypt:32768:8:1$dummyhashrecruiter1', 'recruiter'),
(2, 'alex_talent', 'alex.reyes@fintech.io', 'scrypt:32768:8:1$dummyhashrecruiter2', 'recruiter'),
(3, 'elena_hr', 'elena.rostova@cloudscale.net', 'scrypt:32768:8:1$dummyhashrecruiter3', 'recruiter'),
(4, 'admin_system', 'admin@talentrack.edu', 'scrypt:32768:8:1$dummyhashadmin', 'admin'),
(5, 'candidate_david', 'david.kim@gmail.com', 'scrypt:32768:8:1$dummyhashcand1', 'applicant'),
(6, 'candidate_maya', 'maya.patel@outlook.com', 'scrypt:32768:8:1$dummyhashcand2', 'applicant'),
(7, 'candidate_marcus', 'marcus.vance@yahoo.com', 'scrypt:32768:8:1$dummyhashcand3', 'applicant')
ON CONFLICT (user_id) DO NOTHING;

-- Synchronize users sequence
SELECT setval('users_user_id_seq', (SELECT MAX(user_id) FROM users));


-- 2. SEED COMPANIES
INSERT INTO companies (company_id, name, website, location, industry, description) VALUES
(1, 'Stripe Global', 'https://stripe.com', 'San Francisco, CA', 'Fintech', 'Financial infrastructure and payment platform for online commerce.'),
(2, 'Datadog Systems', 'https://datadoghq.com', 'New York, NY', 'Cloud & Monitoring', 'Observability and security analytics service for cloud applications.'),
(3, 'Snowflake Computing', 'https://snowflake.com', 'Bozeman, MT / Remote', 'Data Warehousing', 'Cloud data storage, data engineering, and analytics architecture.'),
(4, 'Scale AI', 'https://scale.com', 'San Francisco, CA', 'Artificial Intelligence', 'Data-centric AI and machine learning infrastructure.')
ON CONFLICT (company_id) DO NOTHING;

SELECT setval('companies_company_id_seq', (SELECT MAX(company_id) FROM companies));


-- 3. SEED MASTER SKILLS
INSERT INTO skills (skill_id, skill_name, category) VALUES
(1, 'PostgreSQL', 'Database'),
(2, 'Python', 'Programming Languages'),
(3, 'SQL Query Optimization', 'Database'),
(4, 'Flask', 'Web Frameworks'),
(5, 'FastAPI', 'Web Frameworks'),
(6, 'Docker', 'DevOps & Cloud'),
(7, 'Kubernetes', 'DevOps & Cloud'),
(8, 'AWS Cloud Architecture', 'DevOps & Cloud'),
(9, 'Data Modeling & 3NF', 'Database'),
(10, 'Distributed Systems', 'Architecture'),
(11, 'TypeScript / JavaScript', 'Programming Languages'),
(12, 'Go / Golang', 'Programming Languages'),
(13, 'Redis & Caching', 'Database')
ON CONFLICT (skill_id) DO NOTHING;

SELECT setval('skills_skill_id_seq', (SELECT MAX(skill_id) FROM skills));


-- 4. SEED JOBS
INSERT INTO jobs (job_id, company_id, recruiter_id, title, department, location, job_type, salary_min, salary_max, description, requirements, status, created_at) VALUES
(1, 1, 2, 'Senior Backend Engineer (Payments)', 'Engineering', 'San Francisco, CA / Hybrid', 'Full-Time', 165000.00, 215000.00, 
'Build robust, highly scalable payment processing pipelines handling billions of dollars in daily transactions. Collaborate with global teams on latency reduction and zero-downtime ledger consistency.',
'BS/MS in Computer Science, 5+ years experience with Python, Go, or Java, advanced relational database modeling in PostgreSQL, and solid grasp of ACID transactions.', 'Open', CURRENT_TIMESTAMP - INTERVAL '14 days'),

(2, 2, 3, 'Site Reliability & Cloud Infrastructure Engineer', 'DevOps & Cloud', 'New York, NY / Remote', 'Remote', 150000.00, 195000.00,
'Architect resilient multi-region Kubernetes clusters and monitoring pipelines. Automate infrastructure deployment with Terraform and enforce high availability SLAs.',
'Proficiency in Docker, Kubernetes, Linux internals, Prometheus, AWS/GCP, and Python scripting for infrastructure automation.', 'Open', CURRENT_TIMESTAMP - INTERVAL '10 days'),

(3, 3, 1, 'Data Platform Architect', 'Data & AI', 'Bozeman, MT / Hybrid', 'Full-Time', 170000.00, 230000.00,
'Design enterprise-scale analytical pipelines, columnar indexing, and high-throughput ingestion architectures. Work closely with query planner algorithms.',
'Expert understanding of SQL, relational normal forms (3NF/BCNF), query optimization, distributed storage engines, and Python data frameworks.', 'Open', CURRENT_TIMESTAMP - INTERVAL '7 days'),

(4, 4, 1, 'Machine Learning Systems Engineer', 'Data & AI', 'San Francisco, CA', 'Full-Time', 180000.00, 240000.00,
'Scale training and evaluation pipelines for generative foundation models. Optimize GPU cluster resource allocation and data pipelines.',
'Strong fundamentals in Python, PyTorch, CUDA, containerization, and distributed caching with Redis.', 'Open', CURRENT_TIMESTAMP - INTERVAL '5 days'),

(5, 1, 2, 'Junior Database Administrator', 'Engineering', 'Austin, TX', 'Full-Time', 90000.00, 120000.00,
'Assist senior DBAs with backup orchestration, indexing strategy analysis, migration scripts, and monitoring PostgreSQL query performance.',
'B.S. in Computer Science or DBMS specialization, proficiency in SQL, understanding of relational schemas, indexes, and basic Linux administration.', 'Open', CURRENT_TIMESTAMP - INTERVAL '3 days'),

-- Job 6 has zero applications (Demonstrating Query 8: Vacancies with zero applicants)
(6, 2, 3, 'Security Compliance Analyst', 'Security & Compliance', 'Boston, MA / Remote', 'Contract', 95000.00, 135000.00,
'Audit SOC2 Type II compliance controls, review database access logs, and perform security posture assessments across internal systems.',
'3+ years experience with cybersecurity auditing, database user privilege governance, and risk reporting.', 'Open', CURRENT_TIMESTAMP - INTERVAL '2 days')

ON CONFLICT (job_id) DO NOTHING;

SELECT setval('jobs_job_id_seq', (SELECT MAX(job_id) FROM jobs));


-- 5. SEED APPLICANTS
INSERT INTO applicants (applicant_id, user_id, first_name, last_name, email, phone, location, linkedin_url, portfolio_url, created_at) VALUES
(1, 5, 'David', 'Kim', 'david.kim@gmail.com', '+1 (415) 555-0192', 'San Francisco, CA', 'https://linkedin.com/in/davidkim-demo', 'https://github.com/davidkim', CURRENT_TIMESTAMP - INTERVAL '20 days'),
(2, 6, 'Maya', 'Patel', 'maya.patel@outlook.com', '+1 (206) 555-0143', 'Seattle, WA', 'https://linkedin.com/in/mayapatel-demo', 'https://mayapatel.dev', CURRENT_TIMESTAMP - INTERVAL '18 days'),
(3, 7, 'Marcus', 'Vance', 'marcus.vance@yahoo.com', '+1 (512) 555-0178', 'Austin, TX', 'https://linkedin.com/in/marcusvance-demo', NULL, CURRENT_TIMESTAMP - INTERVAL '15 days'),
(4, NULL, 'Chloe', 'Dubois', 'chloe.dubois@proton.me', '+1 (646) 555-0129', 'New York, NY', 'https://linkedin.com/in/chloedubois-demo', 'https://chloedubois.design', CURRENT_TIMESTAMP - INTERVAL '12 days'),
(5, NULL, 'Liam', 'O''Connor', 'liam.oconnor@techmail.io', '+1 (312) 555-0184', 'Chicago, IL', 'https://linkedin.com/in/liamoconnor-demo', NULL, CURRENT_TIMESTAMP - INTERVAL '9 days'),
(6, NULL, 'Sophia', 'Chen', 'sophia.chen@berkeley.edu', '+1 (510) 555-0167', 'Berkeley, CA', 'https://linkedin.com/in/sophiachen-demo', 'https://github.com/sophiachen', CURRENT_TIMESTAMP - INTERVAL '8 days'),
(7, NULL, 'Carlos', 'Mendoza', 'carlos.mendoza@gmail.com', '+1 (305) 555-0155', 'Miami, FL', 'https://linkedin.com/in/carlosmendoza-demo', NULL, CURRENT_TIMESTAMP - INTERVAL '6 days'),
(8, NULL, 'Aisha', 'Al-Mansoor', 'aisha.mansoor@domain.org', '+1 (408) 555-0111', 'San Jose, CA', 'https://linkedin.com/in/aishamansoor-demo', 'https://aishamansoor.ai', CURRENT_TIMESTAMP - INTERVAL '4 days')
ON CONFLICT (applicant_id) DO NOTHING;

SELECT setval('applicants_applicant_id_seq', (SELECT MAX(applicant_id) FROM applicants));


-- 6. SEED APPLICANT SKILLS (M:N Junction Table)
INSERT INTO applicant_skills (applicant_id, skill_id, years_of_experience, proficiency_level) VALUES
-- David Kim (Senior Backend)
(1, 1, 6.0, 'Expert'),       -- PostgreSQL
(1, 2, 7.0, 'Expert'),       -- Python
(1, 3, 5.0, 'Advanced'),     -- SQL Optimization
(1, 6, 4.0, 'Intermediate'), -- Docker
(1, 10, 4.5, 'Advanced'),    -- Distributed Systems

-- Maya Patel (Cloud / DevOps)
(2, 6, 5.0, 'Expert'),       -- Docker
(2, 7, 4.5, 'Expert'),       -- Kubernetes
(2, 8, 5.5, 'Advanced'),     -- AWS
(2, 2, 3.5, 'Intermediate'), -- Python

-- Marcus Vance (Junior DBA)
(3, 1, 2.0, 'Intermediate'), -- PostgreSQL
(3, 3, 1.5, 'Intermediate'), -- SQL Optimization
(3, 9, 2.0, 'Advanced'),     -- Data Modeling

-- Chloe Dubois (Backend & Fullstack)
(4, 2, 4.0, 'Advanced'),     -- Python
(4, 4, 3.5, 'Advanced'),     -- Flask
(4, 11, 4.0, 'Intermediate'),-- TypeScript

-- Liam O'Connor (Data Platform)
(5, 1, 8.0, 'Expert'),       -- PostgreSQL
(5, 3, 8.0, 'Expert'),       -- SQL Optimization
(5, 9, 7.0, 'Expert'),       -- Data Modeling

-- Sophia Chen (ML Systems)
(6, 2, 4.0, 'Advanced'),     -- Python
(6, 5, 3.0, 'Intermediate'), -- FastAPI
(6, 13, 2.5, 'Intermediate'),-- Redis

-- Carlos Mendoza
(7, 2, 3.0, 'Intermediate'),
(7, 6, 2.0, 'Beginner'),

-- Aisha Al-Mansoor
(8, 2, 5.0, 'Expert'),
(8, 10, 4.0, 'Advanced')
ON CONFLICT (applicant_id, skill_id) DO NOTHING;


-- 7. SEED APPLICATIONS
-- Populates diverse stages: Applied, Screening, Interview, Hired, Rejected
INSERT INTO applications (application_id, job_id, applicant_id, status, resume_filename, cover_letter, applied_at) VALUES
-- Hired Candidate (David Kim for Job 1)
(1, 1, 1, 'Hired', 'sample_resume_david_kim.pdf', 
'Excited to apply for the Senior Backend position at Stripe. With 7 years building high-throughput transactional systems in Python and Postgres, I look forward to contributing to payment reliability.', 
CURRENT_TIMESTAMP - INTERVAL '13 days'),

-- Interview Stage (Maya Patel for Job 2)
(2, 2, 2, 'Interview', 'sample_resume_maya_patel.pdf', 
'I have managed large-scale Kubernetes deployments across AWS and Datadog observability suites. Very keen on SRE leadership at Datadog.', 
CURRENT_TIMESTAMP - INTERVAL '9 days'),

-- Screening Stage (Marcus Vance for Job 5)
(3, 5, 3, 'Screening', 'sample_resume_marcus_vance.pdf', 
'Recent computer science graduate with strong honors in Database Systems and PostgreSQL performance tuning.', 
CURRENT_TIMESTAMP - INTERVAL '3 days'),

-- Interview Stage (Liam O''Connor for Job 3)
(4, 3, 5, 'Interview', 'sample_resume_liam_oconnor.pdf', 
'Experienced data architect with deep background in distributed query planning, normal form modeling, and columnar storage.', 
CURRENT_TIMESTAMP - INTERVAL '6 days'),

-- Applied Stage (Sophia Chen for Job 4)
(5, 4, 6, 'Applied', 'sample_resume_sophia_chen.pdf', 
'Specialized in machine learning distributed training systems and Python orchestration.', 
CURRENT_TIMESTAMP - INTERVAL '4 days'),

-- Applied Stage (Chloe Dubois for Job 1)
(6, 1, 4, 'Applied', 'sample_resume_chloe_dubois.pdf', 
'Full stack and backend developer passionate about building reliable APIs and resilient fintech integrations.', 
CURRENT_TIMESTAMP - INTERVAL '10 days'),

-- Rejected Stage (Carlos Mendoza for Job 1)
(7, 1, 7, 'Rejected', 'sample_resume_carlos_mendoza.pdf', 
'Experienced software engineer interested in payment infrastructure.', 
CURRENT_TIMESTAMP - INTERVAL '12 days'),

-- Hired Stage (Aisha Al-Mansoor for Job 4)
(8, 4, 8, 'Hired', 'sample_resume_aisha_mansoor.pdf', 
'5+ years leading high-performance AI infrastructure and distributed model serving.', 
CURRENT_TIMESTAMP - INTERVAL '5 days'),

-- Screening Stage (Chloe Dubois for Job 2)
(9, 2, 4, 'Screening', 'sample_resume_chloe_dubois.pdf', 
'Applying my systems background to cloud observability.', 
CURRENT_TIMESTAMP - INTERVAL '7 days')

ON CONFLICT (application_id) DO NOTHING;

SELECT setval('applications_application_id_seq', (SELECT MAX(application_id) FROM applications));


-- 8. SEED INTERVIEWS
-- Associated with applications in 'Interview' and 'Hired' statuses
INSERT INTO interviews (interview_id, application_id, interviewer_id, interview_type, scheduled_at, duration_minutes, feedback, rating, status) VALUES
-- David Kim (App 1) Completed rounds
(1, 1, 2, 'Phone Screening', CURRENT_TIMESTAMP - INTERVAL '11 days', 30, 'Strong communicator, clear track record in payment gateways.', 5, 'Completed'),
(2, 1, 2, 'Technical Assessment', CURRENT_TIMESTAMP - INTERVAL '9 days', 60, 'Excellent live coding in Python. Designed ACID-compliant transaction locking cleanly in PostgreSQL.', 5, 'Completed'),
(3, 1, 2, 'System Design', CURRENT_TIMESTAMP - INTERVAL '7 days', 60, 'Designed a globally distributed ledger with idempotency keys. Outstanding performance.', 5, 'Completed'),

-- Maya Patel (App 2) Scheduled / Completed
(4, 2, 3, 'Phone Screening', CURRENT_TIMESTAMP - INTERVAL '6 days', 30, 'Solid background in cloud architecture and Terraform.', 4, 'Completed'),
(5, 2, 3, 'Technical Assessment', CURRENT_TIMESTAMP + INTERVAL '2 days', 60, 'Scheduled: Kubernetes failure injection and debugging live cluster scenarios.', NULL, 'Scheduled'),

-- Liam O'Connor (App 4)
(6, 4, 1, 'Technical Assessment', CURRENT_TIMESTAMP - INTERVAL '4 days', 60, 'Deep mastery of B-Trees, GiST, query plan cost model, and partitioning schemes.', 5, 'Completed'),
(7, 4, 1, 'Executive Final', CURRENT_TIMESTAMP + INTERVAL '3 days', 45, 'Scheduled: Final leadership alignment with VP of Data Engineering.', NULL, 'Scheduled'),

-- Aisha Al-Mansoor (App 8)
(8, 8, 1, 'Technical Assessment', CURRENT_TIMESTAMP - INTERVAL '3 days', 60, 'Flawless execution of distributed ML pipeline and GPU memory management.', 5, 'Completed')

ON CONFLICT (interview_id) DO NOTHING;

SELECT setval('interviews_interview_id_seq', (SELECT MAX(interview_id) FROM interviews));
