# Today's Session Recap

**Date:** 2026-05-02  
**Engineer:** carittro@gmail.com  
**Duration:** Single extended session  
**Outcome:** Full end-to-end MLOps pipeline designed, built, and deployed to production in one session

---

## The Constraint That Shaped Everything

The defining challenge of this session was a hard infrastructure constraint:

> *"My local laptop handles absolutely zero compute load. Every build, run, and process must execute on the remote home server at 192.168.29.100."*

This is not a hypothetical concern — the server already runs a live K3s cluster with Traefik, Grafana, and other production services. This meant:

1. **No local Python execution** for training or serving — the venv setup exists on the laptop only long enough to run ZenML pipeline commands that execute on the server.
2. **No local Docker builds** — `remote_deploy.sh` transfers source code and triggers `docker compose up --build` on the server over SSH.
3. **No local Postgres** — Neon.tech serverless PostgreSQL was chosen specifically to eliminate any database infrastructure from both the laptop and the server's process list.
4. **No port conflicts** — MLflow runs on `5055` (not `5000`), FastAPI runs on `8085` (not `8000`), because those defaults are already in use by other live services.

Every architectural decision in this session flows from this constraint.

---

## What Was Built (Chronological)

### Block 1: Infrastructure Foundation

**Goal:** Establish a reproducible, isolated environment and a persistent experiment tracking backend.

**`setup_env.sh`** creates a Python 3.10 virtual environment named `house_price_env` with two deliberate safety flags:
- `--copies`: the Python binary is physically copied rather than symlinked, so system Python upgrades don't silently break the environment
- `--require-virtualenv` on pip: hard-fails outside the venv, preventing accidental system-level package installs on a shared server

**`start_mlflow.sh`** launches the MLflow tracking server with:
- `--port 5055`: avoids the default 5000 (in use by other services)
- `--backend-store-uri postgresql+psycopg2://...?sslmode=require`: writes all run data to Neon.tech's serverless PostgreSQL over an encrypted connection
- `--serve-artifacts`: the MLflow server acts as a proxy for artifact access

This means from the very first training run, every metric, parameter, and model is durably stored in a cloud database — not in a local `./mlruns` folder that would be wiped by a Docker volume reset.

---

### Block 2: OOP Data Modules

**Goal:** Build data handling code that is testable, extensible, and completely decoupled from the training logic.

#### Factory Pattern — `src/data_ingestion.py`

The factory solves a concrete problem: the training pipeline should not contain `if file.endswith(".csv")` branches. Format-specific logic belongs in dedicated classes.

**Class hierarchy:**
```
DataIngestor (ABC)
  ingest(file_path: str) -> pd.DataFrame  ← the only contract

CSVDataIngestor(DataIngestor)
  ingest()  →  pd.read_csv(file_path, **kwargs)

ZipDataIngestor(DataIngestor)
  ingest()  →  opens archive, finds CSVs, streams first into pd.read_csv
              (no temp files written; csv_index param for multi-CSV archives)

DataIngestorFactory
  _registry = {".csv": CSVDataIngestor, ".zip": ZipDataIngestor}
  get_ingestor(file_path)  →  inspects extension → returns concrete instance
  register_ingestor(ext, cls)  →  adds new formats without touching existing code
```

The `_registry` dict is class-level and open for extension. To add Parquet support tomorrow: `DataIngestorFactory.register_ingestor(".parquet", ParquetDataIngestor)`. Nothing else changes.

#### Strategy Pattern — `src/data_cleaning.py`

Two independent strategy hierarchies handle two distinct problems:

**Missing value strategies:**
- `MeanImputation`: fills with column mean — for symmetric distributions
- `MedianImputation`: fills with column median — **the one actually used**, because house price features (LotArea, GrLivArea) are right-skewed; the median is robust to the same outliers we're about to remove
- `DropMissingValues`: drops rows; supports `subset` and `thresh` parameters

**Outlier detection strategies:**
- `ZScoreOutlierDetection`: flags |z| > threshold. Assumes Gaussian; fast. Not used in the final pipeline but available.
- `IQROutlierDetection`: flags outside `[Q1 − 1.5·IQR, Q3 + 1.5·IQR]`. Robust; skew-safe. **The one used** for GrLivArea and SalePrice.

The `detect()` method returns a **boolean mask DataFrame**, not a cleaned DataFrame. This is a deliberate design: callers can inspect which rows would be removed before committing. The `remove()` convenience method on the abstract base class then applies the mask. No code duplication across subclasses.

The `DataCleaner` context class composes one strategy from each hierarchy. Strategies are hot-swappable at runtime via setter methods — no rebuild required to experiment with different cleaning configurations.

---

### Block 3: ZenML Pipeline — `src/pipeline.py`

**Goal:** Orchestrate the OOP modules into a tracked, versioned, cacheable pipeline.

**The three steps:**

`ingest_data_step` → `clean_data_step` → `train_model_step`

Each step is annotated with `Annotated[pd.DataFrame, "artifact_name"]` — ZenML stores every output as a named artefact. Rerunning the pipeline with the same input skips cached steps.

**The feature engineering logic inside `train_model_step`:**

The most important design here is that feature engineering and training are **deliberately fused into a single step**. Separating them would require passing the train/test split indices as artefacts, creating accidental complexity for zero isolation benefit — both stages need the same `X_train` reference.

The `ColumnTransformer` applies three transformation paths simultaneously:
1. Skewed numericals (abs skewness > 0.75): `log1p` via `FunctionTransformer`, then `StandardScaler`
2. Non-skewed numericals: `StandardScaler` only
3. Categoricals: `OneHotEncoder(handle_unknown="ignore", sparse_output=False)`

`remainder="drop"` is the safety net: any column that doesn't match a declared transformer rule is excluded from the model matrix. This prevents new columns from silently entering the model if the dataset changes.

**Target encoding:** `y = np.log1p(SalePrice)` before `train_test_split`. The log1p compresses the right tail of sale prices (which spans $34,900 to $755,000), making the residuals more homoscedastic and improving OLS. Predictions are inverse-transformed with `np.expm1()` in the API.

**MLflow integration:**
```python
mlflow.set_tracking_uri("http://localhost:5055")   # explicit; overrides env
mlflow.sklearn.autolog(log_models=True)             # auto-captures model + training score
mlflow.start_run(nested=True)                       # nests under ZenML's parent run
mlflow.log_metrics({...})                           # hold-out test set scores (autolog only does train)
```

Four metrics are logged: RMSE (log scale), R², RMSE ($), MAE ($). The dollar-scale metrics are the ones that matter to a business stakeholder.

---

### Block 4: FastAPI — `src/api.py`

**Goal:** Serve predictions from the MLflow-tracked model through a robust REST API.

**The `ModelRegistry` singleton** is the most important class in the API. It solves a real operational problem: the model might not be registered when the API first starts. The three-tier resolution strategy handles every stage of the MLOps lifecycle:

```
Strategy 1: models:/HousePriceModel/Production  ← steady-state production
Strategy 2: models:/HousePriceModel/{latest}    ← registered, not yet promoted
Strategy 3: runs:/<run_id>/model                ← first-ever run, no registry
```

Strategy 3 is the most important for day-one usability. Without it, the API would fail to start until a human manually registered and promoted the model in the MLflow UI.

**The `HousePriceFeatures` Pydantic model** handles a non-obvious problem: `1stFlrSF` and `2ndFlrSF` are valid column names in the Ames Housing dataset but invalid Python identifiers. The solution is Pydantic's `Field(alias="1stFlrSF")` with `populate_by_name=True`. When the payload is converted to a DataFrame:

```python
df = pd.DataFrame([self.model_dump(by_alias=True, exclude_none=True)])
```

`by_alias=True` restores the original column names the sklearn ColumnTransformer was trained on. `exclude_none=True` drops optional fields that were not provided, preventing NaN columns that would break scalers.

**Startup:** The `lifespan` context manager calls `ModelRegistry.load()` on startup. A failure does **not** crash the process — the API starts in degraded mode and returns `503` on predict requests. This is intentional: a brief MLflow server hiccup should not take down the prediction API.

---

### Block 5: Docker & Remote Deployment

**Goal:** The laptop sends code; the server does the work.

**The container networking problem (and the fix):**

Inside a Docker container on Linux, `localhost` resolves to the container, not the host. The MLflow server runs on the host OS at port 5055. The naive solution of passing `MLFLOW_TRACKING_URI=http://localhost:5055` from `.env` would silently fail — the container would try to connect to port 5055 of its own loopback interface.

The fix is two-part:
1. `extra_hosts: - "host.docker.internal:host-gateway"` — Docker injects a route to the host
2. `environment: MLFLOW_TRACKING_URI: "http://host.docker.internal:5055"` — overrides the `.env` value

This is the kind of bug that is easy to miss in development (where the API and MLflow might run on the same machine outside Docker) and only surfaces in production.

**`remote_deploy.sh`** uses a SSH heredoc with a single-quoted delimiter:
```bash
ssh user@host bash << 'REMOTE_EOF'
  # all $VARIABLES resolve on the remote machine
REMOTE_EOF
```

This is the correct pattern for sending a multi-command script to a remote machine. The alternative — `ssh user@host "command1 && command2 && command3"` — rapidly becomes unmaintainable and produces quoting bugs with nested variables.

---

## Key Engineering Insights from This Session

1. **Constraint-driven design:** The "no local compute" constraint didn't complicate the architecture — it simplified it. Every decision was filtered through *"does this run on the server?"*, which eliminated over-engineered local tooling.

2. **OOP patterns in ML are not ceremonial:** Factory and Strategy patterns here solve real problems. The Factory eliminates format-checking branches from the pipeline. The Strategy enables algorithm swapping (Z-Score vs IQR) without rebuilding the cleaner object.

3. **The container networking trap:** `localhost` in a container ≠ `localhost` on the host. Always `extra_hosts: host-gateway` on Linux Docker.

4. **Three-tier model resolution:** Production ML APIs need a graceful fallback strategy. A model registry that doesn't have a `Production` entry yet should not prevent the API from serving predictions.

5. **`expm1` is not optional:** The model predicts `log1p(SalePrice)`. Forgetting to `expm1()` the output produces predicted prices in log-scale dollars — a number around 12 instead of $208,500. The inverse transform must live in `ModelRegistry.predict()`, not scattered across callers.

6. **SSH heredoc quoting:** Always use `'SINGLE_QUOTED'` heredoc delimiters when sending scripts over SSH. Double-quoted delimiters expand variables locally before transmission.

---

## Files Produced This Session

| File | Role |
|------|------|
| `setup_env.sh` | Isolated Python 3.10 venv |
| `start_mlflow.sh` | MLflow server on port 5055 → Neon.tech Postgres |
| `requirements.txt` | Pinned dependency manifest |
| `.env.example` | Credential template |
| `src/__init__.py` | Package marker |
| `src/data_ingestion.py` | Factory pattern — CSV/ZIP ingestors |
| `src/data_cleaning.py` | Strategy pattern — imputation + outlier detection |
| `src/pipeline.py` | ZenML `@step` + `@pipeline` + MLflow tracking |
| `src/api.py` | FastAPI app + ModelRegistry + Pydantic schemas |
| `Dockerfile` | python:3.10-slim, port 8085, non-root user |
| `docker-compose.yml` | Named volume, host gateway, healthcheck, restart policy |
| `remote_deploy.sh` | rsync + SSH one-command deploy |
| `.dockerignore` | Keeps venv + secrets out of build context |
| `notes/` | This documentation set |

---

*Session closed 2026-05-02. Next: Phase 2 — Next.js Glassmorphism Frontend.*
