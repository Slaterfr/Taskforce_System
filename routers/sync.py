import logging
from datetime import datetime
from config import settings
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session, select

from utils.templates import templates, url_for
from utils.flash import flash
from services import member_service
from services.roblox_oauth_service import DEFAULT_ROLE_PERMISSIONS
from utils.auth import staff_required
from utils.roblox_sync import sync_from_roblox, get_roblox_api
from utils.tenant_context import get_tenant_id, set_tenant_context
from database.engine import db_session, engine
from database.models import RankMapping
from database.tenant_models import Group, GroupCookie, GroupPermissionRule
from api.roblox_api import RobloxAPI

logger = logging.getLogger(__name__)

router = APIRouter()


@router.api_route('/roblox/rank_mappings', methods=['GET', 'POST'])
@staff_required
async def manage_rank_mappings(request: Request):
    """Manage rank mappings, clearance tier rules, and dedicated bot cookies per group."""
    tenant_id = request.session.get("tenant_id") or get_tenant_id() or 1
    set_tenant_context(tenant_id)

    if request.method == 'GET':
        return RedirectResponse(url_for(request, 'group_settings'), status_code=303)

    with Session(engine) as session:
        current_group = session.exec(select(Group).where(Group.id == tenant_id)).first()
        g_cookie = session.exec(select(GroupCookie).where(GroupCookie.group_id == tenant_id)).first()

    if request.method == 'POST':
        form = await request.form()
        action = form.get('action')

        # 1. Update / Validate Bot Cookie for this Group
        if action == 'update_cookie':
            raw_cookie = form.get('cookie', '').strip()
            if not raw_cookie:
                with Session(engine) as session:
                    existing_c = session.exec(select(GroupCookie).where(GroupCookie.group_id == tenant_id)).first()
                    if existing_c:
                        session.delete(existing_c)
                        session.commit()
                flash(request, 'Sector bot cookie removed. System will fall back to server default.', 'info')
                return RedirectResponse(url_for(request, 'manage_rank_mappings'), status_code=303)

            # Validate cookie against Roblox API
            val_res = RobloxAPI.validate_cookie(raw_cookie)
            if not val_res.get('valid'):
                flash(request, f"Cookie rejected: {val_res.get('error', 'Invalid .ROBLOSECURITY')}", 'error')
                return RedirectResponse(url_for(request, 'manage_rank_mappings'), status_code=303)

            with Session(engine) as session:
                existing_c = session.exec(select(GroupCookie).where(GroupCookie.group_id == tenant_id)).first()
                if not existing_c:
                    existing_c = GroupCookie(
                        group_id=tenant_id,
                        cookie=val_res['cookie'],
                        bot_username=val_res.get('username'),
                        bot_id=val_res.get('user_id'),
                        is_valid=True,
                        last_validated=datetime.utcnow()
                    )
                    session.add(existing_c)
                else:
                    existing_c.cookie = val_res['cookie']
                    existing_c.bot_username = val_res.get('username')
                    existing_c.bot_id = val_res.get('user_id')
                    existing_c.is_valid = True
                    existing_c.last_validated = datetime.utcnow()
                    session.add(existing_c)
                session.commit()

            flash(request, f"Bot connected successfully as @{val_res.get('username')} (ID: {val_res.get('user_id')})!", 'success')
            return RedirectResponse(url_for(request, 'manage_rank_mappings'), status_code=303)

        # 2. Update Role Clearance Tier & Permissions
        elif action == 'update_permission':
            role_id_str = form.get('role_id')
            system_role = form.get('system_role', 'member').strip().lower()
            if role_id_str:
                role_id = int(role_id_str)
                with Session(engine) as session:
                    rule = session.exec(
                        select(GroupPermissionRule).where(
                            GroupPermissionRule.group_id == tenant_id,
                            GroupPermissionRule.specific_role_id == role_id
                        )
                    ).first()

                    perms = DEFAULT_ROLE_PERMISSIONS.get(system_role, DEFAULT_ROLE_PERMISSIONS['member'])
                    if not rule:
                        # Find rank number from RankMapping if possible
                        rule = GroupPermissionRule(
                            group_id=tenant_id,
                            specific_role_id=role_id,
                            min_roblox_rank=1,
                            system_role=system_role,
                            permissions=perms
                        )
                        session.add(rule)
                    else:
                        rule.system_role = system_role
                        rule.permissions = perms
                        session.add(rule)
                    session.commit()

                flash(request, f"Updated role permissions to clearance tier '{system_role.upper()}'.", 'success')
            return RedirectResponse(url_for(request, 'manage_rank_mappings'), status_code=303)

        # 3. Add Custom Rank Mapping
        elif action == 'add':
            system_rank = form.get('system_rank', '').strip()
            roblox_role_id = int(form.get('roblox_role_id')) if form.get('roblox_role_id') else None
            roblox_role_name = form.get('roblox_role_name', '').strip() or None

            if not system_rank or not roblox_role_id:
                flash(request, 'System rank and Roblox role ID are required', 'error')
                return RedirectResponse(url_for(request, 'manage_rank_mappings'), status_code=303)

            result = member_service.add_or_update_rank_mapping(
                system_rank=system_rank,
                roblox_role_id=roblox_role_id,
                roblox_role_name=roblox_role_name,
                tenant_id=tenant_id
            )
            if result['success']:
                flash(request, result['message'], 'success')
            else:
                flash(request, result['message'], 'error')

        # 4. Delete Mapping
        elif action == 'delete':
            mapping_id = int(form.get('mapping_id')) if form.get('mapping_id') else None
            if mapping_id:
                if member_service.delete_rank_mapping(mapping_id):
                    flash(request, 'Mapping deleted', 'success')

        # 5. Toggle Mapping
        elif action == 'toggle':
            mapping_id = int(form.get('mapping_id')) if form.get('mapping_id') else None
            if mapping_id:
                if member_service.toggle_rank_mapping(mapping_id):
                    flash(request, 'Mapping updated', 'success')

        # 6. Auto-Import / Auto-Sync All Roles from Roblox
        elif action == 'auto_import':
            try:
                gid = current_group.roblox_group_id if current_group else getattr(settings, 'ROBLOX_GROUP_ID', None)
                sync_res = sync_from_roblox(tenant_id=tenant_id, roblox_group_id=gid)
                if sync_res.get('success'):
                    flash(
                        request,
                        f"Auto-mapping complete: {sync_res.get('roles_mapped', 0)} roles synchronized, {sync_res.get('added', 0)} members added, {sync_res.get('updated', 0)} updated.",
                        'success'
                    )
                else:
                    flash(request, f"Sync error: {sync_res.get('message')}", 'error')
            except Exception as e:
                logger.error(f'Auto-import error: {e}')
                flash(request, f'Auto-import failed: {e}', 'error')

        return RedirectResponse(url_for(request, 'manage_rank_mappings'), status_code=303)

    # GET: Prepare view data
    with Session(engine) as session:
        current_group = session.exec(select(Group).where(Group.id == tenant_id)).first()
        g_cookie = session.exec(select(GroupCookie).where(GroupCookie.group_id == tenant_id)).first()
        rules = session.exec(select(GroupPermissionRule).where(GroupPermissionRule.group_id == tenant_id)).all()
        rule_map = {r.specific_role_id: r for r in rules if r.specific_role_id}

        mappings = session.exec(
            select(RankMapping).where(RankMapping.tenant_id == tenant_id).order_by(RankMapping.system_rank)
        ).all()

    # Query live Roblox roles for this group
    roblox_roles = []
    gid = current_group.roblox_group_id if current_group else getattr(settings, 'ROBLOX_GROUP_ID', None)
    if gid:
        try:
            roblox_api = get_roblox_api(group_id=tenant_id, roblox_group_id=gid)
            if roblox_api:
                roblox_roles = roblox_api.get_group_roles()
        except Exception as e:
            logger.error(f"Error fetching Roblox roles: {e}")

    # Build combined list of roles with their permissions
    roles_table = []
    seen_role_ids = set()

    for m in mappings:
        seen_role_ids.add(m.roblox_role_id)
        rule = rule_map.get(m.roblox_role_id)
        roles_table.append({
            'mapping_id': m.id,
            'system_rank': m.system_rank,
            'roblox_role_id': m.roblox_role_id,
            'roblox_role_name': m.roblox_role_name or m.system_rank,
            'is_active': m.is_active,
            'last_updated': m.last_updated,
            'system_role': rule.system_role if rule else 'member',
            'permissions': rule.permissions if rule else DEFAULT_ROLE_PERMISSIONS['member'],
        })

    # If Roblox API returned additional roles not yet mapped
    for r in roblox_roles:
        r_id = r.get('id')
        if r_id and r_id not in seen_role_ids and r.get('rank', 0) > 0:
            rule = rule_map.get(r_id)
            roles_table.append({
                'mapping_id': None,
                'system_rank': r.get('name'),
                'roblox_role_id': r_id,
                'roblox_role_name': r.get('name'),
                'is_active': False,
                'last_updated': None,
                'system_role': rule.system_role if rule else 'member',
                'permissions': rule.permissions if rule else DEFAULT_ROLE_PERMISSIONS['member'],
            })

    config_info = {
        'ROBLOX_SYNC_ENABLED': getattr(settings, 'ROBLOX_SYNC_ENABLED', False),
        'ROBLOX_SYNC_INTERVAL': getattr(settings, 'ROBLOX_SYNC_INTERVAL', 600),
        'ROBLOX_GROUP_ID': gid or 'Not configured',
        'GROUP_NAME': current_group.name if current_group else 'Taskforce Command',
    }

    fallback_cookie_active = not bool(g_cookie and g_cookie.cookie) and bool(getattr(settings, 'ROBLOX_COOKIE', None))

    return templates.TemplateResponse(
        'roblox/rank_mappings.html',
        {
            "request": request,
            "group": current_group,
            "cookie_info": g_cookie,
            "fallback_cookie_active": fallback_cookie_active,
            "roles_table": roles_table,
            "roblox_roles": roblox_roles,
            "config": config_info,
            "available_roles": ["member", "staff", "hct", "admin"],
        }
    )


@router.api_route('/roblox/sync_now', methods=['POST'])
@staff_required
async def sync_now(request: Request):
    """Manually trigger a sync from Roblox for the active group."""
    tenant_id = request.session.get("tenant_id") or get_tenant_id() or 1
    try:
        result = sync_from_roblox(tenant_id=tenant_id)
        if result.get('success'):
            flash(
                request,
                f"Sync complete: {result.get('roles_mapped', 0)} ranks mapped, {result.get('added', 0)} added, {result.get('updated', 0)} updated.",
                'success'
            )
        else:
            flash(request, f"Sync failed: {result.get('message')}", 'error')
    except Exception as e:
        flash(request, f"Sync error: {str(e)}", 'error')

    referer = request.headers.get("referer") or "/dashboard"
    return RedirectResponse(referer, status_code=303)

