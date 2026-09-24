"""
Roblox Two-Way Sync Module
Handles synchronization between the system and Roblox group
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from config import settings
import logging

logger = logging.getLogger(__name__)
from database.engine import db_session, engine
from sqlmodel import select, Session
from database.models import Member, RankMapping, PromotionLog
from database.tenant_models import Group, GroupCookie, GroupPermissionRule
from services.roblox_oauth_service import DEFAULT_ROLE_PERMISSIONS
from utils.tenant_context import set_tenant_context, get_tenant_id
from api.roblox_api import RobloxAPI

# Global flag to prevent sync loops
_syncing_from_roblox = False

def get_syncing_flag():
    """Get the current syncing flag state"""
    return _syncing_from_roblox

def set_syncing_flag(value: bool):
    """Set the syncing flag"""
    global _syncing_from_roblox
    _syncing_from_roblox = value

def get_roblox_api(group_id: Optional[int] = None, roblox_group_id: Optional[str] = None) -> Optional[RobloxAPI]:
    """Get configured RobloxAPI instance for a specific group/tenant using its dedicated cookie."""
    target_roblox_group_id = roblox_group_id
    cookie = None

    effective_group_id = group_id or get_tenant_id() or 1

    try:
        with Session(engine) as session:
            # 1. Lookup dedicated cookie for this tenant
            g_cookie = session.exec(select(GroupCookie).where(GroupCookie.group_id == effective_group_id)).first()
            if g_cookie and g_cookie.cookie:
                cookie = g_cookie.cookie

            # 2. Lookup Roblox Group ID if not explicitly passed
            if not target_roblox_group_id:
                grp = session.exec(select(Group).where(Group.id == effective_group_id)).first()
                if grp:
                    target_roblox_group_id = grp.roblox_group_id
    except Exception as e:
        logger.warning(f"Error fetching group/cookie for tenant {effective_group_id}: {e}")

    # Fallback to .env settings if not set in database
    if not cookie:
        cookie = getattr(settings, 'ROBLOX_COOKIE', None)
    if not target_roblox_group_id:
        target_roblox_group_id = getattr(settings, 'ROBLOX_GROUP_ID', None)

    if not target_roblox_group_id:
        logger.warning("Roblox API not configured: missing Roblox Group ID")
        return None

    try:
        group_id_int = int(target_roblox_group_id)
    except (ValueError, TypeError) as e:
        logger.error(f"Roblox API not configured: Group ID '{target_roblox_group_id}' is not a valid integer: {e}")
        return None

    return RobloxAPI(group_id_int, cookie=cookie)


def get_role_id_for_rank(system_rank: str) -> Optional[int]:
    """Get Roblox role ID for a system rank"""
    # Ensure system_rank is a string
    if not isinstance(system_rank, str):
        if isinstance(system_rank, dict):
            logger.warning(f"get_role_id_for_rank received dict instead of string: {system_rank}")
            return None
        system_rank = str(system_rank) if system_rank else 'Aspirant'
    
    try:
        mapping = db_session().query(RankMapping).filter_by(
            system_rank=system_rank,
            is_active=True
        ).first()
        
        return mapping.roblox_role_id if mapping else None
    except Exception as e:
        logger.error(f"Error in get_role_id_for_rank with rank '{system_rank}': {e}")
        return None

def sync_member_to_roblox(member: Member, skip_if_syncing: bool = True) -> Dict:
    """
    Sync a member's rank to Roblox group
    Returns: {'success': bool, 'message': str}
    """
    if skip_if_syncing and _syncing_from_roblox:
        logger.info(f"Skipping sync for {member.discord_username} - currently syncing from Roblox")
        return {'success': True, 'message': 'Skipped - syncing from Roblox'}
    
    logger.info(f"Attempting to sync {member.discord_username} (rank: {member.current_rank}) to Roblox")
    
    roblox_api = get_roblox_api()
    if not roblox_api:
        error_msg = 'Roblox API not configured'
        logger.error(error_msg)
        return {'success': False, 'message': error_msg}
    
    if not member.roblox_id:
        error_msg = f'Member {member.discord_username} has no Roblox ID'
        logger.warning(error_msg)
        return {'success': False, 'message': error_msg}
    
    role_id = get_role_id_for_rank(member.current_rank)
    if not role_id:
        error_msg = f'No role mapping found for rank: {member.current_rank}'
        logger.warning(error_msg)
        return {'success': False, 'message': error_msg}
    
    try:
        user_id = int(member.roblox_id)
        logger.info(f"Updating Roblox user {user_id} to role {role_id} (rank: {member.current_rank})")
        success, error_msg = roblox_api.update_member_role(user_id, role_id)
        
        if success:
            success_msg = f'Updated {member.discord_username} to {member.current_rank} in Roblox'
            logger.info(success_msg)
            return {'success': True, 'message': success_msg}
        else:
            error_msg_full = f'Failed to update role in Roblox: {error_msg}'
            logger.error(f"Roblox sync failed for {member.discord_username}: {error_msg_full}")
            return {'success': False, 'message': error_msg_full}
    except (ValueError, TypeError) as e:
        error_msg = f'Invalid Roblox ID: {member.roblox_id} ({str(e)})'
        logger.error(error_msg)
        return {'success': False, 'message': error_msg}
    except Exception as e:
        error_msg = f'Error updating role: {str(e)}'
        logger.error(f"Unexpected error syncing {member.discord_username} to Roblox: {error_msg}", exc_info=True)
        return {'success': False, 'message': error_msg}

def add_member_to_roblox(member: Member, skip_if_syncing: bool = True) -> Dict:
    """
    Add a member to Roblox group
    Returns: {'success': bool, 'message': str}
    """
    if skip_if_syncing and _syncing_from_roblox:
        return {'success': True, 'message': 'Skipped - syncing from Roblox'}
    
    roblox_api = get_roblox_api()
    if not roblox_api:
        group_id = getattr(settings, 'ROBLOX_GROUP_ID', 'Not set')
        cookie_set = bool(getattr(settings, 'ROBLOX_COOKIE', None))
        return {
            'success': False, 
            'message': f'Roblox API not configured. Group ID: {group_id}, Cookie set: {cookie_set}'
        }
    
    if not member.roblox_username:
        return {'success': False, 'message': f'Member {member.discord_username} has no Roblox username'}
    
    # Get user ID from username
    user_id = roblox_api.get_user_id_by_username(member.roblox_username)
    if not user_id:
        return {'success': False, 'message': f'Could not find Roblox user: {member.roblox_username}'}
    
    # Update member's roblox_id if missing
    if not member.roblox_id:
        member.roblox_id = str(user_id)
        db_session().commit()
    
    role_id = get_role_id_for_rank(member.current_rank)
    if not role_id:
        return {'success': False, 'message': f'No role mapping found for rank: {member.current_rank}'}
    
    try:
        success = roblox_api.add_member_to_group(user_id, role_id)
        
        if success:
            return {'success': True, 'message': f'Added {member.discord_username} to Roblox group'}
        else:
            return {'success': False, 'message': f'Failed to add member to Roblox group'}
    except Exception as e:
        return {'success': False, 'message': f'Error: {str(e)}'}

def remove_member_from_roblox(member: Member, skip_if_syncing: bool = True) -> Dict:
    """
    Remove a member from Roblox group
    Returns: {'success': bool, 'message': str}
    """
    if skip_if_syncing and _syncing_from_roblox:
        return {'success': True, 'message': 'Skipped - syncing from Roblox'}
    
    roblox_api = get_roblox_api()
    if not roblox_api:
        return {'success': False, 'message': 'Roblox API not configured'}
    
    if not member.roblox_id:
        return {'success': False, 'message': f'Member {member.discord_username} has no Roblox ID'}
    
    try:
        user_id = int(member.roblox_id)
        success = roblox_api.remove_member_from_group(user_id)
        
        if success:
            return {'success': True, 'message': f'Removed {member.discord_username} from Roblox group'}
        else:
            return {'success': False, 'message': f'Failed to remove member from Roblox group'}
    except (ValueError, TypeError):
        return {'success': False, 'message': f'Invalid Roblox ID: {member.roblox_id}'}

def sync_from_roblox(tenant_id: int = 1, roblox_group_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Sync members from Roblox group to system with automatic role and rank mapping.
    Scoped to tenant_id to guarantee multi-tenant data isolation.
    """
    set_syncing_flag(True)
    set_tenant_context(tenant_id)

    try:
        roblox_api = get_roblox_api(group_id=tenant_id, roblox_group_id=roblox_group_id)
        if not roblox_api:
            return {'success': False, 'message': f'Roblox API not configured for tenant {tenant_id}'}

        # Step 1: Automatic Rank Mapping from Roblox Roles
        roblox_roles = roblox_api.get_group_roles()
        if not roblox_roles:
            logger.warning(f"No roles returned from Roblox for tenant {tenant_id}")
        else:
            logger.info(f"[Tenant {tenant_id}] Auto-mapping {len(roblox_roles)} roles from Roblox...")
            seen_rank_names = set()
            for role in roblox_roles:
                if not isinstance(role, dict):
                    continue
                role_name = role.get('name', '').strip()
                role_id = role.get('id')
                rank_val = role.get('rank', 1)

                if not role_name or not role_id or rank_val == 0:
                    continue  # Skip Guest / rank 0

                # Disambiguate if group has duplicate role names
                sys_rank = role_name
                if sys_rank in seen_rank_names:
                    sys_rank = f"{role_name} ({rank_val})"
                seen_rank_names.add(sys_rank)

                # Auto-upsert RankMapping for this tenant
                mapping = db_session().exec(
                    select(RankMapping).where(
                        RankMapping.tenant_id == tenant_id,
                        RankMapping.roblox_role_id == role_id
                    )
                ).first()

                if not mapping:
                    mapping = RankMapping(
                        tenant_id=tenant_id,
                        system_rank=sys_rank,
                        roblox_role_id=role_id,
                        roblox_role_name=role_name,
                        is_active=True
                    )
                    db_session().add(mapping)
                else:
                    mapping.roblox_role_name = role_name
                    mapping.is_active = True

                # Auto-ensure default GroupPermissionRule exists for this group
                existing_rule = db_session().exec(
                    select(GroupPermissionRule).where(
                        GroupPermissionRule.group_id == tenant_id,
                        GroupPermissionRule.specific_role_id == role_id
                    )
                ).first()

                if not existing_rule:
                    if rank_val >= 250:
                        s_role = "hct"
                        perms = DEFAULT_ROLE_PERMISSIONS.get("hct", [])
                    elif rank_val >= 150:
                        s_role = "staff"
                        perms = DEFAULT_ROLE_PERMISSIONS.get("staff", [])
                    else:
                        s_role = "member"
                        perms = DEFAULT_ROLE_PERMISSIONS.get("member", [])

                    rule = GroupPermissionRule(
                        group_id=tenant_id,
                        min_roblox_rank=rank_val,
                        specific_role_id=role_id,
                        system_role=s_role,
                        permissions=perms
                    )
                    db_session().add(rule)

            db_session().commit()

        # Build reverse role-to-system-rank map for this tenant
        rank_mappings = db_session().exec(
            select(RankMapping).where(RankMapping.tenant_id == tenant_id, RankMapping.is_active == True)
        ).all()
        roblox_role_to_system_rank = {m.roblox_role_name: m.system_rank for m in rank_mappings if m.roblox_role_name}

        # Step 2: Fetch Members from Roblox
        roblox_members = roblox_api.get_group_members()
        if not roblox_members:
            return {'success': False, 'message': f'Failed to fetch members from Roblox for tenant {tenant_id}'}

        stats = {
            'added': 0,
            'updated': 0,
            'rank_changes': 0,
            'roles_mapped': len(roblox_roles) if roblox_roles else 0,
            'errors': 0
        }

        # Process members
        for roblox_member in roblox_members:
            try:
                role_name = roblox_member.role_name
                if isinstance(role_name, dict):
                    role_name = role_name.get('name', '')
                if not isinstance(role_name, str):
                    role_name = str(role_name) if role_name else ''

                # Resolve system rank
                system_rank = roblox_role_to_system_rank.get(role_name) or role_name
                if not system_rank or system_rank == 'Guest':
                    continue

                member = db_session().exec(
                    select(Member).where(
                        Member.tenant_id == tenant_id,
                        Member.roblox_id == str(roblox_member.user_id)
                    )
                ).first()

                if not member:
                    member = db_session().exec(
                        select(Member).where(
                            Member.tenant_id == tenant_id,
                            Member.roblox_username == roblox_member.username
                        )
                    ).first()

                if member:
                    current_rank = member.current_rank
                    if current_rank != system_rank:
                        old_rank = current_rank
                        member.current_rank = system_rank
                        promotion = PromotionLog(
                            tenant_id=tenant_id,
                            member_id=member.id,
                            from_rank=old_rank,
                            to_rank=system_rank,
                            reason="Automatic sync from Roblox group",
                            promoted_by="Roblox Sync Bot"
                        )
                        db_session().add(promotion)
                        stats['rank_changes'] += 1

                    if not member.roblox_id:
                        member.roblox_id = str(roblox_member.user_id)
                    if member.roblox_username != roblox_member.username:
                        member.roblox_username = roblox_member.username
                    member.last_updated = datetime.utcnow()
                    member.is_active = True
                    stats['updated'] += 1
                else:
                    new_member = Member(
                        tenant_id=tenant_id,
                        discord_username=roblox_member.username,
                        roblox_username=roblox_member.username,
                        roblox_id=str(roblox_member.user_id),
                        current_rank=system_rank,
                        join_date=datetime.utcnow(),
                        last_updated=datetime.utcnow(),
                        is_active=True
                    )
                    db_session().add(new_member)
                    stats['added'] += 1

            except Exception as e:
                logger.error(f"Error syncing member {getattr(roblox_member, 'username', 'unknown')}: {e}")
                stats['errors'] += 1

        # Check for inactive members
        roblox_user_ids = {str(m.user_id) for m in roblox_members}
        system_members = db_session().exec(
            select(Member).where(Member.tenant_id == tenant_id, Member.is_active == True)
        ).all()
        for member in system_members:
            if member.roblox_id and member.roblox_id not in roblox_user_ids:
                member.is_active = False
                member.last_updated = datetime.utcnow()

        db_session().commit()

        return {
            'success': True,
            'message': f'Synced from Roblox (Tenant {tenant_id}): {stats["added"]} added, {stats["updated"]} updated, {stats["rank_changes"]} rank changes, {stats["roles_mapped"]} roles mapped',
            'stats': stats
        }
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Error in sync_from_roblox for tenant {tenant_id}: {e}\n{error_trace}")
        db_session().rollback()
        return {'success': False, 'message': f'Error: {str(e)}'}
    finally:
        set_syncing_flag(False)


