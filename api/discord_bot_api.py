"""
Discord Bot API Module
Provides REST API endpoints for Discord bot integration with TF_System
"""


from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
import logging
_logger = logging.getLogger(__name__)

from services import ac_service, member_service
from utils.api_auth import verify_api_key, log_api_access
from config import settings
from datetime import datetime
import requests

# Create Blueprint
router = APIRouter()

async def _safe_get_json(request):
    try:
        data = await request.json()
        if isinstance(data, list):
            return data[0] if data else {}
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


# Discord webhook configuration
DISCORD_WEBHOOK_URL = None  # Will be set from config
NOTIFICATION_CHANNEL_ID = "1446175728025735393"


def send_discord_notification(message: str, title: str = "TF System Notification"):
    """Send notification to Discord channel via webhook"""
    webhook_url = settings.DISCORD_NOTIFICATION_WEBHOOK_URL
    
    if not webhook_url:
        _logger.warning("Discord webhook not configured, skipping notification")
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
        _logger.error(f"Failed to send Discord notification: {e}")
        return False


# ============================================================================
# SYSTEM STATUS
# ============================================================================

@router.get('/status', dependencies=[Depends(verify_api_key)])
async def get_status(request: Request,):
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
        _logger.error(f"Database check failed: {e}")
        db_status = "error"
        member_count = None
    
    # Check Roblox sync status
    roblox_sync = settings.ROBLOX_SYNC_ENABLED
    
    status_info = {
        'success': True,
        'status': 'online',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat(),
        'database': db_status,
        'roblox_sync': 'enabled' if roblox_sync else 'disabled',
        'total_members': member_count
    }
    
    log_api_access(request, '/status', 'GET', success=True, response_code=200)
    
    return JSONResponse(status_info, status_code=200)


# ============================================================================
# AUTHENTICATION
# ============================================================================

@router.post('/auth/verify', dependencies=[Depends(verify_api_key)])
async def verify_auth(request: Request):
    """
    Verify API authentication
    
    Returns:
        200: Authentication successful
    """
    log_api_access(request, '/auth/verify', 'POST', success=True, response_code=200)
    
    return JSONResponse({
        'success': True,
        'message': 'API key valid',
        'authenticated': True,
        'timestamp': datetime.utcnow().isoformat()
    }, status_code=200)


# ============================================================================
# MEMBER MANAGEMENT
# ============================================================================

@router.get('/members', dependencies=[Depends(verify_api_key)])
async def get_members(request: Request):
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
        search = request.query_params.get('search', '').strip()
        rank_filter = request.query_params.get('rank', '').strip() or None
        limit = min(int(request.query_params.get('limit', 100)), 500)  # Max 500

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
        
        log_api_access(request, '/members', 'GET', success=True, response_code=200)
        
        return JSONResponse({
            'success': True,
            'count': len(members_data),
            'members': members_data
        }, status_code=200)
        
    except Exception as e:
        _logger.error(f"Error getting members: {e}", exc_info=True)
        log_api_access(request, '/members', 'GET', success=False, response_code=500)
        return JSONResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Error retrieving members: {str(e)}'
        }, status_code=500)


@router.get('/members/search', dependencies=[Depends(verify_api_key)])
async def search_members(request: Request):
    """
    Search for members by name
    
    Query Parameters:
        q (str): Search query (required)
        field (str): Field to search (discord_username, roblox_username, both)
    
    Returns:
        200: Search results
    """
    try:
        query_str = request.query_params.get('q', '').strip()
        field = request.query_params.get('field', 'both').lower()
        
        if not query_str:
            return JSONResponse({
                'success': False,
                'error': 'missing_query',
                'message': 'Search query (q) is required'
            }, status_code=400)
        
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
        
        log_api_access(request, '/members/search', 'GET', success=True, response_code=200)
        
        return JSONResponse({
            'success': True,
            'query': query_str,
            'matches': matches,
            'count': len(matches)
        }, status_code=200)
        
    except Exception as e:
        _logger.error(f"Error searching members: {e}", exc_info=True)
        log_api_access(request, '/members/search', 'GET', success=False, response_code=500)
        return JSONResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Error searching members: {str(e)}'
        }, status_code=500)


@router.get('/members/{member_id}', dependencies=[Depends(verify_api_key)])
async def get_member(request: Request, member_id: int):
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
            log_api_access(request, f'/members/{member_id}', 'GET', success=False, response_code=404)
            return JSONResponse({
                'success': False,
                'error': 'member_not_found',
                'message': f'Member with ID {member_id} not found'
            }, status_code=404)

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
        
        log_api_access(request, f'/members/{member_id}', 'GET', success=True, response_code=200)
        
        return JSONResponse({
            'success': True,
            'member': member_data
        }, status_code=200)
        
    except Exception as e:
        _logger.error(f"Error getting member {member_id}: {e}", exc_info=True)
        log_api_access(request, f'/members/{member_id}', 'GET', success=False, response_code=500)
        return JSONResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Error retrieving member: {str(e)}'
        }, status_code=500)


    except Exception as e:
        _logger.error(f"Error searching members: {e}", exc_info=True)
        log_api_access(request, '/members/search', 'GET', success=False, response_code=500)
        return JSONResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Error searching members: {str(e)}'
        }, status_code=500)


@router.patch('/members/{member_id}/rank', dependencies=[Depends(verify_api_key)])
async def update_member_rank(request: Request, member_id: int):
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
        data = await _safe_get_json(request)
        new_rank = data.get('rank', '').strip()
        reason = data.get('reason', 'Promoted via Discord Bot').strip()
        promoted_by = data.get('promoted_by', 'Discord Bot').strip()
        discord_user_id = data.get('discord_user_id')
        
        if not new_rank:
            return JSONResponse({
                'success': False,
                'error': 'missing_rank',
                'message': 'Rank is required'
            }, status_code=400)

        result = member_service.promote_member(
            member_id,
            new_rank,
            reason=reason,
            promoted_by=promoted_by,
        )

        if not result['success']:
            if result.get('error') == 'member_not_found':
                log_api_access(request, f'/members/{member_id}/rank', 'PATCH', discord_user_id, False, 404)
                return JSONResponse({
                    'success': False,
                    'error': 'member_not_found',
                    'message': f'Member with ID {member_id} not found'
                }, status_code=404)
            if result.get('error') == 'invalid_rank':
                return JSONResponse({
                    'success': False,
                    'error': 'invalid_rank',
                    'message': result['message'],
                    'valid_ranks': result.get('valid_ranks', []),
                }, status_code=400)
            # Catch-all for any other failure (e.g. missing_rank, etc.)
            log_api_access(request, f'/members/{member_id}/rank', 'PATCH', discord_user_id, False, 400)
            return JSONResponse({
                'success': False,
                'error': result.get('error', 'unknown_error'),
                'message': result.get('message', 'An unknown error occurred'),
            }, status_code=400)

        member = result['member']
        old_rank = result['old_rank']


        if result.get('unchanged'):
            return JSONResponse({
                'success': True,
                'message': 'Rank unchanged (already at specified rank)',
                'member': {
                    'id': member.id,
                    'discord_username': member.discord_username,
                    'current_rank': member.current_rank
                }
            }, status_code=200)

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
        
        log_api_access(request, f'/members/{member_id}/rank', 'PATCH', discord_user_id, True, 200)
        
        return JSONResponse({
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
        }, status_code=200)
        
    except Exception as e:
        db.session.rollback()
        _logger.error(f"Error updating rank for member {member_id}: {e}", exc_info=True)
        log_api_access(request, f'/members/{member_id}/rank', 'PATCH', 
                      data.get('discord_user_id'), False, 500)
        return JSONResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Error updating rank: {str(e)}'
        }, status_code=500)


@router.post('/members', dependencies=[Depends(verify_api_key)])
async def add_member(request: Request):
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
        data = await _safe_get_json(request)
        discord_username = data.get('discord_username', '').strip()
        roblox_username = data.get('roblox_username', '').strip() or None
        current_rank = data.get('current_rank', 'Aspirant').strip()
        discord_user_id = data.get('discord_user_id')
        
        if not discord_username:
            return JSONResponse({
                'success': False,
                'error': 'missing_discord_username',
                'message': 'Discord username is required'
            }, status_code=400)

        result = member_service.create_member(
            discord_username,
            roblox_username=roblox_username,
            current_rank=current_rank,
        )

        if not result['success']:
            if result.get('error') == 'member_exists':
                log_api_access(request, '/members', 'POST', discord_user_id, False, 409)
                return JSONResponse({
                    'success': False,
                    'error': 'member_exists',
                    'message': result['message'],
                    'existing_member_id': result.get('existing_member_id'),
                }, status_code=409)
            return JSONResponse({
                'success': False,
                'error': result.get('error', 'validation_error'),
                'message': result.get('message', 'Failed to add member'),
            }, status_code=400)

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
        
        log_api_access(request, '/members', 'POST', discord_user_id, True, 201)
        
        return JSONResponse({
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
        }, status_code=201)
        
    except Exception as e:
        db.session.rollback()
        _logger.error(f"Error adding member: {e}", exc_info=True)
        log_api_access(request, '/members', 'POST', data.get('discord_user_id'), False, 500)
        return JSONResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Error adding member: {str(e)}'
        }, status_code=500)


@router.delete('/members/{member_id}', dependencies=[Depends(verify_api_key)])
async def remove_member(request: Request, member_id: int):
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
        data = await _safe_get_json(request)
        discord_user_id = data.get('discord_user_id')

        result = member_service.deactivate_member(member_id)

        if not result['success']:
            log_api_access(request, f'/members/{member_id}', 'DELETE', discord_user_id, False, 404)
            return JSONResponse({
                'success': False,
                'error': 'member_not_found',
                'message': result.get('message'),
            }, status_code=404)

        member_name = result.get('member_name', f'Member {member_id}')

        roblox_sync_result = result.get('roblox_sync', {'success': False, 'message': 'Roblox sync disabled'})
        
        # Send notification
        notification_sent = send_discord_notification(
            f"**Member Removed**\n"
            f"Discord: **{member_name}**\n"
            f"Roblox Sync: {'✅ Removed from group' if roblox_sync_result.get('success') else '⚠️ ' + roblox_sync_result.get('message', 'Failed')}",
            "Member Removed"
        )
        
        log_api_access(request, f'/members/{member_id}', 'DELETE', discord_user_id, True, 200)
        
        return JSONResponse({
            'success': True,
            'message': f'Member {member_name} removed successfully',
            'roblox_sync': roblox_sync_result,
            'notification_sent': notification_sent
        }, status_code=200)
        
    except Exception as e:
        db.session.rollback()
        _logger.error(f"Error removing member {member_id}: {e}", exc_info=True)
        log_api_access(request, f'/members/{member_id}', 'DELETE', 
                      data.get('discord_user_id'), False, 500)
        return JSONResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Error removing member: {str(e)}'
        }, status_code=500)


# ============================================================================
# RANK MANAGEMENT
# ============================================================================

@router.get('/ranks', dependencies=[Depends(verify_api_key)])
async def get_ranks(request: Request):
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
                    'rank_name': rank,
                    'roblox_role_id': None,
                    'roblox_role_name': None,
                    'is_active': True
                }
                for rank in default_ranks
            ]
        else:
            ranks_data = [
                {
                    'system_rank': r if isinstance(r, str) else getattr(r, 'system_rank', str(r)),
                    'rank_name': r if isinstance(r, str) else getattr(r, 'system_rank', str(r)),
                    'roblox_role_id': getattr(r, 'roblox_role_id', None) if not isinstance(r, str) else None,
                    'roblox_role_name': getattr(r, 'roblox_role_name', None) if not isinstance(r, str) else None,
                    'is_active': getattr(r, 'is_active', True) if not isinstance(r, str) else True
                }
                for r in rank_mappings
            ]
        
        log_api_access(request, '/ranks', 'GET', success=True, response_code=200)
        
        return JSONResponse({
            'success': True,
            'ranks': ranks_data,
            'count': len(ranks_data)
        }, status_code=200)
        
    except Exception as e:
        _logger.error(f"Error getting ranks: {e}", exc_info=True)
        log_api_access(request, '/ranks', 'GET', success=False, response_code=500)
        return JSONResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Error retrieving ranks: {str(e)}'
        }, status_code=500)


@router.get('/activity-types', dependencies=[Depends(verify_api_key)])
async def get_activity_types_api(request: Request):
    """
    Get all active activity types and their point values
    
    Returns:
        200: List of active activity types
    """
    try:
        activity_types = ac_service.get_all_activity_types(include_inactive=False)
        data = [act.to_dict() for act in activity_types]
        
        log_api_access(request, '/activity-types', 'GET', success=True, response_code=200)
        return JSONResponse({
            'success': True,
            'activity_types': data,
            'count': len(data)
        }, status_code=200)
    except Exception as e:
        _logger.error(f"Error getting activity types: {e}", exc_info=True)
        log_api_access(request, '/activity-types', 'GET', success=False, response_code=500)
        return JSONResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Error retrieving activity types: {str(e)}'
        }, status_code=500)


@router.get('/quotas', dependencies=[Depends(verify_api_key)])
async def get_quotas_api(request: Request):
    """
    Get all configured rank quotas
    
    Returns:
        200: List of rank quota requirements
    """
    try:
        quotas = ac_service.get_all_rank_quotas()
        data = [q.to_dict() for q in quotas]
        
        log_api_access(request, '/quotas', 'GET', success=True, response_code=200)
        return JSONResponse({
            'success': True,
            'quotas': data,
            'count': len(data)
        }, status_code=200)
    except Exception as e:
        _logger.error(f"Error getting rank quotas: {e}", exc_info=True)
        log_api_access(request, '/quotas', 'GET', success=False, response_code=500)
        return JSONResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Error retrieving rank quotas: {str(e)}'
        }, status_code=500)


# ============================================================================
# ACTIVITY MANAGEMENT
# ============================================================================

@router.post('/activity', dependencies=[Depends(verify_api_key)])
async def log_activity(request: Request,):
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
        data = await _safe_get_json(request)
        member_id = data.get('member_id')
        activity_type = data.get('activity_type', '').strip()
        description = data.get('description', '').strip()
        activity_date_str = data.get('activity_date')
        discord_user_id = data.get('discord_user_id')

        if not member_id:
            return JSONResponse({
                'success': False,
                'error': 'missing_member_id',
                'message': 'member_id is required'
            }, status_code=400)

        if not activity_type:
            return JSONResponse({
                'success': False,
                'error': 'missing_activity_type',
                'message': 'activity_type is required'
            }, status_code=400)

        activity_date = None
        if activity_date_str:
            try:
                activity_date = datetime.strptime(activity_date_str, '%Y-%m-%d')
            except ValueError:
                return JSONResponse({
                    'success': False,
                    'error': 'invalid_date_format',
                    'message': 'activity_date must be in YYYY-MM-DD format'
                }, status_code=400)

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
                log_api_access(request, '/activity', 'POST', discord_user_id, False, 404)
                return JSONResponse({
                    'success': False,
                    'error': 'member_not_found',
                    'message': result['message'],
                }, status_code=404)
            if error == 'no_active_period':
                log_api_access(request, '/activity', 'POST', discord_user_id, False, 404)
                return JSONResponse({
                    'success': False,
                    'error': 'no_active_period',
                    'message': result['message'],
                }, status_code=404)
            if error == 'invalid_activity_type':
                return JSONResponse({
                    'success': False,
                    'error': 'invalid_activity_type',
                    'message': result['message'],
                    'valid_types': result.get('valid_types', []),
                }, status_code=400)
            if error == 'limited_activity_exists':
                log_api_access(request, '/activity', 'POST', discord_user_id, False, 400)
                return JSONResponse({
                    'success': False,
                    'error': 'limited_activity_exists',
                    'message': f'Limited activity "{activity_type}" already logged for this period',
                }, status_code=400)

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

        log_api_access(request, '/activity', 'POST', discord_user_id, True, 201)

        return JSONResponse({
            'success': True,
            'message': f'Logged {quantity} activity entries',
            'activity': {
                'id': created_ids[0],
                'type': activity_type,
                'points': points * quantity,
                'date': activity_date.isoformat()
            },
            'quota_progress': quota_progress,
        }, status_code=201)

    except Exception as e:
        db.session.rollback()
        _logger.error(f"Error logging activity: {e}", exc_info=True)
        log_api_access(request, '/activity', 'POST', data.get('discord_user_id'), False, 500)
        return JSONResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Error logging activity: {str(e)}'
        }, status_code=500)


@router.get('/members/{member_id}/activities', dependencies=[Depends(verify_api_key)])
async def get_member_activities(request: Request, member_id: int):
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
        limit = min(int(request.query_params.get('limit', 50)), 1000)

        member = member_service.get_member(member_id, active_only=True)
        if not member:
            log_api_access(request, f'/members/{member_id}/activities', 'GET', success=False, response_code=404)
            return JSONResponse({
                'success': False,
                'error': 'member_not_found',
                'message': f'Member with ID {member_id} not found'
            }, status_code=404)

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
        
        log_api_access(request, f'/members/{member_id}/activities', 'GET', success=True, response_code=200)
        
        return JSONResponse({
            'success': True,
            'member': {
                'id': member.id,
                'discord_username': member.discord_username
            },
            'activities': activities_data,
            'count': len(activities_data)
        }, status_code=200)
        
    except Exception as e:
        _logger.error(f"Error getting activities for member {member_id}: {e}", exc_info=True)
        log_api_access(request, f'/members/{member_id}/activities', 'GET', success=False, response_code=500)
        return JSONResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Error retrieving activities: {str(e)}'
        }, status_code=500)


@router.delete('/activity/{activity_id}', dependencies=[Depends(verify_api_key)])
async def remove_activity(request: Request, activity_id: int):
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
        data = await _safe_get_json(request)
        discord_user_id = data.get('discord_user_id')

        result = ac_service.delete_activity_entry(activity_id)

        if not result['success']:
            log_api_access(request, '/activity/{id}', 'DELETE', discord_user_id, False, 404)
            return JSONResponse({
                'success': False,
                'error': 'activity_not_found',
                'message': result['message'],
            }, status_code=404)

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

        log_api_access(request, '/activity/{id}', 'DELETE', discord_user_id, True, 200)

        return JSONResponse({
            'success': True,
            'message': 'Activity removed successfully',
            'activity': {
                'id': activity_id,
                'type': activity_type,
                'points': points,
            },
            'quota_progress': quota_progress,
        }, status_code=200)

    except Exception as e:
        db.session.rollback()
        _logger.error(f"Error removing activity: {e}", exc_info=True)
        log_api_access(request, '/activity/{id}', 'DELETE', data.get('discord_user_id'), False, 500)
        return JSONResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Error removing activity: {str(e)}'
        }, status_code=500)


@router.get('/members/{member_id}/points', dependencies=[Depends(verify_api_key)])
async def get_member_points(request: Request, member_id: int):
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
            log_api_access(request, f'/members/{member_id}/points', 'GET', success=False, response_code=404)
            return JSONResponse({
                'success': False,
                'error': 'member_not_found',
                'message': f'Member with ID {member_id} not found'
            }, status_code=404)

        current_period = ac_service.get_active_period()
        if not current_period:
            log_api_access(request, f'/members/{member_id}/points', 'GET', success=False, response_code=404)
            return JSONResponse({
                'success': False,
                'error': 'no_active_period',
                'message': 'No active AC period'
            }, status_code=404)

        quota_progress = ac_service.get_quota_progress(member, current_period)
        
        log_api_access(request, f'/members/{member_id}/points', 'GET', success=True, response_code=200)

        return JSONResponse({
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
        }, status_code=200)
        
    except Exception as e:
        _logger.error(f"Error getting member points: {e}", exc_info=True)
        log_api_access(request, f'/members/{member_id}/points', 'GET', success=False, response_code=500)
        return JSONResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Error retrieving points: {str(e)}'
        }, status_code=500)


# ============================================================================
# BULK ACTIVITY REMOVAL BY TYPE
# ============================================================================

@router.delete('/members/{member_id}/activities/by-type', dependencies=[Depends(verify_api_key)])
async def remove_activities_by_type(request: Request, member_id: int):
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
        data = await _safe_get_json(request)
        activity_type = data.get('activity_type', '').strip()
        quantity = max(1, min(int(data.get('quantity', 1)), 999))
        discord_user_id = data.get('discord_user_id')

        if not activity_type:
            return JSONResponse({
                'success': False,
                'error': 'missing_activity_type',
                'message': 'activity_type is required',
            }, status_code=400)

        result = ac_service.delete_activities_by_type(
            member_id, activity_type, quantity=quantity
        )

        if not result['success']:
            error = result.get('error')
            status = 404 if error in ('member_not_found', 'no_activities_found') else 400
            log_api_access(request, 
                f'/members/{member_id}/activities/by-type', 'DELETE',
                discord_user_id, False, status
            )
            return JSONResponse(content={
                'success': False,
                'error': error,
                'message': result['message'],
            }, status_code=status)

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

        log_api_access(request, 
            f'/members/{member_id}/activities/by-type', 'DELETE',
            discord_user_id, True, 200
        )
        return JSONResponse({
            'success': True,
            'message': f'Removed {deleted} "{activity_type}" activity entries',
            'deleted': deleted,
            'activity_type': activity_type,
            'quota_progress': quota_progress,
        }, status_code=200)

    except Exception as e:
        db.session.rollback()
        _logger.error(
            f'Error bulk-removing activities for member {member_id}: {e}', exc_info=True
        )
        log_api_access(request, 
            f'/members/{member_id}/activities/by-type', 'DELETE',
            data.get('discord_user_id'), False, 500
        )
        return JSONResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Error removing activities: {str(e)}',
        }, status_code=500)


# ============================================================================
# ACTIVITY COUNT BY TYPE
# ============================================================================

@router.get('/members/{member_id}/activities/count', dependencies=[Depends(verify_api_key)])
async def count_member_activities(request: Request, member_id: int):
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
            log_api_access(request, 
                f'/members/{member_id}/activities/count', 'GET',
                success=False, response_code=404
            )
            return JSONResponse({
                'success': False,
                'error': 'member_not_found',
                'message': f'Member with ID {member_id} not found',
            }, status_code=404)

        activity_type = request.query_params.get('type', '').strip() or None
        period_only = request.query_params.get('period_only', 'false').lower() == 'true'

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

        log_api_access(request, 
            f'/members/{member_id}/activities/count', 'GET',
            success=True, response_code=200
        )
        return JSONResponse({
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
        }, status_code=200)

    except Exception as e:
        _logger.error(
            f'Error counting activities for member {member_id}: {e}', exc_info=True
        )
        log_api_access(request, 
            f'/members/{member_id}/activities/count', 'GET',
            success=False, response_code=500
        )
        return JSONResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Error counting activities: {str(e)}',
        }, status_code=500)

