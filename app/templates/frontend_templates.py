"""
Module handling the Jinja2 templates for the frontend.
Same templates as the backend ones, with get_messages() for the flash messages (see src/libs/flash.py).
"""

import jinja2
from fastapi.templating import Jinja2Templates
from src.libs.flash import get_messages

templates = Jinja2Templates(directory="templates/html")


@jinja2.pass_context
def get_request_messages(context: dict):
    return get_messages(context["request"])


templates.env.globals["get_messages"] = get_request_messages
