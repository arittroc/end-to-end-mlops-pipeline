"""
data_cleaning.py
================
Strategy Design Pattern for dataset cleaning.

Architecture
------------
Two independent strategy hierarchies are provided:

  MissingValueStrategy      (ABC)     — contract for imputation
  ├── MeanImputation                  — fills NaN with column mean
  ├── MedianImputation                — fills NaN with column median
  └── DropMissingValues               — removes rows that contain NaNs

  OutlierDetectionStrategy  (ABC)     — contract for outlier identification
  ├── ZScoreOutlierDetection          — flags points beyond N std deviations
  └── IQROutlierDetection             — flags points outside [Q1−k·IQR, Q3+k·IQR]

  DataCleaner                         — context class; composes one strategy
                                        from each hierarchy and exposes a
                                        single ``.clean()`` entry-point.
                                        Strategies are hot-swappable at any
                                        time via setter methods.

Usage
-----
    from src.data_cleaning import (
        DataCleaner,
        MeanImputation,
        IQROutlierDetection,
    )

    cleaner = DataCleaner(
        missing_value_strategy=MeanImputation(),
        outlier_strategy=IQROutlierDetection(factor=1.5),
        outlier_columns=["GrLivArea", "SalePrice"],
    )
    clean_df = cleaner.clean(raw_df)

Notes
-----
- All methods return *new* DataFrames; the input is never mutated.
- No model training logic lives here.
- All public surfaces are fully type-annotated.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

logger: logging.Logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# PART 1 — Missing-Value Strategies
# ═══════════════════════════════════════════════════════════════════════════


class MissingValueStrategy(ABC):
    """
    Abstract strategy for handling missing values in a DataFrame.

    Each concrete strategy encapsulates a single imputation algorithm.
    Strategies are intended to be composable — chain them inside
    ``DataCleaner`` or call them directly on a DataFrame.

    Contract
    --------
    Implementations **must not** mutate the input DataFrame; they must
    return a fresh copy with the transformation applied.
    """

    @abstractmethod
    def handle(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply the missing-value strategy to *df*.

        Parameters
        ----------
        df : pd.DataFrame
            Input DataFrame, potentially containing NaN values.

        Returns
        -------
        pd.DataFrame
            New DataFrame with missing values handled according to the
            concrete strategy.  Shape may differ from input (e.g., rows
            dropped).
        """


class MeanImputation(MissingValueStrategy):
    """
    Fill missing numeric values with the column arithmetic mean.

    Non-numeric columns are silently skipped.  This is the safest default
    for continuous features when the missingness is assumed to be random
    (MAR) and the distribution is roughly symmetric.

    Parameters
    ----------
    columns : list[str] or None
        Explicit list of column names to impute.  When ``None`` (default)
        every numeric column with at least one NaN is processed.

    Examples
    --------
    >>> strategy = MeanImputation(columns=["LotArea", "GrLivArea"])
    >>> clean_df = strategy.handle(df)
    """

    def __init__(self, columns: Optional[list[str]] = None) -> None:
        self._columns: Optional[list[str]] = columns

    def handle(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Replace NaN entries with per-column means.

        Parameters
        ----------
        df : pd.DataFrame
            Source DataFrame.

        Returns
        -------
        pd.DataFrame
            Copy of *df* with NaN values replaced by their column means.

        Raises
        ------
        KeyError
            If an explicitly specified column does not exist in *df*.
        TypeError
            If an explicitly specified column is not numeric.
        """
        result: pd.DataFrame = df.copy()

        target_columns: list[str]
        if self._columns is not None:
            # Validate caller-supplied columns.
            missing_cols = [c for c in self._columns if c not in result.columns]
            if missing_cols:
                raise KeyError(f"MeanImputation: columns not found in DataFrame: {missing_cols}")
            non_numeric = [
                c for c in self._columns if not pd.api.types.is_numeric_dtype(result[c])
            ]
            if non_numeric:
                raise TypeError(
                    f"MeanImputation: mean imputation requires numeric dtype, "
                    f"but these columns are non-numeric: {non_numeric}"
                )
            target_columns = self._columns
        else:
            target_columns = result.select_dtypes(include="number").columns.tolist()

        for col in target_columns:
            n_missing: int = int(result[col].isna().sum())
            if n_missing == 0:
                continue
            col_mean: float = float(result[col].mean())
            result[col] = result[col].fillna(col_mean)
            logger.info(
                "MeanImputation: '%s' — imputed %d NaN(s) with mean=%.4f",
                col,
                n_missing,
                col_mean,
            )

        return result


class MedianImputation(MissingValueStrategy):
    """
    Fill missing numeric values with the column median.

    Preferred over mean imputation when the feature distribution is
    skewed (e.g., ``SalePrice``, ``LotArea``), because the median is
    robust to extreme values.

    Parameters
    ----------
    columns : list[str] or None
        Explicit column list to impute.  Defaults to all numeric columns.

    Examples
    --------
    >>> strategy = MedianImputation(columns=["SalePrice"])
    >>> clean_df = strategy.handle(df)
    """

    def __init__(self, columns: Optional[list[str]] = None) -> None:
        self._columns: Optional[list[str]] = columns

    def handle(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Replace NaN entries with per-column medians.

        Parameters
        ----------
        df : pd.DataFrame
            Source DataFrame.

        Returns
        -------
        pd.DataFrame
            Copy of *df* with NaN values replaced by column medians.

        Raises
        ------
        KeyError
            If a specified column is absent from *df*.
        TypeError
            If a specified column is non-numeric.
        """
        result: pd.DataFrame = df.copy()

        target_columns: list[str]
        if self._columns is not None:
            missing_cols = [c for c in self._columns if c not in result.columns]
            if missing_cols:
                raise KeyError(f"MedianImputation: columns not found: {missing_cols}")
            target_columns = self._columns
        else:
            target_columns = result.select_dtypes(include="number").columns.tolist()

        for col in target_columns:
            n_missing: int = int(result[col].isna().sum())
            if n_missing == 0:
                continue
            col_median: float = float(result[col].median())
            result[col] = result[col].fillna(col_median)
            logger.info(
                "MedianImputation: '%s' — imputed %d NaN(s) with median=%.4f",
                col,
                n_missing,
                col_median,
            )

        return result


class DropMissingValues(MissingValueStrategy):
    """
    Remove rows that contain NaN values.

    Parameters
    ----------
    columns : list[str] or None
        Only consider NaNs in these columns when deciding which rows to drop.
        If ``None``, any NaN in any column triggers row removal.
    thresh : int or None
        Minimum number of non-NaN values required for a row to be kept.
        Rows with fewer than *thresh* valid values are dropped.  Mutually
        exclusive with ``columns`` in typical usage — see ``pd.DataFrame.dropna``
        docs for full semantics.

    Examples
    --------
    >>> strategy = DropMissingValues(columns=["SalePrice", "GrLivArea"])
    >>> clean_df = strategy.handle(df)
    """

    def __init__(
        self,
        columns: Optional[list[str]] = None,
        thresh: Optional[int] = None,
    ) -> None:
        self._columns: Optional[list[str]] = columns
        self._thresh: Optional[int] = thresh

    def handle(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Drop rows with missing values and return the reduced DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            Source DataFrame.

        Returns
        -------
        pd.DataFrame
            Copy of *df* with offending rows removed and the index reset.

        Raises
        ------
        KeyError
            If a specified column does not exist in *df*.
        """
        if self._columns is not None:
            missing_cols = [c for c in self._columns if c not in df.columns]
            if missing_cols:
                raise KeyError(f"DropMissingValues: columns not found: {missing_cols}")

        rows_before: int = len(df)
        result: pd.DataFrame = df.dropna(subset=self._columns, thresh=self._thresh).reset_index(
            drop=True
        )
        rows_dropped: int = rows_before - len(result)

        logger.info(
            "DropMissingValues: dropped %d row(s)  before=%d  after=%d  "
            "(subset=%s, thresh=%s)",
            rows_dropped,
            rows_before,
            len(result),
            self._columns,
            self._thresh,
        )
        return result


# ═══════════════════════════════════════════════════════════════════════════
# PART 2 — Outlier Detection Strategies
# ═══════════════════════════════════════════════════════════════════════════


class OutlierDetectionStrategy(ABC):
    """
    Abstract strategy for detecting outliers in numerical columns.

    Concrete subclasses implement :meth:`detect`, which returns a boolean
    mask DataFrame (``True`` = outlier).  The base class provides
    :meth:`remove` as a convenience that delegates to :meth:`detect` and
    drops the flagged rows — subclasses do **not** need to override it.

    Contract
    --------
    * :meth:`detect` must not mutate the input DataFrame.
    * The returned mask must have the same index as *df* and contain only
      the requested *columns*.
    """

    @abstractmethod
    def detect(self, df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        """
        Identify outliers and return a boolean mask.

        Parameters
        ----------
        df : pd.DataFrame
            Input DataFrame to analyse.
        columns : list[str]
            Numeric columns to inspect for outliers.

        Returns
        -------
        pd.DataFrame
            Boolean mask with the same index as *df* and one column per
            entry in *columns*.  A cell value of ``True`` marks that
            observation as an outlier in that feature.
        """

    def remove(self, df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        """
        Remove rows flagged as outliers in any of *columns*.

        Delegates outlier identification to :meth:`detect`, then drops every
        row where *at least one* column is flagged.

        Parameters
        ----------
        df : pd.DataFrame
            Source DataFrame.
        columns : list[str]
            Columns to inspect.

        Returns
        -------
        pd.DataFrame
            Copy of *df* with outlier rows removed and the index reset.
        """
        mask: pd.DataFrame = self.detect(df, columns)
        outlier_rows: pd.Series = mask.any(axis=1)
        n_removed: int = int(outlier_rows.sum())

        result: pd.DataFrame = df[~outlier_rows].reset_index(drop=True)
        logger.info(
            "%s.remove: removed %d outlier row(s)  before=%d  after=%d",
            self.__class__.__name__,
            n_removed,
            len(df),
            len(result),
        )
        return result


class ZScoreOutlierDetection(OutlierDetectionStrategy):
    """
    Flag outliers whose Z-Score magnitude exceeds a given threshold.

    The Z-Score of observation *x* in column *c* is::

        z = (x − μ_c) / σ_c

    Any |z| > ``threshold`` is labelled an outlier.  This method assumes
    that the underlying distribution is approximately Gaussian; it is
    sensitive to extreme values because mean and std are non-robust
    estimators.

    Parameters
    ----------
    threshold : float
        Absolute Z-Score above which a point is declared an outlier.
        Common choices: ``2.5`` (stricter), ``3.0`` (standard), ``3.5``
        (lenient).  Defaults to ``3.0``.

    Examples
    --------
    >>> detector = ZScoreOutlierDetection(threshold=3.0)
    >>> mask = detector.detect(df, columns=["GrLivArea", "SalePrice"])
    >>> clean_df = detector.remove(df, columns=["GrLivArea", "SalePrice"])
    """

    def __init__(self, threshold: float = 3.0) -> None:
        if threshold <= 0:
            raise ValueError(f"threshold must be positive, got {threshold}")
        self._threshold: float = threshold

    def detect(self, df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        """
        Compute Z-Scores and build a boolean outlier mask.

        NaN values are excluded from the Z-Score calculation and are *not*
        flagged as outliers — handle them with a :class:`MissingValueStrategy`
        before calling this method.

        Parameters
        ----------
        df : pd.DataFrame
            Source DataFrame.
        columns : list[str]
            Numeric columns to evaluate.

        Returns
        -------
        pd.DataFrame
            Boolean mask (same index as *df*, one column per entry in
            *columns*).

        Raises
        ------
        KeyError
            If any column in *columns* is absent from *df*.
        TypeError
            If any column is non-numeric.
        """
        self._validate_columns(df, columns)

        mask: pd.DataFrame = pd.DataFrame(False, index=df.index, columns=columns)

        for col in columns:
            valid_series: pd.Series = df[col].dropna()
            if valid_series.empty:
                logger.warning("ZScoreOutlierDetection: '%s' is entirely NaN — skipping.", col)
                continue

            z_scores: np.ndarray = np.abs(stats.zscore(valid_series))
            outlier_indices = valid_series.index[z_scores > self._threshold]
            mask.loc[outlier_indices, col] = True

            logger.info(
                "ZScoreOutlierDetection: '%s' — %d outlier(s) detected "
                "(threshold=%.1f, n_valid=%d)",
                col,
                int(mask[col].sum()),
                self._threshold,
                len(valid_series),
            )

        return mask

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
        missing = [c for c in columns if c not in df.columns]
        if missing:
            raise KeyError(f"ZScoreOutlierDetection: columns not found: {missing}")
        non_numeric = [c for c in columns if not pd.api.types.is_numeric_dtype(df[c])]
        if non_numeric:
            raise TypeError(
                f"ZScoreOutlierDetection: non-numeric columns supplied: {non_numeric}"
            )


class IQROutlierDetection(OutlierDetectionStrategy):
    """
    Flag outliers using the Interquartile Range (IQR) fence method.

    Bounds are defined as::

        lower = Q1 − factor × IQR
        upper = Q3 + factor × IQR

    where ``IQR = Q3 − Q1``.  Any observation outside ``[lower, upper]``
    is labelled an outlier.  IQR is a *robust* method — unlike Z-Score it
    is insensitive to the extreme values it is trying to identify, making it
    the preferred choice for skewed distributions (e.g. ``SalePrice``).

    Parameters
    ----------
    factor : float
        Multiplier applied to the IQR to set the fence width.  The
        conventional Tukey fence uses ``1.5`` (default) for mild outliers
        and ``3.0`` for extreme outliers.

    Examples
    --------
    >>> detector = IQROutlierDetection(factor=1.5)
    >>> mask = detector.detect(df, columns=["GrLivArea", "SalePrice"])
    >>> clean_df = detector.remove(df, columns=["GrLivArea", "SalePrice"])
    """

    def __init__(self, factor: float = 1.5) -> None:
        if factor <= 0:
            raise ValueError(f"factor must be positive, got {factor}")
        self._factor: float = factor

    def detect(self, df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        """
        Compute IQR fences and build a boolean outlier mask.

        Parameters
        ----------
        df : pd.DataFrame
            Source DataFrame.
        columns : list[str]
            Numeric columns to evaluate.

        Returns
        -------
        pd.DataFrame
            Boolean mask (same index as *df*, one column per entry in
            *columns*).

        Raises
        ------
        KeyError
            If any column in *columns* is absent from *df*.
        TypeError
            If any column is non-numeric.
        """
        self._validate_columns(df, columns)

        mask: pd.DataFrame = pd.DataFrame(False, index=df.index, columns=columns)

        for col in columns:
            series: pd.Series = df[col].dropna()
            if series.empty:
                logger.warning("IQROutlierDetection: '%s' is entirely NaN — skipping.", col)
                continue

            q1: float = float(series.quantile(0.25))
            q3: float = float(series.quantile(0.75))
            iqr: float = q3 - q1

            lower_fence: float = q1 - self._factor * iqr
            upper_fence: float = q3 + self._factor * iqr

            # Mark observations that fall outside [lower_fence, upper_fence].
            mask[col] = ~df[col].between(lower_fence, upper_fence, inclusive="both")
            # NaN positions must not be flagged — revert any NaN rows.
            mask.loc[df[col].isna(), col] = False

            logger.info(
                "IQROutlierDetection: '%s' — %d outlier(s) detected  "
                "Q1=%.2f  Q3=%.2f  IQR=%.2f  fence=[%.2f, %.2f]  factor=%.1f",
                col,
                int(mask[col].sum()),
                q1,
                q3,
                iqr,
                lower_fence,
                upper_fence,
                self._factor,
            )

        return mask

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
        missing = [c for c in columns if c not in df.columns]
        if missing:
            raise KeyError(f"IQROutlierDetection: columns not found: {missing}")
        non_numeric = [c for c in columns if not pd.api.types.is_numeric_dtype(df[c])]
        if non_numeric:
            raise TypeError(
                f"IQROutlierDetection: non-numeric columns supplied: {non_numeric}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Context Class — DataCleaner
# ═══════════════════════════════════════════════════════════════════════════


class DataCleaner:
    """
    Orchestrates the full cleaning pipeline by composing one
    :class:`MissingValueStrategy` and one :class:`OutlierDetectionStrategy`.

    Strategies are injected at construction time and can be swapped at any
    point via the setter methods, enabling runtime reconfiguration without
    rebuilding the object.

    Parameters
    ----------
    missing_value_strategy : MissingValueStrategy
        Strategy used to impute or remove missing values.
    outlier_strategy : OutlierDetectionStrategy or None
        Strategy used to detect and remove outliers.  Pass ``None`` to
        skip outlier removal entirely.
    outlier_columns : list[str] or None
        Columns passed to the outlier strategy.  Required when
        *outlier_strategy* is not ``None``; ignored otherwise.

    Examples
    --------
    Basic usage with mean imputation and IQR outlier removal::

        from src.data_cleaning import (
            DataCleaner, MeanImputation, IQROutlierDetection,
        )

        cleaner = DataCleaner(
            missing_value_strategy=MeanImputation(),
            outlier_strategy=IQROutlierDetection(factor=1.5),
            outlier_columns=["GrLivArea", "SalePrice"],
        )
        clean_df = cleaner.clean(raw_df)

    Swap to Z-Score detection without rebuilding::

        from src.data_cleaning import ZScoreOutlierDetection

        cleaner.set_outlier_strategy(
            ZScoreOutlierDetection(threshold=3.0),
            columns=["GrLivArea", "SalePrice"],
        )
        clean_df_v2 = cleaner.clean(raw_df)
    """

    def __init__(
        self,
        missing_value_strategy: MissingValueStrategy,
        outlier_strategy: Optional[OutlierDetectionStrategy] = None,
        outlier_columns: Optional[list[str]] = None,
    ) -> None:
        if not isinstance(missing_value_strategy, MissingValueStrategy):
            raise TypeError(
                "missing_value_strategy must be an instance of MissingValueStrategy, "
                f"got {type(missing_value_strategy)!r}"
            )
        self._missing_strategy: MissingValueStrategy = missing_value_strategy
        self._outlier_strategy: Optional[OutlierDetectionStrategy] = outlier_strategy
        self._outlier_columns: Optional[list[str]] = outlier_columns

    # ── Strategy setters (hot-swap support) ───────────────────────────────

    def set_missing_value_strategy(self, strategy: MissingValueStrategy) -> None:
        """
        Replace the active missing-value strategy.

        Parameters
        ----------
        strategy : MissingValueStrategy
            New strategy to apply on the next :meth:`clean` call.
        """
        if not isinstance(strategy, MissingValueStrategy):
            raise TypeError(f"Expected MissingValueStrategy, got {type(strategy)!r}")
        self._missing_strategy = strategy
        logger.debug("DataCleaner: missing-value strategy → %s", type(strategy).__name__)

    def set_outlier_strategy(
        self,
        strategy: OutlierDetectionStrategy,
        columns: list[str],
    ) -> None:
        """
        Replace the active outlier-detection strategy.

        Parameters
        ----------
        strategy : OutlierDetectionStrategy
            New strategy to apply on the next :meth:`clean` call.
        columns : list[str]
            Columns the new strategy should inspect.
        """
        if not isinstance(strategy, OutlierDetectionStrategy):
            raise TypeError(f"Expected OutlierDetectionStrategy, got {type(strategy)!r}")
        self._outlier_strategy = strategy
        self._outlier_columns = columns
        logger.debug(
            "DataCleaner: outlier strategy → %s  columns=%s",
            type(strategy).__name__,
            columns,
        )

    # ── Main entry-point ──────────────────────────────────────────────────

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply the full cleaning pipeline to *df* in order:

        1. Missing-value handling (imputation or row removal).
        2. Outlier detection and row removal (skipped if no strategy set).

        Parameters
        ----------
        df : pd.DataFrame
            Raw input DataFrame.  This object is never mutated.

        Returns
        -------
        pd.DataFrame
            Cleaned DataFrame with the same columns as *df* but potentially
            fewer rows.

        Raises
        ------
        ValueError
            If an outlier strategy is configured but ``outlier_columns`` is
            ``None`` or empty.
        """
        logger.info(
            "DataCleaner.clean: START  shape=%s  missing_strategy=%s  outlier_strategy=%s",
            df.shape,
            type(self._missing_strategy).__name__,
            type(self._outlier_strategy).__name__ if self._outlier_strategy else "None",
        )

        # Step 1 — Imputation / row removal for missing values.
        result: pd.DataFrame = self._missing_strategy.handle(df)

        # Step 2 — Outlier removal (optional).
        if self._outlier_strategy is not None:
            if not self._outlier_columns:
                raise ValueError(
                    "DataCleaner: outlier_strategy is set but outlier_columns is empty. "
                    "Pass column names via set_outlier_strategy() or the constructor."
                )
            result = self._outlier_strategy.remove(result, self._outlier_columns)

        logger.info(
            "DataCleaner.clean: END  input_shape=%s  output_shape=%s  rows_removed=%d",
            df.shape,
            result.shape,
            len(df) - len(result),
        )
        return result
