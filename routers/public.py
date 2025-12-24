from flask import Blueprint, render_template, request
from database.models import Member
from database.ac_models import ActivityEntry

public_bp = Blueprint('public', __name__)


@public_bp.route('/')
def public_roster():
    search = request.args.get('search', '')
    query = Member.query.filter_by(is_active=True)
    if search:
        s = f"%{search}%"
        query = query.filter(
            (Member.discord_username.ilike(s)) |
            (Member.roblox_username.ilike(s)) |
            (Member.current_rank.ilike(s))
        )
    members = query.order_by(Member.current_rank, Member.discord_username).all()
    return render_template('public_roster.html', members=members, search=search)


@public_bp.route('/public/member/<int:member_id>')
def public_member(member_id):
    """Public read-only member view (limited data)"""
    member = Member.query.get_or_404(member_id)
    # limit data for public view: basic profile + recent non-sensitive activities
    recent_activities = ActivityEntry.query.filter_by(member_id=member_id).order_by(ActivityEntry.activity_date.desc()).limit(5).all()
    # do not include internal IA notices or editable controls
    return render_template('public_member.html',
                           member=member,
                           recent_activities=recent_activities)


@public_bp.route('/ac_progress')
def public_ac_progress():
    from database.models import db
    from database.ac_models import (
        ACPeriod, ActivityEntry, InactivityNotice, ACExemption,
        ACTIVITY_TYPES, AC_QUOTAS, get_member_quota
    )
    from sqlalchemy import func

    current_period = ACPeriod.query.filter_by(is_active=True).first()
    # If no period, we can just render the page with empty data or a message
    if not current_period:
        return render_template('public_ac_progress.html', 
                             current_period=None, 
                             member_progress=[],
                             activity_types=ACTIVITY_TYPES)

    # Helper query for members with quota (duplicated from ac.py to avoid circular imports/complexity)
    excluded = {'general', 'chief general'}
    allowed = [r.lower() for r, q in AC_QUOTAS.items() if q and q > 0 and r.lower() not in excluded]
    members = Member.query.filter(
        Member.is_active == True,
        func.lower(Member.current_rank).in_(allowed)
    ).order_by(func.lower(Member.current_rank), Member.discord_username).all()

    member_progress = []
    for m in members:
        quota = get_member_quota(m.current_rank) or 0
        if not quota:
            continue

        # Get member's activity summary
        member_activities = db.session.query(
            ActivityEntry.activity_type,
            db.func.count(ActivityEntry.id),
            db.func.sum(ActivityEntry.points)
        ).filter_by(
            member_id=m.id,
            ac_period_id=current_period.id
        ).group_by(ActivityEntry.activity_type).all()

        activity_summary = {
            type_: {'count': count, 'points': float(points or 0)}
            for type_, count, points in member_activities
        }

        total_points = sum(stat['points'] for stat in activity_summary.values())
        
        ia_notice = InactivityNotice.query.filter_by(
            member_id=m.id,
            ac_period_id=current_period.id
        ).first()

        exemption = ACExemption.query.filter_by(
            member_id=m.id,
            ac_period_id=current_period.id
        ).first()

        # Determine status and percentage
        if exemption:
            status = 'Exempt'
            pct = 100.0
        elif ia_notice:
            status = 'Protected (IA)'
            pct = 100.0
        elif total_points >= quota:
            status = 'Passed'
            pct = min(100.0, (total_points / quota) * 100.0) if quota > 0 else 0.0
        else:
            status = 'In Progress'
            pct = min(100.0, (total_points / quota) * 100.0) if quota > 0 else 0.0

        progress = {
            'member': m,
            'quota': quota,
            'points': total_points,
            'percentage': pct,
            'status': status,
            'is_protected': bool(ia_notice),
            'is_exempt': bool(exemption),
            'activity_summary': activity_summary
        }
        member_progress.append(progress)

    # Sort: Exempt first, then IA protected, then by percentage
    member_progress.sort(key=lambda x: (100 if x['is_exempt'] else (99 if x['is_protected'] else x['percentage'])))

    return render_template('public_ac_progress.html',
                         current_period=current_period,
                         member_progress=member_progress,
                         activity_types=ACTIVITY_TYPES)
