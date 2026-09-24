"""Activity Check (AC) business logic."""

from typing import Optional, List, Dict, Any
from datetime import date, datetime
from sqlalchemy import func
from sqlmodel import select, Session

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
    Title,
    _get_periods_in_group,
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


# -- Dynamic Activity Types & Rank Quotas Management -------------------------

def get_all_activity_types(tenant_id: int = 1, include_inactive: bool = True) -> list:
    """Return all ActivityType objects for a tenant, ordered by name."""
    session = db_session()
    stmt = select(ActivityType).where(ActivityType.tenant_id == tenant_id)
    if not include_inactive:
        stmt = stmt.where(ActivityType.is_active == True)
    return session.exec(stmt.order_by(ActivityType.name)).all()


def create_activity_type(
    name: str,
    points: float,
    is_limited: bool = False,
    description: str = "",
    tenant_id: int = 1,
) -> dict:
    """Create a new activity type."""
    name = (name or "").strip()
    if not name:
        return {"success": False, "error": "Name is required"}

    session = db_session()
    existing = session.exec(
        select(ActivityType).where(
            ActivityType.tenant_id == tenant_id,
            func.lower(ActivityType.name) == name.lower(),
        )
    ).first()
    if existing:
        return {"success": False, "error": f"Activity '{name}' already exists"}

    new_type = ActivityType(
        tenant_id=tenant_id,
        name=name,
        points=float(points),
        is_limited=bool(is_limited),
        description=description.strip() if description else None,
        is_active=True,
    )
    session.add(new_type)
    session.commit()
    session.refresh(new_type)
    return {"success": True, "activity_type": new_type}


def update_activity_type(
    activity_type_id: int,
    name: str,
    points: float,
    is_limited: bool,
    description: str,
    is_active: bool = True,
) -> dict:
    """Update an existing activity type."""
    name = (name or "").strip()
    if not name:
        return {"success": False, "error": "Name is required"}

    session = db_session()
    act = session.get(ActivityType, activity_type_id)
    if not act:
        return {"success": False, "error": "Activity type not found"}

    conflict = session.exec(
        select(ActivityType).where(
            ActivityType.tenant_id == act.tenant_id,
            func.lower(ActivityType.name) == name.lower(),
            ActivityType.id != activity_type_id,
        )
    ).first()
    if conflict:
        return {"success": False, "error": f"Another activity named '{name}' already exists"}

    act.name = name
    act.points = float(points)
    act.is_limited = bool(is_limited)
    act.description = description.strip() if description else None
    act.is_active = bool(is_active)
    session.add(act)
    session.commit()
    session.refresh(act)
    return {"success": True, "activity_type": act}


def delete_activity_type(activity_type_id: int) -> dict:
    """Delete an activity type."""
    session = db_session()
    act = session.get(ActivityType, activity_type_id)
    if not act:
        return {"success": False, "error": "Activity type not found"}

    session.delete(act)
    session.commit()
    return {"success": True}


def get_all_rank_quotas(tenant_id: int = 1) -> list:
    """Return all RankQuota objects for a tenant, sorted by quota points descending."""
    session = db_session()
    return session.exec(
        select(RankQuota)
        .where(RankQuota.tenant_id == tenant_id)
        .order_by(RankQuota.required_points.desc(), RankQuota.rank_name)
    ).all()


def create_rank_quota(
    rank_name: str,
    required_points: float,
    tenant_id: int = 1,
) -> dict:
    """Create a new rank quota requirement."""
    rank_name = (rank_name or "").strip()
    if not rank_name:
        return {"success": False, "error": "Rank name is required"}

    session = db_session()
    existing = session.exec(
        select(RankQuota).where(
            RankQuota.tenant_id == tenant_id,
            func.lower(RankQuota.rank_name) == rank_name.lower(),
        )
    ).first()
    if existing:
        return {"success": False, "error": f"Quota for rank '{rank_name}' already exists"}

    new_quota = RankQuota(
        tenant_id=tenant_id,
        rank_name=rank_name,
        required_points=float(required_points),
    )
    session.add(new_quota)
    session.commit()
    session.refresh(new_quota)
    return {"success": True, "quota": new_quota}


def update_rank_quota(
    quota_id: int,
    rank_name: str,
    required_points: float,
) -> dict:
    """Update an existing rank quota requirement."""
    rank_name = (rank_name or "").strip()
    if not rank_name:
        return {"success": False, "error": "Rank name is required"}

    session = db_session()
    quota = session.get(RankQuota, quota_id)
    if not quota:
        return {"success": False, "error": "Rank quota not found"}

    conflict = session.exec(
        select(RankQuota).where(
            RankQuota.tenant_id == quota.tenant_id,
            func.lower(RankQuota.rank_name) == rank_name.lower(),
            RankQuota.id != quota_id,
        )
    ).first()
    if conflict:
        return {"success": False, "error": f"Another quota for rank '{rank_name}' already exists"}

    quota.rank_name = rank_name
    quota.required_points = float(required_points)
    quota.updated_at = datetime.utcnow()
    session.add(quota)
    session.commit()
    session.refresh(quota)
    return {"success": True, "quota": quota}


def delete_rank_quota(quota_id: int) -> dict:
    """Delete a rank quota requirement."""
    session = db_session()
    quota = session.get(RankQuota, quota_id)
    if not quota:
        return {"success": False, "error": "Rank quota not found"}

    session.delete(quota)
    session.commit()
    return {"success": True}


# -- Dynamic Titles & Accolades Management -----------------------------------

def get_all_titles(tenant_id: int = 1, include_inactive: bool = True) -> list:
    """Return all Title objects for a tenant, sorted by name."""
    session = db_session()
    stmt = select(Title).where(Title.tenant_id == tenant_id)
    if not include_inactive:
        stmt = stmt.where(Title.is_active == True)
    return session.exec(stmt.order_by(Title.period_type.desc(), Title.name)).all()


def create_title(
    name: str,
    activity_required: str,
    quantity_required: int = 5,
    description: str = "",
    period_type: str = "monthly",
    tenant_id: int = 1,
) -> dict:
    """Create a new title reward definition."""
    name = (name or "").strip()
    activity_required = (activity_required or "").strip()
    if not name:
        return {"success": False, "error": "Title name is required"}
    if not activity_required:
        return {"success": False, "error": "Activity requirement is required"}

    try:
        qty = int(quantity_required)
        if qty < 1:
            qty = 1
    except (ValueError, TypeError):
        qty = 5

    session = db_session()
    existing = session.exec(
        select(Title).where(
            Title.tenant_id == tenant_id,
            func.lower(Title.name) == name.lower(),
        )
    ).first()
    if existing:
        return {"success": False, "error": f"Title '{name}' already exists in this sector"}

    new_title = Title(
        tenant_id=tenant_id,
        name=name,
        description=description.strip() if description else None,
        activity_required=activity_required,
        quantity_required=qty,
        period_type=period_type if period_type in ["monthly", "cycle"] else "monthly",
        is_active=True,
    )
    session.add(new_title)
    session.commit()
    session.refresh(new_title)
    return {"success": True, "title": new_title}


def update_title(
    title_id: int,
    name: str,
    activity_required: str,
    quantity_required: int,
    description: str = "",
    period_type: str = "monthly",
    is_active: bool = True,
) -> dict:
    """Update an existing title reward definition."""
    name = (name or "").strip()
    activity_required = (activity_required or "").strip()
    if not name:
        return {"success": False, "error": "Title name is required"}
    if not activity_required:
        return {"success": False, "error": "Activity requirement is required"}

    try:
        qty = int(quantity_required)
        if qty < 1:
            qty = 1
    except (ValueError, TypeError):
        qty = 5

    session = db_session()
    title = session.get(Title, title_id)
    if not title:
        return {"success": False, "error": "Title not found"}

    conflict = session.exec(
        select(Title).where(
            Title.tenant_id == title.tenant_id,
            func.lower(Title.name) == name.lower(),
            Title.id != title_id,
        )
    ).first()
    if conflict:
        return {"success": False, "error": f"Another title named '{name}' already exists in this sector"}

    title.name = name
    title.description = description.strip() if description else None
    title.activity_required = activity_required
    title.quantity_required = qty
    title.period_type = period_type if period_type in ["monthly", "cycle"] else "monthly"
    title.is_active = bool(is_active)
    title.updated_at = datetime.utcnow()

    session.add(title)
    session.commit()
    session.refresh(title)
    return {"success": True, "title": title}


def delete_title(title_id: int) -> dict:
    """Delete a title definition."""
    session = db_session()
    title = session.get(Title, title_id)
    if not title:
        return {"success": False, "error": "Title not found"}

    session.delete(title)
    session.commit()
    return {"success": True}




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


def _matches_activity_requirement(entry_act_type: str, req: str) -> bool:
    """Case-insensitive matcher for title activity requirements including presets."""
    t = (entry_act_type or "").strip().lower()
    r = (req or "").strip().lower()
    if r in ["all", "all activities", "all activities (combined)", "any"]:
        return True
    if "events" in r or "training + raid + patrol" in r:
        return t in ["training", "raid", "patrol"]
    if "raids + patrols" in r or "raid + patrol" in r:
        return t in ["raid", "patrol"]
    return t == r


def ensure_default_titles_for_tenant(tenant_id: int, session: Optional[Session] = None):
    """Seed standard sector titles for tenant 1 if no titles exist yet."""
    if session is None:
        session = db_session()
    existing = session.exec(select(Title).where(Title.tenant_id == tenant_id)).first()
    if not existing and tenant_id == 1:
        default_titles = [
            Title(
                tenant_id=1,
                name="Host with the Most",
                activity_required="Events (Training + Raid + Patrol)",
                quantity_required=5,
                period_type="cycle",
                description="5+ events hosted (Training + Raid + Patrol)",
                is_active=True,
            ),
            Title(
                tenant_id=1,
                name="Legionnaire",
                activity_required="Raids + Patrols",
                quantity_required=5,
                period_type="monthly",
                description="5+ raids and patrols hosted across month",
                is_active=True,
            ),
            Title(
                tenant_id=1,
                name="Scout",
                activity_required="Tryout",
                quantity_required=5,
                period_type="monthly",
                description="5+ tryouts hosted across month",
                is_active=True,
            ),
            Title(
                tenant_id=1,
                name="Taskmaster",
                activity_required="Mission",
                quantity_required=5,
                period_type="monthly",
                description="5+ missions posted across month",
                is_active=True,
            ),
        ]
        session.add_all(default_titles)
        session.commit()


def calculate_title_rewards(all_activities, period):
    """
    Calculate title reward winners based strictly on what is in the database for each group.
    Uses MonthlyActivityEntry for persistent title tracking across multiple cycles
    for monthly awards, and ActivityEntry for cycle-specific awards.
    """
    titles = {}
    session = db_session()
    tenant_id = getattr(period, "tenant_id", 1) or 1

    # Ensure default titles exist in DB for Taskforce (Tenant 1)
    ensure_default_titles_for_tenant(tenant_id, session)

    # 1. Fetch configured titles strictly from the database for this group
    title_defs = session.exec(
        select(Title).where(Title.tenant_id == tenant_id, Title.is_active == True)
    ).all()

    if not title_defs:
        return titles

    periods_in_month = _get_periods_in_group(period, session)
    month_period_ids = [p.id for p in periods_in_month]

    for title_def in title_defs:
        is_monthly = (title_def.period_type == "monthly")
        
        # Select persistent data source
        if is_monthly:
            # Query MonthlyActivityEntry across all periods in this month group (replicated & persistent)
            entries = session.exec(
                select(MonthlyActivityEntry).where(MonthlyActivityEntry.ac_period_id.in_(month_period_ids))
            ).all()
        else:
            # Single AC Cycle: query ActivityEntry for this period, falling back to MonthlyActivityEntry for period
            entries = session.exec(
                select(ActivityEntry).where(ActivityEntry.ac_period_id == period.id)
            ).all()
            if not entries:
                entries = session.exec(
                    select(MonthlyActivityEntry).where(MonthlyActivityEntry.ac_period_id == period.id)
                ).all()

        # Tally counts per member matching the activity criteria
        member_counts = {}
        for e in entries:
            if _matches_activity_requirement(e.activity_type, title_def.activity_required):
                member_counts[e.member_id] = member_counts.get(e.member_id, 0) + 1

        # Determine top performer
        max_count = 0
        top_member_id = None
        for m_id, count in member_counts.items():
            if count > max_count:
                max_count = count
                top_member_id = m_id

        # Format requirement display label
        req_label = f"{title_def.quantity_required}+ {title_def.activity_required}"
        if title_def.description:
            req_label += f" ({title_def.description})"
        if is_monthly:
            req_label += " - monthly"

        winner_name = "No participants"
        is_qualified = False
        if top_member_id:
            winner_member = session.get(Member, top_member_id)
            if winner_member:
                winner_name = winner_member.discord_username or winner_member.roblox_username or "Unknown"
            is_qualified = max_count >= title_def.quantity_required

        titles[title_def.name] = {
            'winner': winner_name,
            'count': max_count,
            'requirement': req_label,
            'period_award': not is_monthly,
            'is_monthly': is_monthly,
            'qualified': is_qualified,
            'has_participants': max_count > 0,
            'quantity_required': title_def.quantity_required,
            'activity_required': title_def.activity_required,
            'description': title_def.description or '',
        }

    return titles


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

    tenant_id = getattr(current_period, "tenant_id", 1) or 1

    # Build all ActivityEntry objects at once, then bulk-insert for efficiency.
    activity_entries = [
        ActivityEntry(
            tenant_id=tenant_id,
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
            tenant_id=tenant_id,
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
    session.add_all(monthly_entries)
    session.commit()

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


def create_period(period_name, start_date, end_date, tenant_id: int = None):
    """Deactivate any current period for this sector and create a new AC period."""
    effective_tenant = tenant_id or get_tenant_id() or 1
    session = db_session()
    
    # Deactivate only active periods belonging to THIS sector
    active_periods = session.exec(
        select(ACPeriod).where(ACPeriod.tenant_id == effective_tenant, ACPeriod.is_active == True)
    ).all()
    for p in active_periods:
        p.is_active = False
        session.add(p)

    new_period = ACPeriod(
        tenant_id=effective_tenant,
        period_name=period_name,
        start_date=start_date,
        end_date=end_date,
        is_active=True
    )
    session.add(new_period)
    session.commit()
    session.refresh(new_period)
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


def clear_titles(period_id=None, tenant_id: int = 1):
    """Delete title tracking data (monthly activity entries). If period_id is provided, deletes for that period, otherwise for the whole tenant."""
    query = db_session().query(MonthlyActivityEntry).filter(MonthlyActivityEntry.tenant_id == tenant_id)
    if period_id is not None:
        query = query.filter(MonthlyActivityEntry.ac_period_id == period_id)
    deleted_count = query.delete(synchronize_session=False)
    db_session().commit()
    return deleted_count


def clear_all_monthly_entries(tenant_id: int = 1) -> int:
    """Delete all monthly activity entries for a tenant so they don't accumulate indefinitely."""
    deleted_count = db_session().query(MonthlyActivityEntry).filter(
        MonthlyActivityEntry.tenant_id == tenant_id
    ).delete(synchronize_session=False)
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
