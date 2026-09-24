"""
Group Configuration and Sector Governance Router.
Allows Sector High Command (HCT) and Administrators to modify:
1. Group Identity (Name & Description - immediately reflected in the header navbar).
2. Dedicated Bot Automation Cookie (.ROBLOSECURITY) with live Roblox API validation.
3. Rank Access & Clearance Tiers (Member, Staff, HCT, Admin) and permission mapping.
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session, select

from config import settings
from database.engine import engine
from database.tenant_models import Group, GroupCookie, GroupPermissionRule, GroupMember, User
from database.models import RankMapping
from api.roblox_api import RobloxAPI
from services.roblox_oauth_service import DEFAULT_ROLE_PERMISSIONS
from utils.auth import hct_required
from utils.flash import flash
from utils.jwt_utils import decode_token, create_tenant_token
from utils.roblox_sync import sync_from_roblox
from utils.templates import templates, url_for
from utils.tenant_context import get_tenant_id, set_tenant_context
from services import permission_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get('/group/settings', name='group_settings')
@hct_required
async def view_group_settings(request: Request):
    """Render the centralized Group Configuration & Governance console."""
    tenant_id = request.session.get("tenant_id") or get_tenant_id() or 1
    set_tenant_context(tenant_id)

    with Session(engine) as session:
        group = session.get(Group, tenant_id)
        if not group:
            flash(request, "Active group not found.", "error")
            return RedirectResponse(url="/portal/select-group", status_code=303)

        cookie_record = session.exec(
            select(GroupCookie).where(GroupCookie.group_id == tenant_id)
        ).first()

        db_rules = session.exec(
            select(GroupPermissionRule).where(GroupPermissionRule.group_id == tenant_id)
        ).all()
        rule_map = {r.specific_role_id: r for r in db_rules if r.specific_role_id}

        db_mappings = session.exec(
            select(RankMapping).where(RankMapping.tenant_id == tenant_id)
        ).all()
        mapping_map = {m.roblox_role_id: m for m in db_mappings if m.roblox_role_id}

    # Fetch live roles from Roblox group API to guarantee complete and up-to-date rank hierarchy
    roles_list = []
    try:
        api = RobloxAPI(group_id=group.roblox_group_id)
        roblox_roles = api.get_group_roles()
    except Exception as e:
        logger.warning(f"Failed to fetch live roles from Roblox for group {group.roblox_group_id}: {e}")
        roblox_roles = []

    if roblox_roles:
        for r in roblox_roles:
            role_id = r.get("id")
            role_name = r.get("name")
            rank_num = r.get("rank", 0)
            member_count = r.get("memberCount", 0)

            # Look up existing permission rule
            p_rule = rule_map.get(role_id)
            if p_rule:
                assigned_role = p_rule.system_role
                assigned_perms = p_rule.permissions or []
            else:
                # Default heuristics based on rank level
                if rank_num == 255:
                    assigned_role = "admin"
                elif rank_num >= 100:
                    assigned_role = "hct"
                elif rank_num >= 50:
                    assigned_role = "staff"
                else:
                    assigned_role = "member"
                assigned_perms = DEFAULT_ROLE_PERMISSIONS.get(assigned_role, [])

            roles_list.append({
                "role_id": role_id,
                "role_name": role_name,
                "rank_num": rank_num,
                "member_count": member_count,
                "system_role": assigned_role,
                "permissions": assigned_perms,
            })
    else:
        # Fallback to database mappings if Roblox API is unreachable
        for m in db_mappings:
            p_rule = rule_map.get(m.roblox_role_id)
            assigned_role = p_rule.system_role if p_rule else "member"
            assigned_perms = p_rule.permissions if p_rule else DEFAULT_ROLE_PERMISSIONS["member"]
            roles_list.append({
                "role_id": m.roblox_role_id,
                "role_name": m.roblox_role_name or m.system_rank,
                "rank_num": 1,
                "member_count": 0,
                "system_role": assigned_role,
                "permissions": assigned_perms,
            })

    # Fetch granular rank permissions
    rank_perms = permission_service.get_group_rank_permissions(tenant_id)
    perm_map = {p.role_id: p for p in rank_perms}

    for r in roles_list:
        rp = perm_map.get(r["role_id"])
        if rp:
            r["can_promote"] = rp.can_promote
            r["can_log_activity"] = rp.can_log_activity
            r["can_delete_activity"] = rp.can_delete_activity
            r["can_view_data"] = rp.can_view_data
            r["can_manage_ac"] = rp.can_manage_ac
            r["is_hct"] = rp.is_hct
        else:
            is_adm = r["system_role"] == "admin"
            is_hct_role = r["system_role"] in ["hct", "admin"]
            is_staff_role = r["system_role"] in ["staff", "hct", "admin"]
            r["can_promote"] = is_staff_role
            r["can_log_activity"] = is_staff_role
            r["can_delete_activity"] = is_hct_role
            r["can_view_data"] = True
            r["can_manage_ac"] = is_hct_role
            r["is_hct"] = is_adm

    # Sort roles descending by rank number (highest rank / owner first)
    roles_list.sort(key=lambda x: x["rank_num"], reverse=True)

    active_theme = group.get_settings_dict().get("theme", "neon_purple")
    available_themes = [
        {"id": "neutral", "name": "Slate Charcoal", "type": "Matte / Non-Neon", "primary": "#475569", "bg": "#0b0f19", "desc": "Clean neutral command, muted steel accents"},
        {"id": "dark_matte", "name": "Deep Graphite", "type": "Matte / Non-Neon", "primary": "#52525b", "bg": "#111113", "desc": "Stealth matte obsidian, zero neon"},
        {"id": "slate_gray", "name": "Tactical Steel", "type": "Matte / Non-Neon", "primary": "#64748b", "bg": "#151a21", "desc": "Cool industrial steel gray with silver borders"},
        {"id": "clean_light", "name": "Clean Light", "type": "Light Mode", "primary": "#2563eb", "bg": "#f8fafc", "desc": "Crisp white panels with slate typography"},
        {"id": "neon_purple", "name": "Taskforce Classic", "type": "Neon & Cyber", "primary": "#a855f7", "bg": "#09060f", "desc": "Original Taskforce neon purple glow"},
        {"id": "neon_cyan", "name": "Cyberpunk Grid", "type": "Neon & Cyber", "primary": "#22d3ee", "bg": "#040e14", "desc": "Electric cyan neon cyberpunk aesthetic"},
        {"id": "crimson", "name": "Combat Ops Crimson", "type": "Neon & Cyber", "primary": "#f43f5e", "bg": "#120708", "desc": "Tactical combat strike red with crimson glow"},
        {"id": "emerald", "name": "SpecOps Emerald", "type": "Neon & Cyber", "primary": "#34d399", "bg": "#05120a", "desc": "SpecOps tactical forest green with emerald glow"},
    ]

    return templates.TemplateResponse(
        "group/group_settings.html",
        {
            "request": request,
            "group": group,
            "cookie_record": cookie_record,
            "roles": roles_list,
            "rank_permissions": rank_perms,
            "available_roles": ["member", "staff", "hct", "admin"],
            "role_descriptions": {
                "member": "Standard Operative: View Roster & AC Progress",
                "staff": "Staff Operative: Log Activities & Manage Members",
                "hct": "High Command Team: Manage AC Cycles, Exemptions & Config",
                "admin": "Sector Administrator: Full Control, Bot Cookie & Governance",
            },
            "active_theme": active_theme,
            "available_themes": available_themes,
        }
    )


@router.post('/group/settings/identity', name='update_group_identity')
@hct_required
async def update_group_identity(
    request: Request,
    name: str = Form(...),
    discord_group_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    """Update group name, discord_group_id, and description; immediately reflects across the header and bot."""
    tenant_id = request.session.get("tenant_id") or get_tenant_id() or 1
    new_name = name.strip()

    if not new_name:
        flash(request, "Group name cannot be empty.", "error")
        return RedirectResponse(url_for(request, 'group_settings'), status_code=303)

    with Session(engine) as session:
        group = session.get(Group, tenant_id)
        if not group:
            flash(request, "Group record not found.", "error")
            return RedirectResponse(url_for(request, 'group_settings'), status_code=303)

        group.name = new_name
        group.discord_group_id = discord_group_id.strip() if (discord_group_id and discord_group_id.strip()) else None
        if description is not None:
            group.description = description.strip()
        session.add(group)
        session.commit()

    # Synchronize session immediately so header in template updates instantly
    request.session["group_name"] = new_name

    response = RedirectResponse(url_for(request, 'group_settings'), status_code=303)

    # Re-issue Level 2 JWT cookie if user has one active
    user_token = request.cookies.get("tf_tenant_token")
    if user_token:
        try:
            payload = decode_token(user_token, expected_type="tenant_context")
            new_jwt = create_tenant_token(
                user_id=payload.get("user_id"),
                roblox_id=payload.get("roblox_id"),
                roblox_username=payload.get("roblox_username"),
                group_id=payload.get("group_id"),
                roblox_group_id=payload.get("roblox_group_id"),
                group_name=new_name,
                roblox_rank=payload.get("roblox_rank", 1),
                system_role=payload.get("system_role", "member"),
                permissions=payload.get("permissions", []),
            )
            response.set_cookie(
                key="tf_tenant_token",
                value=new_jwt,
                httponly=True,
                samesite="lax",
                max_age=43200,
            )
        except Exception as e:
            logger.warning(f"Could not refresh tenant token on group rename: {e}")

    flash(request, f"Sector identity updated! Active group name is now '{new_name}'.", "success")
    return response


@router.post('/group/settings/cookie', name='update_group_cookie')
@hct_required
async def update_group_cookie(
    request: Request,
    action: str = Form(...),
    cookie: Optional[str] = Form(None)
):
    """Add, validate, update, or disconnect the sector automation bot cookie."""
    tenant_id = request.session.get("tenant_id") or get_tenant_id() or 1

    if action == "clear":
        with Session(engine) as session:
            existing = session.exec(
                select(GroupCookie).where(GroupCookie.group_id == tenant_id)
            ).first()
            if existing:
                session.delete(existing)
                session.commit()
        flash(request, "Sector bot cookie removed. System will fall back to server default.", "info")
        return RedirectResponse(url_for(request, 'group_settings'), status_code=303)

    # Save and validate
    raw_cookie = (cookie or "").strip()
    if not raw_cookie:
        flash(request, "Please provide a valid .ROBLOSECURITY cookie.", "error")
        return RedirectResponse(url_for(request, 'group_settings'), status_code=303)

    val_res = RobloxAPI.validate_cookie(raw_cookie)
    if not val_res.get('valid'):
        flash(request, f"Cookie validation failed: {val_res.get('error', 'Invalid .ROBLOSECURITY token')}", "error")
        return RedirectResponse(url_for(request, 'group_settings'), status_code=303)

    with Session(engine) as session:
        existing = session.exec(
            select(GroupCookie).where(GroupCookie.group_id == tenant_id)
        ).first()
        if not existing:
            existing = GroupCookie(
                group_id=tenant_id,
                cookie=val_res['cookie'],
                bot_username=val_res.get('username'),
                bot_id=val_res.get('user_id'),
                is_valid=True,
                last_validated=datetime.utcnow(),
            )
            session.add(existing)
        else:
            existing.cookie = val_res['cookie']
            existing.bot_username = val_res.get('username')
            existing.bot_id = val_res.get('user_id')
            existing.is_valid = True
            existing.last_validated = datetime.utcnow()
            existing.updated_at = datetime.utcnow()
            session.add(existing)
        session.commit()

    flash(request, f"Sector automation bot connected as @{val_res.get('username')} (ID: {val_res.get('user_id')})!", "success")
    return RedirectResponse(url_for(request, 'group_settings'), status_code=303)


@router.post('/group/settings/permissions', name='update_group_permissions')
@hct_required
async def update_group_permissions(
    request: Request,
    role_id: int = Form(...),
    system_role: str = Form(...),
    min_rank: Optional[int] = Form(1),
    role_name: Optional[str] = Form(None)
):
    """Update clearance tier (member, staff, hct, admin) for a specific Roblox role."""
    tenant_id = request.session.get("tenant_id") or get_tenant_id() or 1
    system_role = system_role.strip().lower()

    if system_role not in DEFAULT_ROLE_PERMISSIONS:
        flash(request, f"Invalid clearance tier '{system_role}'.", "error")
        return RedirectResponse(url_for(request, 'group_settings'), status_code=303)

    perms = DEFAULT_ROLE_PERMISSIONS[system_role]

    with Session(engine) as session:
        rule = session.exec(
            select(GroupPermissionRule).where(
                GroupPermissionRule.group_id == tenant_id,
                GroupPermissionRule.specific_role_id == role_id
            )
        ).first()

        if not rule:
            rule = GroupPermissionRule(
                group_id=tenant_id,
                specific_role_id=role_id,
                min_roblox_rank=min_rank or 1,
                system_role=system_role,
                permissions=perms
            )
            session.add(rule)
        else:
            rule.system_role = system_role
            rule.permissions = perms
            if min_rank:
                rule.min_roblox_rank = min_rank
            session.add(rule)

        # Synchronize any existing active GroupMember records with this role
        members = session.exec(
            select(GroupMember).where(
                GroupMember.group_id == tenant_id,
                GroupMember.roblox_role_id == role_id
            )
        ).all()
        for m in members:
            m.system_role = system_role
            session.add(m)

        # Keep RankMapping synchronized as well
        mapping = session.exec(
            select(RankMapping).where(
                RankMapping.tenant_id == tenant_id,
                RankMapping.roblox_role_id == role_id
            )
        ).first()
        if mapping and role_name:
            mapping.roblox_role_name = role_name
            session.add(mapping)

        session.commit()

    display_name = role_name or f"Role #{role_id}"
    flash(request, f"Clearance tier for '{display_name}' updated to '{system_role.upper()}'.", "success")
    return RedirectResponse(url_for(request, 'group_settings'), status_code=303)


@router.post('/group/settings/sync-ranks', name='sync_group_ranks')
@hct_required
async def sync_group_ranks(request: Request):
    """Synchronize roles and members directly from Roblox for this active sector."""
    tenant_id = request.session.get("tenant_id") or get_tenant_id() or 1
    try:
        sync_res = sync_from_roblox(tenant_id=tenant_id)
        if sync_res.get("success"):
            flash(request, f"Ranks and members synchronized with Roblox! ({sync_res.get('members_synced', 0)} personnel verified)", "success")
        else:
            flash(request, f"Sync completed: {sync_res.get('message', 'Done')}", "info")
    except Exception as e:
        logger.error(f"Error syncing ranks for tenant {tenant_id}: {e}")
        flash(request, f"Error syncing ranks from Roblox: {e}", "error")

    return RedirectResponse(url_for(request, 'group_settings'), status_code=303)


@router.post('/group/settings/theme', name='update_group_theme')
@hct_required
async def update_group_theme(
    request: Request,
    theme: str = Form(...)
):
    """Save sector visual theme preference into group settings JSON and update session."""
    valid_themes = ["neutral", "dark_matte", "slate_gray", "clean_light", "neon_purple", "neon_cyan", "crimson", "emerald"]
    if theme not in valid_themes:
        flash(request, "Invalid visual theme selected.", "error")
        return RedirectResponse(url_for(request, 'group_settings'), status_code=303)

    tenant_id = request.session.get("tenant_id") or get_tenant_id() or 1
    with Session(engine) as session:
        group = session.get(Group, tenant_id)
        if not group:
            flash(request, "Active sector not found.", "error")
            return RedirectResponse(url_for(request, 'group_settings'), status_code=303)

        settings_dict = group.get_settings_dict()
        settings_dict["theme"] = theme
        group.settings = settings_dict
        session.add(group)
        session.commit()
        session.refresh(group)

    # Immediately reflect in current user session
    request.session["group_theme"] = theme
    display_theme = theme.replace("_", " ").title()
    flash(request, f"Sector visual theme successfully changed to '{display_theme}'.", "success")
    return RedirectResponse(url_for(request, 'group_settings'), status_code=303)


@router.post('/group/settings/rank-permissions', name='update_rank_permissions')
@hct_required
async def update_group_rank_permissions(request: Request):
    """Save granular rank permissions matrix for the active sector."""
    tenant_id = request.session.get("tenant_id") or get_tenant_id() or 1
    form = await request.form()

    role_ids = form.getlist("role_ids")
    updates = []
    for rid_str in role_ids:
        try:
            rid = int(rid_str)
            updates.append({
                "role_id": rid,
                "role_name": form.get(f"role_name_{rid}", f"Role {rid}"),
                "rank_number": int(form.get(f"rank_number_{rid}", 1)),
                "can_promote": f"perm_promote_{rid}" in form,
                "can_log_activity": f"perm_log_{rid}" in form,
                "can_delete_activity": f"perm_delete_{rid}" in form,
                "can_view_data": f"perm_view_{rid}" in form,
                "can_manage_ac": f"perm_ac_{rid}" in form,
                "is_hct": f"perm_hct_{rid}" in form,
            })
        except ValueError:
            continue

    count = permission_service.update_rank_permissions(tenant_id, updates)
    flash(request, f"Successfully updated permissions matrix for {count} ranks.", "success")
    return RedirectResponse(url_for(request, 'group_settings') + "#permissions-section", status_code=303)


