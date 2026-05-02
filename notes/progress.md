# Project Progress Log

Chronological record of everything built, configured, and deployed. Each entry records what was completed, the key decisions made, and any blockers resolved.

---

## 2026-05-02 — Project Inception & Full Build

**Status:** Complete ✅  
**Duration:** Single session  
**Engineer:** carittro@gmail.com

---

### 0. Problem Definition & Architecture Design

**Decided:**
- Use the Ames Housing dataset as the regression target (79 features, ~1,460 rows)
- Target variable: `SalePrice` with `log1p` transform to handle right skew
- Build a full MLOps pipeline, not just a notebook
- Host entirely on home server (`192.168.29.100`) — laptop contributes zero compute
- Use Neon.tech serverless PostgreSQL as the MLflow backend (no local Postgres to manage)

**Key constraint identified:** The server already runs live applications (K3s cluster with Traefik, Grafana). Every new service must use a non-conflicting port. Selected ports: MLflow UI on `5055`, FastAPI on `8085`.

---

### 1. Environment & Tooling Setup

**Files created:**
- `setup_env.sh` — creates `house_price_env` (Python 3.10, `--copies`, `--require-virtualenv`)
- `requirements.txt` — pins ZenML 0.67, MLflow 2.13, scikit-learn 1.4, pandas 2.2, FastAPI 0.111
- `.env.example` — credential template for Neon.tech + MLflow config
- `start_mlflow.sh` — launches MLflow on port 5055 with PostgreSQL backend
- `.gitignore` — excludes venv, `.env`, `__pycache__`, ZenML metadata, MLflow artifacts

**Key decisions:**
- `--copies` in venv creation: Python binary is copied, not symlinked. System Python upgrades don't break the isolated environment.
- `--require-virtualenv` on pip: hard-fails if called outside the venv. Prevents accidental system-level installs on a shared server.
- `MLFLOW_PORT=5055` in `.env.example`: documented the non-default port choice in the template so it's impossible to miss.
- `sslmode=require` in the PostgreSQL URI: mandatory for Neon.tech; all connections are TLS-encrypted.

---

### 2. Core Data Modules (OOP Design Patterns)

**Files created:**
- `src/__init__.py`
- `src/data_ingestion.py`
- `src/data_cleaning.py`

#### data_ingestion.py — Factory Pattern

**Architecture:**
```
DataIngestor (ABC)
├── CSVDataIngestor
└── ZipDataIngestor
DataIngestorFactory  ← registry-based routing
```

**Implementation highlights:**
- `_registry: ClassVar[dict[str, type[DataIngestor]]]` — class-level dict; adding Parquet support means one `register_ingestor()` call, zero existing code changes (OCP)
- `ZipDataIngestor` streams directly from the archive into `pd.read_csv` — no temp files written to disk
- `csv_index` parameter handles archives with multiple CSVs gracefully
- All methods raise `FileNotFoundError` or `ValueError` with explicit messages; no silent failures

#### data_cleaning.py — Strategy Pattern

**Architecture:**
```
MissingValueStrategy (ABC)
├── MeanImputation
├── MedianImputation
└── DropMissingValues

OutlierDetectionStrategy (ABC)
├── ZScoreOutlierDetection  (assumes Gaussian; configurable threshold)
└── IQROutlierDetection     (robust; configurable factor)

DataCleaner (context class)
```

**Implementation highlights:**
- `detect()` returns a boolean mask DataFrame — callers can inspect which rows are flagged before committing to removal. `remove()` is on the abstract base class, not duplicated in every subclass.
- NaN positions are explicitly cleared from the outlier mask in both Z-Score and IQR methods — NaN is not an outlier.
- `DataCleaner` validates strategy types at construction time with `isinstance` checks — type errors surface at object creation, not during a run at 2am.
- Strategies are hot-swappable via `set_missing_value_strategy()` and `set_outlier_strategy()` — the context object survives a strategy swap.

---

### 3. ZenML Pipeline

**File created:** `src/pipeline.py`

**Architecture:**
```
@step  ingest_data_step     DataIngestorFactory.get_ingestor() → pd.DataFrame
@step  clean_data_step      DataCleaner → pd.DataFrame
@step  train_model_step     ColumnTransformer + LinearRegression → (Pipeline, metrics)

@pipeline  house_price_pipeline
```

**Implementation highlights:**
- `PipelineConfig` frozen dataclass: all tunable parameters (test size, IQR factor, skewness threshold, random state) in one place. `CONFIG = PipelineConfig()` is the singleton used by all steps.
- `_split_by_skewness()` separates numeric columns by their absolute skewness vs. `CONFIG.skewness_threshold` (0.75). Skewed columns receive `log1p → StandardScaler`; non-skewed receive `StandardScaler` only.
- `remainder="drop"` in ColumnTransformer: any column not explicitly declared is excluded from the model matrix. Prevents silent data leakage if new columns are added to the dataset.
- `mlflow.sklearn.autolog(log_models=True)` inside the ZenML step captures coefficients, training score, and a serialised model artefact automatically.
- Four metrics logged to the hold-out test set: `test_rmse_log_scale`, `test_r2_score`, `test_rmse_original_scale`, `test_mae_original_scale`. The original-scale metrics (in $) are the business-interpretable ones.
- `mlflow.start_run(nested=True)`: nests the run inside ZenML's parent run, creating a clean hierarchy in the MLflow UI.
- `MLFlowExperimentTrackerSettings` injected via `@step(settings=...)`: the ZenML experiment tracker manages the MLflow run context.

**ZenML stack setup required (one-time):**
```bash
zenml experiment-tracker register house_price_mlflow_tracker \
    --flavor=mlflow --tracking_uri="http://localhost:5055"
zenml stack set house_price_stack
```

---

### 4. FastAPI Prediction Service

**File created:** `src/api.py`

**Architecture:**
```
ModelRegistry (singleton class)
├── load()        — three-tier MLflow model resolution
├── predict()     — sklearn Pipeline → np.expm1() → USD price
├── is_ready()    — liveness guard
└── info()        — metadata for /model-info

HousePriceFeatures (Pydantic v2 BaseModel)  — 30+ fields, aliased, validated
PredictionResponse / HealthResponse / ModelInfoResponse / ErrorDetail

lifespan() → ModelRegistry.load() on startup

FastAPI app
├── CORSMiddleware (allow_origins=["*"])
├── @app.exception_handler(Exception)  — catch-all HTTP 500 handler
└── APIRouter /api/v1
    ├── GET  /health
    ├── GET  /model-info
    └── POST /predict
```

**Three-tier model resolution strategy (the critical design):**
1. `models:/HousePriceModel/Production` — steady-state after manual/automated promotion
2. `models:/HousePriceModel/{latest_version}` — registered but not yet promoted
3. `runs:/<run_id>/model` — first-ever run; no registry entry yet

Strategy 3 ensures the API is servable immediately after the first successful ZenML pipeline run, before any MLflow Registry workflow has been set up.

**Key Pydantic decisions:**
- `1stFlrSF` / `2ndFlrSF` are Python-invalid identifiers. They are aliased to `first_flr_sf` / `second_flr_sf` with `Field(alias="1stFlrSF")`. `model_dump(by_alias=True)` restores the original column names the sklearn Pipeline expects.
- `exclude_none=True` in `to_dataframe()` drops optional fields that were not provided. This keeps the DataFrame free of NaN columns for absent optional fields.
- `@field_validator` coerces float ratings (`7.0 → 7`) and validates the 1–10 range.

**Exception handling layers:**
- Pydantic: `422 Unprocessable Entity` (automatic)
- Model not ready: `503 Service Unavailable`
- sklearn ValueError: `400 Bad Request`
- All other inference errors: `500 Internal Server Error`
- `@app.exception_handler(Exception)`: catch-all for anything that escapes

---

### 5. Docker & Remote Deployment

**Files created:**
- `Dockerfile`
- `docker-compose.yml`
- `remote_deploy.sh`
- `.dockerignore`

**Dockerfile highlights:**
- `python:3.10-slim` base — ~130 MB vs ~900 MB for the full image
- System packages: `curl` (healthcheck) + `libgomp1` (scikit-learn OpenMP)
- Non-root user `appuser` (UID 1001) — least privilege
- Dependency layer before source layer — code changes don't re-trigger pip install
- `EXPOSE 8085` — non-default port to avoid server conflicts

**docker-compose.yml highlights:**
- `extra_hosts: - "host.docker.internal:host-gateway"` — Linux Docker fix. Without this, `localhost:5055` inside the container resolves to the container itself, not the MLflow server on the host.
- `MLFLOW_TRACKING_URI: "http://host.docker.internal:5055"` overrides the `.env` value (which uses `localhost` — correct for the host process but wrong inside a container).
- `MLFLOW_TMP_DIR: "/app/models"` redirects MLflow's artifact download cache to the named volume. Second startup = instant model load from disk.
- `start_period: 90s` on healthcheck — prevents false-positive unhealthy state during the cold-start model load.
- `restart: unless-stopped` — survives server reboots; respects deliberate stops.
- `logging: max-size: 20m, max-file: 5` — prevents unbounded log growth on a long-running server.

**remote_deploy.sh highlights:**
- 5-step workflow: pre-flight → connectivity check → remote prep → rsync → SSH deploy
- `--dry-run` flag: preview rsync without transferring (safe to test)
- SSH heredoc with `'REMOTE_EOF'` (single-quoted): local shell does not expand variables; all `$HOME` references resolve on the remote machine
- `.env` guard: script hard-exits with instructions if `.env` doesn't exist on the server
- Post-deploy: prints live container status and last 20 log lines

---

## Metrics Achieved

| Metric | Value |
|--------|-------|
| Deployment target | `192.168.29.100:8085` |
| API health endpoint | `/api/v1/health` |
| MLflow UI | `http://192.168.29.100:5055` |
| Model type | `sklearn.Pipeline` (log1p + ColumnTransformer + LinearRegression) |
| Target transform | `log1p(SalePrice)` train / `expm1(prediction)` serve |
| Tracked metrics | RMSE (log scale), R², RMSE ($), MAE ($) |
| Container restart policy | `unless-stopped` |
| Model artifact persistence | Named Docker volume `fastapi_model_cache` |

---

*Next: [Phase 2 — Next.js Glassmorphism Frontend](plans.md#phase-2--frontend-next-priority)*
