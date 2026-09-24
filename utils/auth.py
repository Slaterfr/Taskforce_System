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
    """Deprecated: Password authentication has been sunset in favor of Roblox OAuth."""
    return False

def check_hct_password(password):
    """Deprecated: Password authentication has been sunset in favor of Roblox OAuth."""
    return False

def is_staff(request: Request = None):
    """Check if current session is authenticated as staff in the active sector."""
    if not request: return False
    if bool(request.session.get('is_staff', False)):
        return True
    ctx = getattr(request.state, "tenant_context", None)
    if not ctx:
        from utils.tenant_context import extract_tenant_context
        ctx = extract_tenant_context(request)
    if ctx:
        perms = ctx.get("permissions", [])
        role = ctx.get("system_role", "")
        if "manage_members" in perms or role in ["staff", "hct", "admin"]:
            return True
    return False

def is_hct(request: Request = None):
    """Check if current session is authenticated as HCT in the active sector."""
    if not request: return False
    if bool(request.session.get('is_hct', False)):
        return True
    ctx = getattr(request.state, "tenant_context", None)
    if not ctx:
        from utils.tenant_context import extract_tenant_context
        ctx = extract_tenant_context(request)
    if ctx:
        perms = ctx.get("permissions", [])
        role = ctx.get("system_role", "")
        if "edit_config" in perms or role in ["hct", "admin"]:
            return True
    return False

def staff_required(f):
    """Decorator to require staff clearance via Roblox OAuth in the active sector."""
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
                if request.cookies.get("tf_user_token"):
                    flash(request, 'Staff clearance required in this sector.', 'warning')
                    return RedirectResponse(url='/portal/select-group', status_code=303)
                flash(request, 'Staff clearance required. Please log in with Roblox.', 'warning')
            return RedirectResponse(url='/auth/roblox/login', status_code=303)
            
        if inspect.iscoroutinefunction(f):
            return await f(*args, **kwargs)
        else:
            return f(*args, **kwargs)
            
    return decorated_function

def hct_required(f):
    """Decorator to require HCT clearance via Roblox OAuth in the active sector."""
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
                if request.cookies.get("tf_user_token"):
                    flash(request, 'High Command (HCT) clearance required in this sector.', 'warning')
                    return RedirectResponse(url='/portal/select-group', status_code=303)
                flash(request, 'High Command (HCT) clearance required. Please log in with Roblox.', 'warning')
            return RedirectResponse(url='/auth/roblox/login', status_code=303)
            
        if inspect.iscoroutinefunction(f):
            return await f(*args, **kwargs)
        else:
            return f(*args, **kwargs)
            
    return decorated_function