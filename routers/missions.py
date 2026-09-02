from database.engine import db_session
"""
API Routes for Mission Tracking System
Missions posted in Discord with star difficulty.
"""

from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from utils.templates import templates, url_for
from utils.flash import flash
from database.models import Mission
from services import mission_service
from utils.api_auth import api_key_required

router = APIRouter()


@router.api_route('', methods=['POST'])
@api_key_required
async def create_mission(request: Request):
    """Create a new mission from Discord message."""
    try:
        data = (await request.json())
        result = mission_service.create_mission(data)

        if not result['success']:
            status_code = result.get('status_code', 400)
            payload = {'error': result['error']}
            if 'mission_id' in result:
                payload['mission_id'] = result['mission_id']
            return JSONResponse(payload), status_code

        return JSONResponse(content={
            'success': True,
            'mission': result['mission'].to_dict(),
        }, status_code=201)

    except Exception as e:
        from database.models import db
        db_session().rollback()
        return JSONResponse({'error': str(e)}, status_code=500)


@router.api_route('/by-message/<discord_message_id>', methods=['GET'])
@api_key_required
async def get_mission_by_message_id(request: Request, discord_message_id):
    """Get a mission by its Discord message ID"""
    try:
        mission = mission_service.get_mission_by_message_id(discord_message_id)

        if not mission:
            return JSONResponse({'error': 'Mission not found'}, status_code=404)

        return JSONResponse(content={
            'success': True,
            'id': mission.id,
            'title': mission.title,
            'stars': mission.stars,
            'completions': [c.to_dict() for c in mission.completions],
        }, status_code=200)

    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=500)


@router.api_route('/completions', methods=['POST'])
@api_key_required
async def log_mission_completions(request: Request):
    """Log mission completions or removals."""
    try:
        data = (await request.json())
        result = mission_service.log_mission_completions(
            data.get('mission_id'),
            verified_by_username=data.get('verified_by_username'),
            completers=data.get('completers', []),
            deleted_completers=data.get('deleted_completers', []),
        )

        if not result['success']:
            return JSONResponse({'error': result['error']}, status_code=404)

        return JSONResponse(content={
            'success': True,
            'stats': result['stats'],
        }, status_code=200)

    except Exception as e:
        from database.models import db
        db_session().rollback()
        return JSONResponse({'error': str(e)}, status_code=500)


@router.api_route('/monthly-stats/leaderboard', methods=['GET'])
@api_key_required
async def get_monthly_leaderboard(request: Request):
    """Get current month's mission leaderboard sorted by stars"""
    try:
        cycle_month, stats = mission_service.get_monthly_leaderboard()

        return JSONResponse(content={
            'success': True,
            'cycle_month': cycle_month.strftime('%Y-%m'),
            'leaderboard': [s.to_dict() for s in stats],
        }, status_code=200)

    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=500)


@router.api_route('/health', methods=['GET'])
async def health_check(request: Request):
    """Simple health check endpoint"""
    return JSONResponse({'status': 'ok', 'service': 'missions'}, status_code=200)
