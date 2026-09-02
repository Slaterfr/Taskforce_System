"""
Simple authentication system for Taskforce Management
Staff password required for editing, viewing is public
HCT password required for AC management
"""

from functools import wraps
import secrets
import os
from fastapi import Request
from fastapi.responses import RedirectResponse, JSONResponse
from config import settings
from utils.flash import flash
import inspect

def check_password(password):
    """Securely check if provided password matches configured staff password"""
    if not password:
        return False
    return secrets.compare_digest(
        str(password),
        "task2025"
    )

def check_hct_password(password):
    """Securely check if provided password matches configured HCT password"""
    if not password:
        return False
    return secrets.compare_digest(
        str(password),
        "vivaElGonk216"
    )

def is_staff(request: Request = None):
    """Check if current session is authenticated as staff"""
    if not request: return False
    return bool(request.session.get('is_staff', False))

def is_hct(request: Request = None):
    """Check if current session is authenticated as HCT"""
    if not request: return False
    return bool(request.session.get('is_hct', False))

def staff_required(f):
    """Decorator to require staff authentication for a route"""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        request = kwargs.get('request')
        if not request:
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
        
        if not request or not is_staff(request):
            if request:
                is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')
                if is_ajax:
                    return JSONResponse({'error': 'authentication_required'}, status_code=401)
                
                request.session['next_url'] = request.url.path
                flash(request, 'You must be staff to access that page', 'warning')
            return RedirectResponse(url='/staff/login', status_code=303)
            
        if inspect.iscoroutinefunction(f):
            return await f(*args, **kwargs)
        else:
            return f(*args, **kwargs)
            
    return decorated_function

def hct_required(f):
    """Decorator to require HCT authentication for a route"""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        request = kwargs.get('request')
        if not request:
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
                    
        if not request or not is_hct(request):
            if request:
                is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')
                if is_ajax:
                    return JSONResponse({'error': 'authentication_required'}, status_code=401)
                    
                request.session['next_url'] = request.url.path
                flash(request, 'You must be High Command Team (HCT) to access that page', 'warning')
            return RedirectResponse(url='/hct/login', status_code=303)
            
        if inspect.iscoroutinefunction(f):
            return await f(*args, **kwargs)
        else:
            return f(*args, **kwargs)
            
    return decorated_function