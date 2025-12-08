from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session, current_app
from utils.auth import staff_required, check_password
import os.path as op

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


@auth_bp.route('/staff/logout')
def staff_logout():
    session.clear()
    flash('Logged out', 'info')
    return redirect(url_for('public.public_roster'))


@auth_bp.route('/staff/update_cookie', methods=['GET', 'POST'])
@staff_required
def update_cookie():
    from api.roblox_api import RobloxAPI
    
    if request.method == 'POST':
        cookie = request.form.get('cookie', '').strip()
        if not cookie:
            flash('Cookie cannot be empty', 'error')
            return redirect(url_for('auth.update_cookie'))
            
        # Validate cookie
        user_info = RobloxAPI.validate_cookie(cookie)
        if not user_info:
            flash('Invalid cookie! Please check and try again.', 'error')
            return redirect(url_for('auth.update_cookie'))
            
        # Update .env file
        try:
            env_path = op.join(op.dirname(op.dirname(op.abspath(__file__))), '.env')
            
            # Read current lines
            with open(env_path, 'r') as f:
                lines = f.readlines()
                
            # Update or append ROBLOX_COOKIE
            cookie_found = False
            new_lines = []
            for line in lines:
                if line.startswith('ROBLOX_COOKIE='):
                    new_lines.append(f'ROBLOX_COOKIE={cookie}\n')
                    cookie_found = True
                else:
                    new_lines.append(line)
            
            if not cookie_found:
                new_lines.append(f'\nROBLOX_COOKIE={cookie}\n')
                
            # Write back
            with open(env_path, 'w') as f:
                f.writelines(new_lines)
                
            # Update current app config
            current_app.config['ROBLOX_COOKIE'] = cookie
            
            flash(f"Cookie updated successfully! Connected as: {user_info.get('name')} (ID: {user_info.get('id')})", 'success')
            return redirect(url_for('members.dashboard'))
            
        except Exception as e:
            flash(f'Error updating .env file: {e}', 'error')
            
    return render_template('update_cookie.html')
