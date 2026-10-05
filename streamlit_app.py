"""
Streamlit Cloud Entrypoint & Bridge for Job Recruitment and Applicant Tracking System.
Allows running the application on Streamlit Cloud without ValueError signal conflicts.
"""
import os
import sys
import threading
import time

try:
    import streamlit as st
    import streamlit.components.v1 as components
except ImportError:
    st = None

from app import app
import db

def run_flask_background():
    """Runs the Flask web server on a background daemon thread."""
    try:
        db.ensure_database_exists()
    except Exception as exc:
        print(f"Database check notice: {exc}")
    # run with use_reloader=False to avoid signal errors
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# Start background thread once
if 'flask_started' not in globals():
    globals()['flask_started'] = True
    flask_thread = threading.Thread(target=run_flask_background, daemon=True)
    flask_thread.start()
    time.sleep(1)

def main():
    if st is None:
        print("Streamlit not installed. Run 'python app.py' to launch Flask.")
        return

    st.set_page_config(
        page_title="Job Recruitment and Applicant Tracking System",
        page_icon="💼",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    st.markdown("""
        <style>
        .block-container { padding: 0.5rem 1rem !important; }
        iframe { border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        </style>
    """, unsafe_allow_html=True)

    # Top Header banner
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### 💼 Job Recruitment and Applicant Tracking System")
        st.caption("Commercial Multi-Tenant B2B ATS Platform (Python Flask + PostgreSQL)")
    with col2:
        st.info("🟢 Flask Server Active")

    # Render Flask App inside responsive iframe
    components.iframe("http://localhost:5000", height=850, scrolling=True)

if __name__ == '__main__':
    main()
