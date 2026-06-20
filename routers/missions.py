"""
API Routes for Mission Tracking System
Missions posted in Discord with star difficulty.
"""

from flask import Blueprint, jsonify, request
from database.models import Mission
from services import mission_service
from utils.api_auth import api_key_required

missions_bp = Blueprint('missions', __name__)


@missions_bp.route('', methods=['POST'])
@api_key_required
def create_mission():
    """Create a new mission from Discord message."""
    try:
        data = request.get_json()
        result = mission_service.create_mission(data)

        if not result['success']:
            status_code = result.get('status_code', 400)
            payload = {'error': result['error']}
            if 'mission_id' in result:
                payload['mission_id'] = result['mission_id']
            return jsonify(payload), status_code

        return jsonify({
            'success': True,
            'mission': result['mission'].to_dict(),
        }), 201

    except Exception as e:
        from database.models import db
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@missions_bp.route('/by-message/<discord_message_id>', methods=['GET'])
@api_key_required
def get_mission_by_message_id(discord_message_id):
    """Get a mission by its Discord message ID"""
    try:
        mission = mission_service.get_mission_by_message_id(discord_message_id)

        if not mission:
            return jsonify({'error': 'Mission not found'}), 404

        return jsonify({
            'success': True,
            'id': mission.id,
            'title': mission.title,
            'stars': mission.stars,
            'completions': [c.to_dict() for c in mission.completions],
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@missions_bp.route('/completions', methods=['POST'])
@api_key_required
def log_mission_completions():
    """Log mission completions or removals."""
    try:
        data = request.get_json()
        result = mission_service.log_mission_completions(
            data.get('mission_id'),
            verified_by_username=data.get('verified_by_username'),
            completers=data.get('completers', []),
            deleted_completers=data.get('deleted_completers', []),
        )

        if not result['success']:
            return jsonify({'error': result['error']}), 404

        return jsonify({
            'success': True,
            'stats': result['stats'],
        }), 200

    except Exception as e:
        from database.models import db
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@missions_bp.route('/monthly-stats/leaderboard', methods=['GET'])
@api_key_required
def get_monthly_leaderboard():
    """Get current month's mission leaderboard sorted by stars"""
    try:
        cycle_month, stats = mission_service.get_monthly_leaderboard()

        return jsonify({
            'success': True,
            'cycle_month': cycle_month.strftime('%Y-%m'),
            'leaderboard': [s.to_dict() for s in stats],
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@missions_bp.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({'status': 'ok', 'service': 'missions'}), 200
