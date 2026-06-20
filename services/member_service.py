"""Member management business logic."""

from datetime import datetime

from flask import current_app

from database.models import db, Member, PromotionLog, RankMapping, ActivityLog
from utils.roblox_sync import add_member_to_roblox, remove_member_from_roblox, sync_member_to_roblox

DEFAULT_RANKS = [
    'Aspirant', 'Novice', 'Adept', 'Crusader', 'Paladin',
    'Exemplar', 'Prospect', 'Commander', 'Marshal', 'General', 'Chief General',
]


def get_available_ranks():
    """Return active rank names from mappings, or the default rank list."""
    rank_mappings = RankMapping.query.filter_by(is_active=True).order_by(
        RankMapping.system_rank
    ).all()
    if rank_mappings:
        return [mapping.system_rank for mapping in rank_mappings]
    return DEFAULT_RANKS.copy()


def get_member(member_id, *, active_only=True):
    """Fetch a member by ID."""
    query = Member.query.filter_by(id=member_id)
    if active_only:
        query = query.filter_by(is_active=True)
    return query.first()


def find_by_discord_username(discord_username):
    """Find a member by Discord username (any active state)."""
    return Member.query.filter_by(discord_username=discord_username).first()


def search_members(search='', *, active_only=True, limit=None, rank_filter=None):
    """Search members by username or rank, with optional rank and limit filters."""
    query = Member.query.filter_by(is_active=True) if active_only else Member.query
    if search:
        pattern = f'%{search}%'
        query = query.filter(
            (Member.discord_username.ilike(pattern))
            | (Member.roblox_username.ilike(pattern))
            | (Member.current_rank.ilike(pattern))
        )
    if rank_filter:
        from sqlalchemy import func as _func
        query = query.filter(_func.lower(Member.current_rank) == rank_filter.lower())
    query = query.order_by(Member.current_rank, Member.discord_username)
    if limit is not None:
        query = query.limit(limit)
    return query.all()



def _roblox_sync_enabled():
    return current_app.config.get('ROBLOX_SYNC_ENABLED', False)


def create_member(discord_username, roblox_username=None, current_rank='Aspirant'):
    """
    Create a new member.

    Returns ``success``, optional ``error``, the ``member``, and ``roblox_sync`` result.
    """
    discord_username = (discord_username or '').strip()
    roblox_username = (roblox_username or '').strip() or None
    current_rank = (current_rank or 'Aspirant').strip()

    if not discord_username:
        return {
            'success': False,
            'error': 'missing_discord_username',
            'message': 'Discord username is required',
        }

    existing = find_by_discord_username(discord_username)
    if existing:
        return {
            'success': False,
            'error': 'member_exists',
            'message': f'Member with Discord username "{discord_username}" already exists',
            'existing_member_id': existing.id,
        }

    member = Member(
        discord_username=discord_username,
        roblox_username=roblox_username,
        current_rank=current_rank,
        join_date=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )
    db.session.add(member)
    db.session.commit()

    roblox_sync_result = {'success': False, 'message': 'No Roblox username provided'}
    if _roblox_sync_enabled() and roblox_username:
        roblox_sync_result = add_member_to_roblox(member)

    return {
        'success': True,
        'member': member,
        'roblox_sync': roblox_sync_result,
    }


def update_member_profile(member_id, *, discord_username=None, roblox_username=None, current_rank=None):
    """
    Update member profile fields and optionally sync rank changes to Roblox.

    Returns ``success``, ``member``, ``rank_changed``, and ``roblox_sync``.
    """
    member = get_member(member_id, active_only=False)
    if not member:
        return {
            'success': False,
            'error': 'member_not_found',
            'message': f'Member with ID {member_id} not found',
        }

    old_rank = member.current_rank

    if discord_username is not None:
        member.discord_username = discord_username.strip()
    if roblox_username is not None:
        member.roblox_username = roblox_username.strip() or None
    if current_rank is not None:
        member.current_rank = current_rank.strip()

    member.last_updated = datetime.utcnow()
    db.session.commit()

    rank_changed = old_rank != member.current_rank
    roblox_sync_result = {'success': False, 'message': 'Roblox sync disabled'}

    if _roblox_sync_enabled() and rank_changed and member.roblox_id:
        current_app.logger.info(
            f"Syncing {member.discord_username} rank change: {old_rank} -> {member.current_rank}"
        )
        roblox_sync_result = sync_member_to_roblox(member)
    elif _roblox_sync_enabled() and rank_changed and not member.roblox_id:
        roblox_sync_result = {
            'success': False,
            'message': 'Cannot sync to Roblox (no Roblox ID)',
        }

    return {
        'success': True,
        'member': member,
        'old_rank': old_rank,
        'rank_changed': rank_changed,
        'roblox_sync': roblox_sync_result,
    }


def deactivate_member(member_id):
    """Mark a member inactive and optionally remove them from Roblox."""
    member = get_member(member_id)
    if not member:
        return {
            'success': False,
            'error': 'member_not_found',
            'message': f'Member with ID {member_id} not found',
        }

    member_name = member.discord_username
    member.is_active = False
    member.last_updated = datetime.utcnow()

    roblox_sync_result = {'success': False, 'message': 'Roblox sync disabled'}
    if _roblox_sync_enabled() and member.roblox_id:
        roblox_sync_result = remove_member_from_roblox(member)

    db.session.commit()

    return {
        'success': True,
        'member_name': member_name,
        'roblox_sync': roblox_sync_result,
    }


def promote_member(member_id, new_rank, *, reason='', promoted_by='Staff'):
    """
    Promote a member, record promotion history, and optionally sync to Roblox.
    """
    member = get_member(member_id)
    if not member:
        return {
            'success': False,
            'error': 'member_not_found',
            'message': 'Member not found',
        }

    new_rank = (new_rank or '').strip()
    if not new_rank:
        return {
            'success': False,
            'error': 'missing_rank',
            'message': 'Rank is required',
        }

    valid_ranks = get_available_ranks()
    if new_rank not in valid_ranks:
        return {
            'success': False,
            'error': 'invalid_rank',
            'message': f'Rank "{new_rank}" is not valid',
            'valid_ranks': valid_ranks,
        }

    old_rank = member.current_rank
    if old_rank == new_rank:
        return {
            'success': True,
            'unchanged': True,
            'member': member,
            'old_rank': old_rank,
            'new_rank': new_rank,
            'roblox_sync': {'success': True, 'message': 'Rank unchanged'},
        }

    member.current_rank = new_rank
    member.last_updated = datetime.utcnow()

    promotion = PromotionLog(
        member_id=member.id,
        from_rank=old_rank,
        to_rank=new_rank,
        reason=reason,
        promoted_by=promoted_by,
        promotion_date=datetime.utcnow(),
    )
    db.session.add(promotion)
    db.session.commit()

    roblox_sync_result = {'success': False, 'message': 'Roblox sync disabled'}
    if _roblox_sync_enabled() and member.roblox_id:
        current_app.logger.info(
            f"Syncing {member.discord_username} promotion: {old_rank} -> {new_rank}"
        )
        roblox_sync_result = sync_member_to_roblox(member)
    elif _roblox_sync_enabled() and not member.roblox_id:
        roblox_sync_result = {
            'success': False,
            'message': 'Cannot sync to Roblox (no Roblox ID)',
        }

    return {
        'success': True,
        'member': member,
        'old_rank': old_rank,
        'new_rank': new_rank,
        'roblox_sync': roblox_sync_result,
    }


def get_dashboard_data():
    """Return dashboard statistics and recent activity logs."""
    member_count = Member.query.filter_by(is_active=True).count()
    recent_activities = ActivityLog.query.order_by(ActivityLog.log_date.desc()).limit(5).all()
    return {
        'member_count': member_count,
        'recent_activities': recent_activities
    }


def get_member_profile_details(member_id):
    """Return member profile, activity logs, and promotion history."""
    member = get_member(member_id, active_only=False)
    if not member:
        return None
    activities = ActivityLog.query.filter_by(member_id=member_id).order_by(ActivityLog.log_date.desc()).all()
    promotions = PromotionLog.query.filter_by(member_id=member_id).order_by(PromotionLog.promotion_date.desc()).all()
    return {
        'member': member,
        'activities': activities,
        'promotions': promotions
    }


def get_all_active_members():
    """Return all active members ordered by Discord username."""
    return Member.query.filter_by(is_active=True).order_by(Member.discord_username).all()


def get_public_member_data(member_id):
    """Return member profile and their latest 5 activity entries for public view."""
    member = get_member(member_id, active_only=True)
    if not member:
        return None
    from database.ac_models import ActivityEntry
    recent_activities = ActivityEntry.query.filter_by(member_id=member_id).order_by(
        ActivityEntry.activity_date.desc()
    ).limit(5).all()
    return {
        'member': member,
        'recent_activities': recent_activities
    }


def get_all_rank_mappings():
    """Return all rank mappings ordered by system rank."""
    return RankMapping.query.order_by(RankMapping.system_rank).all()


def add_or_update_rank_mapping(system_rank, roblox_role_id, roblox_role_name=None):
    """Add a new mapping or update an existing one."""
    system_rank = (system_rank or '').strip()
    if not system_rank or not roblox_role_id:
        return {'success': False, 'message': 'System rank and Roblox role ID are required'}

    existing = RankMapping.query.filter_by(system_rank=system_rank).first()
    if existing:
        existing.roblox_role_id = roblox_role_id
        existing.roblox_role_name = roblox_role_name
        existing.is_active = True
        existing.last_updated = datetime.utcnow()
        message = f'Updated mapping for {system_rank}'
    else:
        mapping = RankMapping(
            system_rank=system_rank,
            roblox_role_id=roblox_role_id,
            roblox_role_name=roblox_role_name,
            last_updated=datetime.utcnow()
        )
        db.session.add(mapping)
        message = f'Added mapping for {system_rank}'

    db.session.commit()
    return {'success': True, 'message': message}


def delete_rank_mapping(mapping_id):
    """Delete a rank mapping by ID."""
    mapping = RankMapping.query.get(mapping_id)
    if mapping:
        db.session.delete(mapping)
        db.session.commit()
        return True
    return False


def toggle_rank_mapping(mapping_id):
    """Toggle is_active on a rank mapping."""
    mapping = RankMapping.query.get(mapping_id)
    if mapping:
        mapping.is_active = not mapping.is_active
        mapping.last_updated = datetime.utcnow()
        db.session.commit()
        return True
    return False



