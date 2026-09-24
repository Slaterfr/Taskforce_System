"""
Roblox OAuth2 Authentication and Multi-Tenant Group Portal Router.
Manages OAuth lifecycle, Level 1 (Global User) & Level 2 (Tenant Context) tokens,
group selection, and onboarding of new Roblox groups.
"""
import secrets
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session, select

from config import settings
from database.engine import get_session
from database.tenant_models import User, Group, GroupMember, GroupPermissionRule
from database.ac_models import ActivityType, RankQuota
from services.roblox_oauth_service import RobloxOAuthService, DEFAULT_ROLE_PERMISSIONS
from utils.jwt_utils import create_user_token, create_tenant_token, decode_token
from utils.tenant_context import set_tenant_context
from utils.templates import templates
from utils.flash import flash

router = APIRouter(tags=["Roblox OAuth & Group Portal"])


@router.get("/auth/roblox/login")
async def roblox_login(request: Request):
    """Initiate Roblox OAuth2 authorization code flow."""
    if not settings.ROBLOX_CLIENT_ID or not settings.ROBLOX_CLIENT_SECRET:
        flash(request, "Roblox OAuth credentials not configured in .env. Using Developer Portal mode.", "info")
        return RedirectResponse(url="/auth/dev/login", status_code=303)

    # Use a signed JWT token as state so it can be verified stateless across domains/ports without relying on session cookies
    from datetime import datetime, timedelta
    import jwt
    state_payload = {
        "purpose": "roblox_oauth",
        "exp": datetime.utcnow() + timedelta(minutes=15),
    }
    state = jwt.encode(state_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    request.session["oauth_state"] = state

    auth_url = RobloxOAuthService.get_authorization_url(state=state)
    print(f"[Roblox OAuth] Redirecting to authorization URL: {auth_url}")
    response = RedirectResponse(url=auth_url, status_code=303)
    response.set_cookie("oauth_state", state, max_age=900, httponly=True, samesite="lax")
    return response


@router.get("/auth/roblox/callback")
async def roblox_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """Callback endpoint handling Roblox authorization code redirect."""
    print(f"[Roblox OAuth] Callback received - code: {'yes' if code else 'no'}, state: {'yes' if state else 'no'}, error: {error}")

    if error:
        print(f"[Roblox OAuth] Error from Roblox: {error}")
        flash(request, f"Roblox login error: {error}", "error")
        return RedirectResponse(url="/", status_code=303)

    # Verify state: check signed JWT state or session/cookie
    is_state_valid = False
    saved_state = request.session.pop("oauth_state", None) or request.cookies.get("oauth_state")
    if state and saved_state and state == saved_state:
        is_state_valid = True
    elif state:
        try:
            import jwt
            payload = jwt.decode(state, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            if payload.get("purpose") == "roblox_oauth":
                is_state_valid = True
        except Exception as state_err:
            print(f"[Roblox OAuth] State decoding failed: {state_err}")

    if not is_state_valid:
        print(f"[Roblox OAuth] State validation failed! Received: {state}")
        flash(request, "Authentication state expired or mismatch. Please try logging in again.", "error")
        return RedirectResponse(url="/", status_code=303)

    if not code:
        print("[Roblox OAuth] No authorization code provided in callback.")
        flash(request, "No authorization code returned from Roblox.", "error")
        return RedirectResponse(url="/", status_code=303)

    try:
        # 1. Exchange code for access token
        print("[Roblox OAuth] Exchanging code for access token...")
        tokens = await RobloxOAuthService.exchange_code_for_tokens(code)
        access_token = tokens["access_token"]
        print("[Roblox OAuth] Access token obtained successfully.")

        # 2. Retrieve user profile
        print("[Roblox OAuth] Fetching user profile info...")
        userinfo = await RobloxOAuthService.get_userinfo(access_token)
        print(f"[Roblox OAuth] Userinfo: sub={userinfo.get('sub')}, name={userinfo.get('name') or userinfo.get('preferred_username')}")

        # 3. Discover user's Roblox groups and ranks
        roblox_user_id = str(userinfo.get("sub") or userinfo.get("id"))
        print(f"[Roblox OAuth] Fetching user groups for Roblox ID: {roblox_user_id}...")
        user_groups = await RobloxOAuthService.get_user_roblox_groups(roblox_user_id)
        print(f"[Roblox OAuth] Found {len(user_groups)} groups for user.")

        # 4. Upsert User & synchronize memberships
        user, registered_groups, unregistered_groups = RobloxOAuthService.sync_user_with_database(
            session=session,
            roblox_profile=userinfo,
            user_groups=user_groups
        )
        print(f"[Roblox OAuth] Synced user {user.roblox_username} (ID: {user.id}) with {len(registered_groups)} registered groups.")

        # 5. Issue Level 1 JWT (Global User Token)
        user_jwt = create_user_token(
            user_id=user.id,
            roblox_id=user.roblox_id,
            roblox_username=user.roblox_username,
            registered_groups=registered_groups,
            can_register_groups=len(unregistered_groups) > 0 or user.is_superadmin,
        )

        response = RedirectResponse(url="/portal/select-group", status_code=303)
        # Store Level 1 token in secure HttpOnly cookie
        response.set_cookie(
            key="tf_user_token",
            value=user_jwt,
            httponly=True,
            samesite="lax",
            max_age=604800,  # 7 days
        )
        request.session["roblox_username"] = user.roblox_username
        request.session["roblox_id"] = user.roblox_id
        flash(request, f"Welcome, {user.display_name or user.roblox_username}!", "success")
        print(f"[Roblox OAuth] Successful login! Redirecting {user.roblox_username} to /portal/select-group")
        return response

    except Exception as exc:
        import traceback
        print(f"[Roblox OAuth] Exception during callback processing: {exc}")
        traceback.print_exc()
        flash(request, f"Roblox login failed: {exc}", "error")
        return RedirectResponse(url="/", status_code=303)



@router.api_route("/auth/dev/login", methods=["GET", "POST"])
async def dev_login(request: Request, session: Session = Depends(get_session)):
    """Developer / Testing login portal to simulate Roblox OAuth and multi-tenant accounts."""
    if request.method == "POST":
        form = await request.form()
        roblox_id = form.get("roblox_id", "12345678").strip()
        username = form.get("username", "TestCommander").strip()
        rank = int(form.get("rank", 250))
        group_id_to_join = int(form.get("group_id", 1))

        # Upsert dev user
        user = session.exec(select(User).where(User.roblox_id == roblox_id)).first()
        if not user:
            user = User(
                roblox_id=roblox_id,
                roblox_username=username,
                display_name=username,
                is_superadmin=True,
            )
            session.add(user)
            session.flush()

        # Ensure membership in selected group
        target_group = session.exec(select(Group).where(Group.id == group_id_to_join)).first()
        if target_group:
            system_role, perms = RobloxOAuthService.evaluate_user_permissions(
                target_group.id, rank, 999, session
            )
            gm = session.exec(
                select(GroupMember).where(
                    GroupMember.group_id == target_group.id,
                    GroupMember.user_id == user.id
                )
            ).first()
            if not gm:
                gm = GroupMember(
                    group_id=target_group.id,
                    user_id=user.id,
                    roblox_role_name="General" if rank >= 200 else "Officer",
                    roblox_rank=rank,
                    system_role=system_role,
                )
                session.add(gm)
            else:
                gm.roblox_rank = rank
                gm.system_role = system_role
                session.add(gm)
            session.commit()

            registered_groups = [{
                "group_id": target_group.id,
                "roblox_group_id": target_group.roblox_group_id,
                "name": target_group.name,
                "role_name": "General" if rank >= 200 else "Officer",
                "rank": rank,
                "system_role": system_role,
                "permissions": perms,
            }]
        else:
            registered_groups = []

        user_jwt = create_user_token(
            user_id=user.id,
            roblox_id=user.roblox_id,
            roblox_username=user.roblox_username,
            registered_groups=registered_groups,
            can_register_groups=True,
        )

        response = RedirectResponse(url="/portal/select-group", status_code=303)
        response.set_cookie(key="tf_user_token", value=user_jwt, httponly=True, samesite="lax", max_age=604800)
        request.session["roblox_username"] = user.roblox_username
        request.session["roblox_id"] = user.roblox_id
        flash(request, f"Logged in as {username} (Dev Mode)", "success")
        return response

    all_groups = session.exec(select(Group)).all()
    return templates.TemplateResponse(
        "portal/dev_login.html",
        {"request": request, "groups": all_groups}
    )


@router.get("/portal/select-group")
async def select_group_portal(request: Request, session: Session = Depends(get_session)):
    """Group Selection Portal rendering all registered groups accessible to user."""
    user_token = request.cookies.get("tf_user_token")
    if not user_token:
        flash(request, "Please authenticate with your Roblox account first.", "warning")
        return RedirectResponse(url="/auth/roblox/login", status_code=303)

    try:
        user_payload = decode_token(user_token, expected_type="global_user")
    except Exception:
        flash(request, "Session expired. Please log in again.", "warning")
        return RedirectResponse(url="/auth/roblox/login", status_code=303)

    user_id = user_payload["user_id"]
    user = session.exec(select(User).where(User.id == user_id)).first()

    # Query groups user is a member of
    memberships = session.exec(
        select(GroupMember, Group)
        .join(Group, GroupMember.group_id == Group.id)
        .where(GroupMember.user_id == user_id, Group.is_active == True)
    ).all()

    user_groups_data = []
    for gm, grp in memberships:
        user_groups_data.append({
            "group_id": grp.id,
            "roblox_group_id": grp.roblox_group_id,
            "name": grp.name,
            "description": grp.description,
            "icon_url": grp.icon_url,
            "role_name": gm.roblox_role_name,
            "rank": gm.roblox_rank,
            "system_role": gm.system_role,
        })

    return templates.TemplateResponse(
        "portal/select_group.html",
        {
            "request": request,
            "user": user,
            "groups": user_groups_data,
            "can_register": user_payload.get("can_register_groups", False),
        }
    )


@router.api_route("/portal/select-group/{group_id}", methods=["GET", "POST"])
async def enter_group(group_id: int, request: Request, session: Session = Depends(get_session)):
    """Select group, evaluate permissions, and issue Level 2 Tenant Context Token."""
    user_token = request.cookies.get("tf_user_token")
    if not user_token:
        flash(request, "Session expired. Please log in again.", "warning")
        return RedirectResponse(url="/auth/roblox/login", status_code=303)

    try:
        user_payload = decode_token(user_token, expected_type="global_user")
    except Exception:
        flash(request, "Session expired. Please log in again.", "warning")
        return RedirectResponse(url="/auth/roblox/login", status_code=303)

    user_id = user_payload["user_id"]
    group = session.exec(select(Group).where(Group.id == group_id, Group.is_active == True)).first()
    if not group:
        flash(request, "The selected group does not exist or is inactive.", "error")
        return RedirectResponse(url="/portal/select-group", status_code=303)

    # Verify membership
    membership = session.exec(
        select(GroupMember).where(
            GroupMember.group_id == group.id,
            GroupMember.user_id == user_id
        )
    ).first()

    if not membership:
        flash(request, f"You are not registered in {group.name}.", "error")
        return RedirectResponse(url="/portal/select-group", status_code=303)

    # Evaluate permissions
    system_role, permissions = RobloxOAuthService.evaluate_user_permissions(
        group.id, membership.roblox_rank, membership.roblox_role_id, session
    )

    # Issue Level 2 JWT (Tenant Context Token)
    tenant_jwt = create_tenant_token(
        user_id=user_id,
        roblox_id=user_payload["roblox_id"],
        roblox_username=user_payload["roblox_username"],
        group_id=group.id,
        roblox_group_id=group.roblox_group_id,
        group_name=group.name,
        roblox_rank=membership.roblox_rank,
        system_role=system_role,
        permissions=permissions,
    )

    # Set context in session for backwards compatibility with existing templates
    request.session["tenant_id"] = group.id
    request.session["group_name"] = group.name
    request.session["roblox_group_id"] = group.roblox_group_id
    request.session["system_role"] = system_role
    request.session["is_staff"] = "manage_members" in permissions or system_role in ["staff", "hct", "admin"]
    request.session["is_hct"] = "edit_config" in permissions or system_role in ["hct", "admin"]

    set_tenant_context(
        tenant_id=group.id,
        user_id=user_id,
        permissions=permissions,
        system_role=system_role
    )

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="tf_tenant_token",
        value=tenant_jwt,
        httponly=True,
        samesite="lax",
        max_age=604800,  # 7 days
    )
    flash(request, f"Entered command console for {group.name}.", "success")
    return response


@router.post("/portal/register-group")
async def register_new_group(
    request: Request,
    roblox_group_id: str = Form(...),
    group_name: str = Form(...),
    description: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    """Register and onboard a new Roblox group onto the multi-tenant system."""
    user_token = request.cookies.get("tf_user_token")
    if not user_token:
        flash(request, "Session expired. Please log in again.", "warning")
        return RedirectResponse(url="/auth/roblox/login", status_code=303)

    try:
        user_payload = decode_token(user_token, expected_type="global_user")
    except Exception:
        flash(request, "Session expired. Please log in again.", "warning")
        return RedirectResponse(url="/auth/roblox/login", status_code=303)

    user_id = user_payload["user_id"]
    clean_gid = roblox_group_id.strip()

    # Check if group is already registered
    existing = session.exec(select(Group).where(Group.roblox_group_id == clean_gid)).first()
    if existing:
        flash(request, f"Roblox group {clean_gid} is already registered as '{existing.name}'.", "warning")
        return RedirectResponse(url="/portal/select-group", status_code=303)

    # Create new Group
    new_group = Group(
        roblox_group_id=clean_gid,
        name=group_name.strip(),
        description=description,
        owner_user_id=user_id,
        is_active=True,
        settings={"sync_enabled": False}
    )
    session.add(new_group)
    session.flush()

    # Create creator's GroupMember record as Admin
    creator_member = GroupMember(
        group_id=new_group.id,
        user_id=user_id,
        roblox_role_name="Owner",
        roblox_rank=255,
        system_role="admin",
    )
    session.add(creator_member)

    # Seed default permission rules
    default_rules = [
        GroupPermissionRule(group_id=new_group.id, min_roblox_rank=255, system_role="admin", permissions=DEFAULT_ROLE_PERMISSIONS["admin"]),
        GroupPermissionRule(group_id=new_group.id, min_roblox_rank=200, max_roblox_rank=254, system_role="hct", permissions=DEFAULT_ROLE_PERMISSIONS["hct"]),
        GroupPermissionRule(group_id=new_group.id, min_roblox_rank=100, max_roblox_rank=199, system_role="staff", permissions=DEFAULT_ROLE_PERMISSIONS["staff"]),
        GroupPermissionRule(group_id=new_group.id, min_roblox_rank=1, max_roblox_rank=99, system_role="member", permissions=DEFAULT_ROLE_PERMISSIONS["member"]),
    ]
    for rule in default_rules:
        session.add(rule)

    # Seed default activity types for this new tenant
    default_activities = [
        ActivityType(tenant_id=new_group.id, name="Training", points=1.0, is_limited=False),
        ActivityType(tenant_id=new_group.id, name="Patrol", points=1.0, is_limited=False),
        ActivityType(tenant_id=new_group.id, name="Raid", points=2.0, is_limited=False),
        ActivityType(tenant_id=new_group.id, name="Evaluation", points=0.5, is_limited=False),
    ]
    for act in default_activities:
        session.add(act)

    # Seed default rank quotas for this new tenant
    default_quotas = [
        RankQuota(tenant_id=new_group.id, rank_name="Recruit", required_points=1.0),
        RankQuota(tenant_id=new_group.id, rank_name="Member", required_points=2.0),
        RankQuota(tenant_id=new_group.id, rank_name="Officer", required_points=4.0),
    ]
    for q in default_quotas:
        session.add(q)

    session.commit()
    flash(request, f"Group '{new_group.name}' onboarded successfully!", "success")

    # Trigger automatic initial sync for roles, rank mappings, and members
    try:
        from utils.roblox_sync import sync_from_roblox
        sync_res = sync_from_roblox(tenant_id=new_group.id, roblox_group_id=new_group.roblox_group_id)
        if sync_res.get("success"):
            flash(request, f"Synced {sync_res.get('roles_mapped', 0)} ranks and initial members from Roblox.", "info")
    except Exception as e:
        print(f"[Group Onboarding] Initial sync for group {new_group.id} ({clean_gid}) non-fatal error: {e}")

    # Enter the newly registered group immediately
    return await enter_group(group_id=new_group.id, request=request, session=session)


@router.get("/portal/switch-group")
async def switch_group(request: Request):
    """Exit current group context and return to group selection portal."""
    response = RedirectResponse(url="/portal/select-group", status_code=303)
    response.delete_cookie("tf_tenant_token")
    request.session.pop("tenant_id", None)
    request.session.pop("group_name", None)
    request.session.pop("is_staff", None)
    request.session.pop("is_hct", None)
    return response


@router.get("/auth/logout")
async def logout(request: Request):
    """Full platform logout, clearing tokens and session."""
    request.session.clear()
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("tf_user_token")
    response.delete_cookie("tf_tenant_token")
    flash(request, "Successfully logged out.", "info")
    return response
