from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from utils.templates import templates, url_for
from utils.flash import flash
from utils.auth import staff_required, check_password, check_hct_password
from services import config_service

router = APIRouter()


@router.api_route('/staff/login', methods=['GET', 'POST'])
async def staff_login(request: Request):
    """Password login retired in favor of Roblox OAuth."""
    flash(request, "Password login has been retired. Please authenticate with Roblox.", "info")
    return RedirectResponse(url="/auth/roblox/login", status_code=303)


@router.api_route('/hct/login', methods=['GET', 'POST'])
async def hct_login(request: Request):
    """Password login retired in favor of Roblox OAuth."""
    flash(request, "Password login has been retired. Please authenticate with Roblox.", "info")
    return RedirectResponse(url="/auth/roblox/login", status_code=303)


@router.get('/staff/logout')
async def staff_logout(request: Request):
    return RedirectResponse(url="/auth/logout", status_code=303)


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
