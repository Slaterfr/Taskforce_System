from config import settings
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from utils.templates import templates, url_for
from utils.flash import flash
from services import member_service
from utils.auth import staff_required

router = APIRouter()


@router.get('/dashboard')
@staff_required
async def dashboard(request: Request):
    dashboard_data = member_service.get_dashboard_data()
    return templates.TemplateResponse('dashboard.html', {"request": request,
                           "member_count":dashboard_data['member_count'],
                           "recent_activities":dashboard_data['recent_activities']})


@router.get('/members')
@staff_required
async def members(request: Request):
    search = request.query_params.get('search', '')
    members_list = member_service.search_members(search)
    return templates.TemplateResponse('members.html', {"request": request, "members": members_list, "search": search})


@router.get('/member/{member_id}')
@staff_required
async def member_detail(request: Request, member_id):
    detail = member_service.get_member_profile_details(member_id)
    if not detail:
        
        raise HTTPException(status_code=404, detail='Not Found')
    return templates.TemplateResponse('member_detail.html', {"request": request,
                           "member":detail['member'],
                           "activities":detail['activities'],
                           "promotions":detail['promotions']})


@router.api_route('/add_member', methods=['GET', 'POST'])
@staff_required
async def add_member(request: Request):
    if request.method == 'POST':
        result = member_service.create_member(
            (await request.form()).get('discord_username', ''),
            roblox_username=(await request.form()).get('roblox_username'),
            current_rank=(await request.form()).get('current_rank', 'Aspirant'),
        )

        if not result['success']:
            if result.get('error') == 'member_exists':
                flash(request, 'Member with this Discord username already exists!', 'error')
            else:
                flash(request, result.get('message', 'Failed to add member'), 'error')
            return RedirectResponse(url_for(request, 'add_member'), status_code=303)

        member = result['member']
        roblox_sync = result.get('roblox_sync', {})
        if not roblox_sync.get('success') and member.roblox_username:
            flash(request, f"Member added, but Roblox sync failed: {roblox_sync.get('message')}", 'warning')

        flash(request, 'Member added', 'success')
        return RedirectResponse(url_for(request, 'member_detail', member_id=member.id), status_code=303)

    return templates.TemplateResponse('add_member.html', {"request": request})


@router.api_route('/member/{member_id}/edit', methods=['GET', 'POST'])
@staff_required
async def edit_member(request: Request, member_id):
    member = member_service.get_member(member_id, active_only=False)
    if not member:
        
        raise HTTPException(status_code=404, detail='Not Found')
    available_ranks = member_service.get_available_ranks()

    if request.method == 'POST':
        result = member_service.update_member_profile(
            member_id,
            discord_username=(await request.form()).get('discord_username', member.discord_username),
            roblox_username=(await request.form()).get('roblox_username', member.roblox_username),
            current_rank=(await request.form()).get('current_rank', member.current_rank),
        )

        if not result['success']:
            flash(request, result.get('message', 'Failed to update member'), 'error')
            return RedirectResponse(url_for(request, 'edit_member', member_id=member_id), status_code=303)

        roblox_sync = result.get('roblox_sync', {})
        if result.get('rank_changed') and not roblox_sync.get('success'):
            if roblox_sync.get('message') == 'Cannot sync to Roblox (no Roblox ID)':
                flash(request, 'Member updated, but cannot sync to Roblox (no Roblox ID)', 'warning')
            elif getattr(settings, 'ROBLOX_SYNC_ENABLED', None):
                flash(request, f"Member updated, but Roblox sync failed: {roblox_sync.get('message')}", 'warning')

        flash(request, 'Member updated', 'success')
        return RedirectResponse(url_for(request, 'member_detail', member_id=member_id), status_code=303)

    return templates.TemplateResponse('edit_member.html', {"request": request, "member": member, "available_ranks": available_ranks})


@router.api_route('/member/{member_id}/delete', methods=['POST'])
@staff_required
async def delete_member(request: Request, member_id):
    result = member_service.deactivate_member(member_id)
    if not result['success']:
        flash(request, result.get('message', 'Member not found'), 'error')
        return RedirectResponse(url_for(request, 'members'), status_code=303)

    roblox_sync = result.get('roblox_sync', {})
    if not roblox_sync.get('success') and getattr(settings, 'ROBLOX_SYNC_ENABLED', None):
        flash(request, f"Member removed from system, but Roblox sync failed: {roblox_sync.get('message')}", 'warning')

    flash(request, 'Member removed', 'success')
    return RedirectResponse(url_for(request, 'members'), status_code=303)


@router.api_route('/promote_member', methods=['GET', 'POST'])
@staff_required
async def promote_member(request: Request):
    """Promote a member and record a PromotionLog"""
    available_ranks = member_service.get_available_ranks()

    if request.method == 'POST':
        member_id = int((await request.form()).get('member_id')) if (await request.form()).get('member_id') else None
        new_rank = (await request.form()).get('new_rank', '').strip()
        reason = (await request.form()).get('reason', '').strip()
        promoted_by = (await request.form()).get('promoted_by', '').strip() or request.session.get('staff_username', 'Staff')

        result = member_service.promote_member(
            member_id,
            new_rank,
            reason=reason,
            promoted_by=promoted_by,
        )

        if not result['success']:
            flash(request, result.get('message', 'Promotion failed'), 'error')
            return RedirectResponse(url_for(request, 'promote_member'), status_code=303)

        member = result['member']
        roblox_sync = result.get('roblox_sync', {})
        if not result.get('unchanged') and not roblox_sync.get('success'):
            if roblox_sync.get('message') == 'Cannot sync to Roblox (no Roblox ID)':
                flash(request, 'Promotion saved, but cannot sync to Roblox (no Roblox ID)', 'warning')
            elif getattr(settings, 'ROBLOX_SYNC_ENABLED', None):
                flash(request, f"Promotion saved, but Roblox sync failed: {roblox_sync.get('message')}", 'warning')

        flash(
            f'{member.discord_username} promoted from {result["old_rank"]} to {result["new_rank"]}',
            'success',
        )
        return RedirectResponse(url_for(request, 'member_detail', member_id=member.id), status_code=303)

    members_list = member_service.get_all_active_members()
    return templates.TemplateResponse('promote_member.html', {"request": request, "members": members_list, "available_ranks": available_ranks})


@router.get('/stats')
@staff_required
async def stats(request: Request):
    """Member Statistics Dashboard"""
    from utils.stats_logger import get_stats_history
    import json

    data = get_stats_history(days=30)
    total_members = data['totals'][-1] if data['totals'] else 0

    latest_ranks = data['latest_ranks']
    most_populated_rank = "N/A"
    max_count = 0
    if latest_ranks:
        most_populated_rank = max(latest_ranks, key=latest_ranks.get)
        max_count = latest_ranks[most_populated_rank]

    return templates.TemplateResponse('stats.html', {"request": request,
                          "dates":json.dumps(data['dates']),
                          "totals":json.dumps(data['totals']),
                          "rank_labels":json.dumps(list(latest_ranks.keys())),
                          "rank_values":json.dumps(list(latest_ranks.values())),
                          "total_members":total_members,
                          "most_populated_rank":most_populated_rank,
                          "most_populated_count":max_count})
