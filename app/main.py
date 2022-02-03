"""
Module spinning up FastApi
"""

from test import app_init_endpoints

from config import app_config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

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
app.include_router(app_init_endpoints.router)
