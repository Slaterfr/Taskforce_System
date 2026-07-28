"""Activity Check (AC) business logic."""

from datetime import date, datetime

from sqlalchemy import func

from database.models import db, Member, MonthlyStat
from database.ac_models import (
    ACPeriod,
    ACExemption,
    ACTIVITY_TYPES,
    AC_QUOTAS,
    ActivityEntry,
    InactivityNotice,
    MonthlyActivityEntry,
    get_activity_points,
    get_hwtm_winner,
    get_leggionary_winner,
    get_member_quota,
    get_monthly_activity_counts,
    get_scout_winner,
    get_taskmaster_winner,
    is_limited_activity,
)


def get_active_period():
    """Return the current active AC period, or None."""
    return ACPeriod.query.filter_by(is_active=True).first()


def members_with_quota_query():
    """Return a query for active members that have an AC quota (excludes top ranks)."""
    excluded = {''}
    allowed = [
        r.lower()
        for r, q in AC_QUOTAS.items()
        if q and q > 0 and r.lower() not in excluded
    ]
    return Member.query.filter(
        Member.is_active == True,
        func.lower(Member.current_rank).in_(allowed),
    ).order_by(func.lower(Member.current_rank), Member.discord_username)


def get_members_with_quota():
    """Return all active members subject to AC quotas."""
    return members_with_quota_query().all()


def get_activity_stats(period):
    """Aggregate activity counts and points by type for a period."""
    rows = db.session.query(
        ActivityEntry.activity_type,
        db.func.count(ActivityEntry.id).label('count'),
        db.func.sum(ActivityEntry.points).label('total_points'),
    ).filter_by(ac_period_id=period.id).group_by(ActivityEntry.activity_type).all()

    return {
        activity_type: {
            'count': count,
            'total_points': float(total_points or 0),
        }
        for activity_type, count, total_points in rows
    }


def build_member_progress(period):
    """
    Build per-member AC progress for a period.
    Used by the HCT dashboard and public AC progress page.
    """
    member_progress = []

    for member in get_members_with_quota():
        quota = get_member_quota(member.current_rank) or 0
        if not quota:
            continue

        member_activities = db.session.query(
            ActivityEntry.activity_type,
            db.func.count(ActivityEntry.id),
            db.func.sum(ActivityEntry.points),
        ).filter_by(
            member_id=member.id,
            ac_period_id=period.id,
        ).group_by(ActivityEntry.activity_type).all()

        activity_summary = {
            activity_type: {'count': count, 'points': float(points or 0)}
            for activity_type, count, points in member_activities
        }

        total_points = sum(stat['points'] for stat in activity_summary.values())

        ia_notice = InactivityNotice.query.filter_by(
            member_id=member.id,
            ac_period_id=period.id,
        ).first()

        exemption = ACExemption.query.filter_by(
            member_id=member.id,
            ac_period_id=period.id,
        ).first()

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

        member_progress.append({
            'member': member,
            'quota': quota,
            'points': total_points,
            'percentage': pct,
            'status': status,
            'is_protected': bool(ia_notice),
            'is_exempt': bool(exemption),
            'activity_summary': activity_summary,
        })

    member_progress.sort(
        key=lambda x: (
            100 if x['is_exempt'] else (99 if x['is_protected'] else x['percentage'])
        )
    )
    return member_progress


def calculate_title_rewards(all_activities, period):
    """
    Calculate title reward winners based on activity counts for the current period.
    Reads from MonthlyActivityEntry for persistent title tracking.
    """
    titles = {}

    hwtm_winner_id, hwtm_count = get_hwtm_winner(period)
    if hwtm_winner_id and hwtm_count >= 5:
        winner = Member.query.get(hwtm_winner_id)
        titles['Host with the Most'] = {
            'winner': winner.discord_username if winner else 'Unknown',
            'count': hwtm_count,
            'requirement': '5+ events hosted (Training + Raid + Patrol)',
            'period_award': True,
            'qualified': True,
        }
    else:
        activity_counts = get_monthly_activity_counts(period)
        if activity_counts:
            max_events = 0
            top_member_id = None
            for member_id, counts in activity_counts.items():
                combined = counts['trainings'] + counts['raids'] + counts['patrols']
                if combined > max_events:
                    max_events = combined
                    top_member_id = member_id

            if max_events > 0:
                winner = Member.query.get(top_member_id)
                titles['Host with the Most'] = {
                    'winner': (
                        f"{winner.discord_username if winner else 'Unknown'} "
                        f"(Not Qualified - {max_events} events)"
                    ),
                    'count': max_events,
                    'requirement': '5+ events hosted (Training + Raid + Patrol)',
                    'period_award': True,
                    'qualified': False,
                }
            else:
                titles['Host with the Most'] = _empty_title(
                    '5+ events hosted (Training + Raid + Patrol)', period_award=True
                )
        else:
            titles['Host with the Most'] = _empty_title(
                '5+ events hosted (Training + Raid + Patrol)', period_award=True
            )

    leg_winner_id, leg_count = get_leggionary_winner(period)
    titles['Legionnaire'] = _monthly_title(
        period,
        leg_winner_id,
        leg_count,
        5,
        '5+ events hosted (Raids + Patrols - monthly)',
        count_fn=lambda counts: counts['raids'] + counts['patrols'],
        label='events',
    )

    scout_winner_id, scout_count = get_scout_winner(period)
    titles['Scout'] = _monthly_title(
        period,
        scout_winner_id,
        scout_count,
        5,
        '5+ tryouts - monthly',
        count_fn=lambda counts: counts['tryouts'],
        label='tryouts',
    )

    taskmaster_winner_id, taskmaster_count = get_taskmaster_winner(period)
    titles['Taskmaster'] = _monthly_title(
        period,
        taskmaster_winner_id,
        taskmaster_count,
        5,
        '5+ missions - monthly',
        count_fn=lambda counts: counts['missions'],
        label='missions',
    )

    titles['Executor'] = _executor_title()

    return titles


def _empty_title(requirement, period_award=False, is_monthly=False):
    return {
        'winner': 'No participants',
        'count': 0,
        'requirement': requirement,
        'period_award': period_award,
        'is_monthly': is_monthly,
        'qualified': False,
    }


def _monthly_title(period, winner_id, winner_count, minimum, requirement, count_fn, label):
    if winner_id and winner_count >= minimum:
        winner = Member.query.get(winner_id)
        return {
            'winner': winner.discord_username if winner else 'Unknown',
            'count': winner_count,
            'requirement': requirement,
            'period_award': False,
            'is_monthly': True,
            'qualified': True,
        }

    activity_counts = get_monthly_activity_counts(period)
    if activity_counts:
        max_count = 0
        top_member_id = None
        for member_id, counts in activity_counts.items():
            value = count_fn(counts)
            if value > max_count:
                max_count = value
                top_member_id = member_id

        if max_count > 0:
            winner = Member.query.get(top_member_id)
            return {
                'winner': (
                    f"{winner.discord_username if winner else 'Unknown'} "
                    f"(Not Qualified - {max_count} {label})"
                ),
                'count': max_count,
                'requirement': requirement,
                'period_award': False,
                'is_monthly': True,
                'qualified': False,
            }

    return _empty_title(requirement, is_monthly=True)


def _executor_title():
    month_start = date.today().replace(day=1)
    monthly_stats = MonthlyStat.query.filter_by(cycle_month=month_start).all()

    if not monthly_stats:
        return _empty_title('5+ mission stars (⭐⭐⭐+)', is_monthly=True)

    max_stars = 0
    executor_member_id = None
    for stat in monthly_stats:
        if stat.total_stars > max_stars:
            max_stars = stat.total_stars
            executor_member_id = stat.member_id

    base = {
        'requirement': '5+ mission stars (⭐⭐⭐+)',
        'period_award': False,
        'is_monthly': True,
    }

    if executor_member_id and max_stars >= 5:
        executor_member = Member.query.get(executor_member_id)
        return {
            **base,
            'winner': executor_member.discord_username if executor_member else 'Unknown',
            'count': max_stars,
            'qualified': True,
        }
    if max_stars > 0:
        executor_member = Member.query.get(executor_member_id)
        return {
            **base,
            'winner': (
                f"{executor_member.discord_username if executor_member else 'Unknown'} "
                f"(Not Qualified - {max_stars} stars)"
            ),
            'count': max_stars,
            'qualified': False,
        }
    return _empty_title('5+ mission stars (⭐⭐⭐+)', is_monthly=True)


def generate_title_discord_message(titles, period):
    """Generate Discord message text for qualified title winners."""
    qualified_titles = {k: v for k, v in titles.items() if v.get('qualified', False)}

    if not qualified_titles:
        return 'No title winners this cycle (minimum requirements not met).'

    message = f"🏆 **Title Rewards - {period.period_name}** 🏆\n\n"
    for title, info in qualified_titles.items():
        message += f"**@{title}**\n"
        message += f"👑 Winner: **{info['winner']}**\n"
        message += f"📊 Achievement: {info['count']} ({info['requirement']})\n"
        if info.get('is_monthly'):
            message += "📅 *Monthly Accumulated Award*\n"
        else:
            message += "⏱️ *Period Award*\n"
        message += "\n"

    return message


def get_member_period_points(member_id, period_id):
    """Total AC points for a member in a period."""
    entries = ActivityEntry.query.filter_by(
        member_id=member_id,
        ac_period_id=period_id,
    ).all()
    return sum(entry.points for entry in entries)


def get_quota_progress(member, period):
    """Return total points, quota, and completion percentage for a member."""
    total_points = get_member_period_points(member.id, period.id)
    member_quota = get_member_quota(member.current_rank) or 0
    percentage = (total_points / member_quota * 100) if member_quota > 0 else 0
    return {
        'total_points': total_points,
        'quota': member_quota,
        'percentage': round(percentage, 2),
    }


def log_activity(
    member_id,
    activity_type,
    *,
    activity_date=None,
    description=None,
    logged_by='HC Team',
    quantity=1,
    mark_limited=False,
    period=None,
    validate_activity_type=True,
):
    """
    Log one or more AC activity entries for a member.

    Returns a dict with ``success``, optional ``error``, and result fields on success.
    """
    if validate_activity_type and activity_type not in ACTIVITY_TYPES:
        return {
            'success': False,
            'error': 'invalid_activity_type',
            'message': f'Invalid activity type "{activity_type}"',
            'valid_types': list(ACTIVITY_TYPES.keys()),
        }

    member = Member.query.filter_by(id=member_id, is_active=True).first()
    if not member:
        return {
            'success': False,
            'error': 'member_not_found',
            'message': f'Member with ID {member_id} not found',
        }

    current_period = period or get_active_period()
    if not current_period:
        return {
            'success': False,
            'error': 'no_active_period',
            'message': 'No active AC period. Please create one first.',
        }

    if activity_date is None:
        activity_date = datetime.utcnow()
    elif isinstance(activity_date, str):
        activity_date = datetime.strptime(activity_date, '%Y-%m-%d')

    points = get_activity_points(activity_type)

    quantity = int(quantity)
    if is_limited_activity(activity_type):
        quantity = 1
    quantity = max(1, min(999, quantity))

    if is_limited_activity(activity_type):
        existing = ActivityEntry.query.filter_by(
            member_id=member_id,
            ac_period_id=current_period.id,
            activity_type=activity_type,
        ).first()
        if existing:
            return {
                'success': False,
                'error': 'limited_activity_exists',
                'message': 'Limited activity already logged for this period',
            }

    created_ids = []
    for _ in range(quantity):
        entry_kwargs = {
            'member_id': member_id,
            'ac_period_id': current_period.id,
            'activity_type': activity_type,
            'points': points,
            'description': description,
            'activity_date': activity_date,
            'logged_by': logged_by,
        }
        if mark_limited:
            entry_kwargs['is_limited_activity'] = is_limited_activity(activity_type)

        activity_entry = ActivityEntry(**entry_kwargs)
        db.session.add(activity_entry)
        db.session.flush()
        created_ids.append(activity_entry.id)

        monthly_entry = MonthlyActivityEntry(
            member_id=member_id,
            ac_period_id=current_period.id,
            activity_type=activity_type,
            points=points,
            description=description,
            activity_date=activity_date,
            logged_by=logged_by,
        )
        db.session.add(monthly_entry)

    db.session.commit()

    quota_progress = get_quota_progress(member, current_period)

    return {
        'success': True,
        'activity_ids': created_ids,
        'count': quantity,
        'points': points,
        'member': member,
        'period': current_period,
        'activity_date': activity_date,
        'quota_progress': quota_progress,
    }


def toggle_ia_status(member_id, *, reason='Quick log IA', approved_by='HC Team', period=None):
    """Toggle inactivity notice for a member. Returns ``is_ia`` and a message."""
    current_period = period or get_active_period()
    if not current_period:
        return {'success': False, 'error': 'no_active_period', 'message': 'No active AC period'}

    ia_notice = InactivityNotice.query.filter_by(
        member_id=member_id,
        ac_period_id=current_period.id,
    ).first()

    if ia_notice:
        db.session.delete(ia_notice)
        db.session.commit()
        return {'success': True, 'is_ia': False, 'message': 'IA removed'}

    ia_notice = InactivityNotice(
        member_id=member_id,
        ac_period_id=current_period.id,
        start_date=current_period.start_date,
        end_date=current_period.end_date,
        reason=reason,
        approved_by=approved_by,
        protects_ac=True,
    )
    db.session.add(ia_notice)
    db.session.commit()
    return {'success': True, 'is_ia': True, 'message': 'IA set'}


def toggle_exempt_status(member_id, *, reason='Quick log exemption', approved_by='HC Team', period=None):
    """Toggle AC exemption for a member. Returns ``is_exempt`` and a message."""
    current_period = period or get_active_period()
    if not current_period:
        return {'success': False, 'error': 'no_active_period', 'message': 'No active AC period'}

    exemption = ACExemption.query.filter_by(
        member_id=member_id,
        ac_period_id=current_period.id,
    ).first()

    if exemption:
        db.session.delete(exemption)
        db.session.commit()
        return {'success': True, 'is_exempt': False, 'message': 'Exemption removed'}

    exemption = ACExemption(
        member_id=member_id,
        ac_period_id=current_period.id,
        reason=reason,
        approved_by=approved_by,
    )
    db.session.add(exemption)
    db.session.commit()
    return {'success': True, 'is_exempt': True, 'message': 'Exemption set'}


def delete_activity_entry(activity_id):
    """Delete an activity entry. Returns metadata needed for API responses."""
    activity = ActivityEntry.query.filter_by(id=activity_id).first()
    if not activity:
        return {
            'success': False,
            'error': 'activity_not_found',
            'message': f'Activity with ID {activity_id} not found',
        }

    member = Member.query.get(activity.member_id)
    activity_type = activity.activity_type
    points = activity.points
    ac_period_id = activity.ac_period_id

    db.session.delete(activity)
    db.session.commit()

    current_period = ACPeriod.query.get(ac_period_id)
    if current_period and member:
        quota_progress = get_quota_progress(member, current_period)
    else:
        quota_progress = {'total_points': 0, 'quota': 0, 'percentage': 0}

    return {
        'success': True,
        'activity_id': activity_id,
        'activity_type': activity_type,
        'points': points,
        'member': member,
        'period': current_period,
        'quota_progress': quota_progress,
    }


def create_period(period_name, start_date, end_date):
    """Deactivate any current period and create a new AC period."""
    ACPeriod.query.filter_by(is_active=True).update({'is_active': False})
    new_period = ACPeriod(
        period_name=period_name,
        start_date=start_date,
        end_date=end_date,
        is_active=True
    )
    db.session.add(new_period)
    db.session.commit()
    return new_period


def update_period_name(period_id, period_name):
    """Update the name of an AC period."""
    period = ACPeriod.query.get(period_id)
    if period:
        period.period_name = period_name
        db.session.commit()
        return True
    return False


def clear_all_activities(period_id):
    """Delete all activity entries for a period."""
    deleted_count = ActivityEntry.query.filter_by(ac_period_id=period_id).delete()
    db.session.commit()
    return deleted_count


def clear_titles(period_id):
    """Delete all title tracking data (monthly activity entries) for a period."""
    deleted_count = MonthlyActivityEntry.query.filter_by(ac_period_id=period_id).delete()
    db.session.commit()
    return deleted_count


def get_period_activities(period_id):
    """Get all activity entries for a period."""
    return ActivityEntry.query.filter_by(ac_period_id=period_id).all()


def get_quick_log_data(period_id):
    """Get activities, counts, and statuses for quick logging."""
    members_with_quota = get_members_with_quota()
    member_activities = {}
    member_activity_counts = {}
    member_ia_status = {}
    member_exempt_status = {}

    for member in members_with_quota:
        recent = ActivityEntry.query.filter_by(
            member_id=member.id,
            ac_period_id=period_id
        ).order_by(ActivityEntry.activity_date.desc()).limit(3).all()
        member_activities[member.id] = recent

        counts = db.session.query(
            ActivityEntry.activity_type,
            db.func.count(ActivityEntry.id)
        ).filter_by(
            member_id=member.id,
            ac_period_id=period_id
        ).group_by(ActivityEntry.activity_type).all()
        member_activity_counts[member.id] = dict(counts)

        ia_notice = InactivityNotice.query.filter_by(
            member_id=member.id,
            ac_period_id=period_id
        ).first()
        member_ia_status[member.id] = bool(ia_notice)

        exemption = ACExemption.query.filter_by(
            member_id=member.id,
            ac_period_id=period_id
        ).first()
        member_exempt_status[member.id] = bool(exemption)

    return {
        'members': members_with_quota,
        'member_activities': member_activities,
        'member_activity_counts': member_activity_counts,
        'member_ia_status': member_ia_status,
        'member_exempt_status': member_exempt_status
    }


def get_member_ac_detail(member_id, period_id):
    """Fetch details and aggregates of activities for a member in a period."""
    member = Member.query.get(member_id)
    if not member:
        return None

    activities = ActivityEntry.query.filter_by(
        member_id=member_id,
        ac_period_id=period_id
    ).order_by(ActivityEntry.activity_date.desc()).all()

    agg = {}
    for a in activities:
        key = (a.activity_type, a.points)
        if key not in agg:
            agg[key] = {'count': 0, 'last_date': a.activity_date}
        agg[key]['count'] += 1
        if a.activity_date and a.activity_date > agg[key]['last_date']:
            agg[key]['last_date'] = a.activity_date

    aggregated_activities = sorted(
        (
            {
                'activity_type': k[0],
                'points': k[1],
                'count': v['count'],
                'activity_date': v['last_date']
            }
            for k, v in agg.items()
        ),
        key=lambda x: x['activity_date'] or datetime.min,
        reverse=True
    )

    quota = get_member_quota(member.current_rank)
    total_points = sum(a.points for a in activities)

    return {
        'member': member,
        'activities': activities,
        'aggregated_activities': aggregated_activities,
        'quota': quota,
        'total_points': total_points
    }


def clear_member_activities(member_id, period_id=None):
    """Clear all activity entries for a member, optionally restricted to a period."""
    query = ActivityEntry.query.filter_by(member_id=member_id)
    if period_id:
        query = query.filter_by(ac_period_id=period_id)
    deleted_count = query.delete(synchronize_session=False)
    db.session.commit()
    return deleted_count


def get_member_activities(member_id, limit=20):
    """Return recent ActivityEntry records for a member, newest first."""
    return (
        ActivityEntry.query
        .filter_by(member_id=member_id)
        .order_by(ActivityEntry.activity_date.desc())
        .limit(limit)
        .all()
    )


