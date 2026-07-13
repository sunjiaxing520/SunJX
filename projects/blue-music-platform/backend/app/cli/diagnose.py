import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from redis import Redis
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import engine


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _safe_database_url() -> str:
    try:
        return make_url(settings.DATABASE_URL).render_as_string(
            hide_password=True
        )
    except Exception:
        return "invalid database URL"


def _security_check() -> dict[str, Any]:
    using_default = settings.SECRET_KEY == "dev_secret_key_change_in_production"
    too_short = len(settings.SECRET_KEY) < 32
    unsafe = using_default or too_short
    status = "error" if settings.ENVIRONMENT == "production" and unsafe else "ok"
    if unsafe and status == "ok":
        status = "warning"
    return {
        "status": status,
        "secret_key": "unsafe-default-or-short" if unsafe else "configured",
        "jwt_algorithm": settings.JWT_ALGORITHM,
        "access_token_expire_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    }


def _database_check() -> tuple[dict[str, Any], str | None]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        return (
            {
                "status": "error",
                "url": _safe_database_url(),
                "error_type": type(exc).__name__,
            },
            None,
        )

    try:
        with engine.connect() as connection:
            current_revision = connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
    except SQLAlchemyError:
        current_revision = None
    return (
        {"status": "ok", "url": _safe_database_url()},
        str(current_revision) if current_revision else None,
    )


def _redis_check() -> dict[str, Any]:
    client: Redis | None = None
    try:
        client = Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        client.ping()
    except Exception as exc:
        return {"status": "error", "error_type": type(exc).__name__}
    finally:
        if client is not None:
            client.close()
    return {"status": "ok"}


def _migration_check(current_revision: str | None) -> dict[str, Any]:
    try:
        config = Config(str(BACKEND_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
        expected_revision = ScriptDirectory.from_config(config).get_current_head()
    except Exception as exc:
        return {"status": "error", "error_type": type(exc).__name__}
    return {
        "status": "ok" if current_revision == expected_revision else "error",
        "current": current_revision,
        "expected": expected_revision,
    }


def build_diagnostic_report() -> dict[str, Any]:
    database, current_revision = _database_check()
    checks = {
        "security": _security_check(),
        "database": database,
        "redis": _redis_check(),
        "migrations": _migration_check(current_revision),
        "logging": {
            "status": "ok",
            "level": settings.LOG_LEVEL,
            "format": settings.LOG_FORMAT,
            "to_file": settings.LOG_TO_FILE,
        },
    }
    has_error = any(check["status"] == "error" for check in checks.values())
    has_warning = any(
        check["status"] == "warning" for check in checks.values()
    )
    overall_status = "error" if has_error else "warning" if has_warning else "ok"
    return {
        "status": overall_status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "python": platform.python_version(),
        "checks": checks,
    }


def main() -> int:
    report = build_diagnostic_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
