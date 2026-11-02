"""Fail-closed configuration for the local Public Adaptive migration lane."""

from __future__ import annotations

import hashlib
import os
import platform
from collections.abc import Mapping
from importlib.metadata import version
from pathlib import Path


_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})
_LOOPBACK_HOST = "127.0.0.1"
_LOG_LEVELS = frozenset({"debug", "info", "warning", "error", "critical"})
_DEFAULT_LOCAL_STDOUT_LOG_LEVEL = "warning"
_RUNTIME_CONTENT_PATHS = (
    "value.py",
    "requirements.txt",
    "requirements.lock",
    "src/api",
    "src/config",
    "src/domain",
    "src/services",
)


def public_adaptive_runtime_content_sha256(root: Path | None = None) -> str:
    """Hash every executable/configuration byte loaded by the local engine.

    The fingerprint is computed by each ValuationIQ worker from its own local
    filesystem. This closes the gap between a repository seal recorded by the
    batch runner and the code that is actually serving requests.
    """

    repository_root = (
        Path(__file__).resolve().parents[2]
        if root is None
        else Path(root).expanduser().resolve(strict=True)
    )
    candidates: set[Path] = set()
    for relative in _RUNTIME_CONTENT_PATHS:
        scoped = repository_root / relative
        if scoped.is_file():
            candidates.add(scoped)
        elif scoped.is_dir():
            candidates.update(
                candidate
                for candidate in scoped.rglob("*")
                if candidate.is_file()
                and "__pycache__" not in candidate.parts
                and candidate.suffix not in {".pyc", ".pyo"}
            )
        else:
            raise RuntimeError(f"ValuationIQ runtime scope is missing: {relative}")

    digest = hashlib.sha256()
    for candidate in sorted(
        candidates,
        key=lambda path: path.relative_to(repository_root).as_posix(),
    ):
        encoded_name = candidate.relative_to(repository_root).as_posix().encode("utf-8")
        digest.update(len(encoded_name).to_bytes(8, "big"))
        digest.update(encoded_name)
        with candidate.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    return f"sha256:{digest.hexdigest()}"


_BOOT_RUNTIME_CONTENT_SHA256 = public_adaptive_runtime_content_sha256()


def public_adaptive_local_migration_enabled(
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Parse the migration flag strictly instead of treating typos as false."""
    source = os.environ if environ is None else environ
    raw = str(source.get("PUBLIC_ADAPTIVE_LOCAL_MIGRATION_MODE", "")).strip().lower()
    if not raw:
        return False
    if raw in _TRUE_VALUES:
        return True
    if raw in _FALSE_VALUES:
        return False
    raise RuntimeError("PUBLIC_ADAPTIVE_LOCAL_MIGRATION_MODE must be an explicit boolean")


def public_adaptive_local_bind_host(configured_host: str | None) -> str:
    """Require the exact IPv4 loopback bind used by the local migration contract."""
    host = str(configured_host or "").strip()
    if host and host != _LOOPBACK_HOST:
        raise RuntimeError("Public Adaptive local migration mode requires HOST=127.0.0.1")
    return _LOOPBACK_HOST


def public_adaptive_uvicorn_worker_count(
    environ: Mapping[str, str] | None = None,
) -> int:
    """Resolve a bounded process count; one remains the deployment default."""
    source = os.environ if environ is None else environ
    raw = str(source.get("UVICORN_WORKERS", "1")).strip()
    try:
        workers = int(raw)
    except ValueError as exc:
        raise ValueError("UVICORN_WORKERS must be an integer between 1 and 16") from exc
    if not 1 <= workers <= 16:
        raise ValueError("UVICORN_WORKERS must be between 1 and 16")
    return workers


def public_adaptive_uvicorn_worker_healthcheck_timeout(
    environ: Mapping[str, str] | None = None,
) -> int:
    """Resolve the bounded supervisor health window for numeric workers."""
    source = os.environ if environ is None else environ
    raw = str(source.get("UVICORN_TIMEOUT_WORKER_HEALTHCHECK", "60")).strip()
    try:
        timeout = int(raw)
    except ValueError as exc:
        raise ValueError(
            "UVICORN_TIMEOUT_WORKER_HEALTHCHECK must be an integer between 5 and 300"
        ) from exc
    if not 5 <= timeout <= 300:
        raise ValueError("UVICORN_TIMEOUT_WORKER_HEALTHCHECK must be between 5 and 300")
    return timeout


def public_adaptive_stdout_log_level(
    configured_level: str,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Return a bounded stdout level for the high-volume local batch lane.

    A public valuation carries its durable audit and authority evidence in the
    signed result, Titan receipt, and migration ledger. Re-emitting every
    internal calculation step at INFO for every historical year produced about
    0.5 MiB of transient stdout per company during the Belgium scale run. At
    country scale that is operationally unsafe and does not add durable audit
    evidence.

    Normal service deployments preserve the configured application log level.
    Local Public Adaptive migration mode defaults stdout to WARNING, while an
    explicit, validated override remains available for bounded diagnostics.
    """

    source = os.environ if environ is None else environ
    configured = str(configured_level or "info").strip().lower()
    if configured not in _LOG_LEVELS:
        raise ValueError("Configured log level must be debug, info, warning, error, or critical")
    if not public_adaptive_local_migration_enabled(source):
        return configured
    override = str(source.get("PUBLIC_ADAPTIVE_LOCAL_STDOUT_LOG_LEVEL", "")).strip().lower()
    if not override:
        return _DEFAULT_LOCAL_STDOUT_LOG_LEVEL
    if override not in _LOG_LEVELS:
        raise ValueError(
            "PUBLIC_ADAPTIVE_LOCAL_STDOUT_LOG_LEVEL must be debug, info, warning, error, or critical"
        )
    return override


def public_adaptive_runtime_attestation(
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Expose non-secret runtime facts required by the local scale gate."""
    source = os.environ if environ is None else environ
    stateless = str(source.get("STATELESS_MODE", "")).strip().lower() in _TRUE_VALUES
    return {
        "schema_version": "valuation_iq_local_runtime.v2",
        "public_adaptive_local_migration_mode": public_adaptive_local_migration_enabled(source),
        "stateless_mode": stateless,
        "server": "uvicorn",
        "server_version": version("uvicorn"),
        "python_version": platform.python_version(),
        "worker_count": public_adaptive_uvicorn_worker_count(source),
        "worker_healthcheck_timeout_seconds": (
            public_adaptive_uvicorn_worker_healthcheck_timeout(source)
        ),
        "stdout_log_level": public_adaptive_stdout_log_level("info", source),
        "runtime_content_sha256": _BOOT_RUNTIME_CONTENT_SHA256,
    }


__all__ = [
    "public_adaptive_local_bind_host",
    "public_adaptive_local_migration_enabled",
    "public_adaptive_runtime_attestation",
    "public_adaptive_runtime_content_sha256",
    "public_adaptive_stdout_log_level",
    "public_adaptive_uvicorn_worker_count",
    "public_adaptive_uvicorn_worker_healthcheck_timeout",
]
