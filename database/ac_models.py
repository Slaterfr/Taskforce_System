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
    period_name = db.Column(db.String(100), nullable=False)  # "AC Period 1 - Jan 2025"
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_finalized = db.Column(db.Boolean, default=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    activity_entries = db.relationship('ActivityEntry', backref='ac_period', lazy=True)
    inactivity_notices = db.relationship('InactivityNotice', backref='ac_period', lazy=True)
    
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
    
    activity_type = db.Column(db.String(50), nullable=False)  # Mission, Training, Tryout, etc.
    points = db.Column(db.Float, nullable=False)  # 0.5, 1, 1.5, etc.
    description = db.Column(db.Text)
    activity_date = db.Column(db.DateTime, nullable=False)
    logged_by = db.Column(db.String(100), nullable=False)
    logged_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # For limited activities (evaluation, canceled training - only 1 per cycle)
    is_limited_activity = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<ActivityEntry {self.member.discord_username}: {self.activity_type} ({self.points}pts)>'
    
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
    end_date = db.Column(db.DateTime, nullable=False)  # Can be up to 1 month
    reason = db.Column(db.Text)
    approved_by = db.Column(db.String(100), nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Protection logic
    protects_ac = db.Column(db.Boolean, default=False)  # Calculated based on timing
    
    def __repr__(self):
        return f'<InactivityNotice {self.member.discord_username}: {self.start_date.strftime("%m/%d")} - {self.end_date.strftime("%m/%d")}>'
    
    def calculate_protection(self, ac_period):
        """
        Calculate if this IA protects from AC requirements
        Rules: Only protects if went IA in week 1 OR came back during week 2
        """
        # Went IA during week 1
        went_ia_week1 = ac_period.is_week1(self.start_date)
        
        # Came back during week 2  
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

# Activity types and their point values
ACTIVITY_TYPES = {
    'Mission': {
        'points': 0.5,
        'limited': False,
        'description': 'Posted or led a mission'
    },
    'Evaluation': {
        'points': 0.5,
        'limited': True,  # Only 1 per cycle
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
        'points': 1.0,
        'limited': False,
        'description': 'Led or participated in raid'
    },
    'Patrol': {
        'points': 1.0,
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
        'limited': True,  # Only 1 per cycle
        'description': 'Training session that was canceled'
    }
}

# Quota requirements by rank
AC_QUOTAS = {
    'Prospect': 1.0,      # 1 point every 2 weeks
    'Commander': 2.0,     # 2 points every 2 weeks  
    'Marshall': 3.0,      # 3 points every 2 weeks
    'General': 3.0,       # Same as Marshall
    'Chief General': 3.0  # Same as Marshall
}

def get_member_quota(rank):
    """Get AC quota for a member's rank"""
    return AC_QUOTAS.get(rank, 0.0)

def get_activity_points(activity_type):
    """Get point value for an activity type"""
    return ACTIVITY_TYPES.get(activity_type, {}).get('points', 0.0)

def is_limited_activity(activity_type):
    """Check if activity type is limited to 1 per cycle"""
    return ACTIVITY_TYPES.get(activity_type, {}).get('limited', False)