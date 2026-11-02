"""
Infrastructure Services

Keep package imports lightweight. Heavy modules such as `template_service`
should not be imported eagerly here because they probe optional runtime
dependencies like WeasyPrint during module import.
"""

from typing import Any

__all__ = ["get_ai_service", "IndustryInference", "get_template_service", "DocumentParser"]


def get_ai_service(*args: Any, **kwargs: Any):
    from .ai_insights_service import get_ai_service as _get_ai_service

    return _get_ai_service(*args, **kwargs)


def get_template_service(*args: Any, **kwargs: Any):
    from .template_service import get_template_service as _get_template_service

    return _get_template_service(*args, **kwargs)


def __getattr__(name: str):
    if name == "IndustryInference":
        from .ai_industry_inference import IndustryInference

        return IndustryInference
    if name == "DocumentParser":
        from .document_parser import DocumentParser

        return DocumentParser
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
