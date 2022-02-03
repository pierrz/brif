"""
Module handling the Jinja2 templates for the frontend.
Specific to Starlette, in order to use get_messages() and flash messages.
"""

import jinja2
from starlette_core.templating import Jinja2Templates

templates = Jinja2Templates(
    loader=jinja2.ChoiceLoader([jinja2.FileSystemLoader("templates/html")])
)
