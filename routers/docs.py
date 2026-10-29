"""
CORTEX // Tactical Command Network
Interactive Documentation Hub Router (/docs).
Provides 3-Tier rank-gated technical documentation, interactive bot command simulator,
and dynamic sector configuration manuals.
"""
import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from database.engine import engine
from database.tenant_models import Group
from database.ac_models import ActivityType, RankQuota
from utils.auth import is_staff, is_hct
from utils.templates import templates
from utils.tenant_context import get_tenant_id, extract_tenant_context

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get('/docs', name='docs_hub')
async def docs_hub(request: Request):
    """
    Render the Centralized Interactive Documentation Hub.
    Clearance Tiers:
    - Tier 1: All Operatives (Public / Member)
    - Tier 2: Staff & Field Officers (is_staff)
    - Tier 3: High Command Team & Admins (is_hct)
    """
    ctx = getattr(request.state, "tenant_context", None)
    if not ctx:
        ctx = extract_tenant_context(request) or {}

    user_is_staff = is_staff(request)
    user_is_hct = is_hct(request)

    tenant_id = request.session.get("tenant_id") or ctx.get("group_id") or get_tenant_id() or 1
    roblox_username = ctx.get("roblox_username") or request.session.get("roblox_username")
    system_role = ctx.get("system_role") or ("admin" if user_is_hct else ("staff" if user_is_staff else "member"))
    roblox_rank = ctx.get("roblox_rank", 1)

    group_data = None
    custom_activities = []
    custom_quotas = []

    try:
        with Session(engine) as session:
            grp = session.get(Group, tenant_id)
            if not grp:
                grp = session.exec(select(Group)).first()
            if grp:
                group_data = grp.to_dict()

            # Dynamic activities for this sector
            db_acts = session.exec(
                select(ActivityType).where(ActivityType.tenant_id == tenant_id, ActivityType.is_active == True)
            ).all()
            if not db_acts:
                db_acts = session.exec(select(ActivityType).where(ActivityType.is_active == True)).all()
            custom_activities = [a.to_dict() for a in db_acts]

            # Dynamic quotas for this sector
            db_quotas = session.exec(
                select(RankQuota).where(RankQuota.tenant_id == tenant_id)
            ).all()
            if not db_quotas:
                db_quotas = session.exec(select(RankQuota)).all()
            custom_quotas = [q.to_dict() for q in db_quotas]
    except Exception as e:
        logger.warning(f"Error fetching docs context for tenant {tenant_id}: {e}")

    # Fallback sector identity
    current_group_name = (group_data or {}).get("name") or request.session.get("group_name") or "Taskforce"
    active_theme = (group_data or {}).get("settings", {}).get("theme", "neon_purple")

    # Clearance Level computation: 1 (Member), 2 (Staff), 3 (HCT/Admin)
    if user_is_hct or system_role in ["hct", "admin"]:
        clearance_level = 3
        clearance_title = "Level 3: High Command Clearance"
        clearance_badge_class = "badge-danger"
    elif user_is_staff or system_role in ["staff", "commander", "marshal"]:
        clearance_level = 2
        clearance_title = "Level 2: Field Staff Clearance"
        clearance_badge_class = "badge-warning text-dark"
    elif roblox_username:
        clearance_level = 1
        clearance_title = "Level 1: Operative Standing"
        clearance_badge_class = "badge-info"
    else:
        clearance_level = 0
        clearance_title = "Guest / Public Preview"
        clearance_badge_class = "badge-secondary"

    return templates.TemplateResponse(
        'docs/index.html',
        {
            "request": request,
            "current_group_name": current_group_name,
            "group": group_data,
            "tenant_id": tenant_id,
            "roblox_username": roblox_username,
            "system_role": system_role,
            "roblox_rank": roblox_rank,
            "is_staff": user_is_staff,
            "is_hct": user_is_hct,
            "clearance_level": clearance_level,
            "clearance_title": clearance_title,
            "clearance_badge_class": clearance_badge_class,
            "custom_activities": custom_activities,
            "custom_quotas": custom_quotas,
            "active_theme": active_theme,
        }
    )
