from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Member(db.Model):
    __tablename__ = 'members'
    
    id = db.Column(db.Integer, primary_key=True)
    discord_username = db.Column(db.String(100), nullable=False, unique=True)
    discord_id = db.Column(db.String(50), nullable=True, unique=True)
    roblox_username = db.Column(db.String(100), nullable=True)
    roblox_id = db.Column(db.String(50), nullable=True)
    current_rank = db.Column(db.String(100), nullable=False, default='Aspirant')
    join_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    activities = db.relationship('ActivityLog', backref='member', lazy=True, cascade='all, delete-orphan')
    promotions = db.relationship('PromotionLog', backref='member', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Member {self.discord_username}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'discord_username': self.discord_username,
            'roblox_username': self.roblox_username,
            'current_rank': self.current_rank,
            'join_date': self.join_date.strftime('%Y-%m-%d'),
            'last_updated': self.last_updated.strftime('%Y-%m-%d %H:%M'),
            'is_active': self.is_active
        }

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    activity_type = db.Column(db.String(100), nullable=False)  # 'training', 'operation', 'event', etc.
    description = db.Column(db.Text, nullable=True)
    logged_by = db.Column(db.String(100), nullable=False)  # Who logged this activity
    log_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ActivityLog {self.member_id}: {self.activity_type}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'activity_type': self.activity_type,
            'description': self.description,
            'logged_by': self.logged_by,
            'log_date': self.log_date.strftime('%Y-%m-%d %H:%M')
        }

class PromotionLog(db.Model):
    __tablename__ = 'promotion_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    from_rank = db.Column(db.String(100), nullable=False)
    to_rank = db.Column(db.String(100), nullable=False)
    reason = db.Column(db.Text, nullable=True)
    promoted_by = db.Column(db.String(100), nullable=False)
    promotion_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<PromotionLog {self.member_id}: {self.from_rank} -> {self.to_rank}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'from_rank': self.from_rank,
            'to_rank': self.to_rank,
            'reason': self.reason,
            'promoted_by': self.promoted_by,
            'promotion_date': self.promotion_date.strftime('%Y-%m-%d %H:%M')
        }

class RankMapping(db.Model):
    """Maps system ranks to Roblox group role IDs"""
    __tablename__ = 'rank_mappings'
    
    id = db.Column(db.Integer, primary_key=True)
    system_rank = db.Column(db.String(100), nullable=False, unique=True)
    roblox_role_id = db.Column(db.Integer, nullable=False)
    roblox_role_name = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<RankMapping {self.system_rank} -> Role {self.roblox_role_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'system_rank': self.system_rank,
            'roblox_role_id': self.roblox_role_id,
            'roblox_role_name': self.roblox_role_name,
            'is_active': self.is_active
        }

class MemberStats(db.Model):
    """Stores historical snapshots of member counts"""
    __tablename__ = 'member_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    total_members = db.Column(db.Integer, nullable=False)
    rank_counts = db.Column(db.JSON, nullable=False)  # usage: {"General": 2, "Private": 50}
    
    def __repr__(self):
        return f'<MemberStats {self.timestamp}: {self.total_members}>'


# ========== MISSION TRACKING MODELS ==========

class Mission(db.Model):
    """Represents a mission posted in Discord"""
    __tablename__ = 'missions'
    
    id = db.Column(db.Integer, primary_key=True)
    discord_message_id = db.Column(db.String(50), nullable=False, unique=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    stars = db.Column(db.Integer, nullable=False, default=1)  # Difficulty level
    difficulty = db.Column(db.String(50), nullable=True)  # e.g., "⭐⭐⭐"
    expiration_date = db.Column(db.Date, nullable=True)
    planet_coordinates = db.Column(db.String(500), nullable=True)  # URL or coords
    created_by_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=True)
    cycle_month = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    completions = db.relationship('MissionCompletion', backref='mission', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Mission {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'discord_message_id': self.discord_message_id,
            'title': self.title,
            'description': self.description,
            'stars': self.stars,
            'difficulty': self.difficulty,
            'expiration_date': self.expiration_date.strftime('%Y-%m-%d') if self.expiration_date else None,
            'planet_coordinates': self.planet_coordinates,
            'created_by_id': self.created_by_id,
            'cycle_month': self.cycle_month.strftime('%Y-%m'),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'completions_count': len(self.completions)
        }


class MissionCompletion(db.Model):
    """Records which members completed which missions"""
    __tablename__ = 'mission_completions'
    
    id = db.Column(db.Integer, primary_key=True)
    mission_id = db.Column(db.Integer, db.ForeignKey('missions.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    logged_by_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=True)
    logged_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Unique constraint: one member can only complete each mission once
    __table_args__ = (db.UniqueConstraint('mission_id', 'member_id', name='unique_mission_completion'),)
    
    # Relationships
    member = db.relationship('Member', foreign_keys=[member_id], backref='mission_completions')
    logged_by = db.relationship('Member', foreign_keys=[logged_by_id])
    
    def __repr__(self):
        return f'<MissionCompletion mission_id={self.mission_id} member_id={self.member_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'mission_id': self.mission_id,
            'member_id': self.member_id,
            'member_username': self.member.discord_username if self.member else None,
            'logged_at': self.logged_at.strftime('%Y-%m-%d %H:%M:%S')
        }


class MonthlyStat(db.Model):
    """Tracks monthly mission statistics per member"""
    __tablename__ = 'monthly_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    cycle_month = db.Column(db.Date, nullable=False)  # First day of the month
    total_stars = db.Column(db.Integer, nullable=False, default=0)
    missions_completed = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint: one record per member per month
    __table_args__ = (db.UniqueConstraint('member_id', 'cycle_month', name='unique_member_month'),)
    
    # Relationships
    member = db.relationship('Member', backref='monthly_stats')
    
    def __repr__(self):
        return f'<MonthlyStat member_id={self.member_id} {self.cycle_month.strftime("%Y-%m")}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'member_username': self.member.discord_username if self.member else None,
            'cycle_month': self.cycle_month.strftime('%Y-%m'),
            'total_stars': self.total_stars,
            'missions_completed': self.missions_completed,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }
