"""Cirqle API entry point.

Run locally with:  uvicorn app.main:app --reload
Interactive docs:  http://localhost:8000/docs
"""
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()  # read backend/.env if present

from .db import init_db  # noqa: E402  (import after load_dotenv so env is set)
from .routers import auth, campaigns, feed  # noqa: E402
from .storage import MEDIA_DIR  # noqa: E402

app = FastAPI(title="Cirqle API")

# We authenticate with a bearer token (no cookies), so allowing any origin is
# safe for local dev. Restrict this via CIRQLE_CORS_ORIGINS in production.
origins = [o.strip() for o in os.environ.get("CIRQLE_CORS_ORIGINS", "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(feed.router)
app.include_router(campaigns.router)

# Serve locally-stored campaign images (only used when S3_BUCKET is unset; in
# prod images live on S3 and are served by AWS). mkdir so the mount never fails.
MEDIA_DIR.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/")
def health():
    return {"status": "ok", "service": "cirqle-api"}
