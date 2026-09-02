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
        context['is_staff'] = bool(request.session.get('is_staff', False))
        context['is_hct'] = bool(request.session.get('is_hct', False))
    return original_TemplateResponse(name, context, *args, **kwargs)

templates.TemplateResponse = custom_TemplateResponse


