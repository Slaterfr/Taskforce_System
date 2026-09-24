from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from utils.templates import templates, url_for
from utils.flash import flash
from database.ac_constants import ACTIVITY_TYPES
from services import ac_service, member_service

from sqlmodel import Session, select
from database.engine import engine
from database.tenant_models import Group
from database.models import Member
from utils.tenant_context import get_tenant_id, set_tenant_context, extract_tenant_context

router = APIRouter()


@router.get('/', name='landing_page')
async def landing_page(request: Request):
    """Futuristic landing page introducing Nexus with Roblox OAuth login."""
    ctx = getattr(request.state, "tenant_context", None)
    if not ctx:
        ctx = extract_tenant_context(request)

    has_user_token = bool(request.cookies.get("tf_user_token"))
    has_tenant_token = bool(request.cookies.get("tf_tenant_token"))
    active_group_id = (ctx or {}).get("group_id") or request.session.get("tenant_id")
    roblox_username = (ctx or {}).get("roblox_username") or request.session.get("roblox_username")

    # Quick metrics for display
    try:
        with Session(engine) as session:
            total_sectors = len(session.exec(select(Group).where(Group.is_active == True)).all())
            total_operatives = len(session.exec(select(Member).where(Member.is_active == True), execution_options={"skip_tenant_filter": True}).all())
    except Exception:
        total_sectors = 2
        total_operatives = 902

    return templates.TemplateResponse(
        'landing.html',
        {
            "request": request,
            "has_user_token": has_user_token,
            "has_tenant_token": has_tenant_token,
            "active_group_id": active_group_id,
            "roblox_username": roblox_username,
            "total_sectors": total_sectors,
            "total_operatives": total_operatives,
        }
    )


@router.get('/roster', name='public_roster')
async def public_roster(request: Request):
    """Roster view scoped strictly to the authenticated sector/group."""
    ctx = getattr(request.state, "tenant_context", None)
    if not ctx:
        ctx = extract_tenant_context(request)

    tenant_id = request.session.get("tenant_id") or (ctx or {}).get("group_id")

    # If not logged into any group/sector:
    if not tenant_id:
        if request.cookies.get("tf_user_token"):
            flash(request, "Please select an active sector first to view its roster.", "info")
            return RedirectResponse(url="/portal/select-group", status_code=303)
        flash(request, "Authentication required: Please log in with Roblox to access sector rosters.", "info")
        return RedirectResponse(url="/auth/roblox/login", status_code=303)

    set_tenant_context(tenant_id)
    search = request.query_params.get('search', '')
    members = member_service.search_members(search, tenant_id=tenant_id)
    return templates.TemplateResponse(
        'public_roster.html',
        {
            "request": request,
            "members": members,
            "search": search,
            "tenant_id": tenant_id
        }
    )


@router.get('/public-roster')
async def public_roster_redirect(request: Request):
    return RedirectResponse(url="/roster", status_code=301)


@router.get('/public/member/{member_id}')
async def public_member(request: Request, member_id):
    """Public read-only member view (limited data)"""
    ctx = getattr(request.state, "tenant_context", None)
    if not ctx:
        ctx = extract_tenant_context(request)
    tenant_id = request.session.get("tenant_id") or (ctx or {}).get("group_id")
    if tenant_id:
        set_tenant_context(tenant_id)

    data = member_service.get_public_member_data(member_id)
    if not data:
        raise HTTPException(status_code=404, detail='Not Found')
    return templates.TemplateResponse(
        'public_member.html',
        {
            "request": request,
            "member": data['member'],
            "recent_activities": data['recent_activities']
        }
    )


@router.get('/ac_progress')
async def public_ac_progress(request: Request):
    current_period = ac_service.get_active_period()
    act_types = ac_service.get_activity_types_map()
    if not current_period:
        return templates.TemplateResponse('public_ac_progress.html', {"request": request,
                             "current_period":None,
                             "member_progress":[],
                             "activity_types":act_types})

    member_progress = ac_service.build_member_progress(current_period)

    return templates.TemplateResponse('public_ac_progress.html', {"request": request,
                         "current_period":current_period,
                         "member_progress":member_progress,
                         "activity_types":act_types})


@router.get('/privacy', name='privacy_policy')
async def privacy_policy(request: Request):
    """Public Privacy Policy page for Roblox OAuth compliance."""
    return templates.TemplateResponse('privacy.html', {"request": request})


@router.get('/terms', name='terms_of_service')
async def terms_of_service(request: Request):
    """Public Terms of Service page for Roblox OAuth compliance."""
    return templates.TemplateResponse('terms.html', {"request": request})

