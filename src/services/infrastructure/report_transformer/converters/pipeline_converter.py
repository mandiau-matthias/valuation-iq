"""
Pipeline Converter

Converts multiple_pipeline Pydantic models to dictionary structures.
"""

from collections.abc import Iterable, Mapping
from typing import Optional, cast

from src.services.infrastructure.exceptions import DataTransformationError
from src.services.interfaces.request_response_protocol import ValuationResponseProtocol
from src.utils.exceptions import MultiplesCalculationError
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _call_mapping_dumper(value: object, method_name: str) -> Optional[dict[str, object]]:
    dumper = getattr(value, method_name, None)
    if not callable(dumper):
        return None

    return dict(dumper())


def _to_mutable_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)

    for method_name in ("model_dump", "dict"):
        dumped = _call_mapping_dumper(value, method_name)
        if dumped is not None:
            return dumped

    if isinstance(value, Mapping):
        return dict(cast(Mapping[str, object], value))
    if isinstance(value, Iterable):
        return dict(cast(Iterable[tuple[str, object]], value))
    raise TypeError(f"{type(value).__name__} is not a mapping")


def _stage_discount_percentage(stage: object, stage_dict: dict[str, object]) -> object:
    if isinstance(stage, dict):
        return stage.get("discount_percentage")

    discount_percentage = getattr(stage, "discount_percentage", None)
    if discount_percentage is None and "discount_percentage" in stage_dict:
        return stage_dict.get("discount_percentage")
    return discount_percentage


def _normalize_pipeline_stage(stage: object) -> dict[str, object]:
    stage_dict = _to_mutable_dict(stage)
    discount_percentage = _stage_discount_percentage(stage, stage_dict)

    stage_dict.setdefault("discount_percentage", discount_percentage)
    stage_dict.setdefault("adjustment_percentage", discount_percentage)
    return stage_dict


def _iter_stages(stages: object) -> list[object]:
    if isinstance(stages, Iterable):
        return list(stages)
    raise TypeError(f"{type(stages).__name__} is not iterable")


def _normalize_pipeline_stages(pipeline_dict: dict[str, object]) -> None:
    stages = pipeline_dict.get("stages")
    if not stages:
        return

    pipeline_dict["stages"] = [_normalize_pipeline_stage(stage) for stage in _iter_stages(stages)]


class PipelineConverter:
    """
    Converts multiple_pipeline to dictionary structure.

    Handles conversion of Pydantic models to dictionaries with proper field mapping.
    """

    @staticmethod
    def convert_to_dict(
        response: ValuationResponseProtocol,
    ) -> Optional[dict[str, object]]:
        """
        Convert multiple_pipeline to dictionary structure.

        Args:
            response: ValuationResponse containing multiple_pipeline

        Returns:
            Dictionary representation of multiple_pipeline, or None if conversion fails
        """
        if not response.multiple_pipeline:
            return None

        try:
            pipeline_dict = _to_mutable_dict(response.multiple_pipeline)
            _normalize_pipeline_stages(pipeline_dict)
            return pipeline_dict
        except (AttributeError, TypeError, ValueError) as pipeline_error:
            logger.warning(
                "Failed to convert multiple_pipeline to dict",
                extra={
                    "error_type": type(pipeline_error).__name__,
                    "error_message": str(pipeline_error),
                    "company_name": response.company_name,
                },
            )
            return None
        except MultiplesCalculationError as pipeline_error:
            logger.error(
                "Unexpected error converting multiple_pipeline",
                extra={
                    "error_type": type(pipeline_error).__name__,
                    "error_message": str(pipeline_error),
                    "company_name": response.company_name,
                    "valuation_id": response.valuation_id,
                },
                exc_info=True,
            )
            raise DataTransformationError(
                f"Failed to convert multiple_pipeline to dict: {pipeline_error}",
                company_name=response.company_name,
            ) from pipeline_error
