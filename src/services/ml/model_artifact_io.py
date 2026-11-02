"""Trusted model artifact IO for joblib-based ML models.

``joblib.load`` is pickle-backed deserialization. It must only be used for
trusted model artifacts that we produced, stored under expected model roots,
and checksummed before production/staging startup or inference.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
from typing import Any, Iterable

import joblib


SECURE_MODEL_ENVIRONMENTS = {"production", "staging"}
DEFAULT_MODEL_ROOTS = ("models",)
CHECKSUM_SUFFIX = ".sha256"


class UntrustedModelArtifactError(ValueError):
    """Raised when a model artifact cannot be trusted for deserialization."""


def is_secure_model_environment() -> bool:
    """Return true when unsigned model deserialization must fail closed."""

    return os.getenv("ENVIRONMENT", "development").strip().lower() in SECURE_MODEL_ENVIRONMENTS


def _configured_model_roots() -> tuple[Path, ...]:
    raw = os.getenv("VALUATIONIQ_MODEL_ARTIFACT_ROOTS", "")
    values = [value.strip() for value in raw.split(",") if value.strip()]
    return tuple(Path(value) for value in values) or tuple(Path(root) for root in DEFAULT_MODEL_ROOTS)


def _resolve_roots(allowed_roots: Iterable[str | Path] | None) -> tuple[Path, ...]:
    roots = tuple(Path(root).expanduser().resolve() for root in (allowed_roots or _configured_model_roots()))
    if not roots:
        raise UntrustedModelArtifactError("At least one trusted model artifact root is required")
    return roots


def _has_symlink_component(path: Path) -> bool:
    """Detect symlink traversal before resolving the path."""

    probe = Path(path.anchor) if path.is_absolute() else Path(".")
    for part in path.parts:
        if part in ("", path.anchor):
            continue
        probe = probe / part
        if probe.exists() and probe.is_symlink():
            return True
    return False


def _assert_under_trusted_root(path: Path, roots: tuple[Path, ...]) -> None:
    if not any(path == root or path.is_relative_to(root) for root in roots):
        root_list = ", ".join(str(root) for root in roots)
        raise UntrustedModelArtifactError(f"Model artifact is outside trusted roots: {path} (roots: {root_list})")


def resolve_trusted_model_artifact(
    artifact_path: str | Path,
    *,
    allowed_roots: Iterable[str | Path] | None = None,
) -> Path:
    """Resolve and validate a model artifact path before deserialization."""

    candidate = Path(artifact_path).expanduser()
    if _has_symlink_component(candidate):
        raise UntrustedModelArtifactError(f"Model artifact path must not traverse symlinks: {artifact_path}")

    resolved = candidate.resolve(strict=True)
    _assert_under_trusted_root(resolved, _resolve_roots(allowed_roots))
    return resolved


def resolve_trusted_model_artifact_target(
    artifact_path: str | Path,
    *,
    allowed_roots: Iterable[str | Path] | None = None,
) -> Path:
    """Resolve and validate a model artifact write target."""

    candidate = Path(artifact_path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    parent = candidate.parent if candidate.parent != Path("") else Path(".")
    if _has_symlink_component(parent):
        raise UntrustedModelArtifactError(f"Model artifact parent must not traverse symlinks: {artifact_path}")

    resolved_parent = parent.resolve(strict=False)
    _assert_under_trusted_root(resolved_parent, _resolve_roots(allowed_roots))
    resolved_parent.mkdir(parents=True, exist_ok=True)
    return resolved_parent / candidate.name


def checksum_sidecar_path(artifact_path: Path) -> Path:
    return artifact_path.with_name(f"{artifact_path.name}{CHECKSUM_SUFFIX}")


def calculate_sha256(artifact_path: Path) -> str:
    digest = hashlib.sha256()
    with artifact_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_sha256_sidecar(artifact_path: str | Path) -> Path:
    resolved = Path(artifact_path).expanduser().resolve(strict=True)
    sidecar = checksum_sidecar_path(resolved)
    sidecar.write_text(f"{calculate_sha256(resolved)}  {resolved.name}\n", encoding="utf-8")
    return sidecar


def verify_sha256_sidecar(
    artifact_path: Path,
    *,
    checksum_required: bool | None = None,
) -> None:
    required = is_secure_model_environment() if checksum_required is None else checksum_required
    sidecar = checksum_sidecar_path(artifact_path)
    if not sidecar.exists():
        if required:
            raise UntrustedModelArtifactError(
                f"Missing SHA-256 sidecar for trusted model artifact: {sidecar}"
            )
        return

    expected = sidecar.read_text(encoding="utf-8").strip().split()[0]
    actual = calculate_sha256(artifact_path)
    if not hmac.compare_digest(expected, actual):
        raise UntrustedModelArtifactError(f"SHA-256 mismatch for model artifact: {artifact_path}")


def load_trusted_joblib(
    artifact_path: str | Path,
    *,
    allowed_roots: Iterable[str | Path] | None = None,
    checksum_required: bool | None = None,
) -> Any:
    """Load a trusted joblib artifact after root and checksum validation."""

    resolved = resolve_trusted_model_artifact(artifact_path, allowed_roots=allowed_roots)
    verify_sha256_sidecar(resolved, checksum_required=checksum_required)
    return joblib.load(resolved)


def dump_trusted_joblib(
    value: Any,
    artifact_path: str | Path,
    *,
    allowed_roots: Iterable[str | Path] | None = None,
) -> Path:
    """Persist a joblib artifact and write its SHA-256 sidecar."""

    target = resolve_trusted_model_artifact_target(artifact_path, allowed_roots=allowed_roots)
    joblib.dump(value, target)
    write_sha256_sidecar(target)
    return target
