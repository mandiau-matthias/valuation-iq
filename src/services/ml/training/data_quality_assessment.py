"""Training-data quality assessment helpers."""

from dataclasses import dataclass

import numpy as np

from ..pipelines.ml_types import DataQuality


@dataclass(frozen=True)
class DataQualityRatios:
    missing_ratio: float
    constant_ratio: float
    outlier_ratio: float


QUALITY_THRESHOLDS = (
    (0.05, 0.10, 0.10, DataQuality.EXCELLENT),
    (0.10, 0.20, 0.20, DataQuality.GOOD),
    (0.20, 0.30, 0.30, DataQuality.FAIR),
    (0.30, 0.40, 0.40, DataQuality.POOR),
)


def assess_training_data_quality(features: np.ndarray) -> DataQuality:
    """Assess feature quality using missing, constant, and outlier ratios."""

    ratios = calculate_data_quality_ratios(features)
    return classify_data_quality(ratios)


def calculate_data_quality_ratios(features: np.ndarray) -> DataQualityRatios:
    numeric_features = _as_numeric_2d_array(features)
    if numeric_features.size == 0:
        return DataQualityRatios(
            missing_ratio=1.0,
            constant_ratio=1.0,
            outlier_ratio=1.0,
        )

    return DataQualityRatios(
        missing_ratio=float(np.isnan(numeric_features).sum() / numeric_features.size),
        constant_ratio=_constant_feature_ratio(numeric_features),
        outlier_ratio=_outlier_ratio(numeric_features),
    )


def classify_data_quality(ratios: DataQualityRatios) -> DataQuality:
    for missing_limit, constant_limit, outlier_limit, quality in QUALITY_THRESHOLDS:
        if (
            ratios.missing_ratio < missing_limit
            and ratios.constant_ratio < constant_limit
            and ratios.outlier_ratio < outlier_limit
        ):
            return quality
    return DataQuality.UNUSABLE


def _as_numeric_2d_array(features: np.ndarray) -> np.ndarray:
    numeric_features = np.asarray(features, dtype=float)
    if numeric_features.ndim == 1:
        return numeric_features.reshape(-1, 1)
    return numeric_features


def _constant_feature_ratio(features: np.ndarray) -> float:
    if features.shape[1] == 0:
        return 1.0

    with np.errstate(invalid="ignore"):
        variances = np.nanvar(features, axis=0)

    constant_features = np.nan_to_num(variances, nan=0.0) == 0
    return float(constant_features.sum() / len(constant_features))


def _outlier_ratio(features: np.ndarray) -> float:
    if len(features) == 0 or features.shape[1] == 0:
        return 1.0

    outlier_ratios = [
        _feature_outlier_ratio(features[:, index]) for index in range(features.shape[1])
    ]
    return float(np.mean(outlier_ratios))


def _feature_outlier_ratio(values: np.ndarray) -> float:
    finite_values = values[np.isfinite(values)]
    if len(finite_values) == 0:
        return 0.0

    q1 = np.percentile(finite_values, 25)
    q3 = np.percentile(finite_values, 75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    outliers = (finite_values < lower_bound) | (finite_values > upper_bound)
    return float(outliers.sum() / len(values))
