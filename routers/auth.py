from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from utils.templates import templates, url_for
from utils.flash import flash
from utils.auth import staff_required, check_password, check_hct_password
from services import config_service

router = APIRouter()


@router.api_route('/staff/login', methods=['GET', 'POST'])
async def staff_login(request: Request):
    # Support form POST and JSON POST for API/AJAX callers
    if request.method == 'POST':
        password = ''
        if ("application/json" in request.headers.get("content-type", "")):
            try:
                data = (await request.json()) or {}
                password = data.get('password', '')
            except Exception:
                password = ''
        else:
            password = (await request.form()).get('password', '')

        if check_password(password):
            request.session['is_staff'] = True
            request.session['staff_username'] = 'staff'
            # do not make session permanent — avoid persistent login cookies
            

            # If AJAX/JSON request, return JSON success
            is_ajax = ("application/json" in request.headers.get("content-type", "")) or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')
            next_url = request.session.pop('next_url', None)
            
            if is_ajax:
                return JSONResponse({'success': True, 'redirect': next_url or '/dashboard'})
                
            flash(request, 'Staff login successful', 'success')
            return RedirectResponse(next_url or '/dashboard', status_code=303)

        # Invalid password
        if ("application/json" in request.headers.get("content-type", "")) or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):
            return JSONResponse({'error': 'authentication_failed'}, status_code=401)
        flash(request, 'Invalid password', 'error')

    return templates.TemplateResponse('staff_login.html', {"request": request})


@router.api_route('/hct/login', methods=['GET', 'POST'])
async def hct_login(request: Request):
    # Support form POST and JSON POST for API/AJAX callers
    if request.method == 'POST':
        password = ''
        if ("application/json" in request.headers.get("content-type", "")):
            try:
                data = (await request.json()) or {}
                password = data.get('password', '')
            except Exception:
                password = ''
        else:
            password = (await request.form()).get('password', '')

        if check_hct_password(password):
            request.session['is_hct'] = True
            request.session['hct_username'] = 'HCT'  # Generic username for now
            # do not make session permanent — avoid persistent login cookies
            

            # If AJAX/JSON request, return JSON success
            if ("application/json" in request.headers.get("content-type", "")) or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                next_url = request.session.pop('next_url', None)
                flash(request, 'HCT login successful', 'success')
                return JSONResponse({'success': True, 'redirect': next_url or '/ac/'})

            flash(request, 'HCT login successful', 'success')
            next_url = request.session.pop('next_url', None)
            return RedirectResponse(next_url or '/ac/', status_code=303)

        # Invalid password
        if ("application/json" in request.headers.get("content-type", "")) or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):
            flash(request, 'Invalid HCT password', 'error')
            return templates.TemplateResponse('hct_login.html', {"request": request}, status_code=401)
            

    return templates.TemplateResponse('hct_login.html', {"request": request})



@router.get('/staff/logout')
async def staff_logout(request: Request):
    request.session.clear()
    flash(request, 'Logged out', 'info')
    return RedirectResponse(url_for(request, 'public_roster'), status_code=303)


@router.api_route('/staff/update_cookie', methods=['GET', 'POST'])
@staff_required
async def update_cookie(request: Request):
    if request.method == 'POST':
        cookie = (await request.form()).get('cookie', '').strip()
        result = config_service.update_roblox_cookie(cookie)
        if result['success']:
            flash(request, result['message'], 'success')
            return RedirectResponse(url_for(request, 'dashboard'), status_code=303)
        else:
            flash(request, result['message'], 'error')
            return RedirectResponse(url_for(request, 'update_cookie'), status_code=303)
            
    return templates.TemplateResponse('update_cookie.html', {"request": request})
