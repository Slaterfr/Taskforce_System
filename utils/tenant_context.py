"""
Tenant and User context management using contextvars.
Maintains request-scoped tenant_id and permission list for global query filtering.
"""
from typing import Optional, List, Dict, Any
from contextvars import ContextVar
from functools import wraps
from fastapi import Request, HTTPException, status, Depends
from fastapi.responses import RedirectResponse, JSONResponse

from utils.jwt_utils import decode_token

# Request-scoped context variables
current_tenant_id: ContextVar[Optional[int]] = ContextVar("current_tenant_id", default=None)
current_user_id: ContextVar[Optional[int]] = ContextVar("current_user_id", default=None)
current_permissions: ContextVar[List[str]] = ContextVar("current_permissions", default=[])
current_system_role: ContextVar[str] = ContextVar("current_system_role", default="member")


def get_tenant_id() -> Optional[int]:
    """Get currently active tenant_id in request context, defaulting to 1."""
    return current_tenant_id.get() or 1

get_current_tenant = get_tenant_id


def set_tenant_context(
    tenant_id: int,
    user_id: Optional[int] = None,
    permissions: Optional[List[str]] = None,
    system_role: str = "member"
) -> None:
    """Set the current request-scoped tenant context."""
    current_tenant_id.set(tenant_id)
    if user_id is not None:
        current_user_id.set(user_id)
    if permissions is not None:
        current_permissions.set(permissions)
    current_system_role.set(system_role)


def extract_tenant_context(request: Request) -> Optional[Dict[str, Any]]:
    """
    Extract Level 2 Tenant Token from Cookies or Authorization header.
    Returns decoded payload or None if unauthenticated.
    """
    token = request.cookies.get("tf_tenant_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        # Fallback to session for legacy password logins
        session = getattr(request, "session", {})
        tenant_id = session.get("tenant_id")
        is_staff = session.get("is_staff", False)
        is_hct = session.get("is_hct", False)

        # If user is not authenticated via session or token, return None
        if not tenant_id and not is_staff and not is_hct:
            return None

        tenant_id = tenant_id or 1
        perms = ["view_roster", "view_ac_progress"]
        role = "member"
        if is_hct:
            role = "hct"
            perms += ["manage_members", "log_activity", "manage_ac", "edit_config"]
        elif is_staff:
            role = "staff"
            perms += ["manage_members", "log_activity"]

        set_tenant_context(tenant_id=tenant_id, permissions=perms, system_role=role)
        return {
            "group_id": tenant_id,
            "system_role": role,
            "permissions": perms,
        }

    try:
        payload = decode_token(token, expected_type="tenant_context")
        group_id = int(payload["group_id"])
        set_tenant_context(
            tenant_id=group_id,
            user_id=payload.get("user_id"),
            permissions=payload.get("permissions", []),
            system_role=payload.get("system_role", "member")
        )
        return payload
    except Exception:
        return None


def permission_required(permission: str):
    """
    Decorator enforcing that the authenticated user has a specific permission
    within the currently active group context.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Optional[Request] = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                request = kwargs.get("request")

            if not request:
                raise HTTPException(status_code=500, detail="Request object not found in endpoint kwargs")

            ctx = extract_tenant_context(request)
            perms = current_permissions.get()

            # Check if requested permission is in user's permissions
            if not ctx or permission not in perms:
                is_ajax = (
                    request.headers.get("X-Requested-With") == "XMLHttpRequest"
                    or "application/json" in request.headers.get("accept", "")
                )
                if is_ajax:
                    return JSONResponse(
                        {"error": "forbidden", "detail": f"Missing permission: {permission}"},
                        status_code=status.HTTP_403_FORBIDDEN,
                    )

                # Flash and redirect to group selection or login
                from utils.flash import flash
                flash(request, f"Access restricted: requires '{permission}' permission in this group.", "warning")
                return RedirectResponse(url="/portal/select-group", status_code=303)

            return await func(*args, **kwargs)
        return wrapper
    return decorator


from starlette.middleware.base import BaseHTTPMiddleware

class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts tenant context from JWT cookies or Authorization header
    and registers it in request.state and ContextVars.
    """
    async def dispatch(self, request: Request, call_next):
        ctx = extract_tenant_context(request)
        request.state.tenant_context = ctx
        response = await call_next(request)
        return response
