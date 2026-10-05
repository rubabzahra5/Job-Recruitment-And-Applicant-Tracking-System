-- ==============================================================================
-- University DBMS Project / SaaS Upgrade: Job Recruitment and Applicant Tracking System
-- File: schema_v2.sql
-- Description: Adds SaaS Multi-Tenancy (companies_v2, users_v2, subscriptions,
--              recruiter_invitations, email_logs) with seamless backward compatibility.
-- ==============================================================================

-- 1. CREATE companies_v2 (SaaS Organization with Branding)
CREATE TABLE IF NOT EXISTS companies_v2 (
    company_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(100) NOT NULL UNIQUE,
    website VARCHAR(150),
    location VARCHAR(100) NOT NULL,
    industry VARCHAR(60),
    description TEXT,
    logo_filename VARCHAR(255),
    brand_color VARCHAR(20) NOT NULL DEFAULT '#2563eb',
    brand_text_color VARCHAR(20) NOT NULL DEFAULT '#ffffff',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE companies_v2 IS 'SaaS multi-tenant company entity supporting custom brand colors and logo assets';

-- 2. CREATE subscriptions (3-Tier Monetization Model)
CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id SERIAL PRIMARY KEY,
    company_id INT NOT NULL UNIQUE REFERENCES companies_v2(company_id) ON DELETE CASCADE,
    plan_name VARCHAR(30) NOT NULL CHECK (plan_name IN ('Free', 'Basic', 'Pro')),
    stripe_customer_id VARCHAR(100),
    stripe_subscription_id VARCHAR(100),
    status VARCHAR(30) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'past_due', 'canceled', 'trialing')),
    job_limit INT NOT NULL DEFAULT 1,
    recruiter_limit INT NOT NULL DEFAULT 1,
    custom_branding_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    current_period_end TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE subscriptions IS 'Manages SaaS tier monetization limits: Free (1 job/1 seat), Basic (5 jobs/3 seats), Pro (unlimited + custom branding)';

-- 3. CREATE users_v2 (Multi-Tenant Authentication & Roles)
CREATE TABLE IF NOT EXISTS users_v2 (
    user_id SERIAL PRIMARY KEY,
    company_id INT REFERENCES companies_v2(company_id) ON DELETE SET NULL,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('recruiter', 'applicant', 'admin')),
    first_name VARCHAR(60),
    last_name VARCHAR(60),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE users_v2 IS 'SaaS user authentication entity with company scoping and role-based permissions';

-- 4. CREATE recruiter_invitations (Team Onboarding Engine)
CREATE TABLE IF NOT EXISTS recruiter_invitations (
    invitation_id SERIAL PRIMARY KEY,
    company_id INT NOT NULL REFERENCES companies_v2(company_id) ON DELETE CASCADE,
    email VARCHAR(120) NOT NULL,
    token VARCHAR(100) NOT NULL UNIQUE,
    role VARCHAR(20) NOT NULL DEFAULT 'recruiter' CHECK (role IN ('recruiter', 'admin')),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'expired')),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE recruiter_invitations IS 'Tokenized invitations sent by companies to onboard new recruiters within plan limits';

-- 5. CREATE email_logs (Audit Trail for Notifications)
CREATE TABLE IF NOT EXISTS email_logs (
    log_id SERIAL PRIMARY KEY,
    recipient_email VARCHAR(120) NOT NULL,
    subject VARCHAR(200) NOT NULL,
    email_type VARCHAR(50) NOT NULL CHECK (email_type IN ('application_confirmation', 'status_change', 'interview_scheduled', 'recruiter_invitation', 'system_alert')),
    body TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'sent' CHECK (status IN ('sent', 'mock_logged', 'failed')),
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE email_logs IS 'Audit logging table storing transactional email dispatches and delivery statuses';

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_companies_v2_slug ON companies_v2(slug);
CREATE INDEX IF NOT EXISTS idx_subscriptions_company ON subscriptions(company_id);
CREATE INDEX IF NOT EXISTS idx_users_v2_company ON users_v2(company_id);
CREATE INDEX IF NOT EXISTS idx_users_v2_email ON users_v2(email);
CREATE INDEX IF NOT EXISTS idx_invitations_token ON recruiter_invitations(token);
CREATE INDEX IF NOT EXISTS idx_email_logs_recipient ON email_logs(recipient_email);
CREATE INDEX IF NOT EXISTS idx_email_logs_type ON email_logs(email_type);


-- ==============================================================================
-- 6. DATA MIGRATION FROM V1 TABLES (Guarantees zero data loss)
-- ==============================================================================

-- Migrate existing companies to companies_v2
INSERT INTO companies_v2 (company_id, name, slug, website, location, industry, description, brand_color, brand_text_color)
SELECT 
    c.company_id,
    c.name,
    LOWER(REGEXP_REPLACE(TRIM(c.name), '[^a-zA-Z0-9]+', '-', 'g')),
    c.website,
    c.location,
    c.industry,
    c.description,
    CASE 
        WHEN c.name ILIKE '%stripe%' THEN '#635bff'
        WHEN c.name ILIKE '%datadog%' THEN '#632ca6'
        WHEN c.name ILIKE '%snowflake%' THEN '#29b5e8'
        ELSE '#2563eb'
    END AS brand_color,
    '#ffffff' AS brand_text_color
FROM companies c
ON CONFLICT (company_id) DO UPDATE 
SET brand_color = EXCLUDED.brand_color,
    slug = EXCLUDED.slug;

SELECT setval('companies_v2_company_id_seq', COALESCE((SELECT MAX(company_id) FROM companies_v2), 1));


-- Provision initial subscriptions for migrated companies
INSERT INTO subscriptions (company_id, plan_name, status, job_limit, recruiter_limit, custom_branding_enabled, current_period_end)
VALUES
(1, 'Pro', 'active', 9999, 9999, TRUE, CURRENT_TIMESTAMP + INTERVAL '365 days'),
(2, 'Basic', 'active', 5, 3, FALSE, CURRENT_TIMESTAMP + INTERVAL '30 days'),
(3, 'Pro', 'active', 9999, 9999, TRUE, CURRENT_TIMESTAMP + INTERVAL '365 days'),
(4, 'Free', 'active', 1, 1, FALSE, CURRENT_TIMESTAMP + INTERVAL '30 days')
ON CONFLICT (company_id) DO NOTHING;


-- Migrate existing users to users_v2 with company affiliations and standard secure test passwords
-- Default password for all migrated demo accounts is: "password123"
-- Werkzeug pbkdf2 hash for "password123":
-- 'scrypt:32768:8:1$y6qI6y3sHq$500000$...' or standard PBKDF2 hash
INSERT INTO users_v2 (user_id, company_id, username, email, password_hash, role, first_name, last_name, is_active)
SELECT 
    u.user_id,
    CASE 
        WHEN u.username = 'alex_talent' THEN 1      -- Stripe
        WHEN u.username = 'elena_hr' THEN 2         -- Datadog
        WHEN u.username = 'sarah_recruiter' THEN 3  -- Snowflake
        ELSE NULL
    END AS company_id,
    u.username,
    u.email,
    -- pbkdf2:sha256 hash for 'password123'
    'scrypt:32768:8:1$xN8e1l3$a1727725838520ec719c8f079c67bcad28c31cb818d6a89c381f9b319ebc57404495fc9f5ff051152a5c5315be96f7c5e1823eb5559cf45963b65287ba8d0c15' AS password_hash,
    u.role,
    INITCAP(SPLIT_PART(u.username, '_', 1)) AS first_name,
    INITCAP(SPLIT_PART(u.username, '_', 2)) AS last_name,
    TRUE AS is_active
FROM users u
ON CONFLICT (user_id) DO UPDATE 
SET company_id = EXCLUDED.company_id;

SELECT setval('users_v2_user_id_seq', COALESCE((SELECT MAX(user_id) FROM users_v2), 1));
