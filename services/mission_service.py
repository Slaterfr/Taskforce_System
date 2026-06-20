"""Mission tracking business logic."""

from datetime import datetime

from flask import current_app

from database.models import db, Member, Mission, MissionCompletion, MonthlyStat


def create_mission(data):
    """
    Create a mission from API payload.

    Returns ``success``, optional ``error``, and the ``mission`` on success.
    """
    if not data.get('discord_message_id'):
        return {'success': False, 'error': 'discord_message_id required'}
    if not data.get('title'):
        return {'success': False, 'error': 'title required'}
    if not data.get('stars'):
        return {'success': False, 'error': 'stars required'}

    existing = Mission.query.filter_by(
        discord_message_id=data['discord_message_id']
    ).first()
    if existing:
        return {
            'success': False,
            'error': 'Mission already exists',
            'mission_id': existing.id,
            'status_code': 409,
        }

    creator_id = None
    if data.get('created_by_username'):
        creator = Member.query.filter_by(
            discord_username=data['created_by_username']
        ).first()
        if creator:
            creator_id = creator.id

    expiration_date = None
    if data.get('expiration_date'):
        try:
            expiration_date = datetime.strptime(
                data['expiration_date'], '%Y-%m-%d'
            ).date()
        except ValueError:
            pass

    mission = Mission(
        discord_message_id=data['discord_message_id'],
        title=data['title'],
        stars=data['stars'],
        difficulty=data.get('difficulty'),
        expiration_date=expiration_date,
        planet_coordinates=data.get('planet_coordinates'),
        created_by_id=creator_id,
        description=data.get('description'),
        cycle_month=datetime.utcnow().date().replace(day=1),
    )

    db.session.add(mission)
    db.session.commit()

    return {'success': True, 'mission': mission}


def get_mission_by_message_id(discord_message_id):
    """Return a mission by Discord message ID, or None."""
    return Mission.query.filter_by(discord_message_id=discord_message_id).first()


def log_mission_completions(
    mission_id,
    *,
    verified_by_username=None,
    completers=None,
    deleted_completers=None,
):
    """
    Add or remove mission completions and update monthly stats.

    Returns counts of added/deleted completions.
    """
    completers = completers or []
    deleted_completers = deleted_completers or []

    mission = Mission.query.get(mission_id)
    if not mission:
        return {'success': False, 'error': 'Mission not found'}

    verified_by = None
    if verified_by_username:
        verified_by = Member.query.filter_by(
            discord_username=verified_by_username
        ).first()

    stats_added = 0
    stats_deleted = 0

    for completer in completers:
        member_username = completer.get('member_username') or completer.get('discord_username')
        member = Member.query.filter_by(discord_username=member_username).first()
        if not member:
            continue

        existing = MissionCompletion.query.filter_by(
            mission_id=mission_id,
            member_id=member.id,
        ).first()

        if not existing:
            completion = MissionCompletion(
                mission_id=mission_id,
                member_id=member.id,
                logged_by_id=verified_by.id if verified_by else None,
            )
            db.session.add(completion)
            stats_added += 1
            update_monthly_stats(member.id, mission.stars, 1)

    for deleted_member_username in deleted_completers:
        member = Member.query.filter_by(
            discord_username=deleted_member_username
        ).first()
        if not member:
            continue

        completion = MissionCompletion.query.filter_by(
            mission_id=mission_id,
            member_id=member.id,
        ).first()

        if completion:
            db.session.delete(completion)
            stats_deleted += 1
            update_monthly_stats(member.id, -mission.stars, -1)

    db.session.commit()

    return {
        'success': True,
        'stats': {
            'added': stats_added,
            'deleted': stats_deleted,
        },
    }


def update_monthly_stats(member_id, stars_delta, missions_delta):
    """Update or create monthly stats for a member."""
    cycle_month = datetime.utcnow().date().replace(day=1)

    stat = MonthlyStat.query.filter_by(
        member_id=member_id,
        cycle_month=cycle_month,
    ).first()

    if not stat:
        stat = MonthlyStat(
            member_id=member_id,
            cycle_month=cycle_month,
            total_stars=max(0, stars_delta),
            missions_completed=max(0, missions_delta),
        )
        db.session.add(stat)
    else:
        stat.total_stars = max(0, stat.total_stars + stars_delta)
        stat.missions_completed = max(0, stat.missions_completed + missions_delta)
        stat.updated_at = datetime.utcnow()

    db.session.flush()


def get_monthly_leaderboard():
    """Return current month's mission stats ordered by stars."""
    cycle_month = datetime.utcnow().date().replace(day=1)
    stats = MonthlyStat.query.filter_by(cycle_month=cycle_month).order_by(
        MonthlyStat.total_stars.desc(),
        MonthlyStat.missions_completed.desc(),
    ).all()
    return cycle_month, stats
