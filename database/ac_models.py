"""
Activity Check (AC) SQLModel models and statistical helper functions.
"""
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import relationship
from sqlmodel import SQLModel, Field, Relationship, Session, select


class ACPeriod(SQLModel, table=True):
    __tablename__ = "ac_periods"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(default=1, index=True)
    period_name: str = Field(max_length=100)
    start_date: datetime
    end_date: datetime
    is_active: bool = Field(default=True)
    is_finalized: bool = Field(default=False)
    created_date: datetime = Field(default_factory=datetime.utcnow)

    activity_entries: List["ActivityEntry"] = Relationship(back_populates="ac_period")
    monthly_activities: List["MonthlyActivityEntry"] = Relationship(back_populates="ac_period")
    inactivity_notices: List["InactivityNotice"] = Relationship(back_populates="ac_period")
    exemptions: List["ACExemption"] = Relationship(back_populates="ac_period")

    @property
    def week1_end(self) -> datetime:
        return self.start_date + timedelta(weeks=1)

    def is_week1(self, date: datetime = None) -> bool:
        if date is None:
            date = datetime.utcnow()
        return self.start_date <= date <= self.week1_end

    def is_week2(self, date: datetime = None) -> bool:
        if date is None:
            date = datetime.utcnow()
        return self.week1_end < date <= self.end_date

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "period_name": self.period_name,
            "start_date": self.start_date.strftime("%Y-%m-%d"),
            "end_date": self.end_date.strftime("%Y-%m-%d"),
            "is_active": self.is_active,
            "is_finalized": self.is_finalized,
        }


class ActivityEntry(SQLModel, table=True):
    __tablename__ = "activity_entries"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(default=1, index=True)
    member_id: int = Field(foreign_key="members.id")
    ac_period_id: int = Field(foreign_key="ac_periods.id")
    activity_type: str = Field(max_length=50)
    points: float
    description: Optional[str] = None
    activity_date: datetime
    logged_by: str = Field(max_length=100)
    logged_date: datetime = Field(default_factory=datetime.utcnow)
    is_limited_activity: bool = Field(default=False)

    ac_period: Optional[ACPeriod] = Relationship(back_populates="activity_entries")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "activity_type": self.activity_type,
            "points": self.points,
            "description": self.description,
            "activity_date": self.activity_date.strftime("%Y-%m-%d"),
            "logged_by": self.logged_by,
            "logged_date": self.logged_date.strftime("%Y-%m-%d %H:%M"),
        }


class MonthlyActivityEntry(SQLModel, table=True):
    __tablename__ = "monthly_activity_entries"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(default=1, index=True)
    member_id: int = Field(foreign_key="members.id")
    ac_period_id: int = Field(foreign_key="ac_periods.id")
    activity_type: str = Field(max_length=50)
    points: float
    description: Optional[str] = None
    activity_date: datetime
    logged_by: str = Field(max_length=100)
    logged_date: datetime = Field(default_factory=datetime.utcnow)

    ac_period: Optional[ACPeriod] = Relationship(back_populates="monthly_activities")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "activity_type": self.activity_type,
            "points": self.points,
            "description": self.description,
            "activity_date": self.activity_date.strftime("%Y-%m-%d"),
            "logged_by": self.logged_by,
            "logged_date": self.logged_date.strftime("%Y-%m-%d %H:%M"),
        }


class InactivityNotice(SQLModel, table=True):
    __tablename__ = "inactivity_notices"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(default=1, index=True)
    member_id: int = Field(foreign_key="members.id")
    ac_period_id: int = Field(foreign_key="ac_periods.id")
    start_date: datetime
    end_date: datetime
    reason: Optional[str] = None
    approved_by: str = Field(max_length=100)
    created_date: datetime = Field(default_factory=datetime.utcnow)
    protects_ac: bool = Field(default=False)

    ac_period: Optional[ACPeriod] = Relationship(back_populates="inactivity_notices")

    def calculate_protection(self, ac_period: ACPeriod) -> bool:
        went_ia_week1 = ac_period.is_week1(self.start_date)
        came_back_week2 = ac_period.is_week2(self.end_date)
        self.protects_ac = went_ia_week1 or came_back_week2
        return self.protects_ac

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "start_date": self.start_date.strftime("%Y-%m-%d"),
            "end_date": self.end_date.strftime("%Y-%m-%d"),
            "reason": self.reason,
            "approved_by": self.approved_by,
            "protects_ac": self.protects_ac,
        }


class ACExemption(SQLModel, table=True):
    __tablename__ = "ac_exemptions"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(default=1, index=True)
    member_id: int = Field(foreign_key="members.id")
    ac_period_id: int = Field(foreign_key="ac_periods.id")
    reason: Optional[str] = None
    approved_by: str = Field(max_length=100)
    created_date: datetime = Field(default_factory=datetime.utcnow)

    ac_period: Optional[ACPeriod] = Relationship(back_populates="exemptions")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "member_id": self.member_id,
            "ac_period_id": self.ac_period_id,
            "reason": self.reason,
            "approved_by": self.approved_by,
            "created_date": self.created_date.strftime("%Y-%m-%d %H:%M"),
        }


class PeriodStatistics(SQLModel, table=True):
    __tablename__ = "period_statistics"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(default=1, index=True)
    member_id: int = Field(foreign_key="members.id")
    ac_period_id: int = Field(foreign_key="ac_periods.id")
    raids_count: int = Field(default=0)
    patrols_count: int = Field(default=0)
    trainings_count: int = Field(default=0)
    missions_count: int = Field(default=0)
    tryouts_count: int = Field(default=0)
    evaluations_count: int = Field(default=0)
    supervision_count: int = Field(default=0)
    total_points: float = Field(default=0.0)
    captured_date: datetime = Field(default_factory=datetime.utcnow)

    def get_combined_events(self) -> int:
        return self.trainings_count + self.raids_count + self.patrols_count

    def get_raid_patrol_events(self) -> int:
        return self.raids_count + self.patrols_count

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "member_id": self.member_id,
            "ac_period_id": self.ac_period_id,
            "raids_count": self.raids_count,
            "patrols_count": self.patrols_count,
            "trainings_count": self.trainings_count,
            "missions_count": self.missions_count,
            "tryouts_count": self.tryouts_count,
            "total_points": self.total_points,
            "captured_date": self.captured_date.strftime("%Y-%m-%d %H:%M"),
        }


class ActivityType(SQLModel, table=True):
    __tablename__ = "activity_types"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(default=1, index=True)
    name: str = Field(max_length=100, index=True)
    points: float = Field(default=1.0)
    is_limited: bool = Field(default=False)
    description: Optional[str] = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "points": self.points,
            "is_limited": self.is_limited,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
        }


class RankQuota(SQLModel, table=True):
    __tablename__ = "rank_quotas"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(default=1, index=True)
    rank_name: str = Field(max_length=100, index=True)
    required_points: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "rank_name": self.rank_name,
            "required_points": self.required_points,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M"),
        }


class Title(SQLModel, table=True):
    __tablename__ = "titles"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(default=1, index=True)
    name: str = Field(max_length=100, index=True)
    description: Optional[str] = Field(default=None, max_length=255)
    activity_required: str = Field(max_length=100)
    quantity_required: int = Field(default=5)
    period_type: str = Field(default="monthly", max_length=50)  # 'monthly' or 'cycle'
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "description": self.description,
            "activity_required": self.activity_required,
            "quantity_required": self.quantity_required,
            "period_type": self.period_type,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M"),
        }


# -- Statistical helpers (require a Session, no more Model.query) --------------

def get_month_group(ac_period: ACPeriod) -> tuple:
    """Return (year, month, month_group) for the period."""
    start = ac_period.start_date
    month_group = ((ac_period.id - 1) // 2) + 1
    return (start.year, start.month, month_group)


def capture_period_statistics(ac_period: ACPeriod, session: Session) -> None:
    """Snapshot activity counts for all members at the end of a period."""
    from database.models import Member

    all_members = session.exec(select(Member).where(Member.is_active == True)).all()

    for member in all_members:
        activities = session.exec(
            select(ActivityEntry).where(
                ActivityEntry.member_id == member.id,
                ActivityEntry.ac_period_id == ac_period.id,
            )
        ).all()

        raids       = sum(1 for a in activities if a.activity_type == "Raid")
        patrols     = sum(1 for a in activities if a.activity_type == "Patrol")
        trainings   = sum(1 for a in activities if a.activity_type == "Training")
        missions    = sum(1 for a in activities if a.activity_type == "Mission")
        tryouts     = sum(1 for a in activities if a.activity_type == "Tryout")
        evaluations = sum(1 for a in activities if a.activity_type == "Evaluation")
        supervision = sum(1 for a in activities if a.activity_type == "Supervision")
        total_pts   = sum(a.points for a in activities)

        existing = session.exec(
            select(PeriodStatistics).where(
                PeriodStatistics.member_id == member.id,
                PeriodStatistics.ac_period_id == ac_period.id,
            )
        ).first()

        if existing:
            existing.raids_count       = raids
            existing.patrols_count     = patrols
            existing.trainings_count   = trainings
            existing.missions_count    = missions
            existing.tryouts_count     = tryouts
            existing.evaluations_count = evaluations
            existing.supervision_count = supervision
            existing.total_points      = total_pts
            session.add(existing)
        else:
            session.add(PeriodStatistics(
                member_id=member.id,
                ac_period_id=ac_period.id,
                raids_count=raids,
                patrols_count=patrols,
                trainings_count=trainings,
                missions_count=missions,
                tryouts_count=tryouts,
                evaluations_count=evaluations,
                supervision_count=supervision,
                total_points=total_pts,
            ))

    session.commit()


def _get_periods_in_group(ac_period: ACPeriod, session: Optional[Session] = None) -> list:
    if session is None:
        from database.engine import db_session
        session = db_session()
    month_group = get_month_group(ac_period)
    tenant_id = getattr(ac_period, "tenant_id", 1) or 1
    all_periods = session.exec(select(ACPeriod).where(ACPeriod.tenant_id == tenant_id)).all()
    return [p for p in all_periods if get_month_group(p) == month_group]


def get_accumulated_stats(ac_period: ACPeriod, session: Optional[Session] = None) -> dict:
    """Accumulated PeriodStatistics across all periods in the same month group."""
    if session is None:
        from database.engine import db_session
        session = db_session()
    periods = _get_periods_in_group(ac_period, session)
    if not periods:
        return {}
    period_ids = [p.id for p in periods]
    all_stats = session.exec(
        select(PeriodStatistics).where(PeriodStatistics.ac_period_id.in_(period_ids))
    ).all()
    accumulated: dict = {}
    for stat in all_stats:
        acc = accumulated.setdefault(stat.member_id, {
            "raids": 0, "patrols": 0, "trainings": 0,
            "missions": 0, "tryouts": 0, "total_points": 0.0,
        })
        acc["raids"]        += stat.raids_count
        acc["patrols"]      += stat.patrols_count
        acc["trainings"]    += stat.trainings_count
        acc["missions"]     += stat.missions_count
        acc["tryouts"]      += stat.tryouts_count
        acc["total_points"] += stat.total_points
    return accumulated


def get_monthly_activity_counts(ac_period: ACPeriod, session: Optional[Session] = None) -> dict:
    """Activity counts from MonthlyActivityEntry for all periods in the same month group."""
    if session is None:
        from database.engine import db_session
        session = db_session()
    periods = _get_periods_in_group(ac_period, session)
    if not periods:
        return {}
    period_ids = [p.id for p in periods]
    activities = session.exec(
        select(MonthlyActivityEntry).where(MonthlyActivityEntry.ac_period_id.in_(period_ids))
    ).all()
    activity_map: dict = {}
    for activity in activities:
        counts = activity_map.setdefault(activity.member_id, {
            "trainings": 0, "raids": 0, "patrols": 0, "missions": 0, "tryouts": 0,
        })
        t = activity.activity_type.lower()
        if t == "training":   counts["trainings"] += 1
        elif t == "raid":     counts["raids"]     += 1
        elif t == "patrol":   counts["patrols"]   += 1
        elif t == "mission":  counts["missions"]  += 1
        elif t == "tryout":   counts["tryouts"]   += 1
    return activity_map


def get_hwtm_winner(ac_period: ACPeriod, session: Optional[Session] = None) -> tuple:
    if session is None:
        from database.engine import db_session
        session = db_session()
    counts = get_monthly_activity_counts(ac_period, session)
    if not counts:
        return None, 0
    winner_id, max_events = None, 0
    for member_id, c in counts.items():
        combined = c["trainings"] + c["raids"] + c["patrols"]
        if combined > max_events:
            max_events, winner_id = combined, member_id
    return winner_id, max_events


def get_leggionary_winner(ac_period: ACPeriod, session: Optional[Session] = None) -> tuple:
    if session is None:
        from database.engine import db_session
        session = db_session()
    counts = get_monthly_activity_counts(ac_period, session)
    if not counts:
        return None, 0
    winner_id, max_events = None, 0
    for member_id, c in counts.items():
        rp = c["raids"] + c["patrols"]
        if rp > max_events:
            max_events, winner_id = rp, member_id
    return (winner_id, max_events) if max_events >= 5 else (None, 0)


def get_scout_winner(ac_period: ACPeriod, session: Optional[Session] = None) -> tuple:
    if session is None:
        from database.engine import db_session
        session = db_session()
    counts = get_monthly_activity_counts(ac_period, session)
    if not counts:
        return None, 0
    winner_id, max_t = None, 0
    for member_id, c in counts.items():
        if c["tryouts"] > max_t:
            max_t, winner_id = c["tryouts"], member_id
    return (winner_id, max_t) if max_t >= 5 else (None, 0)


def get_taskmaster_winner(ac_period: ACPeriod, session: Optional[Session] = None) -> tuple:
    if session is None:
        from database.engine import db_session
        session = db_session()
    counts = get_monthly_activity_counts(ac_period, session)
    if not counts:
        return None, 0
    winner_id, max_m = None, 0
    for member_id, c in counts.items():
        if c["missions"] > max_m:
            max_m, winner_id = c["missions"], member_id
    return (winner_id, max_m) if max_m >= 5 else (None, 0)


def is_last_period_of_month(ac_period: ACPeriod) -> bool:
    return ac_period.id % 2 == 0
