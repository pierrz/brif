# pylint: disable=no-name-in-module

"""
Module spinning up FastApi
"""

from test import app_init_endpoints

from config import app_config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from psycopg2.errors import \
    DuplicateTable  # triggers pylint warnings but do not make the app fail ...
from src.db.database import prepare_dashboard_table
from src.routers import api_endpoints, dashboard, tasks
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(SessionMiddleware, secret_key=app_config.SECRET_KEY)

if app_config.LOCAL_DEV:
    localhost_origins = [
        "http://localhost",
        "https://localhost",
        "http://localhost:8000",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=localhost_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# routers
app.include_router(dashboard.router)
app.include_router(api_endpoints.router)
app.include_router(tasks.router)
app.include_router(app_init_endpoints.router)

# database
try:
    prepare_dashboard_table()
except DuplicateTable:
    print("! => 'dashboard' table already created")
