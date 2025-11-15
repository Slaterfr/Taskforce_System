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