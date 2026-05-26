"""
API Routes for Mission Tracking System
Missions posted in Discord with star difficulty.
"""

from flask import Blueprint, jsonify, request, current_app
from database.models import db, Mission, MissionCompletion, MonthlyStat, Member
from utils.api_auth import api_key_required
from datetime import datetime, timedelta
from sqlalchemy import func

missions_bp = Blueprint('missions', __name__)


# ==================== CREATE MISSION ====================

@missions_bp.route('', methods=['POST'])
@api_key_required
def create_mission():
    """
    Create a new mission from Discord message
    
    Expected JSON:
    {
        "discord_message_id": "123456789",
        "title": "Arrest Criminals",
        "stars": 3,
        "difficulty": "⭐⭐⭐",
        "expiration_date": "2026-06-02",
        "planet_coordinates": "https://...",
        "created_by_username": "BotName",
        "description": "Optional description"
    }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('discord_message_id'):
            return jsonify({'error': 'discord_message_id required'}), 400
        if not data.get('title'):
            return jsonify({'error': 'title required'}), 400
        if not data.get('stars'):
            return jsonify({'error': 'stars required'}), 400
        
        # Check if mission already exists
        existing = Mission.query.filter_by(
            discord_message_id=data['discord_message_id']
        ).first()
        if existing:
            return jsonify({
                'error': 'Mission already exists',
                'mission_id': existing.id
            }), 409
        
        # Get creator member ID if username provided
        creator_id = None
        if data.get('created_by_username'):
            creator = Member.query.filter_by(
                discord_username=data['created_by_username']
            ).first()
            if creator:
                creator_id = creator.id
        
        # Parse expiration date if provided
        expiration_date = None
        if data.get('expiration_date'):
            try:
                expiration_date = datetime.strptime(
                    data['expiration_date'], '%Y-%m-%d'
                ).date()
            except:
                pass
        
        # Create mission
        mission = Mission(
            discord_message_id=data['discord_message_id'],
            title=data['title'],
            stars=data['stars'],
            difficulty=data.get('difficulty'),
            expiration_date=expiration_date,
            planet_coordinates=data.get('planet_coordinates'),
            created_by_id=creator_id,
            description=data.get('description'),
            cycle_month=datetime.utcnow().date().replace(day=1)
        )
        
        db.session.add(mission)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'mission': mission.to_dict()
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ==================== GET MISSION ====================

@missions_bp.route('/by-message/<discord_message_id>', methods=['GET'])
@api_key_required
def get_mission_by_message_id(discord_message_id):
    """Get a mission by its Discord message ID"""
    try:
        mission = Mission.query.filter_by(
            discord_message_id=discord_message_id
        ).first()
        
        if not mission:
            return jsonify({'error': 'Mission not found'}), 404
        
        return jsonify({
            'success': True,
            'id': mission.id,
            'title': mission.title,
            'stars': mission.stars,
            'completions': [c.to_dict() for c in mission.completions]
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== LOG COMPLETIONS ====================

@missions_bp.route('/completions', methods=['POST'])
@api_key_required
def log_mission_completions():
    """
    Log mission completions or removals
    
    Expected JSON:
    {
        "mission_id": 1,
        "verified_by_username": "StaffName",
        "completers": [
            {"member_username": "PlayerName", "discord_username": "PlayerName"}
        ],
        "deleted_completers": ["PlayerName1", "PlayerName2"]
    }
    """
    try:
        data = request.get_json()
        mission_id = data.get('mission_id')
        verified_by_username = data.get('verified_by_username')
        completers = data.get('completers', [])
        deleted_completers = data.get('deleted_completers', [])
        
        # Get mission
        mission = Mission.query.get(mission_id)
        if not mission:
            return jsonify({'error': 'Mission not found'}), 404
        
        # Get verified_by user
        verified_by = None
        if verified_by_username:
            verified_by = Member.query.filter_by(
                discord_username=verified_by_username
            ).first()
        
        stats_added = 0
        stats_deleted = 0
        
        # Add new completions
        for completer in completers:
            member_username = completer.get('member_username') or completer.get('discord_username')
            member = Member.query.filter_by(
                discord_username=member_username
            ).first()
            
            if not member:
                continue
            
            # Check if already completed
            existing = MissionCompletion.query.filter_by(
                mission_id=mission_id,
                member_id=member.id
            ).first()
            
            if not existing:
                completion = MissionCompletion(
                    mission_id=mission_id,
                    member_id=member.id,
                    logged_by_id=verified_by.id if verified_by else None
                )
                db.session.add(completion)
                stats_added += 1
                
                # Update monthly stats
                update_monthly_stats(member.id, mission.stars, 1)
        
        # Remove completions
        for deleted_member_username in deleted_completers:
            member = Member.query.filter_by(
                discord_username=deleted_member_username
            ).first()
            
            if member:
                completion = MissionCompletion.query.filter_by(
                    mission_id=mission_id,
                    member_id=member.id
                ).first()
                
                if completion:
                    db.session.delete(completion)
                    stats_deleted += 1
                    
                    # Update monthly stats
                    update_monthly_stats(member.id, -mission.stars, -1)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'stats': {
                'added': stats_added,
                'deleted': stats_deleted
            }
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ==================== HELPER FUNCTIONS ====================

def update_monthly_stats(member_id: int, stars_delta: int, missions_delta: int):
    """Update or create monthly stats for a member"""
    try:
        cycle_month = datetime.utcnow().date().replace(day=1)
        
        stat = MonthlyStat.query.filter_by(
            member_id=member_id,
            cycle_month=cycle_month
        ).first()
        
        if not stat:
            stat = MonthlyStat(
                member_id=member_id,
                cycle_month=cycle_month,
                total_stars=max(0, stars_delta),
                missions_completed=max(0, missions_delta)
            )
            db.session.add(stat)
        else:
            stat.total_stars = max(0, stat.total_stars + stars_delta)
            stat.missions_completed = max(0, stat.missions_completed + missions_delta)
            stat.updated_at = datetime.utcnow()
        
        db.session.flush()
    except Exception as e:
        current_app.logger.error(f"Error updating monthly stats: {e}")
        raise


# ==================== GET LEADERBOARD ====================

@missions_bp.route('/monthly-stats/leaderboard', methods=['GET'])
@api_key_required
def get_monthly_leaderboard():
    """Get current month's mission leaderboard sorted by stars"""
    try:
        cycle_month = datetime.utcnow().date().replace(day=1)
        
        stats = MonthlyStat.query.filter_by(
            cycle_month=cycle_month
        ).order_by(
            MonthlyStat.total_stars.desc(),
            MonthlyStat.missions_completed.desc()
        ).all()
        
        return jsonify({
            'success': True,
            'cycle_month': cycle_month.strftime('%Y-%m'),
            'leaderboard': [s.to_dict() for s in stats]
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== HEALTH CHECK ====================

@missions_bp.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({'status': 'ok', 'service': 'missions'}), 200
