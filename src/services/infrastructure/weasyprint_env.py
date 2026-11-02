"""
WeasyPrint Environment Setup

Configures WeasyPrint and its dependencies to suppress noisy warnings before any
weasyprint import. Import this module first in any code path that uses WeasyPrint.

RATIONALE:
- fontTools emits UserWarning for instantiateVariableFont deprecation
- WeasyPrint logs "Ignored" for unsupported CSS (print-color-adjust, filter, etc.)
- fontTools/pikepdf emit INFO during embedding and PDF post-processing
- Pillow (often pulled in transitively with WeasyPrint) can emit noisy DEBUG/INFO
- These are informational and don't affect PDF generation
- Must run BEFORE the first weasyprint import to avoid warning leakage

OPERATORS:
- ``VALUATIONIQ_VERBOSE_PDF_STACK`` (``VERBOSE_PDF_STACK_ENV_VAR``): if the trimmed lowercased value is in
  ``VERBOSE_PDF_VALUE_TOKENS``, ``reapply`` skips reinforcing clamps and only lifts roots still exactly at those
  clamps to ``NOTSET`` (manual overrides such as ``DEBUG`` on a root are left unchanged — verbose debugging).
  Any other token (including ``0``, ``false``, ``no``, ``off``, unknown strings) keeps suppression enabled each
  ``reapply``; the env is re-read inside the apply lock whenever levels adjust. ``configure_weasyprint_env()`` still installs the
  fontTools deprecation warning filter at most once (first completed run installs it even if clamping is skipped).

HIERARCHY:
- Python propagates levels from parent to child (e.g. `weasyprint` covers
  `weasyprint.css`, `weasyprint.parser`, …). We set parent names only where
  that applies. Independent roots (`tinycss2`, `tinycss`, …) are listed explicitly.

LAUNCH ORDER (no race):
- utils/logging.setup_logging(): ``from … import reapply_pdf_vendor_logging_levels`` loads
  this module (module tail runs ``configure_weasyprint_env()`` → warning filters + first apply),
  then calls ``reapply_pdf_vendor_logging_levels()`` and ``attach_vendor_noise_filter_to_root_handlers()``
  so stdout/structlog init cannot undo levels and new root handlers get the filter.
- startup ``load_heavy_routes()``: imports this module again and runs
  ``configure_weasyprint_env()`` (no-op) + ``reapply_pdf_vendor_logging_levels()`` +
  ``attach_vendor_noise_filter_to_root_handlers()`` immediately
  before routers that lazy-import WeasyPrint — defense in depth.
- No request reaches heavy routes until startup completes and ``_app_ready=True``.
- pdf_strategy, pdf_generator, template_service: each imports weasyprint_env before weasyprint.
- Python import lock ensures only one thread runs module body; Lock in configure_weasyprint_env()
  prevents TOCTOU races on _SETUP_DONE.
- configure_weasyprint_env() is idempotent and thread-safe (Lock).
- ``attach_vendor_noise_filter_to_root_handlers()`` caches the filter module-wide when ``logging.root.handlers``
  is still empty so repeated early callers share one ``VendorNoiseFilter`` instance.

USAGE:
    Import this module before importing weasyprint so filters and log levels are applied first.

Author: ValuationIQ
"""

from __future__ import annotations

import logging
import os
import threading
import warnings

# Debugging: omit stdlib logger level clamping while keeping fontTools deprecation filter.
VERBOSE_PDF_STACK_ENV_VAR = "VALUATIONIQ_VERBOSE_PDF_STACK"
VERBOSE_PDF_VALUE_TOKENS: frozenset[str] = frozenset(("1", "true", "yes", "on"))

__all__ = (
    "VERBOSE_PDF_STACK_ENV_VAR",
    "VERBOSE_PDF_VALUE_TOKENS",
    "VendorNoiseFilter",
    "attach_vendor_noise_filter_to_root_handlers",
    "configure_weasyprint_env",
    "pdf_vendor_logging_suppression_active",
    "reapply_pdf_vendor_logging_levels",
)


def _pdf_vendor_level_suppression_enabled() -> bool:
    """
    True: reinstate ERROR/WARNING clamps on PDF vendor roots on each ``reapply``.

    False: trimmed env value matched ``VERBOSE_PDF_VALUE_TOKENS`` — ``reapply`` lifts only matching prior clamps
    to ``NOTSET`` instead of clamping.
    """
    v = os.environ.get(VERBOSE_PDF_STACK_ENV_VAR, "").strip().lower()
    return v not in VERBOSE_PDF_VALUE_TOKENS


def pdf_vendor_logging_suppression_active() -> bool:
    """
    Best-effort snapshot: True iff env does not equal a trimmed, lowercased ``VERBOSE_PDF_VALUE_TOKENS`` value
    (noise suppression / clamps apply on ``reapply``; vendor filter applies per record).

    False means verbose PDF stack mode (``reapply`` lifts matching clamps; filter passes all vendor records).
    Reads ``os.environ`` without ``_APPLY_LOCK`` — use for health checks; not synchronized with concurrent apply.
    """
    return _pdf_vendor_level_suppression_enabled()


_SETUP_DONE: bool = False
_SETUP_LOCK = threading.Lock()
_APPLY_LOCK = threading.Lock()
# Serializes attachment of VendorNoiseFilter to root handlers — avoids two callers both creating flt instances.
_ATTACH_FILTER_LOCK = threading.Lock()


def _setup_done() -> bool:
    return _SETUP_DONE


# Logging levels: ERROR suppresses CSS "Ignored …" INFO lines from WeasyPrint internals;
# WARNING suppresses toolkit INFO (font glyph mutation, pikepdf open/pipeline, etc.)
_LOGGING_ERROR_ROOTS = (
    "weasyprint",  # Covers weasyprint.css, weasyprint.parser, nested modules
    "tinycss",
    "tinycss2",
    "cssselect2",
)
_LOGGING_WARNING_ROOTS = (
    "fontTools",  # Covers subsetting, varLib, ttLib, etc.
    "pikepdf",
    "pydyf",  # Low-level PDF primitives used by WeasyPrint
    "PIL",  # Pillow (often transitive); caps image decode chatter during embeds.
    "cairocffi",  # Cairo bindings WeasyPrint uses; can be chatty during paint.
)

# Single traversal order used for clamp/unclamp — keep logger names disjoint across ERROR/WARNING tuples.
_LOGGING_VENDOR_ROOT_PAIRS: tuple[tuple[str, int], ...] = tuple(
    (name, logging.ERROR) for name in _LOGGING_ERROR_ROOTS
) + tuple((name, logging.WARNING) for name in _LOGGING_WARNING_ROOTS)


def _unset_clamp_when_verbose(lg: logging.Logger, suppressed_level: int) -> None:
    """
    Restore propagation for a root logger if it still carries only our explicit clamp.

    If the level was raised by something else (e.g. developer set DEBUG), leave it untouched.
    """
    if lg.level == suppressed_level:
        lg.setLevel(logging.NOTSET)


def _apply_pdf_vendor_logging_levels() -> None:
    """Apply ERROR/WARNING thresholds to PDF stack roots (stdlib logging only)."""
    with _APPLY_LOCK:
        if not _pdf_vendor_level_suppression_enabled():
            for name, clamp in _LOGGING_VENDOR_ROOT_PAIRS:
                _unset_clamp_when_verbose(logging.getLogger(name), clamp)
            return
        for name, clamp in _LOGGING_VENDOR_ROOT_PAIRS:
            logging.getLogger(name).setLevel(clamp)


def reapply_pdf_vendor_logging_levels() -> None:
    """
    Re-apply vendor logger levels unless verbose mode is requested (token in ``VERBOSE_PDF_VALUE_TOKENS``).

    When clamping/noise-suppression is active: idempotent ERROR/WARNING on PDF stack roots. When verbose: relax only
    roots still at those explicit clamps (drops ``setLevel(NOTSET)`` so loggers propagate); leaves other overrides intact.
    ``VendorNoiseFilter`` reads the same env gate on **each** emitted record — no attach step needed when toggling verbose.
    Use after logging.config.dictConfig / basicConfig / tests that may reset child loggers.
    Does not duplicate warning filters — ``configure_weasyprint_env()`` installs those once per process.
    """
    _apply_pdf_vendor_logging_levels()


class VendorNoiseFilter(logging.Filter):
    """
    Drop noisy vendor-library log records by name prefix and level threshold.

    Why a Filter (not just ``setLevel``):
        Vendor packages reset their own logger levels when imported. ``weasyprint/logger.py``
        does ``LOGGER.setLevel(logging.WARNING)`` on import, overriding our ``ERROR`` clamp,
        and ``Ignored 'box-shadow' …`` (a CSS warning) is emitted at WARNING — which then
        slips through to root and Railway stdout. A Filter on the root StreamHandler runs
        on every record reaching the handler (including propagated children) and cannot
        be removed by a downstream ``setLevel`` call.

    Threshold rules:
        Records from ``error_prefixes`` are dropped unless ``levelno >= ERROR``.
        Records from ``warning_prefixes`` are dropped unless ``levelno >= WARNING``.
        Other records pass through untouched.

    Verbose mode:
        When the verbose-pdf env var is set, the filter is a no-op so devs can debug.

    Malformed records lacking ``levelno`` are passed through (never dropped) so custom logging bridges
    cannot be bricked by accidental attribute omission.
    """

    def __init__(
        self,
        error_prefixes: tuple[str, ...] = _LOGGING_ERROR_ROOTS,
        warning_prefixes: tuple[str, ...] = _LOGGING_WARNING_ROOTS,
    ) -> None:
        super().__init__()
        self._error_prefixes = tuple(p.lower() for p in error_prefixes)
        self._warning_prefixes = tuple(p.lower() for p in warning_prefixes)

    @staticmethod
    def _matches(name: str, prefixes: tuple[str, ...]) -> bool:
        lname = name.lower()
        for prefix in prefixes:
            if lname == prefix or lname.startswith(prefix + "."):
                return True
        return False

    def filter(self, record: logging.LogRecord) -> bool:
        # Verbose mode: pass everything; dev opted in.
        if not _pdf_vendor_level_suppression_enabled():
            return True
        raw_levelno = getattr(record, "levelno", None)
        # Non-standard / broken records — never vet them here (avoid masking real app errors).
        if not isinstance(raw_levelno, int):
            return True
        levelno = raw_levelno
        name = getattr(record, "name", "") or ""
        if self._matches(name, self._error_prefixes):
            return levelno >= logging.ERROR
        if self._matches(name, self._warning_prefixes):
            return levelno >= logging.WARNING
        return True


# When ``attach_vendor_noise_filter_to_root_handlers`` runs before ``logging.root`` has handlers, cache the instance
# so repeated early calls cannot allocate orphan filters.
_VENDOR_NOISE_FILTER_SINGLETON: VendorNoiseFilter | None = None


def attach_vendor_noise_filter_to_root_handlers() -> VendorNoiseFilter:
    """
    Install a single ``VendorNoiseFilter`` on every existing root-logger handler.

    Thread-safe. Idempotent — re-running attaches at most one filter per handler. Returns the filter
    instance so callers can attach it elsewhere (e.g. a custom log file handler).
    Run again after attaching new handlers to ``logging`` root so they receive the same filter instance.

    Why root handlers (not the loggers themselves):
        Filters added to a Logger only run for direct calls on that logger; they don't
        run on records propagated up from children. Filters on the *handler* run on
        every record the handler receives, including propagated ones. That's exactly the
        coverage we need to silence ``weasyprint.css.LOGGER.warning("Ignored …")`` and
        the like, which originate on a child logger and bubble up to root.
    """
    global _VENDOR_NOISE_FILTER_SINGLETON
    with _ATTACH_FILTER_LOCK:
        root = logging.getLogger()
        # Snapshot handlers: another thread (or diagnostic code) might mutate ``root.handlers`` during attach.
        handler_list = list(root.handlers)
        # Prefer an instance already on a handler; else reuse module singleton when root has zero handlers early.
        existing: VendorNoiseFilter | None = None
        for h in handler_list:
            for f in h.filters:
                if isinstance(f, VendorNoiseFilter):
                    existing = f
                    break
            if existing:
                break
        if existing is not None:
            _VENDOR_NOISE_FILTER_SINGLETON = existing
            flt = existing
        elif _VENDOR_NOISE_FILTER_SINGLETON is None:
            _VENDOR_NOISE_FILTER_SINGLETON = VendorNoiseFilter()
            flt = _VENDOR_NOISE_FILTER_SINGLETON
        else:
            flt = _VENDOR_NOISE_FILTER_SINGLETON
        # Re-fetch in case handlers were added while we held the scan lock ordering (list() again).
        for h in list(root.handlers):
            if not any(isinstance(f, VendorNoiseFilter) for f in h.filters):
                h.addFilter(flt)
        return flt


def _preclaim_weasyprint_logger() -> None:
    """
    Add a ``NullHandler`` to the ``weasyprint`` logger before WeasyPrint imports.

    WeasyPrint's ``logger.py`` only calls ``LOGGER.setLevel(WARNING)`` when ``LOGGER.handlers``
    is empty. Pre-claiming with a NullHandler short-circuits that branch so our level
    survives the import. Belt-and-braces alongside ``VendorNoiseFilter`` — the filter is
    already enough, but pre-claiming reduces noise during the brief import window.
    """
    lg = logging.getLogger("weasyprint")
    if not any(isinstance(h, logging.NullHandler) for h in lg.handlers):
        lg.addHandler(logging.NullHandler())


def configure_weasyprint_env() -> None:
    """
    Install warning filters once, pre-claim weasyprint logger, apply clamps, attach noise filter once when possible.

    Idempotent (thread-safe): subsequent calls return immediately (first run completes atomic setup under locks).
    For later changes: ``reapply_pdf_vendor_logging_levels()`` after dictConfig/basicConfig, then
    ``attach_vendor_noise_filter_to_root_handlers()`` if new root handlers were added.
    """
    global _SETUP_DONE
    if _setup_done():
        return
    with _SETUP_LOCK:
        if _setup_done():
            return
        warnings.filterwarnings(
            "ignore",
            message=".*instantiateVariableFont.*",
            category=UserWarning,
        )
        _preclaim_weasyprint_logger()
        _apply_pdf_vendor_logging_levels()
        # Typical: this module imports after ``logging.basicConfig`` (inside ``setup_logging``); root handlers exist
        # and attach runs here. If import happened earlier with no handlers, ``setup_logging`` / ``load_heavy_routes``
        # repeats ``reapply`` + ``attach`` anyway — harmless (singleton + idempotent handlers).
        attach_vendor_noise_filter_to_root_handlers()
        _SETUP_DONE = True


configure_weasyprint_env()
