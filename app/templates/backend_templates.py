"""
Module handling the Jinja2 templates for the backend
"""

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates/html")
