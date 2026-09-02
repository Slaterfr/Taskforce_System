from fastapi import Request
import typing
from jinja2 import pass_context

def flash(request: Request, message: str, category: str = "primary") -> None:
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append({"message": message, "category": category})

@pass_context
def get_flashed_messages(context, with_categories: bool = False) -> typing.List:
    request = context.get('request')
    if not request:
        return []
    messages = request.session.pop("_messages", [])
    if with_categories:
        return [(m["category"], m["message"]) for m in messages]
    return [m["message"] for m in messages]
