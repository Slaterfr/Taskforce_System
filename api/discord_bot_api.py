"""
Discord Bot API Module
Provides REST API endpoints for Discord bot integration with TF_System
"""

from flask import Blueprint, request, jsonify, current_app
from database.models import db, Member, RankMapping, PromotionLog, ActivityLog
from database.ac_models import (
    ACPeriod, ActivityEntry, InactivityNotice, ACExemption,
    ACTIVITY_TYPES, get_activity_points, get_member_quota
)
from utils.api_auth import api_key_required, log_api_access
from utils.roblox_sync import sync_member_to_roblox, add_member_to_roblox, remove_member_from_roblox
from sqlalchemy import or_, func
from datetime import datetime
import requests

# Create Blueprint
api_bp = Blueprint('discord_bot_api', __name__)

# Discord webhook configuration
DISCORD_WEBHOOK_URL = None  # Will be set from config
NOTIFICATION_CHANNEL_ID = "1446175728025735393"


def send_discord_notification(message: str, title: str = "TF System Notification"):
    """Send notification to Discord channel via webhook"""
    webhook_url = current_app.config.get('DISCORD_NOTIFICATION_WEBHOOK_URL')
    
    if not webhook_url:
        current_app.logger.warning("Discord webhook not configured, skipping notification")
        return False
    
    try:
        payload = {
            "embeds": [{
                "title": title,
                "description": message,
                "color": 5814783,  # Blue color
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": "TF System Bot Integration"
                }
            }]
        }
        
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send Discord notification: {e}")
        return False


# ============================================================================
# SYSTEM STATUS
# ============================================================================

@api_bp.route('/status', methods=['GET'])
@api_key_required
def get_status():
    """
    Get API and system status
    
    Returns:
        200: System status information
    """
    try:
        # Check database connection
        member_count = Member.query.filter_by(is_active=True).count()
        db_status = "connected"
    except Exception as e:
        current_app.logger.error(f"Database check failed: {e}")
        db_status = "error"
        member_count = None
    
    # Check Roblox sync status
    roblox_sync = current_app.config.get('ROBLOX_SYNC_ENABLED', False)
    
    status_info = {
        'success': True,
        'status': 'online',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat(),
        'database': db_status,
        'roblox_sync': 'enabled' if roblox_sync else 'disabled',
        'total_members': member_count
    }
    
    log_api_access('/status', 'GET', success=True, response_code=200)
    
    return jsonify(status_info), 200


# ============================================================================
# AUTHENTICATION
# ============================================================================

@api_bp.route('/auth/verify', methods=['POST'])
@api_key_required
def verify_auth():
    """
    Verify API authentication
    
    Returns:
        200: Authentication successful
    """
    log_api_access('/auth/verify', 'POST', success=True, response_code=200)
    
    return jsonify({
        'success': True,
        'message': 'API key valid',
        'authenticated': True,
        'timestamp': datetime.utcnow().isoformat()
    }), 200


# ============================================================================
# MEMBER MANAGEMENT
# ============================================================================

@api_bp.route('/members', methods=['GET'])
@api_key_required
def get_members():
    """
    Get list of all active members
    
    Query Parameters:
        search (str): Search by username or rank
        rank (str): Filter by specific rank
        limit (int): Limit number of results (default: 100)
    
    Returns:
        200: List of members
    """
    try:
        search = request.args.get('search', '').strip()
        rank_filter = request.args.get('rank', '').strip()
        limit = min(int(request.args.get('limit', 100)), 500)  # Max 500
        
        query = Member.query.filter_by(is_active=True)
        
        # Apply search filter
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Member.discord_username.ilike(search_pattern),
                    Member.roblox_username.ilike(search_pattern),
                    Member.current_rank.ilike(search_pattern)
                )
            )
        
        # Apply rank filter
        if rank_filter:
            query = query.filter(func.lower(Member.current_rank) == rank_filter.lower())
        
        members = query.order_by(Member.current_rank, Member.discord_username).limit(limit).all()
        
        members_data = [
            {
                'id': m.id,
                'discord_username': m.discord_username,
                'roblox_username': m.roblox_username,
                'roblox_id': m.roblox_id,
                'current_rank': m.current_rank,
                'join_date': m.join_date.isoformat() if m.join_date else None,
                'last_updated': m.last_updated.isoformat() if m.last_updated else None
            }
            for m in members
        ]
        
        log_api_access('/members', 'GET', success=True, response_code=200)
        
        return jsonify({
            'success': True,
            'count': len(members_data),
            'members': members_data
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting members: {e}", exc_info=True)
        log_api_access('/members', 'GET', success=False, response_code=500)
        return jsonify({
            'success': False,
            'error': 'server_error',
            'message': f'Error retrieving members: {str(e)}'
        }), 500


@api_bp.route('/members/<int:member_id>', methods=['GET'])
@api_key_required
def get_member(member_id):
    """
    Get detailed information about a specific member
    
    Args:
        member_id: Member ID
    
    Returns:
        200: Member details
        404: Member not found
    """
    try:
        member = Member.query.filter_by(id=member_id, is_active=True).first()
        
        if not member:
            log_api_access(f'/members/{member_id}', 'GET', success=False, response_code=404)
            return jsonify({
                'success': False,
                'error': 'member_not_found',
                'message': f'Member with ID {member_id} not found'
            }), 404
        
        # Get recent activities
        recent_activities = ActivityEntry.query.filter_by(member_id=member_id) \
            .order_by(ActivityEntry.activity_date.desc()).limit(10).all()
        
        # Get rank history
        rank_history = PromotionLog.query.filter_by(member_id=member_id) \
            .order_by(PromotionLog.promotion_date.desc()).limit(5).all()
        
        member_data = {
            'id': member.id,
            'discord_username': member.discord_username,
            'roblox_username': member.roblox_username,
            'roblox_id': member.roblox_id,
            'current_rank': member.current_rank,
            'join_date': member.join_date.isoformat() if member.join_date else None,
            'last_updated': member.last_updated.isoformat() if member.last_updated else None,
            'recent_activities': [
                {
                    'type': a.activity_type,
                    'date': a.activity_date.isoformat() if a.activity_date else None,
                    'points': float(a.points) if a.points else 0.0,
                    'description': a.description
                }
                for a in recent_activities
            ],
            'rank_history': [
                {
                    'from_rank': p.from_rank,
                    'to_rank': p.to_rank,
                    'date': p.promotion_date.isoformat() if p.promotion_date else None,
                    'promoted_by': p.promoted_by,
                    'reason': p.reason
                }
                for p in rank_history
            ]
        }
        
        log_api_access(f'/members/{member_id}', 'GET', success=True, response_code=200)
        
        return jsonify({
            'success': True,
            'member': member_data
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting member {member_id}: {e}", exc_info=True)
        log_api_access(f'/members/{member_id}', 'GET', success=False, response_code=500)
        return jsonify({
            'success': False,
            'error': 'server_error',
            'message': f'Error retrieving member: {str(e)}'
        }), 500


@api_bp.route('/members/search', methods=['GET'])
@api_key_required
def search_members():
    """
    Search for members by name
    
    Query Parameters:
        q (str): Search query (required)
        field (str): Field to search (discord_username, roblox_username, both)
    
    Returns:
        200: Search results
    """
    try:
        query_str = request.args.get('q', '').strip()
        field = request.args.get('field', 'both').lower()
        
        if not query_str:
            return jsonify({
                'success': False,
                'error': 'missing_query',
                'message': 'Search query (q) is required'
            }), 400
        
        search_pattern = f"%{query_str}%"
        query = Member.query.filter_by(is_active=True)
        
        if field == 'discord_username':
            query = query.filter(Member.discord_username.ilike(search_pattern))
        elif field == 'roblox_username':
            query = query.filter(Member.roblox_username.ilike(search_pattern))
        else:  # both
            query = query.filter(
                or_(
                    Member.discord_username.ilike(search_pattern),
                    Member.roblox_username.ilike(search_pattern)
                )
            )
        
        members = query.limit(20).all()
        
        matches = [
            {
                'id': m.id,
                'discord_username': m.discord_username,
                'roblox_username': m.roblox_username,
                'current_rank': m.current_rank
            }
            for m in members
        ]
        
        log_api_access('/members/search', 'GET', success=True, response_code=200)
        
        return jsonify({
            'success': True,
            'query': query_str,
            'matches': matches,
            'count': len(matches)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error searching members: {e}", exc_info=True)
        log_api_access('/members/search', 'GET', success=False, response_code=500)
        return jsonify({
            'success': False,
            'error': 'server_error',
            'message': f'Error searching members: {str(e)}'
        }), 500


@api_bp.route('/members/<int:member_id>/rank', methods=['PATCH'])
@api_key_required
def update_member_rank(member_id):
    """
    Update a member's rank
    
    Args:
        member_id: Member ID
    
    Request Body:
        rank (str): New rank name
        reason (str): Reason for rank change (optional)
        promoted_by (str): Who promoted them (optional)
        discord_user_id (str): Discord user ID who made the change (optional)
    
    Returns:
        200: Rank updated successfully
        400: Invalid rank
        404: Member not found
    """
    try:
        data = request.get_json() or {}
        new_rank = data.get('rank', '').strip()
        reason = data.get('reason', 'Promoted via Discord Bot').strip()
        promoted_by = data.get('promoted_by', 'Discord Bot').strip()
        discord_user_id = data.get('discord_user_id')
        
        if not new_rank:
            return jsonify({
                'success': False,
                'error': 'missing_rank',
                'message': 'Rank is required'
            }), 400
        
        # Get member
        member = Member.query.filter_by(id=member_id, is_active=True).first()
        
        if not member:
            log_api_access(f'/members/{member_id}/rank', 'PATCH', discord_user_id, False, 404)
            return jsonify({
                'success': False,
                'error': 'member_not_found',
                'message': f'Member with ID {member_id} not found'
            }), 404
        
        # Validate rank
        valid_ranks = [m.system_rank for m in RankMapping.query.filter_by(is_active=True).all()]
        if not valid_ranks:
            valid_ranks = ['Aspirant', 'Novice', 'Adept', 'Crusader', 'Paladin', 
                          'Exemplar', 'Prospect', 'Commander', 'Marshal', 'General', 'Chief General']
        
        if new_rank not in valid_ranks:
            return jsonify({
                'success': False,
                'error': 'invalid_rank',
                'message': f'Rank "{new_rank}" is not valid',
                'valid_ranks': valid_ranks
            }), 400
        
        old_rank = member.current_rank
        
        # Check if rank actually changed
        if old_rank == new_rank:
            return jsonify({
                'success': True,
                'message': 'Rank unchanged (already at specified rank)',
                'member': {
                    'id': member.id,
                    'discord_username': member.discord_username,
                    'current_rank': member.current_rank
                }
            }), 200
        
        # Update rank
        member.current_rank = new_rank
        member.last_updated = datetime.utcnow()
        
        # Log promotion
        promotion = PromotionLog(
            member_id=member.id,
            from_rank=old_rank,
            to_rank=new_rank,
            reason=reason,
            promoted_by=promoted_by
        )
        db.session.add(promotion)
        db.session.commit()
        
        # Sync to Roblox if enabled
        roblox_sync_result = {'success': False, 'message': 'Roblox sync disabled'}
        if current_app.config.get('ROBLOX_SYNC_ENABLED') and member.roblox_id:
            roblox_sync_result = sync_member_to_roblox(member)
        
        # Send Discord notification
        notification_sent = send_discord_notification(
            f"**Rank Change**\n"
            f"Member: **{member.discord_username}**\n"
            f"Old Rank: {old_rank}\n"
            f"New Rank: **{new_rank}**\n"
            f"Changed by: {promoted_by}\n"
            f"Reason: {reason}\n"
            f"Roblox Sync: {'✅ Success' if roblox_sync_result.get('success') else '❌ ' + roblox_sync_result.get('message', 'Failed')}",
            "Rank Update"
        )
        
        log_api_access(f'/members/{member_id}/rank', 'PATCH', discord_user_id, True, 200)
        
        return jsonify({
            'success': True,
            'message': f'Rank updated successfully from {old_rank} to {new_rank}',
            'member': {
                'id': member.id,
                'discord_username': member.discord_username,
                'roblox_username': member.roblox_username,
                'old_rank': old_rank,
                'new_rank': new_rank
            },
            'roblox_sync': roblox_sync_result,
            'notification_sent': notification_sent
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating rank for member {member_id}: {e}", exc_info=True)
        log_api_access(f'/members/{member_id}/rank', 'PATCH', 
                      data.get('discord_user_id'), False, 500)
        return jsonify({
            'success': False,
            'error': 'server_error',
            'message': f'Error updating rank: {str(e)}'
        }), 500


@api_bp.route('/members', methods=['POST'])
@api_key_required
def add_member():
    """
    Add a new member to the system
    
    Request Body:
        discord_username (str): Discord username (required)
        roblox_username (str): Roblox username (optional)
        current_rank (str): Initial rank (default: Aspirant)
        discord_user_id (str): Discord user ID who added (optional)
    
    Returns:
        201: Member created successfully
        400: Validation error
        409: Member already exists
    """
    try:
        data = request.get_json() or {}
        discord_username = data.get('discord_username', '').strip()
        roblox_username = data.get('roblox_username', '').strip() or None
        current_rank = data.get('current_rank', 'Aspirant').strip()
        discord_user_id = data.get('discord_user_id')
        
        if not discord_username:
            return jsonify({
                'success': False,
                'error': 'missing_discord_username',
                'message': 'Discord username is required'
            }), 400
        
        # Check if member already exists
        existing = Member.query.filter_by(discord_username=discord_username).first()
        if existing:
            log_api_access('/members', 'POST', discord_user_id, False, 409)
            return jsonify({
                'success': False,
                'error': 'member_exists',
                'message': f'Member with Discord username "{discord_username}" already exists',
                'existing_member_id': existing.id
            }), 409
        
        # Create new member
        new_member = Member(
            discord_username=discord_username,
            roblox_username=roblox_username,
            current_rank=current_rank,
            join_date=datetime.utcnow(),
            last_updated=datetime.utcnow()
        )
        db.session.add(new_member)
        db.session.commit()
        
        # Try to add to Roblox if username provided
        roblox_sync_result = {'success': False, 'message': 'No RobloxUsername provided'}
        if current_app.config.get('ROBLOX_SYNC_ENABLED') and roblox_username:
            roblox_sync_result = add_member_to_roblox(new_member)
        
        # Send notification
        notification_sent = send_discord_notification(
            f"**New Member Added**\n"
            f"Discord: **{discord_username}**\n"
            f"Roblox: {roblox_username or 'Not set'}\n"
            f"Rank: {current_rank}\n"
            f"Roblox Sync: {'✅ Success' if roblox_sync_result.get('success') else '⚠️ ' + roblox_sync_result.get('message', 'Skipped')}",
            "Member Added"
        )
        
        log_api_access('/members', 'POST', discord_user_id, True, 201)
        
        return jsonify({
            'success': True,
            'message': 'Member added successfully',
            'member': {
                'id': new_member.id,
                'discord_username': new_member.discord_username,
                'roblox_username': new_member.roblox_username,
                'current_rank': new_member.current_rank
            },
            'roblox_sync': roblox_sync_result,
            'notification_sent': notification_sent
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding member: {e}", exc_info=True)
        log_api_access('/members', 'POST', data.get('discord_user_id'), False, 500)
        return jsonify({
            'success': False,
            'error': 'server_error',
            'message': f'Error adding member: {str(e)}'
        }), 500


@api_bp.route('/members/<int:member_id>', methods=['DELETE'])
@api_key_required
def remove_member(member_id):
    """
    Remove a member (mark as inactive)
    
    Args:
        member_id: Member ID
    
    Request Body:
        discord_user_id (str): Discord user ID who removed (optional)
    
    Returns:
        200: Member removed successfully
        404: Member not found
    """
    try:
        data = request.get_json() or {}
        discord_user_id = data.get('discord_user_id')
        
        member = Member.query.filter_by(id=member_id, is_active=True).first()
        
        if not member:
            log_api_access(f'/members/{member_id}', 'DELETE', discord_user_id, False, 404)
            return jsonify({
                'success': False,
                'error': 'member_not_found',
                'message': f'Member with ID {member_id} not found'
            }), 404
        
        # Mark as inactive
        member_name = member.discord_username
        member.is_active = False
        member.last_updated = datetime.utcnow()
        
        # Try to remove from Roblox
        roblox_sync_result = {'success': False, 'message': 'Roblox sync disabled'}
        if current_app.config.get('ROBLOX_SYNC_ENABLED') and member.roblox_id:
            roblox_sync_result = remove_member_from_roblox(member)
        
        db.session.commit()
        
        # Send notification
        notification_sent = send_discord_notification(
            f"**Member Removed**\n"
            f"Discord: **{member_name}**\n"
            f"Roblox Sync: {'✅ Removed from group' if roblox_sync_result.get('success') else '⚠️ ' + roblox_sync_result.get('message', 'Failed')}",
            "Member Removed"
        )
        
        log_api_access(f'/members/{member_id}', 'DELETE', discord_user_id, True, 200)
        
        return jsonify({
            'success': True,
            'message': f'Member {member_name} removed successfully',
            'roblox_sync': roblox_sync_result,
            'notification_sent': notification_sent
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error removing member {member_id}: {e}", exc_info=True)
        log_api_access(f'/members/{member_id}', 'DELETE', 
                      data.get('discord_user_id'), False, 500)
        return jsonify({
            'success': False,
            'error': 'server_error',
            'message': f'Error removing member: {str(e)}'
        }), 500


# ============================================================================
# RANK MANAGEMENT
# ============================================================================

@api_bp.route('/ranks', methods=['GET'])
@api_key_required
def get_ranks():
    """
    Get list of all available ranks with Roblox mappings
    
    Returns:
        200: List of ranks
    """
    try:
        rank_mappings = RankMapping.query.filter_by(is_active=True) \
            .order_by(RankMapping.system_rank).all()
        
        if not rank_mappings:
            # Return default ranks if no mappings exist
            default_ranks = ['Aspirant', 'Novice', 'Adept', 'Crusader', 'Paladin',
                           'Exemplar', 'Prospect', 'Commander', 'Marshal', 'General', 'Chief General']
            ranks_data = [
                {
                    'system_rank': rank,
                    'roblox_role_id': None,
                    'roblox_role_name': None,
                    'is_active': True
                }
                for rank in default_ranks
            ]
        else:
            ranks_data = [
                {
                    'system_rank': r.system_rank,
                    'roblox_role_id': r.roblox_role_id,
                    'roblox_role_name': r.roblox_role_name,
                    'is_active': r.is_active
                }
                for r in rank_mappings
            ]
        
        log_api_access('/ranks', 'GET', success=True, response_code=200)
        
        return jsonify({
            'success': True,
            'ranks': ranks_data,
            'count': len(ranks_data)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting ranks: {e}", exc_info=True)
        log_api_access('/ranks', 'GET', success=False, response_code=500)
        return jsonify({
            'success': False,
            'error': 'server_error',
            'message': f'Error retrieving ranks: {str(e)}'
        }), 500


# ============================================================================
# ACTIVITY MANAGEMENT
# ============================================================================

@api_bp.route('/activity', methods=['POST'])
@api_key_required
def log_activity():
    """
    Log an activity for a member
    
    Request Body:
        member_id (int): Member ID (required)
        activity_type (str): Type of activity (required)
        description (str): Activity description (optional)
        activity_date (str): Date in YYYY-MM-DD format (default: today)
        quantity (int): Number of activities to log (default: 1, max: 999)
        discord_user_id (str): Discord user ID who logged (optional)
    
    Returns:
        201: Activity logged successfully
        400: Validation error
        404: Member not found or no active AC period
    """
    try:
        data = request.get_json() or {}
        member_id = data.get('member_id')
        activity_type = data.get('activity_type', '').strip()
        description = data.get('description', '').strip()
        activity_date_str = data.get('activity_date')
        discord_user_id = data.get('discord_user_id')
        
        # Validation
        if not member_id:
            return jsonify({
                'success': False,
                'error': 'missing_member_id',
                'message': 'member_id is required'
            }), 400
        
        if not activity_type:
            return jsonify({
                'success': False,
                'error': 'missing_activity_type',
                'message': 'activity_type is required'
            }), 400
        
        if activity_type not in ACTIVITY_TYPES:
            return jsonify({
                'success': False,
                'error': 'invalid_activity_type',
                'message': f'Invalid activity type "{activity_type}"',
                'valid_types': list(ACTIVITY_TYPES.keys())
            }), 400
        
        # Get member
        member = Member.query.filter_by(id=member_id, is_active=True).first()
        if not member:
            log_api_access('/activity', 'POST', discord_user_id, False, 404)
            return jsonify({
                'success': False,
                'error': 'member_not_found',
                'message': f'Member with ID {member_id} not found'
            }), 404
        
        # Get active AC period
        current_period = ACPeriod.query.filter_by(is_active=True).first()
        if not current_period:
            log_api_access('/activity', 'POST', discord_user_id, False, 404)
            return jsonify({
                'success': False,
                'error': 'no_active_period',
                'message': 'No active AC period. Please create one first.'
            }), 404
        
        # Parse activity date
        if activity_date_str:
            try:
                activity_date = datetime.strptime(activity_date_str, '%Y-%m-%d')
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'invalid_date_format',
                    'message': 'activity_date must be in YYYY-MM-DD format'
                }), 400
        else:
            activity_date = datetime.utcnow()
        
        # Get points for activity type
        points = get_activity_points(activity_type)
        
        # Get quantity (default to 1, force 1 for cancelled events)
        quantity = int(data.get('quantity', 1))
        if activity_type in ['Cancelled Tryout', 'Canceled Training']:
            quantity = 1
        quantity = max(1, min(999, quantity))  # Clamp between 1 and 999
        
        # Check limited activity rule (check once regardless of quantity)
        if is_limited_activity(activity_type):
            existing = ActivityEntry.query.filter_by(
                member_id=member_id,
                ac_period_id=current_period.id,
                activity_type=activity_type
            ).first()
            if existing:
                log_api_access('/activity', 'POST', discord_user_id, False, 400)
                return jsonify({
                    'success': False,
                    'error': 'limited_activity_exists',
                    'message': f'Limited activity "{activity_type}" already logged for this period'
                }), 400
        
        # Determine who logged this activity
        logged_by = data.get('logged_by', f'Discord Bot')
        if discord_user_id and not data.get('logged_by'):
            logged_by = f'Discord User {discord_user_id}'
        
        # Create multiple activity entries based on quantity
        created_entries = []
        for i in range(quantity):
            activity_entry = ActivityEntry(
                member_id=member_id,
                ac_period_id=current_period.id,
                activity_type=activity_type,
                activity_date=activity_date,
                points=points,
                description=description or f"{activity_type} logged via Discord",
                logged_by=logged_by,
                is_limited_activity=is_limited_activity(activity_type)
            )
            db.session.add(activity_entry)
            db.session.flush()  # Get the ID before committing
            created_entries.append({
                'id': activity_entry.id,
                'activity_type': activity_type,
                'points': float(points)
            })
        
        db.session.commit()
        
        log_api_access('/activity', 'POST', discord_user_id, True, 201)
        
        return jsonify({
            'success': True,
            'message': f'Successfully logged {quantity} {activity_type} activit{"ies" if quantity > 1 else "y"}',
            'count': quantity,
            'total_points': float(points * quantity),
            'member': {
                'id': member_id,
                'discord_username': member.discord_username
            },
            'activities': created_entries
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error logging activity: {e}", exc_info=True)
        log_api_access('/activity', 'POST', data.get('discord_user_id'), False, 500)
        return jsonify({
            'success': False,
            'error': 'server_error',
            'message': f'Error logging activity: {str(e)}'
        }), 500


@api_bp.route('/members/<int:member_id>/activities', methods=['GET'])
@api_key_required
def get_member_activities(member_id):
    """
    Get activities for a specific member
    
    Args:
        member_id: Member ID
    
    Query Parameters:
        limit (int): Number of activities to return (default: 20)
    
    Returns:
        200: Activity list
        404: Member not found
    """
    try:
        limit = min(int(request.args.get('limit', 20)), 100)
        
        member = Member.query.filter_by(id=member_id, is_active=True).first()
        if not member:
            log_api_access(f'/members/{member_id}/activities', 'GET', success=False, response_code=404)
            return jsonify({
                'success': False,
                'error': 'member_not_found',
                'message': f'Member with ID {member_id} not found'
            }), 404
        
        activities = ActivityEntry.query.filter_by(member_id=member_id) \
            .order_by(ActivityEntry.activity_date.desc()).limit(limit).all()
        
        activities_data = [
            {
                'id': a.id,
                'activity_type': a.activity_type,
                'points': float(a.points) if a.points else 0.0,
                'activity_date': a.activity_date.isoformat() if a.activity_date else None,
                'description': a.description
            }
            for a in activities
        ]
        
        log_api_access(f'/members/{member_id}/activities', 'GET', success=True, response_code=200)
        
        return jsonify({
            'success': True,
            'member': {
                'id': member.id,
                'discord_username': member.discord_username
            },
            'activities': activities_data,
            'count': len(activities_data)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting activities for member {member_id}: {e}", exc_info=True)
        log_api_access(f'/members/{member_id}/activities', 'GET', success=False, response_code=500)
        return jsonify({
            'success': False,
            'error': 'server_error',
            'message': f'Error retrieving activities: {str(e)}'
        }), 500
