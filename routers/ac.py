from database.engine import db_session
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from utils.templates import templates, url_for
from utils.flash import flash
from sqlmodel import select
from database.models import Member
from database.ac_constants import ACTIVITY_TYPES, get_member_quota
from database.ac_models import (
    ACPeriod, ActivityEntry, InactivityNotice, ACExemption,
    MonthlyActivityEntry,
)
from services import ac_service
from utils.auth import hct_required
from utils.tenant_context import get_tenant_id
from utils.ac_reports import send_discord_webhook
from utils.excel_reports import generate_ac_workbook_bytes, merge_into_uploaded_workbook_bytes
from datetime import datetime, timedelta

router = APIRouter()


@router.get('/')
@hct_required
async def ac_dashboard(request: Request):
    current_period = ac_service.get_active_period()
    if not current_period:
        return templates.TemplateResponse('ac/ac_setup.html', {"request": request})

    activity_stats = ac_service.get_activity_stats(current_period)
    member_progress = ac_service.build_member_progress(current_period)

    all_activities = db_session().exec(select(ActivityEntry).filter_by(ac_period_id=current_period.id)).all()
    title_winners = ac_service.calculate_title_rewards(all_activities, current_period)

    return templates.TemplateResponse('ac/ac_dashboard.html', {"request": request,
                         "current_period":current_period,
                         "member_progress":member_progress,
                         "activity_types":ac_service.get_activity_types_map(),
                         "activity_stats":activity_stats,
                         "title_winners":title_winners})


@router.api_route('/create_period', methods=['GET', 'POST'])
@hct_required
async def create_ac_period(request: Request):
    if request.method == 'POST':
        period_name = (await request.form()).get('period_name', '').strip()
        start_date = datetime.strptime((await request.form()).get('start_date'), '%Y-%m-%d')
        end_date = datetime.strptime((await request.form()).get('end_date'), '%Y-%m-%d') if (await request.form()).get('end_date') else (start_date + timedelta(weeks=2) - timedelta(days=1))
        tenant_id = request.session.get("tenant_id") or get_tenant_id() or 1
        ac_service.create_period(period_name, start_date, end_date, tenant_id=tenant_id)
        flash(request, 'AC period created', 'success')
        return RedirectResponse(url_for(request, 'ac_dashboard'), status_code=303)
    return templates.TemplateResponse('ac/create_period.html', {"request": request})


@router.api_route('/edit_period', methods=['GET', 'POST'])
@hct_required
async def edit_ac_period(request: Request):
    current_period = ac_service.get_active_period()
    if not current_period:
        flash(request, 'No active AC period', 'error')
        return RedirectResponse(url_for(request, 'ac_dashboard'), status_code=303)
    
    if request.method == 'POST':
        period_name = (await request.form()).get('period_name', '').strip()
        if period_name:
            ac_service.update_period_name(current_period.id, period_name)
            flash(request, 'Period name updated', 'success')
            return RedirectResponse(url_for(request, 'ac_dashboard'), status_code=303)
        else:
            flash(request, 'Period name cannot be empty', 'error')
    
    return templates.TemplateResponse('ac/edit_period.html', {"request": request, "period": current_period})


@router.api_route('/finalize_period', methods=['POST'])
@hct_required
async def finalize_period(request: Request):
    """
    Finalize the current AC period:
    1. Capture all member statistics for the period
    2. Mark period as finalized
    3. Redirect to title rewards page
    """
    current_period = ac_service.get_active_period()
    if not current_period:
        flash(request, 'No active AC period to finalize', 'error')
        return RedirectResponse(url_for(request, 'ac_dashboard'), status_code=303)


@router.api_route('/clear_all_activities', methods=['POST'])
@hct_required
async def clear_all_activities(request: Request):
    """Clear all activities for all members in the current period (MonthlyActivityEntry preserved)"""
    current_period = ac_service.get_active_period()
    if not current_period:
        flash(request, 'No active AC period', 'error')
        return RedirectResponse(url_for(request, 'ac_dashboard'), status_code=303)
    
    deleted_count = ac_service.clear_all_activities(current_period.id)
    
    flash(request, f'Cleared {deleted_count} activity entries for all members. Title tracking data preserved.', 'success')
    return RedirectResponse(url_for(request, 'ac_dashboard'), status_code=303)


@router.api_route('/clear_monthly_entries', methods=['POST'])
@hct_required
async def clear_monthly_entries(request: Request):
    """Delete all monthly activity entries for this tenant so they do not accumulate indefinitely."""
    tenant_id = request.session.get("tenant_id") or get_tenant_id() or 1
    deleted_count = ac_service.clear_all_monthly_entries(tenant_id=tenant_id)
    
    flash(request, f'Successfully deleted {deleted_count} accumulated monthly entries. Monthly title standings have been reset.', 'success')
    referer = request.headers.get("referer") or url_for(request, 'title_rewards')
    return RedirectResponse(referer, status_code=303)


@router.api_route('/clear_titles', methods=['POST'])
@hct_required
async def clear_titles(request: Request):
    """Clear all title tracking data - manual action to reset title history"""
    tenant_id = request.session.get("tenant_id") or get_tenant_id() or 1
    deleted_count = ac_service.clear_all_monthly_entries(tenant_id=tenant_id)
    
    flash(request, f'Cleared {deleted_count} title tracking entries. Monthly activity history reset.', 'success')
    referer = request.headers.get("referer") or url_for(request, 'title_rewards')
    return RedirectResponse(referer, status_code=303)


@router.get('/title_rewards')
@hct_required
async def title_rewards(request: Request):
    """Display title rewards for the current AC period"""
    current_period = ac_service.get_active_period()
    if not current_period:
        flash(request, 'No active AC period', 'error')
        return RedirectResponse(url_for(request, 'ac_dashboard'), status_code=303)
    
    # Get all activities for the current period
    all_activities = ac_service.get_period_activities(current_period.id)
    
    # Calculate title rewards purely from database
    titles = ac_service.calculate_title_rewards(all_activities, current_period)
    
    return templates.TemplateResponse('ac/title_rewards.html', {
        "request": request,
        "current_period": current_period,
        "titles": titles,
    })


@router.api_route('/send_title_webhook', methods=['POST'])
@hct_required
async def send_title_webhook(request: Request):
    """Send title rewards message to Discord webhook"""
    webhook_url = (await request.form()).get('webhook_url', '').strip()
    message = (await request.form()).get('message', '').strip()
    
    if not webhook_url or not message:
        flash(request, 'Webhook URL and message are required', 'error')
        return RedirectResponse(url_for(request, 'title_rewards'), status_code=303)
    
    current_period = ac_service.get_active_period()
    period_name = current_period.period_name if current_period else 'Current Period'
    
    success = send_discord_webhook(webhook_url, message, f"Title Rewards - {period_name}")
    
    if success:
        flash(request, 'Title rewards sent to Discord successfully!', 'success')
    else:
        flash(request, 'Failed to send to Discord. Please check your webhook URL.', 'error')
    
    return RedirectResponse(url_for(request, 'title_rewards'), status_code=303)


@router.api_route('/log_activity', methods=['GET', 'POST'])
@hct_required
async def log_ac_activity(request: Request):
    current_period = ac_service.get_active_period()
    if not current_period:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JSONResponse({'success': False, 'message': 'no_active_period'}, status_code=400)
        flash(request, 'No active AC period. Please create one first.', 'error')
        return RedirectResponse(url_for(request, 'ac_dashboard'), status_code=303)

    if request.method == 'POST':
        data = (await request.json()) or (await request.form())
        activity_date = datetime.strptime(data.get('activity_date'), '%Y-%m-%d')

        result = ac_service.log_activity(
            data.get('member_id'),
            data.get('activity_type'),
            activity_date=activity_date,
            description=data.get('description'),
            logged_by=data.get('logged_by') or 'HC Team',
            quantity=data.get('quantity', 1),
            period=current_period,
            validate_activity_type=False,
        )

        if not result['success']:
            if result.get('error') == 'limited_activity_exists':
                flash(request, 'Limited activity already logged for this period', 'error')
            return RedirectResponse(url_for(request, 'log_ac_activity'), status_code=303)

        quantity = result['count']
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or ("application/json" in request.headers.get("content-type", "")):
            return JSONResponse(content={
                'success': True,
                'activity_ids': result['activity_ids'],
                'count': quantity,
            }, status_code=200)

        activity_type = data.get('activity_type')
        flash(
            f'Successfully logged {quantity} {activity_type} activit{"ies" if quantity > 1 else "y"}',
            'success',
        )
        return RedirectResponse(url_for(request, 'ac_dashboard'), status_code=303)

    members_with_quota = ac_service.get_members_with_quota()
    return templates.TemplateResponse('ac/log_activity.html', {"request": request,
                           "members":members_with_quota,
                           "activity_types":ac_service.get_activity_types_map(),
                           "current_period":current_period})


@router.api_route('/quick_log', methods=['GET'])
@hct_required
async def quick_log(request: Request):
    current_period = ac_service.get_active_period()
    if not current_period:
        flash(request, 'No active AC period. Please create one first.', 'error')
        return RedirectResponse(url_for(request, 'ac_dashboard'), status_code=303)

    log_data = ac_service.get_quick_log_data(current_period.id)

    return templates.TemplateResponse('ac/ac_quick_log.html', {"request": request,
                         "members":log_data['members'],
                         "activity_types":ac_service.get_activity_types_map(),
                         "current_period":current_period,
                         "today":datetime.utcnow().strftime('%Y-%m-%d'),
                         "member_activities":log_data['member_activities'],
                         "member_activity_counts":log_data['member_activity_counts'],
                         "member_ia_status":log_data['member_ia_status'],
                         "member_exempt_status":log_data['member_exempt_status']})


@router.api_route('/quick_log_activity', methods=['POST'])
@hct_required
async def quick_log_activity(request: Request):
    """
    Accept JSON {member_id, activity_type, activity_date, logged_by, quantity}
    Returns JSON {success, message, points, count} or error.
    """
    data = (await request.json()) or {}
    member_id = data.get('member_id')
    activity_type = data.get('activity_type')
    if not member_id or not activity_type:
        return JSONResponse({'success': False, 'message': 'member_id and activity_type required'}, status_code=400)

    activity_date = None
    if data.get('activity_date'):
        try:
            activity_date = datetime.strptime(data.get('activity_date'), '%Y-%m-%d')
        except Exception:
            activity_date = datetime.utcnow()

    result = ac_service.log_activity(
        member_id,
        activity_type,
        activity_date=activity_date,
        description=data.get('description'),
        logged_by=data.get('logged_by', 'HC Team'),
        quantity=data.get('quantity', 1),
        mark_limited=True,
        validate_activity_type=False,
    )

    if not result['success']:
        message = result.get('message', 'Failed to log activity')
        if result.get('error') == 'no_active_period':
            return JSONResponse({'success': False, 'message': 'No active AC period'}, status_code=400)
        return JSONResponse({'success': False, 'message': message}, status_code=400)

    return JSONResponse(content={
        'success': True,
        'points': result['points'],
        'count': result['count'],
        'activity_ids': result['activity_ids'],
    })


@router.api_route('/quick_log_ia', methods=['POST'])
@hct_required
async def quick_log_ia(request: Request):
    """
    Toggle IA status for a member in the current period.
    Accept JSON {member_id, reason, approved_by}
    Returns JSON {success, message, is_ia}
    """
    data = (await request.json()) or {}
    member_id = data.get('member_id')
    if not member_id:
        return JSONResponse({'success': False, 'message': 'member_id required'}, status_code=400)

    result = ac_service.toggle_ia_status(
        member_id,
        reason=data.get('reason', 'Quick log IA'),
        approved_by=data.get('approved_by', request.session.get('staff_username', 'HC Team')),
    )

    if not result['success']:
        return JSONResponse({'success': False, 'message': result.get('message')}, status_code=400)

    return JSONResponse(content={
        'success': True,
        'is_ia': result['is_ia'],
        'message': result['message'],
    })


@router.api_route('/quick_log_exempt', methods=['POST'])
@hct_required
async def quick_log_exempt(request: Request):
    """
    Toggle Exempt status for a member in the current period.
    Accept JSON {member_id, reason, approved_by}
    Returns JSON {success, message, is_exempt}
    """
    data = (await request.json()) or {}
    member_id = data.get('member_id')
    if not member_id:
        return JSONResponse({'success': False, 'message': 'member_id required'}, status_code=400)

    result = ac_service.toggle_exempt_status(
        member_id,
        reason=data.get('reason', 'Quick log exemption'),
        approved_by=data.get('approved_by', request.session.get('staff_username', 'HC Team')),
    )

    if not result['success']:
        return JSONResponse({'success': False, 'message': result.get('message')}, status_code=400)

    return JSONResponse(content={
        'success': True,
        'is_exempt': result['is_exempt'],
        'message': result['message'],
    })


# Export AC to Excel (GET: new workbook; POST: merge uploaded workbook)
@router.api_route('/export_excel', methods=['GET', 'POST'])
@hct_required
async def export_ac_excel(request: Request):
    period_id = (int(request.query_params.get('period_id')) if request.query_params.get('period_id') else None)
    if request.method == 'POST' and 'workbook' in request.files:
        uploaded = request.files['workbook']
        if uploaded.filename == '':
            flash(request, 'No workbook uploaded', 'error')
            return RedirectResponse(url_for(request, 'ac_dashboard'), status_code=303)
        merged_io, filename = merge_into_uploaded_workbook_bytes(uploaded.stream, period_id=period_id)
        return StreamingResponse(merged_io, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': f'attachment; filename={filename}'})
    out_io, filename = generate_ac_workbook_bytes(period_id=period_id)
    return StreamingResponse(out_io, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': f'attachment; filename={filename}'})


# Replace ac_member_detail route with aggregation + detailed list (keeps delete buttons for staff)
@router.get('/member/{member_id}')
@hct_required
async def ac_member_detail(request: Request, member_id):
    current_period = ac_service.get_active_period()
    if not current_period:
        flash(request, 'No active AC period.', 'error')
        return RedirectResponse(url_for(request, 'ac_dashboard'), status_code=303)

    detail = ac_service.get_member_ac_detail(member_id, current_period.id)
    if not detail:
        
        raise HTTPException(status_code=404, detail='Not Found')

    return templates.TemplateResponse(
        'ac/member_detail.html', {"request": request,
        "member":detail['member'],
        "current_period":current_period,
        "activities":detail['activities'],  # full list for detailed view
        "aggregated_activities":detail['aggregated_activities'],  # summaries for compact view
        "quota":detail['quota'],
        "total_points":detail['total_points']
    })


# Ensure delete/clear endpoints exist (idempotent if already present)
@router.api_route('/activity/{activity_id}/delete', methods=['POST'])
@hct_required
async def delete_ac_activity(request: Request, activity_id):
    try:
        # Use service deletion
        result = ac_service.delete_activity_entry(activity_id)
        if not result['success']:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JSONResponse({'success': False, 'message': result.get('message')}, status_code=404)
            flash(request, result.get('message'), 'error')
            return RedirectResponse(url_for(request, 'quick_log'), status_code=303)
        
        # Return JSON for AJAX requests, else redirect
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JSONResponse({'success': True, 'message': 'Activity deleted'})
        
        flash(request, 'Activity entry deleted.', 'success')
        member_id = result['member'].id if result.get('member') else None
        if member_id:
            return RedirectResponse(url_for(request, 'ac_member_detail', member_id=member_id), status_code=303)
        return RedirectResponse(url_for(request, 'ac_dashboard'), status_code=303)
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JSONResponse({'success': False, 'message': str(e)}, status_code=500)
        flash(request, f'Error deleting activity: {e}', 'error')
        return RedirectResponse(url_for(request, 'quick_log'), status_code=303)


@router.api_route('/member/{member_id}/clear_activities', methods=['POST'])
@hct_required
async def clear_member_activities(request: Request, member_id):
    period_id = int((await request.form()).get('period_id')) if (await request.form()).get('period_id') else None
    if not period_id:
        active = ac_service.get_active_period()
        period_id = active.id if active else None

    deleted_count = ac_service.clear_member_activities(member_id, period_id)
    flash(request, f'Deleted {deleted_count} activity entries for member.', 'success')
    return RedirectResponse(url_for(request, 'ac_member_detail', member_id=member_id), status_code=303)


# ============================================================================
# HCT CONFIGURATION: ACTIVITIES & RANK QUOTAS
# ============================================================================

@router.get('/config', name='ac_config')
@hct_required
async def ac_config(request: Request):
    """Configuration management panel for activities, rank quotas, and titles."""
    tenant_id = request.session.get("tenant_id") or get_tenant_id() or 1
    activity_types = ac_service.get_all_activity_types(tenant_id)
    rank_quotas = ac_service.get_all_rank_quotas(tenant_id)
    titles = ac_service.get_all_titles(tenant_id)
    return templates.TemplateResponse('ac/ac_config.html', {
        "request": request,
        "activity_types": activity_types,
        "rank_quotas": rank_quotas,
        "titles": titles,
    })


@router.post('/config/activity/create', name='create_activity_type')
@hct_required
async def create_activity_type_route(request: Request):
    form = await request.form()
    name = form.get('name', '').strip()
    points = float(form.get('points', 1.0))
    is_limited = form.get('is_limited') == 'on'
    description = form.get('description', '').strip()

    tenant_id = request.session.get("tenant_id") or get_tenant_id() or 1
    result = ac_service.create_activity_type(
        name=name,
        points=points,
        is_limited=is_limited,
        description=description,
        tenant_id=tenant_id,
    )
    if result['success']:
        flash(request, f'Activity "{name}" created successfully ({points} pts).', 'success')
    else:
        flash(request, result.get('error', 'Failed to create activity type.'), 'error')

    return RedirectResponse(url_for(request, 'ac_config'), status_code=303)


@router.post('/config/activity/{activity_id}/edit', name='edit_activity_type')
@hct_required
async def edit_activity_type_route(request: Request, activity_id: int):
    form = await request.form()
    name = form.get('name', '').strip()
    points = float(form.get('points', 1.0))
    is_limited = form.get('is_limited') == 'on'
    description = form.get('description', '').strip()
    is_active = form.get('is_active') == 'on'

    result = ac_service.update_activity_type(
        activity_type_id=activity_id,
        name=name,
        points=points,
        is_limited=is_limited,
        description=description,
        is_active=is_active,
    )
    if result['success']:
        flash(request, f'Activity "{name}" updated successfully.', 'success')
    else:
        flash(request, result.get('error', 'Failed to update activity type.'), 'error')

    return RedirectResponse(url_for(request, 'ac_config'), status_code=303)


@router.post('/config/activity/{activity_id}/delete', name='delete_activity_type')
@hct_required
async def delete_activity_type_route(request: Request, activity_id: int):
    result = ac_service.delete_activity_type(activity_id)
    if result['success']:
        flash(request, 'Activity type deleted successfully.', 'success')
    else:
        flash(request, result.get('error', 'Failed to delete activity type.'), 'error')

    return RedirectResponse(url_for(request, 'ac_config'), status_code=303)


@router.post('/config/quota/create', name='create_rank_quota')
@hct_required
async def create_rank_quota_route(request: Request):
    form = await request.form()
    rank_name = form.get('rank_name', '').strip()
    required_points = float(form.get('required_points', 0.0))

    tenant_id = request.session.get("tenant_id") or get_tenant_id() or 1
    result = ac_service.create_rank_quota(
        rank_name=rank_name,
        required_points=required_points,
        tenant_id=tenant_id,
    )
    if result['success']:
        flash(request, f'Quota for "{rank_name}" set to {required_points} points.', 'success')
    else:
        flash(request, result.get('error', 'Failed to create rank quota.'), 'error')

    return RedirectResponse(url_for(request, 'ac_config'), status_code=303)


@router.post('/config/quota/{quota_id}/edit', name='edit_rank_quota')
@hct_required
async def edit_rank_quota_route(request: Request, quota_id: int):
    form = await request.form()
    rank_name = form.get('rank_name', '').strip()
    required_points = float(form.get('required_points', 0.0))

    result = ac_service.update_rank_quota(
        quota_id=quota_id,
        rank_name=rank_name,
        required_points=required_points,
    )
    if result['success']:
        flash(request, f'Quota for "{rank_name}" updated to {required_points} points.', 'success')
    else:
        flash(request, result.get('error', 'Failed to update rank quota.'), 'error')

    return RedirectResponse(url_for(request, 'ac_config'), status_code=303)


@router.post('/config/quota/{quota_id}/delete', name='delete_rank_quota')
@hct_required
async def delete_rank_quota_route(request: Request, quota_id: int):
    result = ac_service.delete_rank_quota(quota_id)
    if result['success']:
        flash(request, 'Rank quota requirement deleted.', 'success')
    else:
        flash(request, result.get('error', 'Failed to delete rank quota.'), 'error')

    return RedirectResponse(url_for(request, 'ac_config'), status_code=303)


# ============================================================================
# TITLE REWARDS MANAGEMENT
# ============================================================================

@router.post('/config/title/create', name='create_title')
@hct_required
async def create_title_route(request: Request):
    tenant_id = request.session.get("tenant_id") or get_tenant_id() or 1
    form = await request.form()
    name = form.get('name', '').strip()
    activity_required = form.get('activity_required', '').strip()
    quantity_required = form.get('quantity_required', 5)
    description = form.get('description', '').strip()
    period_type = form.get('period_type', 'monthly').strip()

    result = ac_service.create_title(
        name=name,
        activity_required=activity_required,
        quantity_required=quantity_required,
        description=description,
        period_type=period_type,
        tenant_id=tenant_id,
    )
    if result['success']:
        flash(request, f'Title "{name}" configured successfully.', 'success')
    else:
        flash(request, result.get('error', 'Failed to create title.'), 'error')

    return RedirectResponse(url_for(request, 'ac_config'), status_code=303)


@router.post('/config/title/{title_id}/edit', name='edit_title')
@hct_required
async def edit_title_route(request: Request, title_id: int):
    form = await request.form()
    name = form.get('name', '').strip()
    activity_required = form.get('activity_required', '').strip()
    quantity_required = form.get('quantity_required', 5)
    description = form.get('description', '').strip()
    period_type = form.get('period_type', 'monthly').strip()
    is_active = form.get('is_active') == 'on'

    result = ac_service.update_title(
        title_id=title_id,
        name=name,
        activity_required=activity_required,
        quantity_required=quantity_required,
        description=description,
        period_type=period_type,
        is_active=is_active,
    )
    if result['success']:
        flash(request, f'Title "{name}" updated successfully.', 'success')
    else:
        flash(request, result.get('error', 'Failed to update title.'), 'error')

    return RedirectResponse(url_for(request, 'ac_config'), status_code=303)


@router.post('/config/title/{title_id}/delete', name='delete_title')
@hct_required
async def delete_title_route(request: Request, title_id: int):
    result = ac_service.delete_title(title_id)
    if result['success']:
        flash(request, 'Title accolade deleted.', 'success')
    else:
        flash(request, result.get('error', 'Failed to delete title.'), 'error')

    return RedirectResponse(url_for(request, 'ac_config'), status_code=303)


