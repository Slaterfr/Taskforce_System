"""
Activity Check (AC) Models for Taskforce Management System
Handles bi-weekly activity tracking and quota management
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from database.models import db

class ACPeriod(db.Model):
    """Represents a bi-weekly AC period"""
    __tablename__ = 'ac_periods'
    
    id = db.Column(db.Integer, primary_key=True)
    period_name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_finalized = db.Column(db.Boolean, default=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    activity_entries = db.relationship('ActivityEntry', backref='ac_period', lazy=True)
    inactivity_notices = db.relationship('InactivityNotice', backref='ac_period', lazy=True)
    exemptions = db.relationship('ACExemption', backref='ac_period', lazy=True)
    
    def __repr__(self):
        return f'<ACPeriod {self.period_name}>'
    
    @property
    def week1_end(self):
        """End of first week of the period"""
        return self.start_date + timedelta(weeks=1)
    
    def is_week1(self, date=None):
        """Check if a date falls in week 1 of the period"""
        if date is None:
            date = datetime.utcnow()
        return self.start_date <= date <= self.week1_end
    
    def is_week2(self, date=None):
        """Check if a date falls in week 2 of the period"""
        if date is None:
            date = datetime.utcnow()
        return self.week1_end < date <= self.end_date
    
    def to_dict(self):
        return {
            'id': self.id,
            'period_name': self.period_name,
            'start_date': self.start_date.strftime('%Y-%m-%d'),
            'end_date': self.end_date.strftime('%Y-%m-%d'),
            'is_active': self.is_active,
            'is_finalized': self.is_finalized
        }

class ActivityEntry(db.Model):
    """Individual activity entries for AC tracking"""
    __tablename__ = 'activity_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    ac_period_id = db.Column(db.Integer, db.ForeignKey('ac_periods.id'), nullable=False)
    
    activity_type = db.Column(db.String(50), nullable=False)
    points = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    activity_date = db.Column(db.DateTime, nullable=False)
    logged_by = db.Column(db.String(100), nullable=False)
    logged_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    is_limited_activity = db.Column(db.Boolean, default=False)
    
    # Add relationship to member
    member = db.relationship('Member', backref='activity_entries')
    
    def __repr__(self):
        return f'<ActivityEntry {self.activity_type} ({self.points}pts)>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'activity_type': self.activity_type,
            'points': self.points,
            'description': self.description,
            'activity_date': self.activity_date.strftime('%Y-%m-%d'),
            'logged_by': self.logged_by,
            'logged_date': self.logged_date.strftime('%Y-%m-%d %H:%M')
        }

class MonthlyActivityEntry(db.Model):
    """Stores activity entries for title tracking purposes - preserved across AC clears"""
    __tablename__ = 'monthly_activity_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    ac_period_id = db.Column(db.Integer, db.ForeignKey('ac_periods.id'), nullable=False)
    
    activity_type = db.Column(db.String(50), nullable=False)
    points = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    activity_date = db.Column(db.DateTime, nullable=False)
    logged_by = db.Column(db.String(100), nullable=False)
    logged_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    member = db.relationship('Member', backref='monthly_activity_entries')
    ac_period = db.relationship('ACPeriod', backref='monthly_activities')
    
    def __repr__(self):
        return f'<MonthlyActivityEntry {self.activity_type} ({self.points}pts)>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'activity_type': self.activity_type,
            'points': self.points,
            'description': self.description,
            'activity_date': self.activity_date.strftime('%Y-%m-%d'),
            'logged_by': self.logged_by,
            'logged_date': self.logged_date.strftime('%Y-%m-%d %H:%M')
        }



class InactivityNotice(db.Model):
    """Inactivity notices that can protect from AC requirements"""
    __tablename__ = 'inactivity_notices'
    
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    ac_period_id = db.Column(db.Integer, db.ForeignKey('ac_periods.id'), nullable=False)
    
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.Text)
    approved_by = db.Column(db.String(100), nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    protects_ac = db.Column(db.Boolean, default=False)
    
    # Add relationship to member
    member = db.relationship('Member', backref='inactivity_notices')
    
    def __repr__(self):
        return f'<InactivityNotice {self.start_date.strftime("%m/%d")} - {self.end_date.strftime("%m/%d")}>'
    
    def calculate_protection(self, ac_period):
        """Calculate if this IA protects from AC requirements"""
        went_ia_week1 = ac_period.is_week1(self.start_date)
        came_back_week2 = ac_period.is_week2(self.end_date)
        
        self.protects_ac = went_ia_week1 or came_back_week2
        return self.protects_ac
    
    def to_dict(self):
        return {
            'id': self.id,
            'start_date': self.start_date.strftime('%Y-%m-%d'),
            'end_date': self.end_date.strftime('%Y-%m-%d'),
            'reason': self.reason,
            'approved_by': self.approved_by,
            'protects_ac': self.protects_ac
        }

class ACExemption(db.Model):
    """Exemptions from quota requirements for a specific AC period"""
    __tablename__ = 'ac_exemptions'
    
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    ac_period_id = db.Column(db.Integer, db.ForeignKey('ac_periods.id'), nullable=False)
    
    reason = db.Column(db.Text)
    approved_by = db.Column(db.String(100), nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Add relationship to member
    member = db.relationship('Member', backref='ac_exemptions')
    
    def __repr__(self):
        return f'<ACExemption for member {self.member_id} in period {self.ac_period_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'ac_period_id': self.ac_period_id,
            'reason': self.reason,
            'approved_by': self.approved_by,
            'created_date': self.created_date.strftime('%Y-%m-%d %H:%M')
        }

class PeriodStatistics(db.Model):
    """Captures activity statistics at the end of each AC period for title tracking"""
    __tablename__ = 'period_statistics'
    
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    ac_period_id = db.Column(db.Integer, db.ForeignKey('ac_periods.id'), nullable=False)
    
    # Activity counts for the period
    raids_count = db.Column(db.Integer, default=0)
    patrols_count = db.Column(db.Integer, default=0)
    trainings_count = db.Column(db.Integer, default=0)
    missions_count = db.Column(db.Integer, default=0)
    tryouts_count = db.Column(db.Integer, default=0)
    evaluations_count = db.Column(db.Integer, default=0)
    supervision_count = db.Column(db.Integer, default=0)
    
    # Other tracking
    total_points = db.Column(db.Float, default=0.0)
    captured_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    member = db.relationship('Member', backref='period_statistics')
    ac_period = db.relationship('ACPeriod', backref='member_statistics')
    
    def __repr__(self):
        return f'<PeriodStatistics {self.member_id} period {self.ac_period_id}>'
    
    def get_combined_events(self):
        """Get total event count for HWTM (Training + Raid + Patrol)"""
        return self.trainings_count + self.raids_count + self.patrols_count
    
    def get_raid_patrol_events(self):
        """Get combined Raid + Patrol count for Leggionary"""
        return self.raids_count + self.patrols_count
    
    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'ac_period_id': self.ac_period_id,
            'raids_count': self.raids_count,
            'patrols_count': self.patrols_count,
            'trainings_count': self.trainings_count,
            'missions_count': self.missions_count,
            'tryouts_count': self.tryouts_count,
            'total_points': self.total_points,
            'captured_date': self.captured_date.strftime('%Y-%m-%d %H:%M')
        }

# Activity types and their point values
ACTIVITY_TYPES = {
    'Mission': {
        'points': 0.5,
        'limited': False,
        'description': 'Posted or led a mission'
    },
    'Evaluation': {
        'points': 0.5,
        'limited': True,
        'description': 'Conducted member evaluation'
    },
    'Supervision': {
        'points': 1.0,
        'limited': False,
        'description': 'Supervised activities or members'
    },
    'Tryout': {
        'points': 1.5,
        'limited': False,
        'description': 'Conducted recruitment tryout'
    },
    'Raid': {
        'points': 1.5,
        'limited': False,
        'description': 'Led or participated in raid'
    },
    'Patrol': {
        'points': 1.5,
        'limited': False,
        'description': 'Led patrol activity'
    },
    'Training': {
        'points': 1.0,
        'limited': False,
        'description': 'Hosted training session'
    },
    'Canceled Training': {
        'points': 0.5,
        'limited': True,
        'description': 'Training session that was canceled'
    },
    'Cancelled Tryout': {
        'points': 0.5,
        'limited': True,
        'description': 'Tryout that was cancelled'
    }
}

# Quota requirements by rank
AC_QUOTAS = {
    'Prospect': 1.0,
    'Commander': 2.0,
    'Marshal': 3.0,
    'General': 3.0,
    'Chief General': 3.0
}

def get_member_quota(rank):
    """Get AC quota for a member's rank"""
    return AC_QUOTAS.get(rank, 0.0)

def get_activity_points(activity_type):
    """Get point value for an activity type"""
    pts_map = {
        "Mission": 0.5,
        "Evaluation": 0.5,
        "Supervision": 1.0,
        "Tryout": 1.5,
        "Raid": 1.5,
        "Patrol": 1.5,
        "Training": 1.0,
        "Canceled Training": 0.5,
        "Cancelled Tryout": 0.5,
    }
    return pts_map.get(activity_type, 0.0)

def is_limited_activity(activity_type):
    """Check if activity type is limited to 1 per cycle"""
    limited = {
        "Evaluation",
        "Canceled Training",
        "Cancelled Tryout",
    }
    return activity_type in limited


# Statistical Functions for Title Tracking

def get_month_group(ac_period):
    """
    Determine which month group a period belongs to (every 2 periods = 1 month).
    Returns a tuple: (year, month_group) where month_group is 1 or 2
    
    Example: 
        - Periods 1-2 in March = (2026, 1)
        - Periods 3-4 in March = (2026, 2)
    """
    start = ac_period.start_date
    period_number = ac_period.id  # Assuming sequential IDs
    
    # Simple grouping: every 2 periods = new month group
    month_group = ((period_number - 1) // 2) + 1
    year = start.year
    month = start.month
    
    return (year, month, month_group)


def capture_period_statistics(ac_period):
    """
    Capture activity statistics for all members at the end of an AC period.
    This stores stats in PeriodStatistics for later accumulation.
    
    Called when finalizing a period.
    """
    from database.models import Member
    
    all_members = Member.query.filter_by(is_active=True).all()
    
    for member in all_members:
        # Count activities for this period
        activities = ActivityEntry.query.filter_by(
            member_id=member.id,
            ac_period_id=ac_period.id
        ).all()
        
        # Count by type
        raids = sum(1 for a in activities if a.activity_type == 'Raid')
        patrols = sum(1 for a in activities if a.activity_type == 'Patrol')
        trainings = sum(1 for a in activities if a.activity_type == 'Training')
        missions = sum(1 for a in activities if a.activity_type == 'Mission')
        tryouts = sum(1 for a in activities if a.activity_type == 'Tryout')
        evaluations = sum(1 for a in activities if a.activity_type == 'Evaluation')
        supervision = sum(1 for a in activities if a.activity_type == 'Supervision')
        
        total_points = sum(a.points for a in activities)
        
        # Check if we already captured stats for this period
        existing = PeriodStatistics.query.filter_by(
            member_id=member.id,
            ac_period_id=ac_period.id
        ).first()
        
        if existing:
            # Update existing record
            existing.raids_count = raids
            existing.patrols_count = patrols
            existing.trainings_count = trainings
            existing.missions_count = missions
            existing.tryouts_count = tryouts
            existing.evaluations_count = evaluations
            existing.supervision_count = supervision
            existing.total_points = total_points
        else:
            # Create new record
            stats = PeriodStatistics(
                member_id=member.id,
                ac_period_id=ac_period.id,
                raids_count=raids,
                patrols_count=patrols,
                trainings_count=trainings,
                missions_count=missions,
                tryouts_count=tryouts,
                evaluations_count=evaluations,
                supervision_count=supervision,
                total_points=total_points
            )
            db.session.add(stats)
    
    db.session.commit()


def get_accumulated_stats(ac_period):
    """
    Get accumulated statistics for all members based on their month group.
    Returns dict: {member_id: {'raids': count, 'patrols': count, ...}}
    
    For a given period, this returns summed stats from all periods in the same month.
    """
    month_group = get_month_group(ac_period)
    year, month, group = month_group
    
    # Find all periods in this month group
    all_periods = ACPeriod.query.all()
    periods_in_group = [
        p for p in all_periods 
        if get_month_group(p) == month_group
    ]
    
    if not periods_in_group:
        return {}
    
    period_ids = [p.id for p in periods_in_group]
    
    # Get all statistics for these periods
    all_stats = PeriodStatistics.query.filter(
        PeriodStatistics.ac_period_id.in_(period_ids)
    ).all()
    
    # Accumulate by member
    accumulated = {}
    for stat in all_stats:
        if stat.member_id not in accumulated:
            accumulated[stat.member_id] = {
                'raids': 0,
                'patrols': 0,
                'trainings': 0,
                'missions': 0,
                'tryouts': 0,
                'total_points': 0.0
            }
        
        accumulated[stat.member_id]['raids'] += stat.raids_count
        accumulated[stat.member_id]['patrols'] += stat.patrols_count
        accumulated[stat.member_id]['trainings'] += stat.trainings_count
        accumulated[stat.member_id]['missions'] += stat.missions_count
        accumulated[stat.member_id]['tryouts'] += stat.tryouts_count
        accumulated[stat.member_id]['total_points'] += stat.total_points
    
    return accumulated


def get_monthly_activity_counts(ac_period):
    """
    Get activity counts from MonthlyActivityEntry for all periods in the same month group.
    Returns dict: {member_id: {'trainings': count, 'raids': count, 'patrols': count, 'missions': count, 'tryouts': count}}
    
    This is used for title winner calculations that rely on MonthlyActivityEntry data.
    """
    month_group = get_month_group(ac_period)
    year, month, group = month_group
    
    # Find all periods in this month group
    all_periods = ACPeriod.query.all()
    periods_in_group = [
        p for p in all_periods 
        if get_month_group(p) == month_group
    ]
    
    if not periods_in_group:
        return {}
    
    period_ids = [p.id for p in periods_in_group]
    
    # Get all monthly activity entries for these periods
    activities = MonthlyActivityEntry.query.filter(
        MonthlyActivityEntry.ac_period_id.in_(period_ids)
    ).all()
    
    # Count by member and activity type
    activity_map = {}
    for activity in activities:
        if activity.member_id not in activity_map:
            activity_map[activity.member_id] = {
                'trainings': 0,
                'raids': 0,
                'patrols': 0,
                'missions': 0,
                'tryouts': 0
            }
        
        activity_type = activity.activity_type.lower()
        if activity_type == 'training':
            activity_map[activity.member_id]['trainings'] += 1
        elif activity_type == 'raid':
            activity_map[activity.member_id]['raids'] += 1
        elif activity_type == 'patrol':
            activity_map[activity.member_id]['patrols'] += 1
        elif activity_type == 'mission':
            activity_map[activity.member_id]['missions'] += 1
        elif activity_type == 'tryout':
            activity_map[activity.member_id]['tryouts'] += 1
    
    return activity_map


def get_hwtm_winner(ac_period):
    """
    Get the winner for "Host with the Most" for a specific period.
    HWTM counts: Training + Raid + Patrol from MonthlyActivityEntry for this month
    
    Returns: member_id or None, event_count
    """
    # Get activity counts from MonthlyActivityEntry for this month
    activity_counts = get_monthly_activity_counts(ac_period)
    
    if not activity_counts:
        return None, 0
    
    # Calculate combined events (Training + Raid + Patrol)
    max_events = 0
    winner_id = None
    
    for member_id, counts in activity_counts.items():
        combined = counts['trainings'] + counts['raids'] + counts['patrols']
        if combined > max_events:
            max_events = combined
            winner_id = member_id
    
    return winner_id, max_events


def get_leggionary_winner(ac_period):
    """
    Get the winner for "Leggionary" title for a period's month.
    Leggionary counts: Raid + Patrol from MonthlyActivityEntry, accumulated across the month
    
    Returns: member_id or None, event_count
    """
    # Get activity counts from MonthlyActivityEntry for this month
    activity_counts = get_monthly_activity_counts(ac_period)
    
    if not activity_counts:
        return None, 0
    
    max_events = 0
    winner_id = None
    
    for member_id, counts in activity_counts.items():
        raid_patrol_count = counts['raids'] + counts['patrols']
        if raid_patrol_count > max_events:
            max_events = raid_patrol_count
            winner_id = member_id
    
    # Must have at least 5 combined Raid + Patrol events
    if max_events >= 5:
        return winner_id, max_events
    return None, 0


def get_scout_winner(ac_period):
    """
    Get the winner for "Scout" title (most tryouts).
    Counts accumulated tryouts from MonthlyActivityEntry across the month.
    
    Returns: member_id or None, tryout_count
    """
    # Get activity counts from MonthlyActivityEntry for this month
    activity_counts = get_monthly_activity_counts(ac_period)
    
    if not activity_counts:
        return None, 0
    
    max_tryouts = 0
    winner_id = None
    
    for member_id, counts in activity_counts.items():
        if counts['tryouts'] > max_tryouts:
            max_tryouts = counts['tryouts']
            winner_id = member_id
    
    # Must have at least 5 tryouts
    if max_tryouts >= 5:
        return winner_id, max_tryouts
    return None, 0


def get_taskmaster_winner(ac_period):
    """
    Get the winner for "Taskmaster" title (most missions).
    Counts accumulated missions from MonthlyActivityEntry across the month.
    
    Returns: member_id or None, mission_count
    """
    # Get activity counts from MonthlyActivityEntry for this month
    activity_counts = get_monthly_activity_counts(ac_period)
    
    if not activity_counts:
        return None, 0
    
    max_missions = 0
    winner_id = None
    
    for member_id, counts in activity_counts.items():
        if counts['missions'] > max_missions:
            max_missions = counts['missions']
            winner_id = member_id
    
    # Must have at least 5 missions
    if max_missions >= 5:
        return winner_id, max_missions
    return None, 0


def is_last_period_of_month(ac_period):
    """
    Check if this period is the last period of its month group.
    Returns True if this is period 2, 4, 6, etc. (every even-numbered period)
    """
    return ac_period.id % 2 == 0