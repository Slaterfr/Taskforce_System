"""
Simple authentication system for Taskforce Management
Staff password required for editing, viewing is public
"""

from functools import wraps
from flask import session, redirect, url_for, flash, current_app, request, jsonify
import secrets

def check_password(password):
    """Securely check if provided password matches configured staff password"""
    if not password:
        return False
    return secrets.compare_digest(
        str(password),
        str(current_app.config.get('STAFF_PASSWORD', ''))
    )

def is_staff():
    """Check if current session is authenticated as staff"""
    return bool(session.get('is_staff', False))

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