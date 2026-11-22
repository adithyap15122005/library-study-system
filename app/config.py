import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url


def load_config(app, overrides):
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY"),
        LEDGER_SECRET=os.getenv("LEDGER_SECRET"),
        DEMO_PASSWORD=os.getenv("DEMO_PASSWORD"),
        DEMO_ADMIN_PASSWORD=os.getenv("DEMO_ADMIN_PASSWORD"),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL"),
        SQLALCHEMY_ENGINE_OPTIONS={
            "pool_pre_ping": True, "pool_recycle": 1800,
            "connect_args": {"connect_timeout": 5},
        },
        BORROW_DAYS=int(os.getenv("BORROW_DAYS", "14")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "0").lower() in {"1", "true"},
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        MAX_CONTENT_LENGTH=128 * 1024,
    )
    app.config.update(overrides or {})
    for key in ("SECRET_KEY", "LEDGER_SECRET"):
        value = app.config[key]
        if not isinstance(value, str) or len(value) < 32 or value.startswith("replace_"):
            raise RuntimeError(f"Set {key} to an independent random value of at least 32 characters.")
    if app.config["SECRET_KEY"] == app.config["LEDGER_SECRET"]:
        raise RuntimeError("SECRET_KEY and LEDGER_SECRET must be different.")
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if not uri or make_url(uri).drivername != "mysql+pymysql":
        raise RuntimeError("Set DATABASE_URL to a MySQL URL using mysql+pymysql.")
    if not 1 <= app.config["BORROW_DAYS"] <= 365:
        raise RuntimeError("BORROW_DAYS must be between 1 and 365.")
