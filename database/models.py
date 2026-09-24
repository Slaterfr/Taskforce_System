"""
Core SQLModel models with multi-tenant scoping (tenant_id).
"""
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON, BigInteger

if TYPE_CHECKING:
    from database.ac_models import ActivityEntry, InactivityNotice, ACExemption
    from database.tenant_models import Group


class Member(SQLModel, table=True):
    __tablename__ = "members"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(default=1, index=True)
    discord_username: str = Field(max_length=100, index=True)
    discord_id: Optional[str] = Field(default=None, max_length=50, index=True)
    roblox_username: Optional[str] = Field(default=None, max_length=100)
    roblox_id: Optional[str] = Field(default=None, max_length=50)
    current_rank: str = Field(default="Aspirant", max_length=100)
    join_date: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)

    # Relationships
    activities: List["ActivityLog"] = Relationship(back_populates="member")
    promotions: List["PromotionLog"] = Relationship(back_populates="member")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "discord_username": self.discord_username,
            "discord_id": self.discord_id,
            "roblox_username": self.roblox_username,
            "roblox_id": self.roblox_id,
            "current_rank": self.current_rank,
            "join_date": self.join_date.strftime("%Y-%m-%d %H:%M:%S"),
            "last_updated": self.last_updated.strftime("%Y-%m-%d %H:%M:%S"),
        }


class ActivityLog(SQLModel, table=True):
    __tablename__ = "activity_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(default=1, index=True)
    member_id: int = Field(foreign_key="members.id")
    activity_type: str = Field(max_length=100)
    description: Optional[str] = None
    logged_by: str = Field(max_length=100)
    log_date: datetime = Field(default_factory=datetime.utcnow)

    member: Optional[Member] = Relationship(back_populates="activities")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "member_id": self.member_id,
            "activity_type": self.activity_type,
            "description": self.description,
            "logged_by": self.logged_by,
            "log_date": self.log_date.strftime("%Y-%m-%d %H:%M"),
        }


class PromotionLog(SQLModel, table=True):
    __tablename__ = "promotion_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(default=1, index=True)
    member_id: int = Field(foreign_key="members.id")
    from_rank: str = Field(max_length=100)
    to_rank: str = Field(max_length=100)
    promotion_date: datetime = Field(default_factory=datetime.utcnow)
    reason: Optional[str] = Field(default=None)
    promoted_by: Optional[str] = Field(default=None, max_length=100)

    member: Optional[Member] = Relationship(back_populates="promotions")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "member_id": self.member_id,
            "from_rank": self.from_rank,
            "to_rank": self.to_rank,
            "promotion_date": self.promotion_date.strftime("%Y-%m-%d %H:%M:%S"),
            "reason": self.reason,
            "promoted_by": self.promoted_by,
        }


class RankMapping(SQLModel, table=True):
    __tablename__ = "rank_mappings"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(default=1, index=True)
    system_rank: str = Field(max_length=100, index=True)
    roblox_role_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    roblox_role_name: Optional[str] = Field(default=None, max_length=100)
    is_active: bool = Field(default=True)
    created_date: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "system_rank": self.system_rank,
            "roblox_role_id": self.roblox_role_id,
            "roblox_role_name": self.roblox_role_name,
            "is_active": self.is_active,
        }


class MemberStats(SQLModel, table=True):
    __tablename__ = "member_stats"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(default=1, index=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_members: int
    rank_counts: dict = Field(default_factory=dict, sa_column=Column(JSON))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "total_members": self.total_members,
            "rank_counts": self.rank_counts,
        }


# ========== MISSION TRACKING MODELS ==========

class Mission(SQLModel, table=True):
    __tablename__ = "missions"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(default=1, index=True)
    discord_message_id: str = Field(max_length=50, unique=True)
    title: str = Field(max_length=255)
    description: Optional[str] = None
    stars: int = Field(default=1)
    difficulty: Optional[str] = Field(default=None, max_length=50)
    expiration_date: Optional[datetime] = None
    planet_coordinates: Optional[str] = Field(default=None, max_length=500)
    created_by_id: Optional[int] = Field(default=None, foreign_key="members.id")
    cycle_month: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    completions: List["MissionCompletion"] = Relationship(back_populates="mission")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "discord_message_id": self.discord_message_id,
            "title": self.title,
            "description": self.description,
            "stars": self.stars,
            "difficulty": self.difficulty,
            "expiration_date": self.expiration_date.strftime("%Y-%m-%d") if self.expiration_date else None,
            "planet_coordinates": self.planet_coordinates,
            "created_by_id": self.created_by_id,
            "cycle_month": self.cycle_month.strftime("%Y-%m"),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "completions_count": len(self.completions) if self.completions else 0,
        }


class MissionCompletion(SQLModel, table=True):
    __tablename__ = "mission_completions"
    __table_args__ = ({"extend_existing": True},)

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(default=1, index=True)
    mission_id: int = Field(foreign_key="missions.id")
    member_id: int = Field(foreign_key="members.id")
    logged_by_id: Optional[int] = Field(default=None, foreign_key="members.id")
    logged_at: datetime = Field(default_factory=datetime.utcnow)

    mission: Optional[Mission] = Relationship(back_populates="completions")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "mission_id": self.mission_id,
            "member_id": self.member_id,
            "logged_at": self.logged_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class MonthlyStat(SQLModel, table=True):
    __tablename__ = "monthly_stats"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(default=1, index=True)
    member_id: int = Field(foreign_key="members.id")
    cycle_month: datetime
    total_stars: int = Field(default=0)
    missions_completed: int = Field(default=0)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "member_id": self.member_id,
            "cycle_month": self.cycle_month.strftime("%Y-%m"),
            "total_stars": self.total_stars,
            "missions_completed": self.missions_completed,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
