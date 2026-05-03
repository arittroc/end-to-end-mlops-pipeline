"""
api.py
======
Production FastAPI application for serving the House Price Prediction model.

Architecture
------------
  ModelRegistry           — singleton that owns the loaded MLflow model,
                            its metadata, and all prediction logic.
  HousePriceFeatures      — Pydantic v2 input schema (Ames Housing feature set).
  PredictionResponse      — typed response schema.
  HealthResponse          — liveness / readiness schema.
  ModelInfoResponse       — exposes loaded model metadata.

  lifespan()              — FastAPI lifespan context: loads the model on startup,
                            releases resources on shutdown.
  /api/v1/health          — GET  liveness + model readiness check.
  /api/v1/model-info      — GET  loaded model URI, version, and experiment.
  /api/v1/predict         — POST accepts HousePriceFeatures, returns price in $.

Model resolution order (applied at startup)
--------------------------------------------
  1. Registered model at ``Production`` stage  → models:/ModelName/Production
  2. Registered model latest version           → models:/ModelName/latest
  3. Latest successful run in experiment       → runs:/<run_id>/model
     (covers the first run before any model is promoted in the Registry)

Startup command
---------------
::

    # With the venv active and MLflow server running on port 5055:
    uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from fastapi import APIRouter, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mlflow.tracking import MlflowClient
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, ConfigDict, Field, field_validator

logger: logging.Logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────

MLFLOW_TRACKING_URI: str = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5055")
MLFLOW_MODEL_NAME: str = os.getenv("MLFLOW_MODEL_NAME", "HousePriceModel")
MLFLOW_EXPERIMENT_NAME: str = os.getenv(
    "MLFLOW_EXPERIMENT_NAME", "house_price_prediction"
)
APP_VERSION: str = "1.0.0"


# ═══════════════════════════════════════════════════════════════════════════
# Model Registry — singleton responsible for model lifecycle
# ═══════════════════════════════════════════════════════════════════════════


class ModelRegistry:
    """
    Singleton that owns the MLflow model lifecycle for this process.

    Attributes
    ----------
    _model : Any | None
        The loaded sklearn Pipeline; ``None`` until ``load()`` succeeds.
    _model_uri : str | None
        The resolved MLflow model URI (e.g. ``models:/HousePriceModel/Production``).
    _run_id : str | None
        MLflow run ID from which the model was loaded.
    _experiment_name : str | None
        MLflow experiment name associated with the run.
    _model_version : str | None
        Registered model version string, if the model is in the Registry.

    Notes
    -----
    The ``load()`` class-method implements a three-tier resolution strategy
    so the API is servable at every stage of the MLOps lifecycle:

    * **Stage 1** — Registered model at ``Production`` stage.  This is the
      expected steady-state for a deployed service.
    * **Stage 2** — Latest version of the registered model (any stage).
      Covers promoted-but-not-yet-Production models.
    * **Stage 3** — Latest successful run in the named experiment.  Allows
      the API to serve predictions immediately after the first ZenML pipeline
      run, before any model has been registered.
    """

    _model: Optional[Any] = None
    _model_uri: Optional[str] = None
    _run_id: Optional[str] = None
    _experiment_name: Optional[str] = None
    _model_version: Optional[str] = None

    @classmethod
    def load(cls) -> None:
        """
        Resolve and load the best available model from the MLflow server.

        Applies the three-tier resolution strategy documented on the class.
        Sets all private attributes on success.

        Raises
        ------
        RuntimeError
            If no model can be found via any of the three strategies.
        mlflow.exceptions.MlflowException
            If the MLflow server is unreachable or the URI is malformed.
        """
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        client: MlflowClient = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)

        uri: Optional[str] = None
        version: Optional[str] = None
        run_id: Optional[str] = None

        # ── Strategy 1: Registered model at Production stage ──────────────
        try:
            prod_versions = client.get_latest_versions(
                MLFLOW_MODEL_NAME, stages=["Production"]
            )
            if prod_versions:
                best = prod_versions[0]
                uri = f"models:/{MLFLOW_MODEL_NAME}/Production"
                version = best.version
                run_id = best.run_id
                logger.info(
                    "ModelRegistry: resolved via Production stage  "
                    "model=%s  version=%s  run_id=%s",
                    MLFLOW_MODEL_NAME,
                    version,
                    run_id,
                )
        except Exception as exc:
            logger.debug("ModelRegistry: Strategy 1 skipped — %s", exc)

        # ── Strategy 2: Latest registered model version (any stage) ───────
        if uri is None:
            try:
                all_versions = client.get_latest_versions(MLFLOW_MODEL_NAME)
                if all_versions:
                    best = max(all_versions, key=lambda v: int(v.version))
                    uri = f"models:/{MLFLOW_MODEL_NAME}/{best.version}"
                    version = best.version
                    run_id = best.run_id
                    logger.info(
                        "ModelRegistry: resolved via latest registered version  "
                        "model=%s  version=%s  run_id=%s",
                        MLFLOW_MODEL_NAME,
                        version,
                        run_id,
                    )
            except Exception as exc:
                logger.debug("ModelRegistry: Strategy 2 skipped — %s", exc)

        # ── Strategy 3: Latest successful run in the experiment ────────────
        if uri is None:
            try:
                experiment = client.get_experiment_by_name(MLFLOW_EXPERIMENT_NAME)
                if experiment is None:
                    raise RuntimeError(
                        f"MLflow experiment '{MLFLOW_EXPERIMENT_NAME}' not found."
                    )
                runs = client.search_runs(
                    experiment_ids=[experiment.experiment_id],
                    filter_string="status = 'FINISHED'",
                    order_by=["start_time DESC"],
                    max_results=1,
                )
                if not runs:
                    raise RuntimeError(
                        f"No finished runs found in experiment "
                        f"'{MLFLOW_EXPERIMENT_NAME}'."
                    )
                latest_run = runs[0]
                run_id = latest_run.info.run_id
                uri = f"runs:/{run_id}/model"
                logger.info(
                    "ModelRegistry: resolved via latest experiment run  "
                    "experiment=%s  run_id=%s",
                    MLFLOW_EXPERIMENT_NAME,
                    run_id,
                )
            except RuntimeError:
                raise
            except Exception as exc:
                logger.debug("ModelRegistry: Strategy 3 skipped — %s", exc)

        if uri is None:
            raise RuntimeError(
                "ModelRegistry.load: could not resolve a model URI via any "
                "strategy.  Ensure the ZenML pipeline has completed at least "
                f"one successful run against MLflow at {MLFLOW_TRACKING_URI}."
            )

        logger.info("ModelRegistry: loading model from URI '%s' ...", uri)
        cls._model = mlflow.sklearn.load_model(uri)
        cls._model_uri = uri
        cls._run_id = run_id
        cls._model_version = version
        cls._experiment_name = MLFLOW_EXPERIMENT_NAME
        logger.info("ModelRegistry: model loaded successfully.")

    @classmethod
    def predict(cls, df: pd.DataFrame) -> np.ndarray:
        """
        Run inference on a feature DataFrame and return prices in original $.

        The model was trained on ``log1p(SalePrice)``, so this method applies
        ``np.expm1`` to the raw predictions before returning them.

        Parameters
        ----------
        df : pd.DataFrame
            One or more rows of house features matching the training schema.
            Columns not recognised by the pipeline's ColumnTransformer are
            silently ignored (``remainder="drop"`` in the transformer).

        Returns
        -------
        np.ndarray
            Predicted sale prices in original USD scale, shape ``(n_rows,)``.

        Raises
        ------
        RuntimeError
            If ``load()`` has not been called or failed.
        """
        if cls._model is None:
            raise RuntimeError(
                "ModelRegistry: model is not loaded. "
                "The startup lifespan hook may have failed."
            )
        log_predictions: np.ndarray = cls._model.predict(df)
        return np.expm1(log_predictions)

    @classmethod
    def is_ready(cls) -> bool:
        """Return ``True`` if a model has been successfully loaded."""
        return cls._model is not None

    @classmethod
    def info(cls) -> Dict[str, Optional[str]]:
        """Return a dict of loaded model metadata for the /model-info endpoint."""
        return {
            "model_uri": cls._model_uri,
            "run_id": cls._run_id,
            "model_version": cls._model_version,
            "experiment_name": cls._experiment_name,
            "tracking_uri": MLFLOW_TRACKING_URI,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════════════════════════════════════


class HousePriceFeatures(BaseModel):
    """
    Input payload for the /predict endpoint.

    All features correspond to columns in the Ames Housing dataset that the
    ZenML pipeline was trained on.  Fields with Python-invalid names (e.g.
    ``1stFlrSF``) are exposed through Pydantic aliases — send the original
    column name in the JSON body and it maps to the correct field.

    Only ``GrLivArea`` and ``OverallQual`` are required; every other field is
    optional.  The pipeline's ColumnTransformer was trained with
    ``remainder="drop"``, so missing optional columns are simply excluded from
    the feature matrix and the model falls back to learned defaults for those
    dimensions via the OHE / scaler behaviour.

    Notes
    -----
    Pass the JSON key exactly as the alias (e.g. ``"1stFlrSF": 800``), not
    the Python field name.  Set ``model_config.populate_by_name = True`` if
    you need to construct the model programmatically using Python field names.
    """

    model_config = ConfigDict(
        populate_by_name=True,   # allow both alias and Python name in code
        extra="allow",           # pass undeclared columns through to the model
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "GrLivArea": 1850,
                "OverallQual": 8,
                "Location": "Gurgaon",
                "YearBuilt": 2018,
                "TotalBsmtSF": 0,
            }
        },
    )

    # ── Required features ─────────────────────────────────────────────────
    GrLivArea: int = Field(
        ...,
        gt=0,
        description="Above-grade (ground) living area in square feet.",
        examples=[1850],
    )
    OverallQual: int = Field(
        ...,
        ge=1,
        le=10,
        description="Overall material and finish quality, rated 1 (very poor) to 10 (very excellent).",
        examples=[8],
    )
    Location: str = Field(
        ...,
        description="City market for Indian real estate pricing (Gurgaon, Bangalore, or Kolkata).",
        examples=["Gurgaon"],
    )

    # ── Numerical features (optional) ─────────────────────────────────────
    YearBuilt: Optional[int] = Field(
        None,
        ge=1800,
        le=2025,
        description="Original construction year.",
        examples=[2003],
    )
    YearRemodAdd: Optional[int] = Field(
        None,
        ge=1800,
        le=2025,
        description="Remodel date (same as YearBuilt if no remodelling).",
        examples=[2003],
    )
    LotArea: Optional[int] = Field(
        None,
        gt=0,
        description="Lot size in square feet.",
        examples=[8450],
    )
    LotFrontage: Optional[float] = Field(
        None,
        ge=0.0,
        description="Linear feet of street connected to the property.",
        examples=[65.0],
    )
    TotalBsmtSF: Optional[float] = Field(
        None,
        ge=0.0,
        description="Total square feet of basement area (0 if no basement).",
        examples=[856.0],
    )
    BsmtFinSF1: Optional[float] = Field(
        None,
        ge=0.0,
        description="Type 1 finished square feet of basement.",
        examples=[706.0],
    )
    BsmtUnfSF: Optional[float] = Field(
        None,
        ge=0.0,
        description="Unfinished square feet of basement area.",
        examples=[150.0],
    )
    first_flr_sf: Optional[float] = Field(
        None,
        ge=0.0,
        alias="1stFlrSF",
        description="First floor area in square feet.",
        examples=[856.0],
    )
    second_flr_sf: Optional[float] = Field(
        None,
        ge=0.0,
        alias="2ndFlrSF",
        description="Second floor area in square feet (0 if single storey).",
        examples=[854.0],
    )
    GarageArea: Optional[float] = Field(
        None,
        ge=0.0,
        description="Size of garage in square feet.",
        examples=[548.0],
    )
    GarageCars: Optional[int] = Field(
        None,
        ge=0,
        description="Size of garage in car capacity.",
        examples=[2],
    )
    MasVnrArea: Optional[float] = Field(
        None,
        ge=0.0,
        description="Masonry veneer area in square feet.",
        examples=[196.0],
    )
    WoodDeckSF: Optional[float] = Field(
        None,
        ge=0.0,
        description="Wood deck area in square feet.",
        examples=[0.0],
    )
    OpenPorchSF: Optional[float] = Field(
        None,
        ge=0.0,
        description="Open porch area in square feet.",
        examples=[61.0],
    )
    EnclosedPorch: Optional[float] = Field(
        None,
        ge=0.0,
        description="Enclosed porch area in square feet.",
        examples=[0.0],
    )
    BedroomAbvGr: Optional[int] = Field(
        None,
        ge=0,
        description="Bedrooms above grade (does not include basement bedrooms).",
        examples=[3],
    )
    TotRmsAbvGrd: Optional[int] = Field(
        None,
        ge=0,
        description="Total rooms above grade (does not include bathrooms).",
        examples=[8],
    )
    Fireplaces: Optional[int] = Field(
        None,
        ge=0,
        description="Number of fireplaces.",
        examples=[0],
    )
    FullBath: Optional[int] = Field(
        None,
        ge=0,
        description="Full bathrooms above grade.",
        examples=[2],
    )
    HalfBath: Optional[int] = Field(
        None,
        ge=0,
        description="Half bathrooms above grade.",
        examples=[1],
    )
    OverallCond: Optional[int] = Field(
        None,
        ge=1,
        le=10,
        description="Overall condition rating, 1 (very poor) to 10 (very excellent).",
        examples=[5],
    )
    PoolArea: Optional[float] = Field(
        None,
        ge=0.0,
        description="Pool area in square feet.",
        examples=[0.0],
    )

    # ── Categorical features (optional) ───────────────────────────────────
    MSZoning: Optional[str] = Field(
        None,
        description="General zoning classification (RL, RM, C, FV, RH).",
        examples=["RL"],
    )
    Neighborhood: Optional[str] = Field(
        None,
        description="Physical locations within Ames city limits.",
        examples=["CollgCr"],
    )
    BldgType: Optional[str] = Field(
        None,
        description="Type of dwelling (1Fam, 2FmCon, Duplx, TwnhsE, TwnhsI).",
        examples=["1Fam"],
    )
    HouseStyle: Optional[str] = Field(
        None,
        description="Style of dwelling (1Story, 2Story, 1.5Fin, etc.).",
        examples=["2Story"],
    )
    RoofStyle: Optional[str] = Field(
        None,
        description="Type of roof (Flat, Gable, Hip, Mansard, Shed).",
        examples=["Gable"],
    )
    ExterQual: Optional[str] = Field(
        None,
        description="Exterior material quality (Ex/Gd/TA/Fa/Po).",
        examples=["Gd"],
    )
    ExterCond: Optional[str] = Field(
        None,
        description="Present condition of exterior material (Ex/Gd/TA/Fa/Po).",
        examples=["TA"],
    )
    Foundation: Optional[str] = Field(
        None,
        description="Type of foundation (BrkTil, CBlock, PConc, Slab, Stone, Wood).",
        examples=["PConc"],
    )
    BsmtQual: Optional[str] = Field(
        None,
        description="Height of the basement (Ex/Gd/TA/Fa/Po/NA).",
        examples=["Gd"],
    )
    HeatingQC: Optional[str] = Field(
        None,
        description="Heating quality and condition (Ex/Gd/TA/Fa/Po).",
        examples=["Ex"],
    )
    CentralAir: Optional[str] = Field(
        None,
        description="Central air conditioning (Y/N).",
        examples=["Y"],
    )
    KitchenQual: Optional[str] = Field(
        None,
        description="Kitchen quality (Ex/Gd/TA/Fa/Po).",
        examples=["Gd"],
    )
    GarageType: Optional[str] = Field(
        None,
        description="Garage location (Attchd, Detchd, BuiltIn, CarPort, etc.).",
        examples=["Attchd"],
    )
    GarageFinish: Optional[str] = Field(
        None,
        description="Interior finish of the garage (Fin/RFn/Unf/NA).",
        examples=["RFn"],
    )
    SaleType: Optional[str] = Field(
        None,
        description="Type of sale (WD, New, COD, etc.).",
        examples=["WD"],
    )
    SaleCondition: Optional[str] = Field(
        None,
        description="Condition of sale (Normal, Abnorml, AdjLand, Alloca, Family, Partial).",
        examples=["Normal"],
    )
    LandContour: Optional[str] = Field(
        None,
        description="Flatness of the property (Lvl, Bnk, HLS, Low).",
        examples=["Lvl"],
    )
    LotShape: Optional[str] = Field(
        None,
        description="General shape of property (Reg/IR1/IR2/IR3).",
        examples=["Reg"],
    )
    PavedDrive: Optional[str] = Field(
        None,
        description="Paved driveway (Y/P/N).",
        examples=["Y"],
    )

    @field_validator("OverallQual", "OverallCond", mode="before")
    @classmethod
    def validate_rating_scale(cls, value: Any) -> int:
        """Coerce float ratings (e.g. 7.0) to int and reject out-of-range values."""
        try:
            int_val = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Rating must be an integer, got {value!r}") from exc
        if not (1 <= int_val <= 10):
            raise ValueError(f"Rating must be between 1 and 10, got {int_val}")
        return int_val

    @field_validator("Location", mode="before")
    @classmethod
    def validate_location(cls, value: Any) -> str:
        allowed = {"Gurgaon", "Bangalore", "Kolkata"}
        s = str(value).strip()
        if s not in allowed:
            raise ValueError(
                f"Location must be one of {sorted(allowed)}, got {value!r}"
            )
        return s

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert this payload to a single-row DataFrame with original column names.

        Fields that are ``None`` are excluded so the ColumnTransformer's
        ``remainder="drop"`` silently ignores them rather than producing NaN
        columns that could trip up downstream scalers.

        The ``by_alias=True`` flag ensures Python-invalid names like
        ``1stFlrSF`` are used as column headers, matching the training data.

        Returns
        -------
        pd.DataFrame
            One-row DataFrame ready to pass to ``ModelRegistry.predict()``.
        """
        raw: Dict[str, Any] = self.model_dump(
            by_alias=True,
            exclude_none=True,
        )
        # Include any extra fields sent by the caller (undeclared Ames columns)
        if self.model_extra:
            raw.update({k: v for k, v in self.model_extra.items() if v is not None})
        return pd.DataFrame([raw])


class PredictionResponse(BaseModel):
    """Successful prediction response."""

    predicted_price_usd: float = Field(
        ...,
        description="Predicted sale price in US dollars (expm1 of model output).",
        examples=[208500.0],
    )
    predicted_price_formatted: str = Field(
        ...,
        description="Human-readable price string.",
        examples=["$208,500.00"],
    )
    model_uri: Optional[str] = Field(
        None,
        description="MLflow URI of the model that produced this prediction.",
    )


class HealthResponse(BaseModel):
    """API liveness and model readiness status."""

    status: str = Field(..., examples=["ok"])
    model_ready: bool = Field(
        ...,
        description="True if the MLflow model loaded successfully at startup.",
    )
    version: str = Field(..., examples=[APP_VERSION])


class ModelInfoResponse(BaseModel):
    """Metadata about the currently loaded model."""

    model_uri: Optional[str]
    run_id: Optional[str]
    model_version: Optional[str]
    experiment_name: Optional[str]
    tracking_uri: Optional[str]


class ErrorDetail(BaseModel):
    """Structured error payload returned on 4xx / 5xx responses."""

    error: str
    detail: str
    status_code: int


# ═══════════════════════════════════════════════════════════════════════════
# FastAPI application
# ═══════════════════════════════════════════════════════════════════════════


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """
    FastAPI lifespan context manager.

    Startup
    -------
    Configures logging and attempts to load the production model from the
    MLflow tracking server at ``MLFLOW_TRACKING_URI``.  A startup failure
    does *not* crash the process — the API starts in degraded mode and
    returns HTTP 503 on predict requests until the model is available.

    Shutdown
    --------
    Placeholder for future cleanup (e.g., closing DB connections).
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info(
        "API startup: loading model from MLflow at %s ...", MLFLOW_TRACKING_URI
    )
    try:
        ModelRegistry.load()
        logger.info("API startup: model ready.")
    except Exception as exc:
        logger.error(
            "API startup: model load FAILED — %s. "
            "The /predict endpoint will return HTTP 503 until the model is available.",
            exc,
        )
    yield
    logger.info("API shutdown: releasing resources.")


app: FastAPI = FastAPI(
    title="House Price Prediction API",
    description=(
        "Serves predictions from a ZenML + MLflow trained LinearRegression pipeline "
        "built on the Ames Housing dataset.  The model is loaded from the MLflow "
        f"tracking server at {MLFLOW_TRACKING_URI} on startup."
    ),
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ───────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Prometheus metrics (/metrics endpoint) ─────────────────────────────────
Instrumentator().instrument(app).expose(app)


# ── Global exception handler ───────────────────────────────────────────────

@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Catch-all for any exception that escapes the route handlers."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorDetail(
            error="InternalServerError",
            detail="An unexpected error occurred. Check server logs for details.",
            status_code=500,
        ).model_dump(),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Router — /api/v1
# ═══════════════════════════════════════════════════════════════════════════

router: APIRouter = APIRouter(prefix="/api/v1", tags=["predictions"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness and readiness check",
    status_code=status.HTTP_200_OK,
)
async def health_check() -> HealthResponse:
    """
    Returns API liveness status and whether the ML model is loaded.

    A ``model_ready: false`` response means the startup model load failed.
    POST requests to ``/predict`` will return HTTP 503 in this state.
    """
    return HealthResponse(
        status="ok",
        model_ready=ModelRegistry.is_ready(),
        version=APP_VERSION,
    )


@router.get(
    "/model-info",
    response_model=ModelInfoResponse,
    summary="Metadata of the currently loaded model",
    status_code=status.HTTP_200_OK,
)
async def model_info() -> ModelInfoResponse:
    """
    Returns MLflow metadata for the model currently serving predictions.

    Includes the resolved model URI (which encodes the resolution strategy
    that succeeded at startup), the MLflow run ID, and the registered model
    version if applicable.
    """
    if not ModelRegistry.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model is not loaded. Check startup logs.",
        )
    return ModelInfoResponse(**ModelRegistry.info())


@router.post(
    "/predict",
    response_model=PredictionResponse,
    summary="Predict house sale price",
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorDetail, "description": "Invalid input features."},
        503: {"model": ErrorDetail, "description": "Model not loaded."},
        500: {"model": ErrorDetail, "description": "Inference error."},
    },
)
async def predict(payload: HousePriceFeatures) -> PredictionResponse:
    """
    Accept a house feature payload and return a predicted sale price in USD.

    **Flow**

    1. Pydantic validates and type-coerces the JSON body.
    2. ``HousePriceFeatures.to_dataframe()`` converts the payload to a
       single-row DataFrame using original column names (via aliases).
    3. ``ModelRegistry.predict()`` runs the sklearn Pipeline and applies
       ``np.expm1`` to reverse the log1p target transform.
    4. The predicted USD price is returned with a formatted string.

    **Error handling**

    - ``422 Unprocessable Entity`` — Pydantic validation failure (auto-raised
      by FastAPI before this handler is reached).
    - ``400 Bad Request`` — payload converts to a valid DataFrame but the
      model rejects it (e.g. all features are None after alias resolution).
    - ``503 Service Unavailable`` — model failed to load at startup.
    - ``500 Internal Server Error`` — unexpected inference failure.
    """
    # ── Guard: model readiness ─────────────────────────────────────────────
    if not ModelRegistry.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The prediction model is not available. "
                "The MLflow server may be unreachable or startup failed. "
                f"Confirm the server is running at {MLFLOW_TRACKING_URI}."
            ),
        )

    # ── Build feature DataFrame ────────────────────────────────────────────
    try:
        feature_df: pd.DataFrame = payload.to_dataframe()
    except Exception as exc:
        logger.warning("predict: failed to build feature DataFrame — %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not construct feature DataFrame from payload: {exc}",
        ) from exc

    # ── Validate the DataFrame is non-trivial ─────────────────────────────
    if feature_df.empty or feature_df.shape[1] == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Payload produced an empty DataFrame. "
                "Provide at least GrLivArea and OverallQual."
            ),
        )

    logger.info(
        "predict: running inference  shape=%s  columns=%s",
        feature_df.shape,
        feature_df.columns.tolist(),
    )

    # ── Inference ─────────────────────────────────────────────────────────
    try:
        predictions: np.ndarray = ModelRegistry.predict(feature_df)
    except ValueError as exc:
        # sklearn raises ValueError for shape / dtype mismatches.
        logger.warning("predict: sklearn ValueError — %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model rejected the input features: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("predict: unexpected inference error — %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference failed unexpectedly: {exc}",
        ) from exc

    # ── Format and return ──────────────────────────────────────────────────
    predicted_price: float = float(predictions[0])

    logger.info("predict: predicted_price_usd=%.2f", predicted_price)

    return PredictionResponse(
        predicted_price_usd=round(predicted_price, 2),
        predicted_price_formatted=f"${predicted_price:,.2f}",
        model_uri=ModelRegistry._model_uri,
    )


app.include_router(router)
