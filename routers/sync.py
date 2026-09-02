import logging
logger = logging.getLogger(__name__)
from config import settings
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from utils.templates import templates, url_for
from utils.flash import flash
from services import member_service
from utils.auth import staff_required
from utils.roblox_sync import sync_from_roblox

router = APIRouter()


@router.api_route('/roblox/rank_mappings', methods=['GET', 'POST'])
@staff_required
async def manage_rank_mappings(request: Request):
    """Manage rank mappings between system ranks and Roblox role IDs"""
    if request.method == 'POST':
        action = (await request.form()).get('action')
        
        if action == 'add':
            system_rank = (await request.form()).get('system_rank', '').strip()
            roblox_role_id = int((await request.form()).get('roblox_role_id')) if (await request.form()).get('roblox_role_id') else None
            roblox_role_name = (await request.form()).get('roblox_role_name', '').strip() or None
            
            if not system_rank or not roblox_role_id:
                flash(request, 'System rank and Roblox role ID are required', 'error')
                return RedirectResponse(url_for(request, 'manage_rank_mappings'), status_code=303)
            
            result = member_service.add_or_update_rank_mapping(system_rank, roblox_role_id, roblox_role_name)
            if result['success']:
                flash(request, result['message'], 'success')
            else:
                flash(request, result['message'], 'error')
        
        elif action == 'delete':
            mapping_id = int((await request.form()).get('mapping_id')) if (await request.form()).get('mapping_id') else None
            if mapping_id:
                if member_service.delete_rank_mapping(mapping_id):
                    flash(request, 'Mapping deleted', 'success')
        
        elif action == 'toggle':
            mapping_id = int((await request.form()).get('mapping_id')) if (await request.form()).get('mapping_id') else None
            if mapping_id:
                if member_service.toggle_rank_mapping(mapping_id):
                    flash(request, 'Mapping updated', 'success')

        elif action == 'auto_import':
            # Fetch all roles from Roblox and upsert them into rank_mapping
            try:
                from utils.roblox_sync import get_roblox_api
                roblox_api = get_roblox_api()
                if not roblox_api:
                    flash(request, 'Roblox API not configured — check ROBLOX_GROUP_ID and ROBLOX_COOKIE.', 'error')
                else:
                    roles = roblox_api.get_group_roles()
                    if not roles:
                        flash(request, 'No roles returned from Roblox. Is the group ID correct?', 'error')
                    else:
                        imported, skipped = 0, 0
                        for role in roles:
                            role_name = role.get('name', '').strip()
                            role_id = role.get('id')
                            if not role_name or not role_id:
                                skipped += 1
                                continue
                            result = member_service.add_or_update_rank_mapping(
                                system_rank=role_name,
                                roblox_role_id=role_id,
                                roblox_role_name=role_name,
                            )
                            if result['success']:
                                imported += 1
                            else:
                                skipped += 1
                        flash(
                            f'Auto-import complete: {imported} role(s) imported/updated'
                            + (f', {skipped} skipped.' if skipped else '.'),
                            'success',
                        )
            except Exception as e:
                logger.error(f'Auto-import error: {e}')
                flash(request, f'Auto-import failed: {e}', 'error')

        return RedirectResponse(url_for(request, 'manage_rank_mappings'), status_code=303)
    
    # GET: show all mappings
    mappings = member_service.get_all_rank_mappings()
    
    # Get available roles from Roblox if configured
    roblox_roles = []
    if getattr(settings, 'ROBLOX_GROUP_ID', None):
        try:
            from utils.roblox_sync import get_roblox_api
            roblox_api = get_roblox_api()
            if roblox_api:
                roblox_roles = roblox_api.get_group_roles()
        except Exception as e:
            logger.error(f"Error fetching Roblox roles: {e}")
    
    # Pass config values to template
    config_info = {
        'ROBLOX_SYNC_ENABLED': getattr(settings, 'ROBLOX_SYNC_ENABLED', False),
        'ROBLOX_SYNC_INTERVAL': getattr(settings, 'ROBLOX_SYNC_INTERVAL', 600),
        'ROBLOX_GROUP_ID': getattr(settings, 'ROBLOX_GROUP_ID', '')
    }
    
    return templates.TemplateResponse('roblox/rank_mappings.html', {"request": request, "mappings": mappings, "roblox_roles": roblox_roles, "config": config_info})


@router.api_route('/roblox/sync_now', methods=['POST'])
@staff_required
async def sync_now(request: Request):
    """Manually trigger a sync from Roblox"""
    try:
        result = sync_from_roblox()
        if result['success']:
            flash(request, result['message'], 'success')
        else:
            flash(request, f"Sync failed: {result['message']}", 'error')
    except Exception as e:
        flash(request, f"Sync error: {str(e)}", 'error')
    
    return RedirectResponse(request.referrer or url_for(request, 'dashboard'))
