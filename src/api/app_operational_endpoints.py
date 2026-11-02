"""Operational endpoint registration for the ValuationIQ API."""

import logging
import os
import pathlib
import subprocess
from datetime import datetime
from typing import Callable, Optional

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from src.api.json_response import JSONResponse
from src.config import Settings
from src.config.public_adaptive_local_migration import public_adaptive_runtime_attestation
from src.database import get_db
from src.database.connection import is_stateless_mode
from src.utils.exceptions import DataValidationError


def should_expose_metrics(settings: Settings) -> bool:
    """Return True when Prometheus endpoints should be publicly served."""
    if not settings.enable_metrics:
        return False
    if settings.is_production and not settings.expose_metrics_in_production:
        return False
    return True


def register_operational_endpoints(
    app: FastAPI,
    settings: Settings,
    logger: logging.Logger,
    is_ready: Callable[[], bool],
    runtime_status: Optional[Callable[[], dict[str, object]]] = None,
) -> None:
    """Register root, health, and metrics endpoints."""

    def instance_status() -> dict[str, object]:
        return runtime_status() if runtime_status else {"ready": is_ready()}

    @app.get("/metrics", response_model=None)
    async def metrics() -> Response:
        if not should_expose_metrics(settings):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/")
    async def root() -> dict[str, object]:
        return {
            "message": "ValuationIQ - The Muscle (Stateless Calculation Engine)",
            "version": "2.0.0",
            "architecture": "Brain & Muscle",
            "status": "healthy",
            "instance": instance_status(),
            "timestamp": datetime.now().isoformat(),
            "endpoints": {
                "stateless_calculate": "/api/v2/stateless/calculate",
                "stateless_validate": "/api/v2/stateless/validate",
                "stateless_report": "/api/v2/stateless/generate-report",
                "valuation": "/api/v1/valuation",
                "registry": "/api/v1/registry",
                "docs": "/docs",
                "redoc": "/redoc",
            },
        }

    @app.get("/robots.txt")
    async def robots_txt() -> Response:
        content = "User-agent: *\nDisallow: /\n"
        return Response(content=content, media_type="text/plain")

    def _liveness_response() -> JSONResponse:
        if not is_ready():
            return JSONResponse(status_code=503, content={"status": "starting"})
        return JSONResponse(status_code=200, content={"status": "ok"})

    @app.get("/health/live", response_model=None)
    async def liveness() -> JSONResponse:
        return _liveness_response()

    @app.get("/health/ready", response_model=None)
    async def readiness() -> JSONResponse:
        startup_ready = is_ready()
        git_metadata = _get_git_metadata()
        revision_identified = git_metadata["git_commit"] != "unknown"
        deployment_identity_ready = not settings.is_production or revision_identified

        try:
            from src.services.infrastructure.report_generation.strategies.pdf_strategy import (
                WEASYPRINT_AVAILABLE,
            )

            pdf_ready = bool(WEASYPRINT_AVAILABLE)
        except ImportError:
            pdf_ready = False

        ready = startup_ready and deployment_identity_ready and pdf_ready
        dependencies = {
            "startup": {"status": "ready" if startup_ready else "not_ready"},
            "pdf_renderer": {"status": "ready" if pdf_ready else "not_ready"},
            "database": {"status": "not_required" if is_stateless_mode() else "configured"},
            "redis": {"status": "not_required" if is_stateless_mode() else "configured"},
        }
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "status": "ready" if ready else "not_ready",
                "service": "valuation-iq",
                "instance": instance_status(),
                "build": {
                    "revision": git_metadata["git_commit"],
                    "branch": git_metadata["git_branch"],
                    "identified": revision_identified,
                },
                "contracts": {
                    "valuation_run": "ValuationRunV2",
                    "report_artifact": "ReportArtifactV1",
                },
                "dependencies": dependencies,
            },
        )

    @app.get("/{hostname}/health/live", response_model=None)
    async def host_prefixed_liveness(hostname: str) -> JSONResponse:
        # Railway/custom healthcheck misconfigurations can send the host as a path segment.
        # Keep this limited to hostname-like single segments so real 404s stay useful.
        hostname_labels = hostname.lower().split(".")
        is_hostname_like = (
            len(hostname_labels) > 1
            and all(label for label in hostname_labels)
            and hostname_labels[-1].isalpha()
        )
        if not is_hostname_like:
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        return _liveness_response()

    @app.get("/health", response_model=None)
    async def health_check() -> dict[str, object] | JSONResponse:
        try:
            if is_stateless_mode():
                db_status = "skipped (stateless)"
            else:
                from src.database.connection import check_db_connection

                db_status = "healthy" if check_db_connection() else "unhealthy (no database)"

            pdf_generator_error = None
            try:
                from src.services.infrastructure.report_generation.strategies.pdf_strategy import (
                    WEASYPRINT_AVAILABLE,
                    WEASYPRINT_IMPORT_ERROR,
                )

                pdf_status = "healthy" if WEASYPRINT_AVAILABLE else "unavailable"
                if not WEASYPRINT_AVAILABLE and WEASYPRINT_IMPORT_ERROR:
                    pdf_generator_error = str(WEASYPRINT_IMPORT_ERROR)
            except ImportError:
                pdf_status = "unavailable"
                pdf_generator_error = "pdf_strategy import failed"

            services_status = {
                "stateless_api": "healthy",
                "valuation_engine": "healthy",
                "pdf_generator": pdf_status,
                "registry_integration": "healthy",
            }
            if pdf_generator_error:
                services_status["pdf_generator_error"] = pdf_generator_error

            git_metadata = _get_git_metadata()

            result: dict[str, object] = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
                "instance": instance_status(),
                "runtime": public_adaptive_runtime_attestation(),
                "services": services_status,
                "database": db_status,
            }
            if settings.debug:
                result.update(git_metadata)
            return result

        except DataValidationError as exc:
            logger.error(f"❌ Health check failed: {str(exc)}")
            content: dict[str, object] = {
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
            }
            if settings.debug:
                content["error"] = str(exc)
            return JSONResponse(status_code=500, content=content)
        except Exception as exc:
            logger.error(f"❌ Health check failed: {str(exc)}", exc_info=True)
            return {
                "status": "degraded",
                "timestamp": datetime.now().isoformat(),
                "error": str(exc)[:500],
                "services": {"note": "Health check encountered an error"},
            }

    @app.get("/metrics/service", response_model=None)
    async def service_metrics() -> dict[str, object] | JSONResponse:
        if not should_expose_metrics(settings):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        if is_stateless_mode():
            return {
                "service": "upswitch-valuation-engine",
                "mode": "stateless",
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "note": "Database metrics disabled in STATELESS_MODE. Use Titan for persistent metrics.",
                    "uptime": "running",
                    "version": "2.0.0",
                    "architecture": "Brain & Muscle",
                },
            }

        try:
            async for db in get_db():
                from sqlalchemy import text

                total_valuations = (
                    await db.execute(text("SELECT COUNT(*) FROM valuations"))
                ).scalar()
                total_business_types = (
                    await db.execute(text("SELECT COUNT(*) FROM business_type_analysis"))
                ).scalar()
                total_conversations = (
                    await db.execute(text("SELECT COUNT(*) FROM conversation_sessions"))
                ).scalar()
                break

            return {
                "service": "upswitch-valuation-engine",
                "mode": "stateful",
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "total_valuations": total_valuations,
                    "total_business_types": total_business_types,
                    "total_conversations": total_conversations,
                    "uptime": "running",
                    "version": "2.0.0",
                },
            }

        except Exception as exc:
            logger.error(f"❌ Metrics retrieval failed: {str(exc)}")
            return {
                "service": "upswitch-valuation-engine",
                "mode": "error",
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "note": f"Database metrics unavailable: {str(exc)}",
                    "uptime": "running",
                    "version": "2.0.0",
                },
            }


def _get_git_metadata() -> dict[str, str]:
    git_commit = os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_COMMIT") or "unknown"
    git_branch = os.getenv("RAILWAY_GIT_BRANCH") or os.getenv("GIT_BRANCH") or "unknown"
    git_message = (
        os.getenv("RAILWAY_GIT_COMMIT_MESSAGE") or os.getenv("GIT_COMMIT_MESSAGE") or "unknown"
    )

    if git_commit == "unknown":
        try:
            project_root = str(pathlib.Path(__file__).parent.parent.parent)
            commit_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2,
                cwd=project_root,
            )
            if commit_result.returncode == 0:
                git_commit = commit_result.stdout.strip()[:7]

                msg_result = subprocess.run(
                    ["git", "log", "-1", "--pretty=format:%s"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    cwd=project_root,
                )
                if msg_result.returncode == 0:
                    git_message = msg_result.stdout.strip()
        except Exception:
            pass

    return {
        "git_commit": git_commit,
        "git_branch": git_branch,
        "git_message": git_message,
    }
