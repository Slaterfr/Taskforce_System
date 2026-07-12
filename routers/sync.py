from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from services import member_service
from utils.auth import staff_required
from utils.roblox_sync import sync_from_roblox

sync_bp = Blueprint('sync', __name__)


@sync_bp.route('/roblox/rank_mappings', methods=['GET', 'POST'])
@staff_required
def manage_rank_mappings():
    """Manage rank mappings between system ranks and Roblox role IDs"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            system_rank = request.form.get('system_rank', '').strip()
            roblox_role_id = request.form.get('roblox_role_id', type=int)
            roblox_role_name = request.form.get('roblox_role_name', '').strip() or None
            
            if not system_rank or not roblox_role_id:
                flash('System rank and Roblox role ID are required', 'error')
                return redirect(url_for('sync.manage_rank_mappings'))
            
            result = member_service.add_or_update_rank_mapping(system_rank, roblox_role_id, roblox_role_name)
            if result['success']:
                flash(result['message'], 'success')
            else:
                flash(result['message'], 'error')
        
        elif action == 'delete':
            mapping_id = request.form.get('mapping_id', type=int)
            if mapping_id:
                if member_service.delete_rank_mapping(mapping_id):
                    flash('Mapping deleted', 'success')
        
        elif action == 'toggle':
            mapping_id = request.form.get('mapping_id', type=int)
            if mapping_id:
                if member_service.toggle_rank_mapping(mapping_id):
                    flash('Mapping updated', 'success')

        elif action == 'auto_import':
            # Fetch all roles from Roblox and upsert them into rank_mapping
            try:
                from utils.roblox_sync import get_roblox_api
                roblox_api = get_roblox_api()
                if not roblox_api:
                    flash('Roblox API not configured — check ROBLOX_GROUP_ID and ROBLOX_COOKIE.', 'error')
                else:
                    roles = roblox_api.get_group_roles()
                    if not roles:
                        flash('No roles returned from Roblox. Is the group ID correct?', 'error')
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
                current_app.logger.error(f'Auto-import error: {e}')
                flash(f'Auto-import failed: {e}', 'error')

        return redirect(url_for('sync.manage_rank_mappings'))
    
    # GET: show all mappings
    mappings = member_service.get_all_rank_mappings()
    
    # Get available roles from Roblox if configured
    roblox_roles = []
    if current_app.config.get('ROBLOX_GROUP_ID'):
        try:
            from utils.roblox_sync import get_roblox_api
            roblox_api = get_roblox_api()
            if roblox_api:
                roblox_roles = roblox_api.get_group_roles()
        except Exception as e:
            current_app.logger.error(f"Error fetching Roblox roles: {e}")
    
    # Pass config values to template
    config_info = {
        'ROBLOX_SYNC_ENABLED': current_app.config.get('ROBLOX_SYNC_ENABLED', False),
        'ROBLOX_SYNC_INTERVAL': current_app.config.get('ROBLOX_SYNC_INTERVAL', 600),
        'ROBLOX_GROUP_ID': current_app.config.get('ROBLOX_GROUP_ID', '')
    }
    
    return render_template('roblox/rank_mappings.html', mappings=mappings, roblox_roles=roblox_roles, config=config_info)


@sync_bp.route('/roblox/sync_now', methods=['POST'])
@staff_required
def sync_now():
    """Manually trigger a sync from Roblox"""
    try:
        result = sync_from_roblox()
        if result['success']:
            flash(result['message'], 'success')
        else:
            flash(f"Sync failed: {result['message']}", 'error')
    except Exception as e:
        flash(f"Sync error: {str(e)}", 'error')
    
    return redirect(request.referrer or url_for('members.dashboard'))
