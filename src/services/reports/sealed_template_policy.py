"""Static fail-closed policy for the publishable Jinja template bundle."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, nodes
from jinja2.visitor import NodeVisitor


class SealedTemplatePolicyError(ValueError):
    pass


_ARITHMETIC_NODES = (
    nodes.Add,
    nodes.Sub,
    nodes.Mul,
    nodes.Div,
    nodes.FloorDiv,
    nodes.Mod,
    nodes.Pow,
)


class _PolicyVisitor(NodeVisitor):
    def __init__(self, template: str):
        self.template = template
        self.violations: list[str] = []

    def generic_visit(self, node: nodes.Node, *args: object, **kwargs: object) -> None:
        if isinstance(node, _ARITHMETIC_NODES):
            self.violations.append(
                f"{self.template}:{getattr(node, 'lineno', '?')}: arithmetic"
            )
        if isinstance(node, nodes.Assign):
            self.violations.append(
                f"{self.template}:{getattr(node, 'lineno', '?')}: assignment"
            )
        super().generic_visit(node, *args, **kwargs)


def validate_sealed_template_source(source: str, *, template: str) -> None:
    visitor = _PolicyVisitor(template)
    visitor.visit(Environment(autoescape=True).parse(source))
    if visitor.violations:
        raise SealedTemplatePolicyError(
            "sealed templates may format and branch only: "
            + "; ".join(visitor.violations)
        )


@lru_cache(maxsize=1)
def assert_sealed_template_policy() -> tuple[str, ...]:
    """Parse every sealed page once per process and reject calculation logic."""

    root = Path(__file__).resolve().parents[2] / "templates" / "main_report_pdf" / "sealed"
    files = sorted(root.glob("*.html"))
    if not files:
        raise SealedTemplatePolicyError("sealed memorandum template pack is missing")
    for path in files:
        relative = path.relative_to(root).as_posix()
        validate_sealed_template_source(
            path.read_text(encoding="utf-8"), template=relative
        )
    return tuple(path.name for path in files)
