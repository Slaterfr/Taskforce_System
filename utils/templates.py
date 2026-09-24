from fastapi.templating import Jinja2Templates
import typing
import urllib.parse

templates = Jinja2Templates(directory="templates")

def url_for(request, name: str, **path_params: typing.Any) -> str:
    if "_external" in path_params:
        del path_params["_external"]
    try:
        url = request.url_for(name, **path_params)
        return str(url)
    except Exception:
        return f"/{name}" + ("?" + urllib.parse.urlencode(path_params) if path_params else "")

from utils.flash import get_flashed_messages
from config import settings

templates.env.globals['get_flashed_messages'] = get_flashed_messages
templates.env.globals['config'] = settings

original_TemplateResponse = templates.TemplateResponse

def custom_TemplateResponse(name, context, *args, **kwargs):
    request = context.get('request')
    if request:
        ctx = getattr(request.state, "tenant_context", None)
        if not ctx:
            from utils.tenant_context import extract_tenant_context
            ctx = extract_tenant_context(request)
            
        session = getattr(request, "session", {})
        legacy_staff = bool(session.get('is_staff', False))
        legacy_hct = bool(session.get('is_hct', False))
        
        system_role = (ctx or {}).get("system_role", "member")
        perms = (ctx or {}).get("permissions", [])
        
        active_group_name = session.get("group_name") or (ctx or {}).get("group_name") or "Taskforce"
        context['tenant_context'] = ctx
        context['current_group_name'] = active_group_name
        context['current_group_id'] = session.get("tenant_id") or (ctx or {}).get("group_id", 1)
        context['roblox_username'] = (ctx or {}).get("roblox_username")
        context['roblox_id'] = (ctx or {}).get("roblox_id")
        context['is_roblox_user'] = bool((ctx or {}).get("roblox_id"))
        context['system_role'] = system_role
        
        # Staff is True if legacy staff OR role is staff/hct/admin OR has manage_members
        context['is_staff'] = legacy_staff or system_role in ["staff", "hct", "admin"] or "manage_members" in perms
        # HCT is True if legacy HCT OR role is hct/admin OR has edit_config
        context['is_hct'] = legacy_hct or system_role in ["hct", "admin"] or "edit_config" in perms
        context['has_permission'] = lambda perm: (legacy_hct or perm in perms)

        # Theme Resolution: fetch active sector theme from session or group settings
        group_id = session.get("tenant_id") or (ctx or {}).get("group_id") or 1
        current_theme = session.get("group_theme")
        if not current_theme:
            from database.engine import engine
            from sqlmodel import Session as DbSession
            from database.tenant_models import Group
            try:
                with DbSession(engine) as db:
                    grp = db.get(Group, group_id)
                    if grp:
                        current_theme = grp.get_settings_dict().get("theme")
            except Exception:
                pass
        context['current_theme'] = current_theme or "neon_purple"

    return original_TemplateResponse(name, context, *args, **kwargs)

templates.TemplateResponse = custom_TemplateResponse


