"""
pipeline.py
===========
ZenML production pipeline: End-to-End House Price Prediction.

Topology
--------
  ingest_data_step
      ↓  raw_dataset  (pd.DataFrame)
  clean_data_step
      ↓  clean_dataset  (pd.DataFrame)
  train_model_step
      ↓  trained_sklearn_pipeline  (sklearn.Pipeline)
      ↓  evaluation_metrics        (Dict[str, float])

Every step is independently versioned, cached, and re-runnable by ZenML.
MLflow experiment tracking is routed to the custom port server at
``http://localhost:5055`` and persisted in the remote Neon.tech PostgreSQL
backend store established in ``start_mlflow.sh``.

One-time ZenML stack setup
--------------------------
Run these shell commands once before executing the pipeline::

    # 1. Install ZenML's MLflow integration
    zenml integration install mlflow -y

    # 2. Register the MLflow experiment tracker pointed at your server
    zenml experiment-tracker register house_price_mlflow_tracker \\
        --flavor=mlflow \\
        --tracking_uri="http://localhost:5055"

    # 3. Register a local artifact store (or reuse an existing one)
    zenml artifact-store register local_store --flavor=local

    # 4. Assemble the stack
    zenml stack register house_price_stack \\
        --orchestrator=default \\
        --artifact-store=local_store \\
        --experiment-tracker=house_price_mlflow_tracker

    # 5. Activate the stack for this project
    zenml stack set house_price_stack

Running the pipeline
--------------------
::

    # From the project root with the venv active:
    python -m src.pipeline --data-path data/train.csv

    # Or import and call programmatically:
    from src.pipeline import run_pipeline
    run_pipeline(data_path="data/train.csv")
"""

import argparse
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline as SklearnPipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler
from zenml import pipeline, step
from zenml.integrations.mlflow.flavors.mlflow_experiment_tracker_flavor import (
    MLFlowExperimentTrackerSettings,
)

from src.data_cleaning import DataCleaner, IQROutlierDetection, MedianImputation
from src.data_ingestion import DataIngestorFactory

logger: logging.Logger = logging.getLogger(__name__)

# ── Pipeline-wide configuration ────────────────────────────────────────────
#
# All tunable parameters live here.  Change values in this block rather than
# hunting through function bodies.


@dataclass(frozen=True)
class PipelineConfig:
    """
    Immutable configuration for the House Price Prediction pipeline.

    Attributes
    ----------
    mlflow_tracking_uri : str
        URI of the running MLflow tracking server.  Must match the port
        used in ``start_mlflow.sh`` (default: 5055).
    mlflow_experiment_name : str
        Logical experiment namespace inside the MLflow server.
    zenml_experiment_tracker_name : str
        Name of the ZenML stack component registered for MLflow.
    target_column : str
        Name of the regression target column in the raw dataset.
    outlier_columns : List[str]
        Columns inspected by :class:`IQROutlierDetection` in the cleaning step.
    iqr_factor : float
        IQR fence multiplier — 1.5 = mild outliers, 3.0 = extreme only.
    skewness_threshold : float
        Absolute skewness above which a numeric feature receives a
        log1p transform before standard scaling.
    test_size : float
        Fraction of rows reserved for the hold-out test set.
    random_state : int
        Seed for all random processes (train/test split, etc.).
    """

    mlflow_tracking_uri: str = field(
        default_factory=lambda: os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5055")
    )
    mlflow_experiment_name: str = "house_price_prediction"
    zenml_experiment_tracker_name: str = "house_price_mlflow_tracker"
    target_column: str = "SalePrice"
    outlier_columns: List[str] = field(
        default_factory=lambda: ["GrLivArea", "SalePrice"]
    )
    iqr_factor: float = 1.5
    skewness_threshold: float = 0.75
    test_size: float = 0.20
    random_state: int = 42


# Singleton config used by all steps and the pipeline definition.
CONFIG = PipelineConfig()

# Per-step MLflow settings injected via ZenML's settings API.
# These override the stack-level defaults for this specific step.
_MLFLOW_STEP_SETTINGS = MLFlowExperimentTrackerSettings(
    experiment_name=CONFIG.mlflow_experiment_name,
)


# ═══════════════════════════════════════════════════════════════════════════
# Private helpers (not ZenML steps — pure functions for internal reuse)
# ═══════════════════════════════════════════════════════════════════════════


def _identify_column_types(
    df: pd.DataFrame,
    target_column: str,
) -> Tuple[List[str], List[str]]:
    """
    Partition *df*'s columns (excluding the target) into numeric and
    categorical lists.

    Parameters
    ----------
    df : pd.DataFrame
        Feature matrix that still contains the target column.
    target_column : str
        Name of the target column to exclude.

    Returns
    -------
    Tuple[List[str], List[str]]
        ``(numerical_columns, categorical_columns)`` — both lists contain
        only feature columns (target excluded).
    """
    features = df.drop(columns=[target_column], errors="raise")
    numerical: List[str] = features.select_dtypes(include="number").columns.tolist()
    categorical: List[str] = features.select_dtypes(
        include=["object", "category"]
    ).columns.tolist()
    return numerical, categorical


def _split_by_skewness(
    df: pd.DataFrame,
    numerical_cols: List[str],
    threshold: float,
) -> Tuple[List[str], List[str]]:
    """
    Split *numerical_cols* into high-skew and low-skew buckets.

    Absolute skewness is computed on *df* for each column.  Columns whose
    |skew| exceeds *threshold* go into the high-skew bucket and will receive
    a log1p transform prior to standard scaling.

    Parameters
    ----------
    df : pd.DataFrame
        The training split (used to compute skewness — never the test set).
    numerical_cols : List[str]
        Candidate numeric columns.
    threshold : float
        Absolute skewness cut-off.

    Returns
    -------
    Tuple[List[str], List[str]]
        ``(skewed_columns, non_skewed_columns)``
    """
    skewness: pd.Series = df[numerical_cols].skew().abs()
    skewed: List[str] = skewness[skewness > threshold].index.tolist()
    non_skewed: List[str] = [c for c in numerical_cols if c not in skewed]

    logger.info(
        "_split_by_skewness: threshold=%.2f  skewed=%d cols  non_skewed=%d cols",
        threshold,
        len(skewed),
        len(non_skewed),
    )
    logger.debug("Skewed columns   : %s", skewed)
    logger.debug("Non-skewed columns: %s", non_skewed)
    return skewed, non_skewed


def _build_preprocessor(
    skewed_cols: List[str],
    non_skewed_cols: List[str],
    categorical_cols: List[str],
) -> ColumnTransformer:
    """
    Construct the :class:`~sklearn.compose.ColumnTransformer` that forms the
    first stage of the training pipeline.

    Transformation rules
    --------------------
    * **Skewed numericals** → log1p (via FunctionTransformer) → StandardScaler
    * **Non-skewed numericals** → StandardScaler
    * **Categoricals** → OneHotEncoder (unknown categories ignored at inference)
    * **All other columns** → dropped (``remainder="drop"``)

    Using ``remainder="drop"`` is intentional: any column not explicitly
    declared here is excluded from the model, preventing silent data leakage
    from columns added to the dataset after the pipeline was designed.

    Parameters
    ----------
    skewed_cols : List[str]
        High-skew numeric feature names.
    non_skewed_cols : List[str]
        Low-skew numeric feature names.
    categorical_cols : List[str]
        Categorical feature names.

    Returns
    -------
    ColumnTransformer
        Unfitted preprocessor ready to be embedded inside a
        :class:`~sklearn.pipeline.Pipeline`.
    """
    # log1p is applied element-wise; validate=False preserves column names.
    log_then_scale = SklearnPipeline(
        steps=[
            ("log1p", FunctionTransformer(np.log1p, validate=False)),
            ("scaler", StandardScaler()),
        ]
    )

    transformers = []

    if skewed_cols:
        transformers.append(("skewed_num", log_then_scale, skewed_cols))

    if non_skewed_cols:
        transformers.append(("num", StandardScaler(), non_skewed_cols))

    if categorical_cols:
        transformers.append(
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                categorical_cols,
            )
        )

    if not transformers:
        raise ValueError(
            "_build_preprocessor: no columns were classified for transformation. "
            "Verify that the cleaned DataFrame contains numeric or categorical features."
        )

    return ColumnTransformer(transformers=transformers, remainder="drop")


# ═══════════════════════════════════════════════════════════════════════════
# ZenML Steps
# ═══════════════════════════════════════════════════════════════════════════


@step
def ingest_data_step(
    file_path: str,
) -> pd.DataFrame:
    """
    ZenML step — Data Ingestion.

    Delegates entirely to :class:`~src.data_ingestion.DataIngestorFactory`.
    The factory inspects the file extension at runtime and routes to the
    correct concrete ingestor (``CSVDataIngestor`` or ``ZipDataIngestor``).

    This step has *no knowledge* of file formats; adding support for a new
    format (e.g., ``.parquet``) only requires registering a new ingestor in
    the factory — this step remains unchanged.

    Parameters
    ----------
    file_path : str
        Absolute or relative path to the raw dataset file.
        Supported extensions: ``.csv``, ``.zip``.

    Returns
    -------
    pd.DataFrame
        Raw, unprocessed dataset as loaded from disk.

    Raises
    ------
    FileNotFoundError
        If *file_path* does not exist.
    ValueError
        If the file extension is not registered in the factory.
    """
    logger.info("ingest_data_step: reading from '%s'", file_path)

    ingestor = DataIngestorFactory.get_ingestor(file_path)
    raw_df: pd.DataFrame = ingestor.ingest(file_path)

    logger.info(
        "ingest_data_step: ingestion complete  shape=%s  columns=%d  "
        "memory=%.1f MB",
        raw_df.shape,
        len(raw_df.columns),
        raw_df.memory_usage(deep=True).sum() / 1_048_576,
    )
    return raw_df


@step
def clean_data_step(
    raw_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    ZenML step — Data Cleaning.

    Composes two strategies from ``src.data_cleaning``:

    1. **MedianImputation** — fills all numeric NaNs with the per-column
       median.  Median is preferred over mean here because house price
       features (``LotArea``, ``GrLivArea``) are typically right-skewed,
       making the mean sensitive to the same outliers we are about to remove.

    2. **IQROutlierDetection** — removes rows where any value in
       ``CONFIG.outlier_columns`` lies outside the Tukey fence
       ``[Q1 − factor·IQR, Q3 + factor·IQR]``.

    The :class:`~src.data_cleaning.DataCleaner` context class guarantees
    that imputation always runs *before* outlier removal, so outlier
    statistics are never computed on NaN-containing columns.

    Parameters
    ----------
    raw_df : pd.DataFrame
        Raw dataset artifact produced by ``ingest_data_step``.

    Returns
    -------
    pd.DataFrame
        Cleaned dataset with missing values imputed and outlier rows removed.
    """
    logger.info(
        "clean_data_step: START  shape=%s  outlier_cols=%s  iqr_factor=%.1f",
        raw_df.shape,
        CONFIG.outlier_columns,
        CONFIG.iqr_factor,
    )

    # Validate that outlier columns exist before wiring up the cleaner —
    # fail fast here rather than inside the ZenML artifact store.
    missing = [c for c in CONFIG.outlier_columns if c not in raw_df.columns]
    if missing:
        raise ValueError(
            f"clean_data_step: outlier_columns not found in dataset: {missing}. "
            f"Available columns: {raw_df.columns.tolist()}"
        )

    cleaner = DataCleaner(
        missing_value_strategy=MedianImputation(),
        outlier_strategy=IQROutlierDetection(factor=CONFIG.iqr_factor),
        outlier_columns=CONFIG.outlier_columns,
    )
    clean_df: pd.DataFrame = cleaner.clean(raw_df)

    logger.info(
        "clean_data_step: END  shape=%s  rows_removed=%d",
        clean_df.shape,
        len(raw_df) - len(clean_df),
    )
    return clean_df


@step(
    experiment_tracker=CONFIG.zenml_experiment_tracker_name,
    settings={"experiment_tracker": _MLFLOW_STEP_SETTINGS},
)
def train_model_step(
    clean_df: pd.DataFrame,
) -> Tuple[SklearnPipeline, Dict[str, float]]:
    """
    ZenML step — Feature Engineering + Model Training.

    This step is responsible for three tightly coupled sub-tasks that share
    the same train/test split and therefore cannot be separated into
    independent ZenML steps without risking data leakage:

    1. **Target encoding** — ``SalePrice`` is log1p-transformed before
       splitting.  The log transform compresses the long right tail of
       house prices, making the residuals more homoscedastic and improving
       Linear Regression's OLS assumptions.

    2. **Feature preprocessing** via a :class:`~sklearn.compose.ColumnTransformer`:

       - *Skewed numericals* (|skew| > ``CONFIG.skewness_threshold``) →
         log1p then StandardScaler.
       - *Non-skewed numericals* → StandardScaler only.
       - *Categoricals* → OneHotEncoder (``handle_unknown="ignore"`` so
         unseen categories at inference time silently map to all-zero vectors
         rather than raising exceptions).

    3. **Training** — a :class:`~sklearn.linear_model.LinearRegression` is
       appended to the preprocessor inside a single
       :class:`~sklearn.pipeline.Pipeline`, ensuring that preprocessing
       parameters (scaler means, OHE vocabulary) are *always* fitted on the
       training split only.

    MLflow integration
    ------------------
    * ``mlflow.set_tracking_uri`` explicitly points at the custom-port
      server (``http://localhost:5055``) as a guard regardless of any
      environment-level defaults.
    * ``mlflow.sklearn.autolog`` captures coefficients, intercept, training
      score, and the serialised model artefact automatically.
    * Additional metrics (RMSE, MAE, R²) are logged manually because
      ``autolog`` only records training-set scores; we log hold-out scores.
    * The MLflow run is started via ``mlflow.start_run``; ZenML's experiment
      tracker wrapper will nest this inside its own parent run, creating a
      clean hierarchy in the MLflow UI.

    Parameters
    ----------
    clean_df : pd.DataFrame
        Cleaned dataset artifact from ``clean_data_step``.

    Returns
    -------
    Tuple[SklearnPipeline, Dict[str, float]]
        * ``trained_sklearn_pipeline`` — fitted end-to-end sklearn Pipeline
          (preprocessor + LinearRegression), ready to call ``.predict()`` on
          raw feature rows.
        * ``evaluation_metrics`` — hold-out test set scores:
          ``rmse``, ``mae``, ``r2_score``, ``rmse_log_scale``.

    Raises
    ------
    ValueError
        If the target column is absent or the cleaned DataFrame is empty.
    """
    # ── Guard rails ───────────────────────────────────────────────────────
    # NaN in categorical columns (e.g. PoolQC, Alley) means "no feature", not missing.
    # Fill with "None" so OHE encodes them as a proper category.
    cat_cols = clean_df.select_dtypes(include=["object", "category"]).columns
    if len(cat_cols) > 0:
        clean_df = clean_df.copy()
        clean_df[cat_cols] = clean_df[cat_cols].fillna("None")

    if clean_df.empty:
        raise ValueError("train_model_step: received an empty DataFrame.")
    if CONFIG.target_column not in clean_df.columns:
        raise ValueError(
            f"train_model_step: target column '{CONFIG.target_column}' not found. "
            f"Available columns: {clean_df.columns.tolist()}"
        )

    # ── Explicit tracking URI —— overrides any environment default ─────────
    mlflow.set_tracking_uri(CONFIG.mlflow_tracking_uri)
    logger.info(
        "train_model_step: MLflow tracking URI = %s  experiment = %s",
        CONFIG.mlflow_tracking_uri,
        CONFIG.mlflow_experiment_name,
    )

    # ── Target + feature split ─────────────────────────────────────────────
    X: pd.DataFrame = clean_df.drop(columns=[CONFIG.target_column])
    # log1p on SalePrice: compresses right tail, stabilises variance.
    y: pd.Series = np.log1p(clean_df[CONFIG.target_column])

    # ── Train / test split ─────────────────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=CONFIG.test_size,
        random_state=CONFIG.random_state,
    )
    logger.info(
        "train_model_step: split  train=%d  test=%d  (test_size=%.0f%%)",
        len(X_train),
        len(X_test),
        CONFIG.test_size * 100,
    )

    # ── Column type identification (on training split only) ────────────────
    numerical_cols, categorical_cols = _identify_column_types(
        clean_df, CONFIG.target_column
    )
    skewed_cols, non_skewed_cols = _split_by_skewness(
        X_train, numerical_cols, CONFIG.skewness_threshold
    )

    logger.info(
        "train_model_step: features  numerical=%d  categorical=%d  "
        "(skewed=%d  non_skewed=%d)",
        len(numerical_cols),
        len(categorical_cols),
        len(skewed_cols),
        len(non_skewed_cols),
    )

    # ── Build sklearn Pipeline ─────────────────────────────────────────────
    preprocessor: ColumnTransformer = _build_preprocessor(
        skewed_cols=skewed_cols,
        non_skewed_cols=non_skewed_cols,
        categorical_cols=categorical_cols,
    )

    model_pipeline: SklearnPipeline = SklearnPipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("regressor", LinearRegression()),
        ]
    )

    # ── MLflow run ─────────────────────────────────────────────────────────
    # autolog must be enabled *before* .fit() is called so it can intercept
    # the sklearn training lifecycle hooks.
    mlflow.sklearn.autolog(
        log_models=True,
        log_datasets=False,  # We track data via ZenML artifacts instead.
        silent=False,
    )

    with mlflow.start_run(
        run_name=f"linear_regression_v{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}",
        nested=True,  # Nest inside ZenML's parent run for a clean UI hierarchy.
    ):
        # ── Training ──────────────────────────────────────────────────────
        model_pipeline.fit(X_train, y_train)

        # ── Predictions & hold-out evaluation ─────────────────────────────
        y_pred_log: np.ndarray = model_pipeline.predict(X_test)

        # Log-scale metrics (what the model optimises directly).
        rmse_log: float = float(np.sqrt(mean_squared_error(y_test, y_pred_log)))
        r2: float = float(r2_score(y_test, y_pred_log))

        # Original-scale metrics (business-interpretable, in $).
        y_test_orig: np.ndarray = np.expm1(y_test.to_numpy())
        y_pred_orig: np.ndarray = np.expm1(np.clip(y_pred_log, 0, 20))
        rmse_orig: float = float(np.sqrt(mean_squared_error(y_test_orig, y_pred_orig)))
        mae_orig: float = float(mean_absolute_error(y_test_orig, y_pred_orig))

        # ── Log everything to MLflow ───────────────────────────────────────
        mlflow.log_params(
            {
                "target_column": CONFIG.target_column,
                "target_transform": "log1p",
                "test_size": CONFIG.test_size,
                "random_state": CONFIG.random_state,
                "skewness_threshold": CONFIG.skewness_threshold,
                "iqr_factor": CONFIG.iqr_factor,
                "n_skewed_features": len(skewed_cols),
                "n_non_skewed_features": len(non_skewed_cols),
                "n_categorical_features": len(categorical_cols),
                "skewed_features": str(skewed_cols),
                "categorical_features": str(categorical_cols),
                "train_rows": len(X_train),
                "test_rows": len(X_test),
            }
        )
        mlflow.log_metrics(
            {
                "test_rmse_log_scale": rmse_log,
                "test_r2_score": r2,
                "test_rmse_original_scale": rmse_orig,
                "test_mae_original_scale": mae_orig,
            }
        )

        logger.info(
            "train_model_step: evaluation  "
            "RMSE(log)=%.4f  R²=%.4f  RMSE($)=%.2f  MAE($)=%.2f",
            rmse_log,
            r2,
            rmse_orig,
            mae_orig,
        )

    metrics: Dict[str, float] = {
        "rmse_log_scale": rmse_log,
        "r2_score": r2,
        "rmse_original_scale": rmse_orig,
        "mae_original_scale": mae_orig,
    }
    return model_pipeline, metrics


# ═══════════════════════════════════════════════════════════════════════════
# ZenML Pipeline
# ═══════════════════════════════════════════════════════════════════════════


@pipeline(name="house_price_prediction_pipeline")
def house_price_pipeline(file_path: str) -> None:
    """
    End-to-end House Price Prediction pipeline.

    Wires the three steps together.  ZenML handles:
    * Passing DataFrame artifacts between steps (no manual serialisation).
    * Caching — a step is only re-executed when its inputs or code change.
    * Lineage tracking — every artifact is version-stamped and queryable.

    Parameters
    ----------
    file_path : str
        Path to the raw dataset file (``data/train.csv`` or
        ``data/train.zip``).  Passed directly into ``ingest_data_step``.
    """
    raw_df = ingest_data_step(file_path=file_path)
    clean_df = clean_data_step(raw_df=raw_df)
    train_model_step(clean_df=clean_df)


# ═══════════════════════════════════════════════════════════════════════════
# Entrypoint
# ═══════════════════════════════════════════════════════════════════════════


def run_pipeline(
    data_path: str,
    log_level: str = "INFO",
) -> None:
    """
    Configure logging and execute the ZenML pipeline programmatically.

    Parameters
    ----------
    data_path : str
        Path to the dataset file passed to ``ingest_data_step``.
    log_level : str
        Python logging level for this process (``DEBUG``, ``INFO``, etc.).
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("=" * 60)
    logger.info("House Price Prediction Pipeline")
    logger.info("  data_path    : %s", data_path)
    logger.info("  mlflow_uri   : %s", CONFIG.mlflow_tracking_uri)
    logger.info("  target       : %s", CONFIG.target_column)
    logger.info("  test_size    : %.0f%%", CONFIG.test_size * 100)
    logger.info("  random_state : %d", CONFIG.random_state)
    logger.info("=" * 60)

    house_price_pipeline(file_path=data_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the ZenML House Price Prediction pipeline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data-path",
        type=str,
        required=True,
        help="Path to the raw dataset (.csv or .zip).",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    args = parser.parse_args()
    run_pipeline(data_path=args.data_path, log_level=args.log_level)
