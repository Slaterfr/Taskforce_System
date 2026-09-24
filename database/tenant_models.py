"""
Multi-tenant and Identity models: User, Group, GroupMember, and GroupPermissionRule.
"""
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON, Text, BigInteger

if TYPE_CHECKING:
    from database.models import Member



class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    roblox_id: str = Field(max_length=50, unique=True, index=True)
    roblox_username: str = Field(max_length=100, index=True)
    display_name: Optional[str] = Field(default=None, max_length=100)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    is_superadmin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    group_memberships: List["GroupMember"] = Relationship(back_populates="user")
    owned_groups: List["Group"] = Relationship(back_populates="owner")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "roblox_id": self.roblox_id,
            "roblox_username": self.roblox_username,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "is_superadmin": self.is_superadmin,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "last_login": self.last_login.strftime("%Y-%m-%d %H:%M:%S"),
        }


class Group(SQLModel, table=True):
    __tablename__ = "groups"

    id: Optional[int] = Field(default=None, primary_key=True)
    roblox_group_id: str = Field(max_length=50, unique=True, index=True)
    name: str = Field(max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    icon_url: Optional[str] = Field(default=None, max_length=500)
    owner_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    is_active: bool = Field(default=True)
    discord_group_id: Optional[str] = Field(default=None, max_length=50, index=True)
    settings: dict = Field(default_factory=dict, sa_column=Column(JSON))

    # Relationships
    owner: Optional[User] = Relationship(back_populates="owned_groups")
    members: List["GroupMember"] = Relationship(back_populates="group")
    permission_rules: List["GroupPermissionRule"] = Relationship(back_populates="group")
    cookie: Optional["GroupCookie"] = Relationship(back_populates="group")

    def get_settings_dict(self) -> dict:
        if not self.settings:
            return {}
        if isinstance(self.settings, dict):
            return dict(self.settings)
        if isinstance(self.settings, str):
            import json
            try:
                parsed = json.loads(self.settings)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        return {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "roblox_group_id": self.roblox_group_id,
            "name": self.name,
            "description": self.description,
            "icon_url": self.icon_url,
            "owner_user_id": self.owner_user_id,
            "is_active": self.is_active,
            "discord_group_id": self.discord_group_id,
            "settings": self.get_settings_dict(),
        }


class GroupMember(SQLModel, table=True):
    __tablename__ = "group_members"

    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="groups.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    roblox_role_id: int = Field(default=0, sa_column=Column(BigInteger, default=0))
    roblox_role_name: str = Field(default="Guest", max_length=100)
    roblox_rank: int = Field(default=1)
    system_role: str = Field(default="member", max_length=50)  # member, staff, hct, admin
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    last_synced: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    group: Optional[Group] = Relationship(back_populates="members")
    user: Optional[User] = Relationship(back_populates="group_memberships")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "group_id": self.group_id,
            "user_id": self.user_id,
            "roblox_role_id": self.roblox_role_id,
            "roblox_role_name": self.roblox_role_name,
            "roblox_rank": self.roblox_rank,
            "system_role": self.system_role,
            "joined_at": self.joined_at.strftime("%Y-%m-%d %H:%M:%S"),
            "last_synced": self.last_synced.strftime("%Y-%m-%d %H:%M:%S"),
        }


class GroupPermissionRule(SQLModel, table=True):
    __tablename__ = "group_permission_rules"

    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="groups.id", index=True)
    min_roblox_rank: int = Field(default=1)
    max_roblox_rank: Optional[int] = Field(default=None)
    specific_role_id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    system_role: str = Field(max_length=50)  # member, staff, hct, admin
    permissions: list = Field(default_factory=list, sa_column=Column(JSON))

    # Relationships
    group: Optional[Group] = Relationship(back_populates="permission_rules")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "group_id": self.group_id,
            "min_roblox_rank": self.min_roblox_rank,
            "max_roblox_rank": self.max_roblox_rank,
            "specific_role_id": self.specific_role_id,
            "system_role": self.system_role,
            "permissions": self.permissions,
        }


class GroupCookie(SQLModel, table=True):
    __tablename__ = "group_cookies"

    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="groups.id", unique=True, index=True)
    cookie: str = Field(sa_column=Column(Text, nullable=False))
    bot_username: Optional[str] = Field(default=None, max_length=100)
    bot_id: Optional[str] = Field(default=None, max_length=50)
    is_valid: bool = Field(default=True)
    last_validated: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    group: Optional[Group] = Relationship(back_populates="cookie")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "group_id": self.group_id,
            "bot_username": self.bot_username,
            "bot_id": self.bot_id,
            "is_valid": self.is_valid,
            "last_validated": self.last_validated.strftime("%Y-%m-%d %H:%M:%S") if self.last_validated else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

