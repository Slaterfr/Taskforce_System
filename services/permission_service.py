"""
Permission Service for Multi-Tenant Granular Rank Permissions.
Handles permission retrieval, default seeding, updates, and Discord/Web clearance checks.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlmodel import select, Session

from database.engine import engine, db_session
from database.permission_models import RankPermission
from database.models import RankMapping, Member
from database.tenant_models import GroupPermissionRule, GroupMember

logger = logging.getLogger(__name__)


def ensure_default_rank_permissions(tenant_id: int) -> List[RankPermission]:
    """
    Ensures that every mapped rank for a tenant has an entry in rank_permissions.
    Assigns sensible defaults based on rank number if creating fresh.
    """
    with Session(engine) as session:
        # Fetch existing permissions
        existing_perms = session.exec(
            select(RankPermission).where(RankPermission.tenant_id == tenant_id)
        ).all()
        existing_role_ids = {p.role_id for p in existing_perms}

        # Fetch mapped ranks
        mappings = session.exec(
            select(RankMapping).where(
                RankMapping.tenant_id == tenant_id,
                RankMapping.is_active == True
            )
        ).all()

        created = []
        for m in mappings:
            if m.roblox_role_id in existing_role_ids:
                continue

            # Calculate rank level heuristics
            rank_name_lower = (m.system_rank or "").lower()
            # If rank number is known or inferred
            rank_num = getattr(m, 'rank_num', 1)
            is_high_rank = any(w in rank_name_lower for w in ["general", "marshal", "commander", "admiral", "colonel", "hct", "owner", "leader"])
            is_officer = any(w in rank_name_lower for w in ["officer", "captain", "lieutenant", "sergeant", "staff", "trainer", "prospect"])

            if is_high_rank:
                can_promote = True
                can_log = True
                can_delete = True
                can_view = True
                can_ac = True
                is_hct = True
            elif is_officer:
                can_promote = True
                can_log = True
                can_delete = False
                can_view = True
                can_ac = False
                is_hct = False
            else:
                can_promote = False
                can_log = False
                can_delete = False
                can_view = True
                can_ac = False
                is_hct = False

            perm = RankPermission(
                tenant_id=tenant_id,
                role_id=m.roblox_role_id,
                role_name=m.system_rank or m.roblox_role_name or f"Rank {m.roblox_role_id}",
                rank_number=rank_num,
                can_promote=can_promote,
                can_log_activity=can_log,
                can_delete_activity=can_delete,
                can_view_data=can_view,
                can_manage_ac=can_ac,
                is_hct=is_hct,
            )
            session.add(perm)
            created.append(perm)

        if created:
            session.commit()
            logger.info(f"Seeded {len(created)} default rank permissions for tenant {tenant_id}")

        # Return full updated list
        all_perms = session.exec(
            select(RankPermission).where(RankPermission.tenant_id == tenant_id)
        ).all()
        return sorted(all_perms, key=lambda x: x.rank_number, reverse=True)


def get_group_rank_permissions(tenant_id: int) -> List[RankPermission]:
    """Retrieve all rank permissions for a tenant, ensuring defaults exist."""
    perms = db_session().exec(
        select(RankPermission).where(RankPermission.tenant_id == tenant_id)
    ).all()
    if not perms:
        return ensure_default_rank_permissions(tenant_id)
    return sorted(perms, key=lambda x: x.rank_number, reverse=True)


def update_rank_permissions(tenant_id: int, updates: List[Dict[str, Any]]) -> int:
    """
    Batch update rank permissions for a sector.
    Each item in updates must contain 'role_id' and boolean keys.
    """
    updated_count = 0
    with Session(engine) as session:
        for item in updates:
            role_id = item.get("role_id")
            if not role_id:
                continue

            perm = session.exec(
                select(RankPermission).where(
                    RankPermission.tenant_id == tenant_id,
                    RankPermission.role_id == int(role_id)
                )
            ).first()

            if not perm:
                perm = RankPermission(
                    tenant_id=tenant_id,
                    role_id=int(role_id),
                    role_name=item.get("role_name", f"Role {role_id}"),
                    rank_number=item.get("rank_number", 1)
                )

            if "can_promote" in item: perm.can_promote = bool(item["can_promote"])
            if "can_log_activity" in item: perm.can_log_activity = bool(item["can_log_activity"])
            if "can_delete_activity" in item: perm.can_delete_activity = bool(item["can_delete_activity"])
            if "can_view_data" in item: perm.can_view_data = bool(item["can_view_data"])
            if "can_manage_ac" in item: perm.can_manage_ac = bool(item["can_manage_ac"])
            if "is_hct" in item: perm.is_hct = bool(item["is_hct"])
            perm.updated_at = datetime.utcnow()

            session.add(perm)
            updated_count += 1

            # Synchronize with GroupPermissionRule for backward compatibility
            system_role = "admin" if perm.is_hct else ("staff" if (perm.can_log_activity or perm.can_promote) else "member")
            rule = session.exec(
                select(GroupPermissionRule).where(
                    GroupPermissionRule.group_id == tenant_id,
                    GroupPermissionRule.specific_role_id == int(role_id)
                )
            ).first()
            if rule:
                rule.system_role = system_role
                session.add(rule)

        session.commit()
    return updated_count


def check_member_permission(
    tenant_id: int,
    discord_id: Optional[str] = None,
    roblox_id: Optional[str] = None,
    required_permission: str = "view_data",
    discord_roles: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Checks if a user has the required permission in the specified tenant.
    Prioritizes Discord Server Roles directly against the sector's Rank Permissions Matrix (no database linking needed).
    Normalizes permission names: promote, log_activity, delete_activity, view_data, manage_ac, hct.
    """
    clean_perm = required_permission.lower().replace("-", "_")
    if not clean_perm.startswith("can_") and clean_perm not in ["is_hct", "hct"]:
        clean_perm = f"can_{clean_perm}"
    if clean_perm == "hct":
        clean_perm = "is_hct"

    # Platform Developer Master Clearance
    if discord_id and str(discord_id) == "751920066332721152":
        return {"allowed": True, "rank": "Developer / General", "reason": "Authorized via Platform Developer Clearance."}

    with Session(engine) as session:
        # A. Evaluate by Discord Server Profile Roles (Strictly role-based, no Discord ID database linking)
        if discord_roles:
            sector_perms = session.exec(
                select(RankPermission).where(RankPermission.tenant_id == tenant_id)
            ).all()

            def norm(s: str) -> str:
                return "".join(c.lower() for c in s if c.isalnum())

            valid_roles = [r for r in discord_roles if r and r != "@everyone"]
            normalized_roles = {norm(r): r for r in valid_roles}

            exact_matches = []
            partial_matches = []
            for p in sector_perms:
                p_norm = norm(p.role_name)
                if not p_norm:
                    continue
                if p_norm in normalized_roles:
                    exact_matches.append(p)
                else:
                    for dr_norm in normalized_roles:
                        if p_norm in dr_norm:
                            partial_matches.append(p)
                            break

            matched_perms = exact_matches if exact_matches else partial_matches

            if matched_perms:
                # Prioritize HCT and permission-granting roles, then rank_number
                matched_perms.sort(
                    key=lambda x: (
                        1 if x.is_hct else 0,
                        1 if getattr(x, clean_perm, False) else 0,
                        getattr(x, "rank_number", 0) or 0
                    ),
                    reverse=True
                )
                for p in matched_perms:
                    if p.is_hct:
                        return {"allowed": True, "rank": p.role_name, "reason": "Authorized via HCT Clearance."}
                    if getattr(p, clean_perm, False):
                        return {"allowed": True, "rank": p.role_name, "reason": f"Authorized via server role '{p.role_name}'."}

                human_perm = clean_perm.replace("can_", "").replace("_", " ").title()
                highest = matched_perms[0]
                return {
                    "allowed": False,
                    "rank": highest.role_name,
                    "reason": f"Your server rank '{highest.role_name}' does not have permission to {human_perm} in this sector."
                }

            # If roles provided but none matched a mapped rank directly, check standard tactical roles
            for r in valid_roles:
                r_lower = r.lower()
                if any(w in r_lower for w in ["general", "hct", "high command", "owner", "admin", "commander"]):
                    return {"allowed": True, "rank": r, "reason": f"Authorized via elevated Discord role '{r}'."}
                if clean_perm in ["can_log_activity", "can_view_data"] and any(w in r_lower for w in ["staff", "officer", "marshal"]):
                    return {"allowed": True, "rank": r, "reason": f"Authorized via Discord role '{r}'."}

            return {
                "allowed": False,
                "rank": valid_roles[0] if valid_roles else None,
                "reason": "None of your Discord server roles grant permission for this action in this sector."
            }

        # B. Roblox ID verification fallback (e.g. from in-game game server calls)
        if roblox_id:
            member = session.exec(
                select(Member).where(
                    Member.tenant_id == tenant_id,
                    Member.roblox_id == str(roblox_id)
                )
            ).first()
            if not member:
                return {"allowed": False, "rank": None, "reason": "Roblox user not found on this sector's roster."}

            perm = session.exec(
                select(RankPermission).where(
                    RankPermission.tenant_id == tenant_id,
                    RankPermission.role_name == member.current_rank
                )
            ).first()
            if perm:
                if perm.is_hct:
                    return {"allowed": True, "rank": perm.role_name, "reason": "Authorized via HCT Clearance."}
                if getattr(perm, clean_perm, False):
                    return {"allowed": True, "rank": perm.role_name, "reason": f"Authorized via rank '{perm.role_name}'."}

        # If neither Discord roles nor Roblox ID were provided to identify rank
        return {
            "allowed": False,
            "rank": None,
            "reason": "No Discord server roles provided to identify rank in this sector."
        }

