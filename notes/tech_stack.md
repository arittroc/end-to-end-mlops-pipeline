# Technology Stack

A deliberate breakdown of every technology in this project, why it was chosen, and what problem it solves. Each decision has a specific justification — nothing was included because it was trendy.

---

## Runtime & Language

### Python 3.10
**Role:** Application runtime for the entire stack.

**Why 3.10 specifically:**
Python 3.10 introduced structural pattern matching and union types (`X | Y`) and represents the sweet spot of stability and ecosystem support. It is the oldest version with first-class support across ZenML 0.67, MLflow 2.13, and FastAPI 0.111. Python 3.12 was explicitly avoided because ZenML's dependency tree has not fully validated against it at the pinned versions used here.

The virtual environment is created with `--copies` (not symlinks) and `--require-virtualenv` to guarantee strict isolation from the system Python — critical on a server that hosts other live applications.

---

## MLOps Orchestration

### ZenML 0.67
**Role:** Pipeline orchestration, artifact versioning, step caching.

**Why ZenML:**
ZenML treats each pipeline step as a first-class, independently versioned, re-runnable unit. When only the cleaning logic changes, the ingestion step's cached output is reused — the raw data is not re-read from disk. This is the key operational advantage over a plain Python script.

ZenML also enforces a clean **separation of orchestration from business logic**: the `@step` decorator adds ZenML's tracking and caching behaviour without polluting the underlying functions with framework-specific code. The data ingestion, cleaning, and training logic all work as pure Python functions when called outside ZenML.

The stack-based architecture allows swapping the orchestrator (local → Airflow → Kubeflow) without changing application code.

**What it replaced:** A Jupyter notebook with manual execution ordering and no artifact lineage.

---

## Experiment Tracking & Model Registry

### MLflow 2.13
**Role:** Experiment tracking, metric logging, model serialisation, model registry.

**Why MLflow:**
MLflow's `sklearn.autolog()` captures every sklearn model's coefficients, intercept, training score, and a serialised model artefact automatically — zero boilerplate. The UI at `http://localhost:5055` provides a complete audit trail of every training run.

The model registry (`models:/HousePriceModel/Production`) provides a clean promotion workflow: a model is trained, evaluated, and only promoted to `Production` by a human decision or an automated quality gate. The API's three-tier model resolution strategy means:
1. A freshly trained model is served immediately (Strategy 3: latest run).
2. A reviewed model is served once registered (Strategy 2: latest version).
3. A production-blessed model is served from the `Production` stage (Strategy 1).

**Custom port 5055:** The default MLflow port (5000) is in use by other live services on the server. 5055 was chosen explicitly to avoid clashes.

---

## Machine Learning

### Scikit-Learn 1.4
**Role:** Preprocessing pipeline construction and model training.

**Why Scikit-Learn:**
The `sklearn.pipeline.Pipeline` object is the right abstraction for this project because it guarantees that preprocessing parameters (scaler means, OHE vocabulary) are **fitted on training data only** and **applied consistently to inference data**. This eliminates an entire class of data leakage bugs that plague notebook-style ML.

The `ColumnTransformer` applies three distinct transformation rules simultaneously:
- **Skewed numericals** (abs skewness > 0.75): `log1p → StandardScaler`. The log1p compresses the right tail before the scaler operates, improving the OLS assumptions.
- **Non-skewed numericals**: `StandardScaler` only.
- **Categoricals**: `OneHotEncoder(handle_unknown="ignore")` — unseen categories at inference time produce an all-zero vector rather than raising exceptions.

`remainder="drop"` is intentional: any column not declared in the transformer is silently excluded, preventing new columns from accidentally leaking into the model after the pipeline was designed.

**Why LinearRegression as the base model:**
LinearRegression is the correct starting point for an MLOps demonstration because:
1. It is fully explainable (coefficients are interpretable).
2. Its training is deterministic and fast — no hyperparameter search needed for the first iteration.
3. It establishes a performance baseline that more complex models must beat to justify their cost.

### Pandas 2.2 / NumPy 1.26 / SciPy 1.x
**Role:** Data manipulation, numerical operations, statistical functions.

SciPy is used specifically for `scipy.stats.zscore` in the Z-Score outlier detection strategy. Pandas 2.2's Copy-on-Write semantics align with the project's design principle that every transformation returns a **new DataFrame** — the input is never mutated.

---

## Database

### Neon.tech Serverless PostgreSQL
**Role:** MLflow backend store — persists all runs, metrics, parameters, and the model registry.

**Why Neon.tech:**
1. **Serverless:** Zero infrastructure to manage. No Postgres container to maintain, backup, or patch.
2. **Free tier:** Suitable for a personal MLOps project without operational cost.
3. **SSL by default:** All connections use `sslmode=require` — credentials cannot be sent in plaintext.
4. **Branching:** Neon supports database branching (like git for data), useful for future staging/production environment separation.

**What this replaced:** MLflow's default file-based backend (`./mlruns`), which does not support concurrent writes and cannot be accessed from inside a Docker container on the same host.

The connection string format:
```
postgresql+psycopg2://user:password@host:5432/dbname?sslmode=require
```

---

## API Layer

### FastAPI 0.111
**Role:** REST API framework serving model predictions.

**Why FastAPI:**
1. **Pydantic v2 integration:** Request validation, type coercion, and serialisation are handled automatically. The `HousePriceFeatures` schema with 30+ fields, aliases for Python-invalid column names (`1stFlrSF`), and field validators costs zero extra code.
2. **Async-native:** The `lifespan` context manager for startup/shutdown is a first-class FastAPI concept, not a workaround.
3. **Auto-generated OpenAPI docs:** `/docs` and `/redoc` are available immediately without additional tooling.
4. **Performance:** FastAPI benchmarks faster than Flask and Django REST Framework for I/O-bound workloads.

### Pydantic v2
**Role:** Input schema validation and serialisation.

The `HousePriceFeatures` model handles three challenges cleanly:
- **Type coercion:** `7.0` is automatically coerced to `int` for rating fields.
- **Field aliases:** `1stFlrSF` (invalid Python identifier) is aliased to `first_flr_sf` in Python but exposed as `1stFlrSF` in the JSON API via `by_alias=True`.
- **Selective serialisation:** `model_dump(exclude_none=True)` drops optional fields that were not provided, preventing NaN columns in the inference DataFrame.

### Uvicorn 0.30
**Role:** ASGI server running FastAPI in production.

`--workers 1` is deliberate: the sklearn Pipeline lives in process memory. Multiple workers would each load their own copy, multiplying RAM usage. Horizontal scaling is done at the **container** level (multiple Docker containers behind a load balancer), not the worker level.

---

## Infrastructure & DevOps

### Docker + Docker Compose
**Role:** Application containerisation and service orchestration.

**Design decisions:**
- `python:3.10-slim` base — minimal Debian image. Full `python:3.10` adds ~800 MB with no benefit for this use case.
- Non-root user (`appuser`, UID 1001) — running as root inside a container violates the principle of least privilege.
- Dependency layer before source layer — Docker's layer cache means a code-only change does not re-trigger a 5-minute pip install.
- `fastapi_model_cache` named volume at `/app/models` — MLflow artifact downloads survive container restarts. `MLFLOW_TMP_DIR=/app/models` redirects MLflow's download cache to this persistent path.
- `extra_hosts: - "host.docker.internal:host-gateway"` — on Linux Docker, this is required to resolve `host.docker.internal` to the Docker host. Without it, the container cannot reach the MLflow server running on the host OS at port 5055.
- `restart: unless-stopped` — the container restarts after crashes and server reboots, but respects a deliberate `docker compose stop`.
- `start_period: 90s` on healthcheck — prevents false-positive unhealthy status during the model loading phase.

### rsync + SSH (`remote_deploy.sh`)
**Role:** One-command remote deployment.

`rsync` was chosen over `scp` because it is incremental — only changed files are transferred on subsequent deploys. The `--delete` flag keeps the remote directory in sync with the local source.

**Key exclusions from rsync:**
- `house_price_env/` — the venv would be ~2 GB and is rebuilt inside the container anyway.
- `.env` — credentials are never synced; they must be created manually on the server once.
- `mlflow-artifacts/` — local MLflow cache; the container fetches from the server.

The SSH heredoc pattern (`bash << 'REMOTE_EOF'`) with a single-quoted delimiter ensures local shell variables are not expanded before transmission — all `$HOME`, `$VAR` references resolve on the remote machine.

---

## Object-Oriented Design Patterns

### Factory Pattern (`data_ingestion.py`)
**Problem:** The pipeline must handle `.csv` and `.zip` files without the caller knowing which format is being loaded.

**Solution:** `DataIngestorFactory` maintains a class-level registry of extension → class mappings. `get_ingestor(file_path)` inspects the extension at runtime and returns the correct concrete `DataIngestor`. New formats are added via `register_ingestor()` with zero changes to existing code (Open/Closed Principle).

### Strategy Pattern (`data_cleaning.py`)
**Problem:** Missing value imputation and outlier detection are not one-size-fits-all. The right strategy depends on the data distribution.

**Solution:** Two independent abstract hierarchies (`MissingValueStrategy`, `OutlierDetectionStrategy`) that are injected into the `DataCleaner` context class. Strategies are hot-swappable at runtime via setter methods — no rebuild required to switch from Z-Score to IQR outlier detection.

---

## Version Control

### Git + GitHub
**Role:** Source of truth for all project code, documentation, and configuration.

`.env` files and Python virtual environments are excluded via `.gitignore`. The `.env.example` template is committed so collaborators know exactly which variables to set without exposing real credentials.

---

*See [plans.md](plans.md) for what gets added to this stack next.*
