"""
Automated Resume Parser Module using pypdf and Database Skill Taxonomy.
Extracts contact information (name, email, phone) and automatically identifies
matched technical competencies from the PostgreSQL master skills taxonomy.
"""

import re
import os
from pypdf import PdfReader
import db


def extract_text_from_pdf(file_path):
    """Extracts raw text strings from all pages of a PDF document."""
    text_content = []
    try:
        reader = PdfReader(file_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_content.append(page_text)
    except Exception as e:
        print(f"Error reading PDF {file_path}: {e}")
    return "\n".join(text_content)


def extract_email(text):
    """Extracts candidate email address using RFC pattern matching."""
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    match = re.search(email_pattern, text)
    return match.group(0).lower() if match else None


def extract_phone(text):
    """Extracts candidate phone number supporting standard international & US formats."""
    phone_pattern = r'(\+?\d{1,3}[-.\s]?)?(\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}'
    matches = re.finditer(phone_pattern, text)
    for m in matches:
        raw = m.group(0).strip()
        # Ensure minimum digit count to prevent false positives with dates or numbers
        digits_only = re.sub(r'\D', '', raw)
        if 9 <= len(digits_only) <= 15:
            return raw
    return None


def extract_name(text):
    """
    Extracts candidate name based on header line heuristics,
    filtering out generic document titles.
    """
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    ignore_keywords = {'resume', 'curriculum', 'vitae', 'cv', 'profile', 'contact', 'email', 'phone', 'page', 'senior', 'software', 'engineer', 'developer'}
    
    for line in lines[:8]:
        # Clean special characters
        cleaned = re.sub(r'[^a-zA-Z\s]', '', line).strip()
        words = cleaned.split()
        if 2 <= len(words) <= 3:
            if not any(w.lower() in ignore_keywords for w in words):
                first_name = words[0].capitalize()
                last_name = " ".join([w.capitalize() for w in words[1:]])
                return first_name, last_name

    return None, None


def extract_matched_skills(text):
    """
    Scans the extracted document text against the database's master skills taxonomy.
    Returns matched skills with skill_id and skill_name.
    """
    try:
        all_skills = db.query_all("SELECT skill_id, skill_name FROM skills;")
    except Exception as e:
        print(f"Error fetching skills for parser: {e}")
        all_skills = []

    matched = []
    text_lower = f" {text.lower()} "

    for s in all_skills:
        skill_name = s['skill_name'].strip()
        # Word boundary or special character matching
        pattern = r'(?:\b|[^\w])' + re.escape(skill_name.lower()) + r'(?:\b|[^\w])'
        if re.search(pattern, text_lower):
            matched.append({
                'skill_id': s['skill_id'],
                'skill_name': skill_name
            })

    return matched


def parse_resume(file_path):
    """
    Primary interface: parses uploaded resume document and returns structured dictionary.
    """
    if not os.path.exists(file_path):
        return {'error': 'File not found'}

    # If PDF, extract using pypdf; if text file, read directly
    if file_path.lower().endswith('.pdf'):
        raw_text = extract_text_from_pdf(file_path)
    else:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                raw_text = f.read()
        except Exception:
            raw_text = ""

    first_name, last_name = extract_name(raw_text)
    email = extract_email(raw_text)
    phone = extract_phone(raw_text)
    matched_skills = extract_matched_skills(raw_text)

    return {
        'first_name': first_name or '',
        'last_name': last_name or '',
        'email': email or '',
        'phone': phone or '',
        'matched_skills': matched_skills,
        'raw_text_length': len(raw_text)
    }
