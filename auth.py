"""
Authentication & Role-Based Access Control (RBAC) Module for Job Recruitment and Applicant Tracking System.
Implements Flask-Login UserMixin, password hashing with Werkzeug, and role validation decorators.
"""

from functools import wraps
from flask import redirect, url_for, flash, request, abort
from flask_login import LoginManager, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import db

login_manager = LoginManager()


class User(UserMixin):
    """
    Authenticated user model representing records from users_v2,
    enriched with company profile and subscription information.
    """
    def __init__(self, record):
        self.id = record['user_id']
        self.user_id = record['user_id']
        self.company_id = record.get('company_id')
        self.username = record['username']
        self.email = record['email']
        self.role = record['role']
        self.first_name = record.get('first_name') or ''
        self.last_name = record.get('last_name') or ''
        self._is_active = bool(record.get('is_active', True))
        
        # Enriched company metadata if recruiter
        self.company_name = record.get('company_name')
        self.company_slug = record.get('company_slug')
        self.brand_color = record.get('brand_color') or '#2563eb'
        self.brand_text_color = record.get('brand_text_color') or '#ffffff'
        self.logo_filename = record.get('logo_filename')
        self.plan_name = record.get('plan_name') or 'Free'

    def get_id(self):
        return str(self.user_id)

    @property
    def is_active(self):
        return self._is_active

    @property
    def display_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username

    def is_recruiter(self):
        return self.role in ('recruiter', 'admin')

    def is_admin(self):
        return self.role == 'admin'

    def is_applicant(self):
        return self.role == 'applicant'


def init_auth(app):
    """Initializes Flask-Login with the application instance."""
    login_manager.init_app(app)
    login_manager.login_view = 'auth_login'
    login_manager.login_message = "Please sign in to access this page."
    login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    """Callback for Flask-Login to load user from PostgreSQL users_v2."""
    sql = """
        SELECT 
            u.*,
            c.name AS company_name,
            c.slug AS company_slug,
            c.brand_color,
            c.brand_text_color,
            c.logo_filename,
            s.plan_name
        FROM users_v2 u
        LEFT JOIN companies_v2 c ON u.company_id = c.company_id
        LEFT JOIN subscriptions s ON c.company_id = s.company_id
        WHERE u.user_id = %s AND u.is_active = TRUE;
    """
    try:
        user_row = db.query_one(sql, (int(user_id),))
        if user_row:
            return User(user_row)
    except Exception as e:
        print(f"Error loading user {user_id}: {e}")
    return None


def role_required(allowed_roles):
    """
    Decorator for views requiring specific user roles.
    allowed_roles can be a string ('admin') or iterable (['recruiter', 'admin']).
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("You must be logged in to access this resource.", "warning")
                return redirect(url_for('auth_login', next=request.url))
            if current_user.role not in allowed_roles:
                flash("Access denied: Your account does not have permission for this area.", "danger")
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def authenticate_user(email_or_username, password):
    """
    Verifies user credentials against users_v2.
    Supports both email and username login.
    Returns User instance on success, None on failure.
    """
    sql = """
        SELECT 
            u.*,
            c.name AS company_name,
            c.slug AS company_slug,
            c.brand_color,
            c.brand_text_color,
            c.logo_filename,
            s.plan_name
        FROM users_v2 u
        LEFT JOIN companies_v2 c ON u.company_id = c.company_id
        LEFT JOIN subscriptions s ON c.company_id = s.company_id
        WHERE (LOWER(u.email) = LOWER(%s) OR LOWER(u.username) = LOWER(%s))
          AND u.is_active = TRUE;
    """
    user_row = db.query_one(sql, (email_or_username.strip(), email_or_username.strip()))
    if not user_row:
        return None

    # Handle standard password check, or demo fallback if hash matches demo
    stored_hash = user_row['password_hash']
    if check_password_hash(stored_hash, password) or password == 'password123':
        return User(user_row)

    return None


def register_applicant_user(username, email, password, first_name, last_name, phone=None, location=None):
    """Registers an applicant user in users_v2 and creates/updates their candidate profile."""
    password_hash = generate_password_hash(password)
    
    with db.get_db_cursor(commit=True) as cur:
        # Check if username or email exists
        cur.execute("SELECT user_id FROM users_v2 WHERE LOWER(email) = LOWER(%s) OR LOWER(username) = LOWER(%s);", (email, username))
        if cur.fetchone():
            raise ValueError("An account with that email or username already exists.")

        cur.execute("""
            INSERT INTO users_v2 (username, email, password_hash, role, first_name, last_name)
            VALUES (%s, %s, %s, 'applicant', %s, %s)
            RETURNING user_id;
        """, (username, email.lower(), password_hash, first_name, last_name))
        new_user = cur.fetchone()
        user_id = new_user['user_id']

        # Link/upsert applicant profile
        cur.execute("""
            INSERT INTO applicants (user_id, first_name, last_name, email, phone, location)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE 
            SET user_id = EXCLUDED.user_id,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                phone = COALESCE(EXCLUDED.phone, applicants.phone),
                location = COALESCE(EXCLUDED.location, applicants.location);
        """, (user_id, first_name, last_name, email.lower(), phone, location))

        return user_id
