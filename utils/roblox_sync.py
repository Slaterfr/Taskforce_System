"""
Roblox Two-Way Sync Module
Handles synchronization between the system and Roblox group
"""

import os
from typing import Optional, Dict
from datetime import datetime
from flask import current_app
from database.models import db, Member, RankMapping, PromotionLog
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

def get_roblox_api() -> Optional[RobloxAPI]:
    """Get configured RobloxAPI instance"""
    group_id = current_app.config.get('ROBLOX_GROUP_ID')
    cookie = current_app.config.get('ROBLOX_COOKIE')
    
    # Debug logging
    if not group_id:
        current_app.logger.warning("Roblox API not configured: ROBLOX_GROUP_ID is missing or empty")
        return None
    
    # Check if group_id is just whitespace
    if isinstance(group_id, str) and not group_id.strip():
        current_app.logger.warning("Roblox API not configured: ROBLOX_GROUP_ID is empty string")
        return None
    
    try:
        group_id_int = int(group_id)
    except (ValueError, TypeError) as e:
        current_app.logger.error(f"Roblox API not configured: ROBLOX_GROUP_ID '{group_id}' is not a valid integer: {e}")
        return None
    
    return RobloxAPI(group_id_int, cookie=cookie)

def get_role_id_for_rank(system_rank: str) -> Optional[int]:
    """Get Roblox role ID for a system rank"""
    # Ensure system_rank is a string
    if not isinstance(system_rank, str):
        if isinstance(system_rank, dict):
            current_app.logger.warning(f"get_role_id_for_rank received dict instead of string: {system_rank}")
            return None
        system_rank = str(system_rank) if system_rank else 'Aspirant'
    
    try:
        mapping = RankMapping.query.filter_by(
            system_rank=system_rank,
            is_active=True
        ).first()
        
        return mapping.roblox_role_id if mapping else None
    except Exception as e:
        current_app.logger.error(f"Error in get_role_id_for_rank with rank '{system_rank}': {e}")
        return None

def sync_member_to_roblox(member: Member, skip_if_syncing: bool = True) -> Dict:
    """
    Sync a member's rank to Roblox group
    Returns: {'success': bool, 'message': str}
    """
    if skip_if_syncing and _syncing_from_roblox:
        current_app.logger.info(f"Skipping sync for {member.discord_username} - currently syncing from Roblox")
        return {'success': True, 'message': 'Skipped - syncing from Roblox'}
    
    current_app.logger.info(f"Attempting to sync {member.discord_username} (rank: {member.current_rank}) to Roblox")
    
    roblox_api = get_roblox_api()
    if not roblox_api:
        error_msg = 'Roblox API not configured'
        current_app.logger.error(error_msg)
        return {'success': False, 'message': error_msg}
    
    if not member.roblox_id:
        error_msg = f'Member {member.discord_username} has no Roblox ID'
        current_app.logger.warning(error_msg)
        return {'success': False, 'message': error_msg}
    
    role_id = get_role_id_for_rank(member.current_rank)
    if not role_id:
        error_msg = f'No role mapping found for rank: {member.current_rank}'
        current_app.logger.warning(error_msg)
        return {'success': False, 'message': error_msg}
    
    try:
        user_id = int(member.roblox_id)
        current_app.logger.info(f"Updating Roblox user {user_id} to role {role_id} (rank: {member.current_rank})")
        success, error_msg = roblox_api.update_member_role(user_id, role_id)
        
        if success:
            success_msg = f'Updated {member.discord_username} to {member.current_rank} in Roblox'
            current_app.logger.info(success_msg)
            return {'success': True, 'message': success_msg}
        else:
            error_msg_full = f'Failed to update role in Roblox: {error_msg}'
            current_app.logger.error(f"Roblox sync failed for {member.discord_username}: {error_msg_full}")
            return {'success': False, 'message': error_msg_full}
    except (ValueError, TypeError) as e:
        error_msg = f'Invalid Roblox ID: {member.roblox_id} ({str(e)})'
        current_app.logger.error(error_msg)
        return {'success': False, 'message': error_msg}
    except Exception as e:
        error_msg = f'Error updating role: {str(e)}'
        current_app.logger.error(f"Unexpected error syncing {member.discord_username} to Roblox: {error_msg}", exc_info=True)
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
        group_id = current_app.config.get('ROBLOX_GROUP_ID', 'Not set')
        cookie_set = bool(current_app.config.get('ROBLOX_COOKIE'))
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
        db.session.commit()
    
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

def sync_from_roblox():
    """
    Sync members from Roblox group to system
    This is called by the background polling task
    """
    set_syncing_flag(True)
    
    try:
        roblox_api = get_roblox_api()
        if not roblox_api:
            return {'success': False, 'message': 'Roblox API not configured'}
        
        # Get all members from Roblox
        roblox_members = roblox_api.get_group_members()
        if not roblox_members:
            return {'success': False, 'message': 'Failed to fetch members from Roblox'}
        
        # Get all roles to create mapping
        roblox_roles = roblox_api.get_group_roles()
        role_name_to_id = {}
        for role in roblox_roles:
            if isinstance(role, dict):
                role_name = role.get('name', '')
                role_id = role.get('id')
                if role_name and role_id:
                    role_name_to_id[str(role_name)] = role_id
        
        # Get rank mappings (reverse: roblox role name -> system rank)
        # Also use the RANK_MAPPING from roblox_api as fallback
        from api.roblox_api import RANK_MAPPING
        rank_mappings = RankMapping.query.filter_by(is_active=True).all()
        roblox_role_to_system_rank = {}
        for mapping in rank_mappings:
            if mapping.roblox_role_name:
                roblox_role_to_system_rank[mapping.roblox_role_name] = mapping.system_rank
        
        # Also add reverse mapping from RANK_MAPPING (system rank -> roblox rank)
        # We need to match by role name from Roblox
        for roblox_role in roblox_roles:
            if not isinstance(roblox_role, dict):
                continue
            role_name = roblox_role.get('name', '')
            if not isinstance(role_name, str):
                role_name = str(role_name) if role_name else ''
            # Check if this role name maps to a system rank
            if role_name and role_name in RANK_MAPPING:
                system_rank = RANK_MAPPING[role_name]
                if isinstance(system_rank, str):
                    roblox_role_to_system_rank[role_name] = system_rank
        
        stats = {
            'added': 0,
            'updated': 0,
            'rank_changes': 0,
            'errors': 0
        }
        
        # Process each Roblox member
        for roblox_member in roblox_members:
            try:
                # Ensure role_name is a string
                role_name = roblox_member.role_name
                if isinstance(role_name, dict):
                    role_name = role_name.get('name', '') if isinstance(role_name, dict) else str(role_name)
                if not isinstance(role_name, str):
                    role_name = str(role_name) if role_name else ''
                
                # Find member by Roblox ID, Roblox Username, or Discord Username (fallback)
                # We check these sequentially to prioritize ID match
                member = Member.query.filter_by(roblox_id=str(roblox_member.user_id)).first()
                
                if not member:
                    member = Member.query.filter_by(roblox_username=roblox_member.username).first()
                
                if not member:
                    member = Member.query.filter_by(discord_username=roblox_member.username).first()
                
                system_rank = roblox_role_to_system_rank.get(role_name)
                if not system_rank:
                    # Try to use role name directly if no mapping
                    system_rank = role_name
                
                # Ensure system_rank is a string
                if not isinstance(system_rank, str):
                    system_rank = str(system_rank) if system_rank else 'Aspirant'
                
                if member:
                    # Check for ID mismatch (collision protection)
                    if member.roblox_id and member.roblox_id != str(roblox_member.user_id):
                        # We found a member (likely by username), but they have a DIFFERENT Roblox ID.
                        # This implies a name collision (different person) or they changed accounts.
                        # We cannot safely sync this user without manual intervention.
                        current_app.logger.warning(
                            f"Sync collision: Roblox user {roblox_member.username} ({roblox_member.user_id}) "
                            f"matches Member {member.discord_username} ({member.id}) but Roblox IDs differ "
                            f"({member.roblox_id} vs {roblox_member.user_id}). Skipping."
                        )
                        continue

                    # Update existing member
                    rank_changed = False
                    # Ensure member.current_rank is a string for comparison
                    current_rank = member.current_rank
                    if not isinstance(current_rank, str):
                        current_rank = str(current_rank) if current_rank else 'Aspirant'
                        member.current_rank = current_rank
                    
                    if current_rank != system_rank:
                        old_rank = current_rank
                        member.current_rank = system_rank
                        rank_changed = True
                        
                        # Log promotion
                        promotion = PromotionLog(
                            member_id=member.id,
                            from_rank=old_rank,
                            to_rank=system_rank,
                            reason="Automatic sync from Roblox group",
                            promoted_by="Roblox Sync Bot"
                        )
                        db.session.add(promotion)
                        stats['rank_changes'] += 1
                    
                    # Update Roblox info
                    if not member.roblox_id:
                        member.roblox_id = str(roblox_member.user_id)
                    if member.roblox_username != roblox_member.username:
                        member.roblox_username = roblox_member.username
                    
                    member.last_updated = datetime.utcnow()
                    stats['updated'] += 1
                else:
                    # New member - add to system
                    # Only add if they have a mapped rank (Aspirant+)
                    eligible_ranks = ['Aspirant', 'Novice', 'Adept', 'Crusader', 'Paladin', 
                                     'Exemplar', 'Prospect', 'Commander', 'Marshal', 'General', 'Chief General']
                    # Ensure system_rank is a string for comparison
                    if isinstance(system_rank, str) and system_rank in eligible_ranks:
                        new_member = Member(
                            discord_username=roblox_member.username,  # Will be updated when Discord is linked
                            roblox_username=roblox_member.username,
                            roblox_id=str(roblox_member.user_id),
                            current_rank=system_rank,
                            join_date=datetime.utcnow(),
                            last_updated=datetime.utcnow()
                        )
                        db.session.add(new_member)
                        stats['added'] += 1
                
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                current_app.logger.error(f"Error syncing member {getattr(roblox_member, 'username', 'unknown')}: {e}\n{error_details}")
                print(f"❌ Error syncing member: {e}")
                stats['errors'] += 1
        
        # Check for members in system but not in Roblox (they may have left)
        roblox_user_ids = {str(m.user_id) for m in roblox_members}
        system_members = Member.query.filter_by(is_active=True).all()
        
        for member in system_members:
            if member.roblox_id and member.roblox_id not in roblox_user_ids:
                # Member is in system but not in Roblox - mark as inactive
                # (Don't auto-delete, just mark inactive for manual review)
                if member.is_active:
                    member.is_active = False
                    member.last_updated = datetime.utcnow()
        
        db.session.commit()
        
        return {
            'success': True,
            'message': f'Synced from Roblox: {stats["added"]} added, {stats["updated"]} updated, {stats["rank_changes"]} rank changes',
            'stats': stats
        }
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        current_app.logger.error(f"Error in sync_from_roblox: {e}\n{error_trace}")
        print(f"❌ Full error trace:\n{error_trace}")
        db.session.rollback()
        return {'success': False, 'message': f'Error: {str(e)}'}
    finally:
        set_syncing_flag(False)

