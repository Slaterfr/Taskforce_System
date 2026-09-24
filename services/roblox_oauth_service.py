"""
Roblox OAuth 2.0 and Groups integration service.
Handles OAuth authentication, profile retrieval, user groups discovery,
and automatic role/permission evaluation based on GroupPermissionRules.
"""
from typing import Optional, List, Dict, Any, Tuple
import urllib.parse
from datetime import datetime
import httpx
from sqlmodel import Session, select

from config import settings
from database.tenant_models import User, Group, GroupMember, GroupPermissionRule

ROBLOX_OAUTH_AUTH_URL = "https://apis.roblox.com/oauth/v1/authorize"
ROBLOX_OAUTH_TOKEN_URL = "https://apis.roblox.com/oauth/v1/token"
ROBLOX_OAUTH_USERINFO_URL = "https://apis.roblox.com/oauth/v1/userinfo"
ROBLOX_USER_GROUPS_URL = "https://groups.roblox.com/v2/users/{user_id}/groups/roles"

# Default permissions by system role
DEFAULT_ROLE_PERMISSIONS = {
    "admin": [
        "view_roster", "view_ac_progress", "log_activity", "manage_members",
        "manage_ac", "edit_config", "manage_group_rules", "sync_roblox"
    ],
    "hct": [
        "view_roster", "view_ac_progress", "log_activity", "manage_members",
        "manage_ac", "edit_config"
    ],
    "staff": [
        "view_roster", "view_ac_progress", "log_activity", "manage_members"
    ],
    "member": [
        "view_roster", "view_ac_progress"
    ]
}


import asyncio
import concurrent.futures

_oauth_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="roblox_oauth")


class RobloxOAuthService:
    @staticmethod
    def get_authorization_url(state: str, code_challenge: Optional[str] = None) -> str:
        """Generate Roblox OAuth 2.0 authorization URL."""
        params = {
            "client_id": settings.ROBLOX_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": settings.ROBLOX_REDIRECT_URI,
            "scope": "openid profile",
            "state": state,
        }
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        return f"{ROBLOX_OAUTH_AUTH_URL}?{urllib.parse.urlencode(params)}"

    @staticmethod
    async def exchange_code_for_tokens(
        code: str, code_verifier: Optional[str] = None
    ) -> Dict[str, Any]:
        """Exchange authorization code for Roblox access token."""
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.ROBLOX_REDIRECT_URI,
            "client_id": str(settings.ROBLOX_CLIENT_ID),
            "client_secret": str(settings.ROBLOX_CLIENT_SECRET),
        }
        if code_verifier:
            data["code_verifier"] = code_verifier

        def _do_exchange():
            with httpx.Client(timeout=15.0) as client:
                # Primary: form-urlencoded with client credentials in body
                response = client.post(
                    ROBLOX_OAUTH_TOKEN_URL,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                if response.status_code == 200:
                    return response.json()

                error_text = response.text
                # Secondary fallback: Basic Auth
                auth = (str(settings.ROBLOX_CLIENT_ID), str(settings.ROBLOX_CLIENT_SECRET))
                fallback_data = {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.ROBLOX_REDIRECT_URI,
                }
                if code_verifier:
                    fallback_data["code_verifier"] = code_verifier

                resp2 = client.post(
                    ROBLOX_OAUTH_TOKEN_URL,
                    data=fallback_data,
                    auth=auth,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                if resp2.status_code == 200:
                    return resp2.json()

                raise RuntimeError(f"Roblox token exchange failed ({response.status_code}): {error_text}")

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_oauth_pool, _do_exchange)

    @staticmethod
    async def get_userinfo(access_token: str) -> Dict[str, Any]:
        """Fetch authenticated Roblox user profile information."""
        headers = {"Authorization": f"Bearer {access_token}"}

        def _do_get_userinfo():
            with httpx.Client(timeout=15.0) as client:
                response = client.get(ROBLOX_OAUTH_USERINFO_URL, headers=headers)
                if response.status_code != 200:
                    raise RuntimeError(f"Roblox userinfo failed ({response.status_code}): {response.text}")
                return response.json()

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_oauth_pool, _do_get_userinfo)

    @staticmethod
    async def get_user_roblox_groups(roblox_user_id: str) -> List[Dict[str, Any]]:
        """Fetch all Roblox groups and ranks for a given Roblox user ID."""
        url = ROBLOX_USER_GROUPS_URL.format(user_id=roblox_user_id)

        def _do_get_groups():
            with httpx.Client(timeout=15.0) as client:
                response = client.get(url)
                if response.status_code != 200:
                    # Fallback to v1 endpoint if v2 is unavailable
                    v1_url = f"https://groups.roblox.com/v1/users/{roblox_user_id}/groups/roles"
                    v1_response = client.get(v1_url)
                    if v1_response.status_code != 200:
                        return []
                    data = v1_response.json()
                else:
                    data = response.json()

            groups = []
            for item in data.get("data", []):
                group_data = item.get("group", {})
                role_data = item.get("role", {})
                groups.append({
                    "roblox_group_id": str(group_data.get("id")),
                    "name": group_data.get("name", ""),
                    "role_id": role_data.get("id", 0),
                    "role_name": role_data.get("name", "Guest"),
                    "rank": role_data.get("rank", 1),
                })
            return groups

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_oauth_pool, _do_get_groups)

    @classmethod
    def evaluate_user_permissions(
        cls, group_id: int, roblox_rank: int, role_id: int, session: Session
    ) -> Tuple[str, List[str]]:
        """Evaluate system role and permission list for a user's rank in a group."""
        rules = session.exec(
            select(GroupPermissionRule)
            .where(GroupPermissionRule.group_id == group_id)
            .order_by(GroupPermissionRule.min_roblox_rank.desc())
        ).all()

        # Check explicit rules first
        for rule in rules:
            if rule.specific_role_id and rule.specific_role_id == role_id:
                return rule.system_role, rule.permissions or DEFAULT_ROLE_PERMISSIONS.get(rule.system_role, [])
            if rule.min_roblox_rank and roblox_rank >= rule.min_roblox_rank:
                if rule.max_roblox_rank is None or roblox_rank <= rule.max_roblox_rank:
                    return rule.system_role, rule.permissions or DEFAULT_ROLE_PERMISSIONS.get(rule.system_role, [])

        # Default fallback heuristics
        if roblox_rank == 255:
            return "admin", DEFAULT_ROLE_PERMISSIONS["admin"]
        elif roblox_rank >= 200:
            return "hct", DEFAULT_ROLE_PERMISSIONS["hct"]
        elif roblox_rank >= 100:
            return "staff", DEFAULT_ROLE_PERMISSIONS["staff"]
        else:
            return "member", DEFAULT_ROLE_PERMISSIONS["member"]

    @classmethod
    def sync_user_with_database(
        cls,
        session: Session,
        roblox_profile: Dict[str, Any],
        user_groups: List[Dict[str, Any]]
    ) -> Tuple[User, List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Upsert User, synchronize GroupMember associations, and match against registered groups.
        Returns:
            user: User record
            registered_groups: List of groups registered in DB that user belongs to
            unregistered_groups: List of user groups not yet registered (where rank >= 250)
        """
        roblox_id = str(roblox_profile.get("sub") or roblox_profile.get("id"))
        username = (
            roblox_profile.get("preferred_username")
            or roblox_profile.get("name")
            or f"User_{roblox_id}"
        )
        display_name = roblox_profile.get("nickname") or roblox_profile.get("name")
        avatar_url = roblox_profile.get("picture")

        # 1. Upsert User
        user = session.exec(select(User).where(User.roblox_id == roblox_id)).first()
        if not user:
            user = User(
                roblox_id=roblox_id,
                roblox_username=username,
                display_name=display_name,
                avatar_url=avatar_url,
                last_login=datetime.utcnow(),
            )
            session.add(user)
            session.flush()
        else:
            user.roblox_username = username
            user.display_name = display_name
            if avatar_url:
                user.avatar_url = avatar_url
            user.last_login = datetime.utcnow()
            session.add(user)
            session.flush()

        # 2. Match with registered groups
        user_group_ids = [g["roblox_group_id"] for g in user_groups]
        registered_db_groups = session.exec(
            select(Group).where(Group.roblox_group_id.in_(user_group_ids), Group.is_active == True)
        ).all()
        registered_group_map = {g.roblox_group_id: g for g in registered_db_groups}

        registered_groups_info = []
        unregistered_groups_info = []

        for g in user_groups:
            r_gid = g["roblox_group_id"]
            if r_gid in registered_group_map:
                db_group = registered_group_map[r_gid]
                system_role, permissions = cls.evaluate_user_permissions(
                    db_group.id, g["rank"], g["role_id"], session
                )

                # Upsert GroupMember
                gm = session.exec(
                    select(GroupMember).where(
                        GroupMember.group_id == db_group.id,
                        GroupMember.user_id == user.id
                    )
                ).first()

                if not gm:
                    gm = GroupMember(
                        group_id=db_group.id,
                        user_id=user.id,
                        roblox_role_id=g["role_id"],
                        roblox_role_name=g["role_name"],
                        roblox_rank=g["rank"],
                        system_role=system_role,
                        last_synced=datetime.utcnow(),
                    )
                else:
                    gm.roblox_role_id = g["role_id"]
                    gm.roblox_role_name = g["role_name"]
                    gm.roblox_rank = g["rank"]
                    gm.system_role = system_role
                    gm.last_synced = datetime.utcnow()
                session.add(gm)

                registered_groups_info.append({
                    "group_id": db_group.id,
                    "roblox_group_id": db_group.roblox_group_id,
                    "name": db_group.name,
                    "icon_url": db_group.icon_url,
                    "role_name": g["role_name"],
                    "rank": g["rank"],
                    "system_role": system_role,
                    "permissions": permissions,
                })
            else:
                # Group not registered in Taskforce system yet.
                # If user has rank >= 250 (owner or co-owner), they can register it!
                if g["rank"] >= 250:
                    unregistered_groups_info.append({
                        "roblox_group_id": r_gid,
                        "name": g["name"],
                        "role_name": g["role_name"],
                        "rank": g["rank"],
                    })

        session.commit()
        return user, registered_groups_info, unregistered_groups_info
