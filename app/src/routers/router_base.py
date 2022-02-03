"""
Module gathering the Jinja2 templates
"""

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")
