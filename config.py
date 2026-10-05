import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

BASE_DIR = str(Path(__file__).resolve().parent)

class Config:
    """Application configuration for Flask & PostgreSQL ATS SaaS system."""
    BASE_DIR = BASE_DIR
    SECRET_KEY = os.environ.get('SECRET_KEY', 'ats-university-dbms-secret-key-2026')
    
    # PostgreSQL Database Connection Parameters
    _db_url = os.environ.get('DATABASE_URL')
    if _db_url:
        import urllib.parse as _up
        if _db_url.startswith("postgres://"):
            _db_url = _db_url.replace("postgres://", "postgresql://", 1)
        _parsed = _up.urlparse(_db_url)
        DB_HOST = _parsed.hostname or 'localhost'
        DB_PORT = _parsed.port or 5432
        DB_NAME = _parsed.path.lstrip('/') or 'ats_db'
        DB_USER = _parsed.username or 'postgres'
        DB_PASSWORD = _parsed.password or ''
    else:
        DB_HOST = os.environ.get('DB_HOST', 'localhost')
        DB_PORT = int(os.environ.get('DB_PORT', 5432))
        DB_NAME = os.environ.get('DB_NAME', 'ats_db')
        DB_USER = os.environ.get('DB_USER', 'postgres')
        DB_PASSWORD = os.environ.get('DB_PASSWORD', 'adeela@875')
    
    # File Upload Settings (Resume and Logo storage)
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'resumes')
    LOGO_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'logos')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}
    ALLOWED_LOGO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'svg', 'webp'}

    # Flask-Mail Settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', None)
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', None)
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'notifications@ats-recruitment.com')
    # If True, suppresses actual socket send and falls back smoothly to email_logs
    MAIL_SUPPRESS_SEND = os.environ.get('MAIL_SUPPRESS_SEND', 'false').lower() in ['true', 'on', '1']

    # Stripe Payment Settings
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', 'pk_test_51MockATSPublishableKey')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_51MockATSSecretKey')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', 'whsec_mock_ats')

    # SaaS Subscription Plan Specifications
    SUBSCRIPTION_PLANS = {
        'Free': {
            'name': 'Free',
            'price': 0,
            'job_limit': 1,
            'recruiter_limit': 1,
            'custom_branding': False,
            'description': 'Ideal for early-stage startups and single-job recruitment.'
        },
        'Basic': {
            'name': 'Basic',
            'price': 49,
            'job_limit': 5,
            'recruiter_limit': 3,
            'custom_branding': False,
            'description': 'Designed for growing teams hiring across multiple departments.'
        },
        'Pro': {
            'name': 'Pro',
            'price': 149,
            'job_limit': 9999,
            'recruiter_limit': 9999,
            'custom_branding': True,
            'description': 'Full white-label SaaS suite with unlimited postings and custom branded career portal.'
        }
    }
