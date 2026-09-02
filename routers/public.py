from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from utils.templates import templates, url_for
from utils.flash import flash
from database.ac_constants import ACTIVITY_TYPES
from services import ac_service, member_service

router = APIRouter()


@router.get('/')
async def public_roster(request: Request):
    search = request.query_params.get('search', '')
    members = member_service.search_members(search)
    return templates.TemplateResponse('public_roster.html', {"request": request, "members": members, "search": search})


@router.get('/public/member/{member_id}')
async def public_member(request: Request, member_id):
    """Public read-only member view (limited data)"""
    data = member_service.get_public_member_data(member_id)
    if not data:
        
        raise HTTPException(status_code=404, detail='Not Found')
    return templates.TemplateResponse('public_member.html', {"request": request,
                           "member":data['member'],
                           "recent_activities":data['recent_activities']})


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
