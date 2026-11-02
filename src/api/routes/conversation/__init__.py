"""
Conversation route helpers.

The AI-guided conversation endpoints moved to Titan. This package still hosts
shared streaming helpers and a few legacy modules, so importing any submodule
must not eagerly import routers that no longer exist in ValuationIQ.
"""

from typing import Any, NoReturn


_MOVED_MESSAGE = (
    "ValuationIQ no longer owns AI-guided conversation endpoints. "
    "Use Titan's conversation APIs for interactive flows."
)

_RETIRED_ROUTER_EXPORTS = {
    "intelligent_conversation_router",
    "intelligent_conversation_stream_router",
    "progressive_report_router",
    "valuation_conversation_router",
}


def _raise_moved(attribute_name: str) -> NoReturn:
    raise RuntimeError(f"{_MOVED_MESSAGE} Attempted to access `{attribute_name}`.")


def __getattr__(name: str) -> Any:
    if name in _RETIRED_ROUTER_EXPORTS:
        _raise_moved(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_intelligent_conversation_router() -> Any:
    _raise_moved("intelligent_conversation_router")


def get_intelligent_conversation_stream_router() -> Any:
    _raise_moved("intelligent_conversation_stream_router")


def get_progressive_report_router() -> Any:
    _raise_moved("progressive_report_router")


def get_valuation_conversation_router() -> Any:
    _raise_moved("valuation_conversation_router")


__all__ = [
    "get_intelligent_conversation_router",
    "get_intelligent_conversation_stream_router",
    "get_progressive_report_router",
    "get_valuation_conversation_router",
    "intelligent_conversation_router",
    "intelligent_conversation_stream_router",
    "progressive_report_router",
    "valuation_conversation_router",
]
