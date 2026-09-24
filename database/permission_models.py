"""
RankPermission Model for granular multi-tenant role permissions.
"""
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger

class RankPermission(SQLModel, table=True):
    __tablename__ = "rank_permissions"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(default=1, index=True)
    role_id: int = Field(sa_column=Column(BigInteger, nullable=False, index=True))
    role_name: str = Field(max_length=100)
    rank_number: int = Field(default=1)  # Roblox rank number 1-255

    # Granular permissions
    can_promote: bool = Field(default=False)
    can_log_activity: bool = Field(default=False)
    can_delete_activity: bool = Field(default=False)
    can_view_data: bool = Field(default=True)
    can_manage_ac: bool = Field(default=False)
    is_hct: bool = Field(default=False)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "role_id": self.role_id,
            "role_name": self.role_name,
            "rank_number": self.rank_number,
            "can_promote": self.can_promote,
            "can_log_activity": self.can_log_activity,
            "can_delete_activity": self.can_delete_activity,
            "can_view_data": self.can_view_data,
            "can_manage_ac": self.can_manage_ac,
            "is_hct": self.is_hct,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
