"""Read-only Shopwise readiness checks for local operators."""

from dataclasses import dataclass
import importlib
import importlib.util
import os
from pathlib import Path
import sys
from typing import Callable

from dotenv import load_dotenv

from app.db.schema import validate_account_schema, validate_shopping_schema
from app.observability import configure_logging, log_failure

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class HealthCheck:
    name: str
    status: str
    message: str


def _check(name: str, operation: Callable[[], None]) -> HealthCheck:
    try:
        operation()
    except Exception as error:
        log_failure(f"health_{name.casefold().replace(' ', '_')}_failed", error)
        return HealthCheck(name, "unhealthy", "Check failed; review application logs.")
    return HealthCheck(name, "healthy", "Check passed.")


def _check_runtime() -> None:
    if sys.version_info < (3, 11):
        raise RuntimeError("Python 3.11 or newer is required.")
    for module in ("streamlit", "google.genai", "mcp", "dotenv", "app.mcp.mcp_server"):
        importlib.import_module(module)
    if importlib.util.find_spec("app.ui.web_app") is None:
        raise ModuleNotFoundError("Streamlit application entry point is unavailable.")


def collect_health_checks() -> tuple[str, list[HealthCheck]]:
    """Check runtime readiness without network calls or database writes."""
    load_dotenv(PROJECT_ROOT / ".env")
    checks = [
        _check("Runtime imports", _check_runtime),
        _check("Shopping database", validate_shopping_schema),
        _check("Accounts database", validate_account_schema),
    ]
    if os.getenv("GEMINI_API_KEY"):
        checks.append(HealthCheck("Gemini configuration", "healthy", "Configured."))
    else:
        checks.append(
            HealthCheck(
                "Gemini configuration",
                "degraded",
                "Not configured; AI chat is unavailable, while shopping remains available.",
            )
        )
    checks.append(
        HealthCheck(
            "MCP subprocess",
            "not_checked",
            "Starts on demand for chat; no subprocess was launched by this check.",
        )
    )

    if any(check.status == "unhealthy" for check in checks):
        overall = "unhealthy"
    elif any(check.status == "degraded" for check in checks):
        overall = "degraded"
    else:
        overall = "healthy"
    return overall, checks


def main() -> int:
    configure_logging()
    overall, checks = collect_health_checks()
    print(f"Shopwise readiness: {overall.upper()}")
    for check in checks:
        print(f"{check.status.upper():12} {check.name}: {check.message}")
    return 1 if overall == "unhealthy" else 0


if __name__ == "__main__":
    raise SystemExit(main())
