"""
Dual-JWT Utility module for Roblox OAuth and Multi-Tenant Contexts.
Level 1: Global User Token (User identity + eligible registered groups)
Level 2: Tenant Context Token (Group ID + permissions + system role)
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import jwt
from fastapi import HTTPException, status
from config import settings


def create_user_token(
    user_id: int,
    roblox_id: str,
    roblox_username: str,
    registered_groups: List[Dict[str, Any]],
    can_register_groups: bool = True,
    expires_minutes: Optional[int] = None,
) -> str:
    """Create Level 1 JWT (Global User Token) after Roblox OAuth login."""
    if expires_minutes is None:
        expires_minutes = settings.JWT_USER_TOKEN_EXPIRE_MINUTES

    now = datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "roblox_id": str(roblox_id),
        "roblox_username": roblox_username,
        "token_type": "global_user",
        "registered_groups": registered_groups,
        "can_register_groups": can_register_groups,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_tenant_token(
    user_id: int,
    roblox_id: str,
    roblox_username: str,
    group_id: int,
    roblox_group_id: str,
    group_name: str,
    roblox_rank: int,
    system_role: str,
    permissions: List[str],
    expires_minutes: Optional[int] = None,
) -> str:
    """Create Level 2 JWT (Tenant Context Token) after user selects a group."""
    if expires_minutes is None:
        expires_minutes = settings.JWT_TENANT_TOKEN_EXPIRE_MINUTES

    now = datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "roblox_id": str(roblox_id),
        "roblox_username": roblox_username,
        "group_id": group_id,
        "roblox_group_id": str(roblox_group_id),
        "group_name": group_name,
        "roblox_rank": roblox_rank,
        "system_role": system_role,
        "permissions": permissions,
        "token_type": "tenant_context",
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, expected_type: Optional[str] = None) -> Dict[str, Any]:
    """Decode and validate a JWT, optionally verifying its token_type."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        )

    if expected_type and payload.get("token_type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid token scope. Expected {expected_type}, got {payload.get('token_type')}",
        )

    return payload
