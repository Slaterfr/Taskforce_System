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
    """Legacy route: Redirect to Sector Settings where bot cookies are managed per sector."""
    flash(request, "Bot cookies are now configured dynamically per sector in Sector Settings.", "info")
    return RedirectResponse(url="/group/settings", status_code=303)
