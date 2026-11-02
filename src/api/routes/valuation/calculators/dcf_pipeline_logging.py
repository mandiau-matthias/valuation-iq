"""Structured breadcrumbs for DCF post-engine diagnostics."""

from __future__ import annotations

from typing import Protocol

_DCF_PIPELINE_EVENT = "dcf_post_engine_stage"


class PipelineLogger(Protocol):
    def debug(self, message: str, *, extra: dict[str, object]) -> object: ...
    def info(self, message: str, *, extra: dict[str, object]) -> object: ...


def dcf_pipeline_breadcrumb(
    log: PipelineLogger,
    *,
    stage: str,
    phase: str,
    correlation_id: object = None,
    company: object = None,
    **extra: object,
) -> None:
    # Structured breadcrumbs are useful when debugging DCF assembly, but they
    # are too chatty for normal INFO logs: one valuation emits several stages.
    log.debug(
        _DCF_PIPELINE_EVENT,
        extra={
            "dcf_stage": stage,
            "dcf_phase": phase,
            "correlation_id": correlation_id,
            "company": company,
            **extra,
        },
    )
