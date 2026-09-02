"""Activity Check (AC) business logic."""

from datetime import date, datetime
from sqlalchemy import func
from sqlmodel import select

from database.engine import db_session
from database.models import Member, MonthlyStat
from database.ac_constants import (
    ACTIVITY_TYPES,
    AC_QUOTAS,
)
from database.ac_models import (
    ACPeriod,
    ACExemption,
    ActivityEntry,
    InactivityNotice,
    MonthlyActivityEntry,
    ActivityType,
    RankQuota,
    get_hwtm_winner,
    get_leggionary_winner,
    get_monthly_activity_counts,
    get_scout_winner,
    get_taskmaster_winner,
)


def get_activity_types_map(tenant_id: int = 1) -> dict:
    """Return dict of {name: {'points': float, 'limited': bool, 'description': str}} from DB with constants fallback."""
    try:
        session = db_session()
        db_types = session.exec(
            select(ActivityType).where(
                ActivityType.tenant_id == tenant_id,
                ActivityType.is_active == True,
            )
        ).all()
        if db_types:
            return {
                a.name: {
                    'points': a.points,
                    'limited': a.is_limited,
                    'description': a.description or '',
                }
                for a in db_types
            }
    except Exception:
        pass
    return ACTIVITY_TYPES


def get_rank_quotas_map(tenant_id: int = 1) -> dict:
    """Return dict of {rank_name: required_points} from DB with constants fallback."""
    try:
        session = db_session()
        db_quotas = session.exec(
            select(RankQuota).where(RankQuota.tenant_id == tenant_id)
        ).all()
        if db_quotas:
            return {q.rank_name: q.required_points for q in db_quotas}
    except Exception:
        pass
    return AC_QUOTAS


def get_member_quota(rank: str, tenant_id: int = 1) -> float:
    """Get AC quota for a member's rank."""
    quotas = get_rank_quotas_map(tenant_id)
    for r_name, pts in quotas.items():
        if r_name.lower() == (rank or '').lower():
            return pts
    return 0.0


def get_activity_points(activity_type: str, tenant_id: int = 1) -> float:
    """Get point value for an activity type."""
    types_map = get_activity_types_map(tenant_id)
    for name, data in types_map.items():
        if name.lower() == (activity_type or '').lower():
            return data.get('points', 0.0)
    return 0.0


def is_limited_activity(activity_type: str, tenant_id: int = 1) -> bool:
    """Check if activity type is limited to 1 per cycle."""
    types_map = get_activity_types_map(tenant_id)
    for name, data in types_map.items():
        if name.lower() == (activity_type or '').lower():
            return data.get('limited', False)
    return False


# Hardcoded rank order for AC tables: lower number = displayed first (top of table)
RANK_ORDER = {
    'prospect':      1,
    'commander':     2,
    'marshal':       3,
    'general':       4,
    'chief general': 5,
}


def _rank_sort_key(rank_str):
    """Return a numeric sort key for a rank string (case-insensitive). Unknown ranks go last."""
    return RANK_ORDER.get((rank_str or '').lower(), 99)


def get_active_period():
    """Return the current active AC period, or None."""
    return db_session().exec(select(ACPeriod).filter_by(is_active=True)).first()


def members_with_quota_query(tenant_id: int = 1):
    """Return a query for active members that have an AC quota (excludes top ranks)."""
    quotas = get_rank_quotas_map(tenant_id)
    allowed = [
        r.lower()
        for r, q in quotas.items()
        if q and q > 0
    ]
    return db_session().query(Member).filter(
        Member.is_active == True,
        func.lower(Member.current_rank).in_(allowed),
    ).order_by(Member.discord_username)


def get_members_with_quota():
    """Return all active members subject to AC quotas."""
    return members_with_quota_query().all()


def get_activity_stats(period):
    """Aggregate activity counts and points by type for a period."""
    rows = db_session().query(
        ActivityEntry.activity_type,
        func.count(ActivityEntry.id).label('count'),
        func.sum(ActivityEntry.points).label('total_points'),
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

        member_activities = db_session().query(
            ActivityEntry.activity_type,
            func.count(ActivityEntry.id),
            func.sum(ActivityEntry.points),
        ).filter_by(
            member_id=member.id,
            ac_period_id=period.id,
        ).group_by(ActivityEntry.activity_type).all()

        activity_summary = {
            activity_type: {'count': count, 'points': float(points or 0)}
            for activity_type, count, points in member_activities
        }

        total_points = sum(stat['points'] for stat in activity_summary.values())

        ia_notice = db_session().query(InactivityNotice).filter_by(
            member_id=member.id,
            ac_period_id=period.id,
        ).first()

        exemption = db_session().query(ACExemption).filter_by(
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
            _rank_sort_key(x['member'].current_rank),
            x['member'].discord_username.lower(),
        )
    )
    return member_progress


def calculate_title_rewards(all_activities, period):
    """
    Calculate title reward winners based on activity counts for the current period.
    Reads from MonthlyActivityEntry for persistent title tracking.
    """
    titles = {}

    hwtm_winner_id, hwtm_count = get_hwtm_winner(period, db_session())
    if hwtm_winner_id and hwtm_count >= 5:
        winner = db_session().get(Member, hwtm_winner_id)
        titles['Host with the Most'] = {
            'winner': winner.discord_username if winner else 'Unknown',
            'count': hwtm_count,
            'requirement': '5+ events hosted (Training + Raid + Patrol)',
            'period_award': True,
            'qualified': True,
        }
    else:
        activity_counts = get_monthly_activity_counts(period, db_session())
        if activity_counts:
            max_events = 0
            top_member_id = None
            for member_id, counts in activity_counts.items():
                combined = counts['trainings'] + counts['raids'] + counts['patrols']
                if combined > max_events:
                    max_events = combined
                    top_member_id = member_id

            if max_events > 0:
                winner = db_session().get(Member, top_member_id)
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

    leg_winner_id, leg_count = get_leggionary_winner(period, db_session())
    titles['Legionnaire'] = _monthly_title(
        period,
        leg_winner_id,
        leg_count,
        5,
        '5+ events hosted (Raids + Patrols - monthly)',
        count_fn=lambda counts: counts['raids'] + counts['patrols'],
        label='events',
    )

    scout_winner_id, scout_count = get_scout_winner(period, db_session())
    titles['Scout'] = _monthly_title(
        period,
        scout_winner_id,
        scout_count,
        5,
        '5+ tryouts - monthly',
        count_fn=lambda counts: counts['tryouts'],
        label='tryouts',
    )

    taskmaster_winner_id, taskmaster_count = get_taskmaster_winner(period, db_session())
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
        winner = db_session().get(Member, winner_id)
        return {
            'winner': winner.discord_username if winner else 'Unknown',
            'count': winner_count,
            'requirement': requirement,
            'period_award': False,
            'is_monthly': True,
            'qualified': True,
        }

    activity_counts = get_monthly_activity_counts(period, db_session())
    if activity_counts:
        max_count = 0
        top_member_id = None
        for member_id, counts in activity_counts.items():
            value = count_fn(counts)
            if value > max_count:
                max_count = value
                top_member_id = member_id

        if max_count > 0:
            winner = db_session().get(Member, top_member_id)
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
    monthly_stats = db_session().exec(select(MonthlyStat).filter_by(cycle_month=month_start)).all()

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
        executor_member = db_session().get(Member, executor_member_id)
        return {
            **base,
            'winner': executor_member.discord_username if executor_member else 'Unknown',
            'count': max_stars,
            'qualified': True,
        }
    if max_stars > 0:
        executor_member = db_session().get(Member, executor_member_id)
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
    entries = db_session().query(ActivityEntry).filter_by(
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
    valid_types = get_activity_types_map()
    if validate_activity_type and activity_type not in valid_types:
        return {
            'success': False,
            'error': 'invalid_activity_type',
            'message': f'Invalid activity type "{activity_type}"',
            'valid_types': list(valid_types.keys()),
        }

    member = db_session().exec(select(Member).filter_by(id=member_id, is_active=True)).first()
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
        existing = db_session().query(ActivityEntry).filter_by(
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

    is_limited = is_limited_activity(activity_type)

    # Build all ActivityEntry objects at once, then bulk-insert for efficiency.
    activity_entries = [
        ActivityEntry(
            member_id=member_id,
            ac_period_id=current_period.id,
            activity_type=activity_type,
            points=points,
            description=description,
            activity_date=activity_date,
            logged_by=logged_by,
            is_limited_activity=is_limited if mark_limited else False,
        )
        for _ in range(quantity)
    ]
    session = db_session()
    for entry in activity_entries:
        session.add(entry)
    session.flush()

    # Collect the generated IDs (flush populates them).
    created_ids = [e.id for e in activity_entries]

    # Bulk-insert the corresponding MonthlyActivityEntry rows.
    monthly_entries = [
        MonthlyActivityEntry(
            member_id=member_id,
            ac_period_id=current_period.id,
            activity_type=activity_type,
            points=points,
            description=description,
            activity_date=activity_date,
            logged_by=logged_by,
        )
        for _ in range(quantity)
    ]
    db_session().add_all(monthly_entries)

    db_session().commit()

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

    ia_notice = db_session().query(InactivityNotice).filter_by(
        member_id=member_id,
        ac_period_id=current_period.id,
    ).first()

    if ia_notice:
        db_session().delete(ia_notice)
        db_session().commit()
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
    db_session().add(ia_notice)
    db_session().commit()
    return {'success': True, 'is_ia': True, 'message': 'IA set'}


def toggle_exempt_status(member_id, *, reason='Quick log exemption', approved_by='HC Team', period=None):
    """Toggle AC exemption for a member. Returns ``is_exempt`` and a message."""
    current_period = period or get_active_period()
    if not current_period:
        return {'success': False, 'error': 'no_active_period', 'message': 'No active AC period'}

    exemption = db_session().query(ACExemption).filter_by(
        member_id=member_id,
        ac_period_id=current_period.id,
    ).first()

    if exemption:
        db_session().delete(exemption)
        db_session().commit()
        return {'success': True, 'is_exempt': False, 'message': 'Exemption removed'}

    exemption = ACExemption(
        member_id=member_id,
        ac_period_id=current_period.id,
        reason=reason,
        approved_by=approved_by,
    )
    db_session().add(exemption)
    db_session().commit()
    return {'success': True, 'is_exempt': True, 'message': 'Exemption set'}


def delete_activity_entry(activity_id):
    """Delete an activity entry. Returns metadata needed for API responses."""
    activity = db_session().exec(select(ActivityEntry).filter_by(id=activity_id)).first()
    if not activity:
        return {
            'success': False,
            'error': 'activity_not_found',
            'message': f'Activity with ID {activity_id} not found',
        }

    member = db_session().get(Member, activity.member_id)
    activity_type = activity.activity_type
    points = activity.points
    ac_period_id = activity.ac_period_id

    db_session().delete(activity)
    db_session().commit()

    current_period = db_session().get(ACPeriod, ac_period_id)
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
    db_session().query(ACPeriod).filter_by(is_active=True).update({'is_active': False})
    new_period = ACPeriod(
        period_name=period_name,
        start_date=start_date,
        end_date=end_date,
        is_active=True
    )
    db_session().add(new_period)
    db_session().commit()
    return new_period


def update_period_name(period_id, period_name):
    """Update the name of an AC period."""
    period = db_session().get(ACPeriod, period_id)
    if period:
        period.period_name = period_name
        db_session().commit()
        return True
    return False


def clear_all_activities(period_id):
    """Delete all activity entries for a period."""
    deleted_count = db_session().query(ActivityEntry).filter_by(ac_period_id=period_id).delete()
    db_session().commit()
    return deleted_count


def clear_titles(period_id):
    """Delete all title tracking data (monthly activity entries) for a period."""
    deleted_count = db_session().query(MonthlyActivityEntry).filter_by(ac_period_id=period_id).delete()
    db_session().commit()
    return deleted_count


def get_period_activities(period_id):
    """Get all activity entries for a period."""
    return db_session().exec(select(ActivityEntry).filter_by(ac_period_id=period_id)).all()


def get_quick_log_data(period_id):
    """Get activities, counts, and statuses for quick logging."""
    members_with_quota = sorted(
        get_members_with_quota(),
        key=lambda m: (_rank_sort_key(m.current_rank), m.discord_username.lower()),
    )
    member_activities = {}
    member_activity_counts = {}
    member_ia_status = {}
    member_exempt_status = {}

    for member in members_with_quota:
        recent = db_session().query(ActivityEntry).filter_by(
            member_id=member.id,
            ac_period_id=period_id
        ).order_by(ActivityEntry.activity_date.desc()).limit(3).all()
        member_activities[member.id] = recent

        counts = db_session().query(
            ActivityEntry.activity_type,
            func.count(ActivityEntry.id)
        ).filter_by(
            member_id=member.id,
            ac_period_id=period_id
        ).group_by(ActivityEntry.activity_type).all()
        member_activity_counts[member.id] = dict(counts)

        ia_notice = db_session().query(InactivityNotice).filter_by(
            member_id=member.id,
            ac_period_id=period_id
        ).first()
        member_ia_status[member.id] = bool(ia_notice)

        exemption = db_session().query(ACExemption).filter_by(
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
    member = db_session().get(Member, member_id)
    if not member:
        return None

    activities = db_session().query(ActivityEntry).filter_by(
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
    query = db_session().query(ActivityEntry).filter_by(member_id=member_id)
    if period_id:
        query = query.filter_by(ac_period_id=period_id)
    deleted_count = query.delete(synchronize_session=False)
    db_session().commit()
    return deleted_count


def get_member_activities(member_id, limit=500):
    """Return recent ActivityEntry records for a member, newest first.

    The default limit is intentionally large (500) so that the Discord bot can
    search across a member's full recent history when looking up activities to
    remove.  Callers that only need a short preview should pass a smaller limit.
    """
    return (
        db_session().query(ActivityEntry)
        .filter_by(member_id=member_id)
        .order_by(ActivityEntry.activity_date.desc())
        .limit(limit)
        .all()
    )


def count_activities_by_type(member_id, activity_type=None, period_id=None):
    """Return the count of activity entries for a member.

    Args:
        member_id:      The member to query.
        activity_type:  If given, restrict to this activity type.
        period_id:      If given, restrict to a specific AC period.

    Returns:
        int if activity_type is specified, else dict mapping type → count.
    """
    query = (
        db_session().query(
            ActivityEntry.activity_type,
            func.count(ActivityEntry.id).label('cnt'),
        )
        .filter(ActivityEntry.member_id == member_id)
    )
    if period_id is not None:
        query = query.filter(ActivityEntry.ac_period_id == period_id)
    if activity_type is not None:
        query = query.filter(ActivityEntry.activity_type == activity_type)
    query = query.group_by(ActivityEntry.activity_type)

    rows = query.all()
    if activity_type is not None:
        return rows[0].cnt if rows else 0
    return {row.activity_type: row.cnt for row in rows}


def delete_activities_by_type(member_id, activity_type, quantity=1, period_id=None):
    """Delete the ``quantity`` most-recent ActivityEntry rows of ``activity_type``
    for ``member_id``.

    Args:
        member_id:      The member whose activities should be removed.
        activity_type:  The activity type to delete.
        quantity:       How many entries to delete (newest first). Use 0 or a
                        very large number to delete all of that type.
        period_id:      If given, restrict deletion to a specific AC period.

    Returns:
        dict with ``success``, ``deleted`` count, ``member``, and
        ``quota_progress`` (if a current period exists).
    """
    member = db_session().exec(select(Member).filter_by(id=member_id, is_active=True)).first()
    if not member:
        return {
            'success': False,
            'error': 'member_not_found',
            'message': f'Member with ID {member_id} not found',
        }

    # Fetch the target rows ordered newest-first so we delete the most recent.
    target_query = (
        db_session().query(ActivityEntry)
        .filter(
            ActivityEntry.member_id == member_id,
            ActivityEntry.activity_type == activity_type,
        )
    )
    if period_id is not None:
        target_query = target_query.filter(ActivityEntry.ac_period_id == period_id)

    target_query = target_query.order_by(ActivityEntry.activity_date.desc())

    # Count how many entries actually exist (before applying the limit).
    total_available = target_query.count()

    if total_available == 0:
        return {
            'success': False,
            'error': 'no_activities_found',
            'message': f'No "{activity_type}" activities found for member {member_id}',
        }

    # Guard: don't allow removing more entries than the member actually has.
    if quantity and quantity > 0 and quantity > total_available:
        return {
            'success': False,
            'error': 'not_enough_activities',
            'message': (
                f'You can\'t subtract more activity entries than the ones you have for this activity! '
                f'**{member.discord_username}** only has **{total_available}** '
                f'"{activity_type}" entr{"y" if total_available == 1 else "ies"}.'
            ),
            'available': total_available,
        }

    if quantity and quantity > 0:
        target_query = target_query.limit(quantity)

    entries_to_delete = target_query.all()
    deleted_count = len(entries_to_delete)

    for entry in entries_to_delete:
        db_session().delete(entry)
    db_session().commit()

    # Compute updated quota progress.
    current_period = get_active_period()
    if current_period:
        quota_progress = get_quota_progress(member, current_period)
    else:
        quota_progress = {'total_points': 0, 'quota': 0, 'percentage': 0}

    return {
        'success': True,
        'deleted': deleted_count,
        'activity_type': activity_type,
        'member': member,
        'quota_progress': quota_progress,
    }
