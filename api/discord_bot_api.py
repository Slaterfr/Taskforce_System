"""
Discord Bot API Module
Provides REST API endpoints for Discord bot integration with TF_System
"""

from flask import Blueprint, request, jsonify, current_app
from database.models import db
from services import ac_service, member_service
from utils.api_auth import api_key_required, log_api_access
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
        dashboard = member_service.get_dashboard_data()
        member_count = dashboard.get('member_count')
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
        rank_filter = request.args.get('rank', '').strip() or None
        limit = min(int(request.args.get('limit', 100)), 500)  # Max 500

        members = member_service.search_members(
            search, rank_filter=rank_filter, limit=limit
        )

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
        member = member_service.get_member(member_id, active_only=True)

        if not member:
            log_api_access(f'/members/{member_id}', 'GET', success=False, response_code=404)
            return jsonify({
                'success': False,
                'error': 'member_not_found',
                'message': f'Member with ID {member_id} not found'
            }), 404

        profile = member_service.get_member_profile_details(member_id)
        recent_activities = ac_service.get_member_activities(member_id, limit=10)
        rank_history = profile['promotions'][:5] if profile else []

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
        
        # search_members covers discord_username, roblox_username, and rank
        members = member_service.search_members(query_str, limit=20)

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

        result = member_service.promote_member(
            member_id,
            new_rank,
            reason=reason,
            promoted_by=promoted_by,
        )

        if not result['success']:
            if result.get('error') == 'member_not_found':
                log_api_access(f'/members/{member_id}/rank', 'PATCH', discord_user_id, False, 404)
                return jsonify({
                    'success': False,
                    'error': 'member_not_found',
                    'message': f'Member with ID {member_id} not found'
                }), 404
            if result.get('error') == 'invalid_rank':
                return jsonify({
                    'success': False,
                    'error': 'invalid_rank',
                    'message': result['message'],
                    'valid_ranks': result.get('valid_ranks', []),
                }), 400
            # Catch-all for any other failure (e.g. missing_rank, etc.)
            log_api_access(f'/members/{member_id}/rank', 'PATCH', discord_user_id, False, 400)
            return jsonify({
                'success': False,
                'error': result.get('error', 'unknown_error'),
                'message': result.get('message', 'An unknown error occurred'),
            }), 400

        member = result['member']
        old_rank = result['old_rank']


        if result.get('unchanged'):
            return jsonify({
                'success': True,
                'message': 'Rank unchanged (already at specified rank)',
                'member': {
                    'id': member.id,
                    'discord_username': member.discord_username,
                    'current_rank': member.current_rank
                }
            }), 200

        roblox_sync_result = result.get('roblox_sync', {'success': False, 'message': 'Roblox sync disabled'})
        
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

        result = member_service.create_member(
            discord_username,
            roblox_username=roblox_username,
            current_rank=current_rank,
        )

        if not result['success']:
            if result.get('error') == 'member_exists':
                log_api_access('/members', 'POST', discord_user_id, False, 409)
                return jsonify({
                    'success': False,
                    'error': 'member_exists',
                    'message': result['message'],
                    'existing_member_id': result.get('existing_member_id'),
                }), 409
            return jsonify({
                'success': False,
                'error': result.get('error', 'validation_error'),
                'message': result.get('message', 'Failed to add member'),
            }), 400

        new_member = result['member']
        roblox_sync_result = result.get('roblox_sync', {'success': False, 'message': 'No RobloxUsername provided'})
        
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

        result = member_service.deactivate_member(member_id)

        if not result['success']:
            log_api_access(f'/members/{member_id}', 'DELETE', discord_user_id, False, 404)
            return jsonify({
                'success': False,
                'error': 'member_not_found',
                'message': result.get('message'),
            }), 404

        member_name = result.get('member_name', f'Member {member_id}')

        roblox_sync_result = result.get('roblox_sync', {'success': False, 'message': 'Roblox sync disabled'})
        
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
        rank_mappings = member_service.get_available_ranks()

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

        activity_date = None
        if activity_date_str:
            try:
                activity_date = datetime.strptime(activity_date_str, '%Y-%m-%d')
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'invalid_date_format',
                    'message': 'activity_date must be in YYYY-MM-DD format'
                }), 400

        logged_by = data.get('logged_by', 'Discord Bot')
        if discord_user_id and not data.get('logged_by'):
            logged_by = f'Discord User {discord_user_id}'

        result = ac_service.log_activity(
            member_id,
            activity_type,
            activity_date=activity_date,
            description=description or f"{activity_type} logged via Discord",
            logged_by=logged_by,
            quantity=data.get('quantity', 1),
            mark_limited=True,
        )

        if not result['success']:
            error = result.get('error')
            if error == 'member_not_found':
                log_api_access('/activity', 'POST', discord_user_id, False, 404)
                return jsonify({
                    'success': False,
                    'error': 'member_not_found',
                    'message': result['message'],
                }), 404
            if error == 'no_active_period':
                log_api_access('/activity', 'POST', discord_user_id, False, 404)
                return jsonify({
                    'success': False,
                    'error': 'no_active_period',
                    'message': result['message'],
                }), 404
            if error == 'invalid_activity_type':
                return jsonify({
                    'success': False,
                    'error': 'invalid_activity_type',
                    'message': result['message'],
                    'valid_types': result.get('valid_types', []),
                }), 400
            if error == 'limited_activity_exists':
                log_api_access('/activity', 'POST', discord_user_id, False, 400)
                return jsonify({
                    'success': False,
                    'error': 'limited_activity_exists',
                    'message': f'Limited activity "{activity_type}" already logged for this period',
                }), 400

        member = result['member']
        quantity = result['count']
        points = result['points']
        activity_date = result['activity_date']
        quota_progress = result['quota_progress']
        created_ids = result['activity_ids']

        qty_str = f" (x{quantity})" if quantity > 1 else ""
        notification_message = (
            f"**Activity Logged**\n"
            f"Activity: **{activity_type}**{qty_str}\n"
            f"Points: {points * quantity}\n"
            f"Member: **{member.discord_username}**\n"
            f"Logged by: {logged_by}\n"
            f"New Total: **{quota_progress['total_points']}/{quota_progress['quota']} points** "
            f"({round(quota_progress['percentage'], 1)}%)"
        )
        if description:
            notification_message += f"\nDescription: {description}"
        notification_message += f"\nDate: {activity_date.strftime('%Y-%m-%d')}"

        send_discord_notification(notification_message, title="Activity Log")

        log_api_access('/activity', 'POST', discord_user_id, True, 201)

        return jsonify({
            'success': True,
            'message': f'Logged {quantity} activity entries',
            'activity': {
                'id': created_ids[0],
                'type': activity_type,
                'points': points * quantity,
                'date': activity_date.isoformat()
            },
            'quota_progress': quota_progress,
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
        limit = min(int(request.args.get('limit', 50)), 1000)

        member = member_service.get_member(member_id, active_only=True)
        if not member:
            log_api_access(f'/members/{member_id}/activities', 'GET', success=False, response_code=404)
            return jsonify({
                'success': False,
                'error': 'member_not_found',
                'message': f'Member with ID {member_id} not found'
            }), 404

        activities = ac_service.get_member_activities(member_id, limit=limit)

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


@api_bp.route('/activity/<int:activity_id>', methods=['DELETE'])
@api_key_required
def remove_activity(activity_id):
    """
    Remove/delete an activity entry
    
    Args:
        activity_id: Activity ID to remove
    
    Request Body:
        discord_user_id (str): Discord user ID who is removing (optional)
    
    Returns:
        200: Activity removed successfully
        404: Activity not found
    """
    try:
        data = request.get_json() or {}
        discord_user_id = data.get('discord_user_id')

        result = ac_service.delete_activity_entry(activity_id)

        if not result['success']:
            log_api_access('/activity/<id>', 'DELETE', discord_user_id, False, 404)
            return jsonify({
                'success': False,
                'error': 'activity_not_found',
                'message': result['message'],
            }), 404

        member = result['member']
        activity_type = result['activity_type']
        points = result['points']
        quota_progress = result['quota_progress']

        notification_message = (
            f"**Activity Removed**\n"
            f"Activity: **{activity_type}** ({points} pts)\n"
            f"Member: **{member.discord_username if member else 'Unknown'}**\n"
            f"Removed by: {f'Discord User {discord_user_id}' if discord_user_id else 'API'}\n"
            f"New Total: **{quota_progress['total_points']}/{quota_progress['quota']} points** "
            f"({round(quota_progress['percentage'], 1)}%)"
        )
        send_discord_notification(notification_message, title="Activity Removed")

        log_api_access('/activity/<id>', 'DELETE', discord_user_id, True, 200)

        return jsonify({
            'success': True,
            'message': 'Activity removed successfully',
            'activity': {
                'id': activity_id,
                'type': activity_type,
                'points': points,
            },
            'quota_progress': quota_progress,
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error removing activity: {e}", exc_info=True)
        log_api_access('/activity/<id>', 'DELETE', data.get('discord_user_id'), False, 500)
        return jsonify({
            'success': False,
            'error': 'server_error',
            'message': f'Error removing activity: {str(e)}'
        }), 500


@api_bp.route('/members/<int:member_id>/points', methods=['GET'])
@api_key_required
def get_member_points(member_id):
    """
    Get a member's current AC points and quota progress
    
    Args:
        member_id: Member ID
    
    Returns:
        200: Member's current AC points and quota
        404: Member not found
    """
    try:
        member = member_service.get_member(member_id, active_only=True)
        if not member:
            log_api_access(f'/members/{member_id}/points', 'GET', success=False, response_code=404)
            return jsonify({
                'success': False,
                'error': 'member_not_found',
                'message': f'Member with ID {member_id} not found'
            }), 404

        current_period = ac_service.get_active_period()
        if not current_period:
            log_api_access(f'/members/{member_id}/points', 'GET', success=False, response_code=404)
            return jsonify({
                'success': False,
                'error': 'no_active_period',
                'message': 'No active AC period'
            }), 404

        quota_progress = ac_service.get_quota_progress(member, current_period)
        
        log_api_access(f'/members/{member_id}/points', 'GET', success=True, response_code=200)

        return jsonify({
            'success': True,
            'member': {
                'id': member.id,
                'discord_username': member.discord_username,
                'current_rank': member.current_rank
            },
            'points': {
                'total_points': quota_progress['total_points'],
                'quota': quota_progress['quota'],
                'percentage': quota_progress['percentage'],
                'period_name': current_period.period_name
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting member points: {e}", exc_info=True)
        log_api_access(f'/members/{member_id}/points', 'GET', success=False, response_code=500)
        return jsonify({
            'success': False,
            'error': 'server_error',
            'message': f'Error retrieving points: {str(e)}'
        }), 500


# ============================================================================
# BULK ACTIVITY REMOVAL BY TYPE
# ============================================================================

@api_bp.route('/members/<int:member_id>/activities/by-type', methods=['DELETE'])
@api_key_required
def remove_activities_by_type(member_id):
    """
    Remove the N most-recent activity entries of a given type for a member.

    Request Body:
        activity_type (str): Activity type to remove (required)
        quantity     (int): How many to remove — default 1, max 999
        discord_user_id (str): Who is removing (optional, for logging)

    Returns:
        200: Activities removed with updated quota progress
        400: Missing / invalid parameters
        404: Member or activities not found
    """
    try:
        data = request.get_json() or {}
        activity_type = data.get('activity_type', '').strip()
        quantity = max(1, min(int(data.get('quantity', 1)), 999))
        discord_user_id = data.get('discord_user_id')

        if not activity_type:
            return jsonify({
                'success': False,
                'error': 'missing_activity_type',
                'message': 'activity_type is required',
            }), 400

        result = ac_service.delete_activities_by_type(
            member_id, activity_type, quantity=quantity
        )

        if not result['success']:
            error = result.get('error')
            status = 404 if error in ('member_not_found', 'no_activities_found') else 400
            log_api_access(
                f'/members/{member_id}/activities/by-type', 'DELETE',
                discord_user_id, False, status
            )
            return jsonify({
                'success': False,
                'error': error,
                'message': result['message'],
            }), status

        member = result['member']
        deleted = result['deleted']
        quota_progress = result['quota_progress']

        notification_message = (
            f"**{deleted} Activity{'s' if deleted > 1 else ''} Removed**\n"
            f"Activity: **{activity_type}**\n"
            f"Member: **{member.discord_username}**\n"
            f"Removed by: {f'Discord User {discord_user_id}' if discord_user_id else 'API'}\n"
            f"New Total: **{quota_progress['total_points']}/{quota_progress['quota']} points** "
            f"({round(quota_progress['percentage'], 1)}%)"
        )
        send_discord_notification(notification_message, title="Activities Removed")

        log_api_access(
            f'/members/{member_id}/activities/by-type', 'DELETE',
            discord_user_id, True, 200
        )
        return jsonify({
            'success': True,
            'message': f'Removed {deleted} "{activity_type}" activity entries',
            'deleted': deleted,
            'activity_type': activity_type,
            'quota_progress': quota_progress,
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f'Error bulk-removing activities for member {member_id}: {e}', exc_info=True
        )
        log_api_access(
            f'/members/{member_id}/activities/by-type', 'DELETE',
            data.get('discord_user_id'), False, 500
        )
        return jsonify({
            'success': False,
            'error': 'server_error',
            'message': f'Error removing activities: {str(e)}',
        }), 500


# ============================================================================
# ACTIVITY COUNT BY TYPE
# ============================================================================

@api_bp.route('/members/<int:member_id>/activities/count', methods=['GET'])
@api_key_required
def count_member_activities(member_id):
    """
    Count activity entries for a member, optionally filtered by type and/or
    the current AC period.

    Query Parameters:
        type        (str):  Filter to a specific activity type (optional)
        period_only (bool): If "true", restrict count to the active AC period

    Returns:
        200: {count: int, breakdown: {type: count, ...}}
        404: Member not found
    """
    try:
        member = member_service.get_member(member_id, active_only=True)
        if not member:
            log_api_access(
                f'/members/{member_id}/activities/count', 'GET',
                success=False, response_code=404
            )
            return jsonify({
                'success': False,
                'error': 'member_not_found',
                'message': f'Member with ID {member_id} not found',
            }), 404

        activity_type = request.args.get('type', '').strip() or None
        period_only = request.args.get('period_only', 'false').lower() == 'true'

        period_id = None
        if period_only:
            active_period = ac_service.get_active_period()
            period_id = active_period.id if active_period else None

        result = ac_service.count_activities_by_type(
            member_id, activity_type=activity_type, period_id=period_id
        )

        if activity_type:
            count = result  # scalar int
            breakdown = {activity_type: count}
        else:
            breakdown = result
            count = sum(breakdown.values())

        log_api_access(
            f'/members/{member_id}/activities/count', 'GET',
            success=True, response_code=200
        )
        return jsonify({
            'success': True,
            'member': {
                'id': member.id,
                'discord_username': member.discord_username,
            },
            'filters': {
                'activity_type': activity_type,
                'period_only': period_only,
            },
            'count': count,
            'breakdown': breakdown,
        }), 200

    except Exception as e:
        current_app.logger.error(
            f'Error counting activities for member {member_id}: {e}', exc_info=True
        )
        log_api_access(
            f'/members/{member_id}/activities/count', 'GET',
            success=False, response_code=500
        )
        return jsonify({
            'success': False,
            'error': 'server_error',
            'message': f'Error counting activities: {str(e)}',
        }), 500
