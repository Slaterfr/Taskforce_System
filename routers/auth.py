from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session
from utils.auth import staff_required, check_password, check_hct_password
from services import config_service

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/staff/login', methods=['GET', 'POST'])
def staff_login():
    # Support form POST and JSON POST for API/AJAX callers
    if request.method == 'POST':
        password = ''
        if request.is_json:
            try:
                data = request.get_json(silent=True) or {}
                password = data.get('password', '')
            except Exception:
                password = ''
        else:
            password = request.form.get('password', '')

        if check_password(password):
            session['is_staff'] = True
            session['staff_username'] = 'staff'
            # do not make session permanent — avoid persistent login cookies
            session.permanent = False

            # If AJAX/JSON request, return JSON success
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                next_url = session.pop('next_url', None)

                flash('Staff login successful', 'success')
                next_url = session.pop('next_url', None)
                return redirect(next_url or url_for('members.dashboard'))

        # Invalid password
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
            return jsonify({'error': 'authentication_failed'}), 401
        flash('Invalid password', 'error')

    return render_template('staff_login.html')


@auth_bp.route('/hct/login', methods=['GET', 'POST'])
def hct_login():
    # Support form POST and JSON POST for API/AJAX callers
    if request.method == 'POST':
        password = ''
        if request.is_json:
            try:
                data = request.get_json(silent=True) or {}
                password = data.get('password', '')
            except Exception:
                password = ''
        else:
            password = request.form.get('password', '')

        if check_hct_password(password):
            session['is_hct'] = True
            session['hct_username'] = 'HCT'  # Generic username for now
            # do not make session permanent — avoid persistent login cookies
            session.permanent = False

            # If AJAX/JSON request, return JSON success
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                next_url = session.pop('next_url', None)
                flash('HCT login successful', 'success')
                return jsonify({'success': True, 'redirect': next_url or url_for('ac.ac_dashboard')})

            flash('HCT login successful', 'success')
            next_url = session.pop('next_url', None)
            return redirect(next_url or url_for('ac.ac_dashboard'))

        # Invalid password
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
            flash('Invalid HCT password', 'error')
            return render_template('hct_login.html'), 401
            

    return render_template('hct_login.html')



@auth_bp.route('/staff/logout')
def staff_logout():
    session.clear()
    flash('Logged out', 'info')
    return redirect(url_for('public.public_roster'))


@auth_bp.route('/staff/update_cookie', methods=['GET', 'POST'])
@staff_required
def update_cookie():
    if request.method == 'POST':
        cookie = request.form.get('cookie', '').strip()
        result = config_service.update_roblox_cookie(cookie)
        if result['success']:
            flash(result['message'], 'success')
            return redirect(url_for('members.dashboard'))
        else:
            flash(result['message'], 'error')
            return redirect(url_for('auth.update_cookie'))
            
    return render_template('update_cookie.html')
