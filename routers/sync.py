from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from database.models import db, RankMapping
from utils.auth import staff_required
from utils.roblox_sync import sync_from_roblox
from datetime import datetime

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
            
            # Check if mapping already exists
            existing = RankMapping.query.filter_by(system_rank=system_rank).first()
            if existing:
                existing.roblox_role_id = roblox_role_id
                existing.roblox_role_name = roblox_role_name
                existing.is_active = True
                existing.last_updated = datetime.utcnow()
                flash(f'Updated mapping for {system_rank}', 'success')
            else:
                mapping = RankMapping(
                    system_rank=system_rank,
                    roblox_role_id=roblox_role_id,
                    roblox_role_name=roblox_role_name
                )
                db.session.add(mapping)
                flash(f'Added mapping for {system_rank}', 'success')
            
            db.session.commit()
        
        elif action == 'delete':
            mapping_id = request.form.get('mapping_id', type=int)
            if mapping_id:
                mapping = RankMapping.query.get(mapping_id)
                if mapping:
                    db.session.delete(mapping)
                    db.session.commit()
                    flash('Mapping deleted', 'success')
        
        elif action == 'toggle':
            mapping_id = request.form.get('mapping_id', type=int)
            if mapping_id:
                mapping = RankMapping.query.get(mapping_id)
                if mapping:
                    mapping.is_active = not mapping.is_active
                    mapping.last_updated = datetime.utcnow()
                    db.session.commit()
                    flash('Mapping updated', 'success')
        
        return redirect(url_for('sync.manage_rank_mappings'))
    
    # GET: show all mappings
    mappings = RankMapping.query.order_by(RankMapping.system_rank).all()
    
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
