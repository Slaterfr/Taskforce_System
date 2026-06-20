"""Configuration and settings business logic."""

import os
import os.path as op
from flask import current_app
from api.roblox_api import RobloxAPI

def update_roblox_cookie(cookie):
    """
    Validate and update the Roblox .ROBLOSECURITY cookie.
    Updates both the .env file and the active Flask configuration.
    
    Returns a dict with success, message, and optional user_info.
    """
    cookie = (cookie or '').strip()
    if not cookie:
        return {'success': False, 'message': 'Cookie cannot be empty'}

    user_info = RobloxAPI.validate_cookie(cookie)
    if not user_info:
        return {'success': False, 'message': 'Invalid cookie! Please check and try again.'}

    try:
        # Resolve path to .env file relative to the Taskforce_System directory root
        base_dir = op.dirname(op.dirname(op.abspath(__file__)))
        env_path = op.join(base_dir, '.env')

        # Read current lines
        lines = []
        if op.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
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
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        # Update active app config
        current_app.config['ROBLOX_COOKIE'] = cookie

        return {
            'success': True,
            'message': f"Cookie updated successfully! Connected as: {user_info.get('name')} (ID: {user_info.get('id')})",
            'user_info': user_info
        }
    except Exception as e:
        return {'success': False, 'message': f'Error updating configuration: {e}'}
