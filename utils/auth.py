"""
Simple authentication system for Taskforce Management
Staff password required for editing, viewing is public
HCT password required for AC management
"""

from functools import wraps
from flask import session, redirect, url_for, flash, current_app, request, jsonify
import secrets
import os

def check_password(password):
    """Securely check if provided password matches configured staff password"""
    if not password:
        return False
    return secrets.compare_digest(
        str(password),
        str(current_app.config.get('STAFF_PASSWORD', ''))
    )

def check_hct_password(password):
    """Securely check if provided password matches configured HCT password"""
    if not password:
        return False
    return secrets.compare_digest(
        str(password),
        str(os.getenv('HCT_PASSWORD', ''))
    )

def is_staff():
    """Check if current session is authenticated as staff"""
    return bool(session.get('is_staff', False))

def is_hct():
    """Check if current session is authenticated as HCT"""
    return bool(session.get('is_hct', False))

def staff_required(f):
    """Decorator to require staff authentication for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Prefer session-based staff flag (set by `staff_login`) — fall back to request.user if present
        if not is_staff() and not (getattr(request, 'user', None) and getattr(request.user, 'is_staff', False)):
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json
            if is_ajax:
                return jsonify({'error': 'authentication_required'}), 401
            # Save the requested path so staff_login can redirect back after successful login
            session['next_url'] = request.path
            flash('You must be staff to access that page', 'warning')
            return redirect(url_for('staff_login'))
        return f(*args, **kwargs)
    return decorated_function

def hct_required(f):
    """Decorator to require HCT authentication for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is HCT authenticated
        if not is_hct():
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json
            if is_ajax:
                return redirect(url_for('auth.hct_login'))
            # Save the requested path so hct_login can redirect back
            session['next_url'] = request.path
            flash('You must be High Command Team (HCT) to access that page', 'warning')
            return redirect(url_for('auth.hct_login'))
        return f(*args, **kwargs)
    return decorated_function