# Day 3 — Full Indian Market Pivot & Production Deployment

## What the Project Does

**House Price Oracle** is an end-to-end MLOps system that predicts residential real estate prices across three Indian tech hub cities — Gurgaon (Delhi NCR), Bangalore, and Kolkata.

A user opens the frontend, selects a city, enters the property details (living area, quality rating, year built, basement area), clicks "Predict Price", and gets back an animated price in Indian Rupees (Crore notation) with the USD equivalent shown as a subtitle. The entire stack — data generation, model training, experiment tracking, API serving, monitoring, and the frontend UI — runs as a collection of Docker containers managed by Docker Compose on a home Linux server.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Data generation | Python · NumPy · Pandas |
| ML pipeline orchestration | ZenML 0.67.0 |
| Experiment tracking & model registry | MLflow 2.13.2 |
| ML backend store | Neon.tech serverless PostgreSQL |
| Model | scikit-learn LinearRegression inside a ColumnTransformer Pipeline |
| API | FastAPI · Uvicorn · Pydantic v2 |
| Containerisation | Docker · Docker Compose |
| Reverse proxy / routing | Traefik (K3s ingress on the same host) |
| Frontend | Next.js 16 (App Router) · Framer Motion · Tailwind CSS · Lucide icons |
| Monitoring | Prometheus · Grafana |
| CI/CD | GitHub Actions → SSH deploy workflow |
| Version control | Git · GitHub |

---

## How the Model Was Trained

### 1. Synthetic Dataset Generation

Because real Indian residential transaction data is not publicly available at scale, a 1,000-row synthetic dataset was generated with `generate_data.py`. The pricing model is grounded in real market research:

```
price_per_sqft_INR = city_base × quality_mult × year_factor × lognormal_noise(μ=0, σ=0.08)
SalePrice_USD      = (price_per_sqft × effective_area) / 83
```

City base rates (INR/sqft):
- Gurgaon: ₹8,000 (DLF/Sohna Road corridor)
- Bangalore: ₹6,500 (Whitefield/ITPL belt)
- Kolkata: ₹5,000 (New Town/Salt Lake)

Quality multiplier ranges from 0.30× (very poor) to 2.00× (ultra-luxury).
Year factor ranges from 0.60× (pre-1980 stock) to 1.25× (RERA-era 2020+ launches).

The calibration anchor: Gurgaon · OverallQual 8 · 2,000 sqft · YearBuilt 2018 → ≈ ₹2.5 Cr ($300k), which matches real listings on PropTiger/99acres for that segment.

Resulting Pearson correlations with SalePrice:
- GrLivArea: r = +0.774
- OverallQual: r = +0.543
- YearBuilt: r = +0.281
- TotalBsmtSF: r = +0.072

### 2. ZenML Pipeline

The pipeline has three steps:

**`ingest_data_step`** — reads `data/indian_housing.csv` into a Pandas DataFrame using the existing `DataIngestorFactory` (CSV strategy).

**`clean_data_step`** — applies `MedianImputation` for numeric NaN and `IQROutlierDetection` (factor 1.5) on `GrLivArea` and `SalePrice`. Removed 26 outlier rows, leaving 974 clean rows.

**`train_model_step`** — splits 80/20, builds a ColumnTransformer that:
- Log-transforms skewed numeric features (GrLivArea, SalePrice) via FunctionTransformer
- Standard-scales non-skewed numeric features
- One-Hot-Encodes the `Location` categorical column

Trains a LinearRegression on log1p(SalePrice). Final metrics:
- RMSE (log scale): 0.1259
- R²: 0.9513
- RMSE ($): $19,338
- MAE ($): $14,222

MLflow autolog tracked the experiment under `house_price_prediction`. The model was registered as `HousePriceModel` version 2 in the MLflow registry (version 1 was the earlier Ames Housing run).

### 3. Run Command

```bash
cd ~/end-to-end-mlops-pipeline
source house_price_env/bin/activate
export MLFLOW_TRACKING_URI='http://localhost:5055'
python run_pipeline.py --data-path data/indian_housing.csv
```

---

## Challenges and Issues Faced

### Challenge 1 — `from __future__ import annotations` breaks ZenML

**What happened:** ZenML crashed with `AttributeError: 'str' object has no attribute '__mro__'` inside its materializer registry.

**Root cause:** PEP 563 (`from __future__ import annotations`) makes ALL type annotations lazy strings at runtime. ZenML calls `output_type.__mro__` to find the right materializer for a step's return type, but gets a plain string instead of a class.

**Fix:** Removed `from __future__ import annotations` from `src/pipeline.py`. Also removed all `Annotated[Type, "name"]` return wrappers which had the same effect.

---

### Challenge 2 — Categorical NaN fills causing infinity overflow

**What happened:** The pipeline ran but MLflow logged `RMSE = inf`. The Docker API container crashed on inference.

**Root cause:** 7,481 categorical NaN values were left unfilled before OneHotEncoding. OHE maps them to all-zero rows. The LinearRegression produced log-scale predictions above 709, and `np.expm1(x > 709)` overflows to `+inf`. sklearn then raises `ValueError: Input contains infinity`.

**Fix:**
1. Fill categorical NaN with the sentinel string `"None"` before OHE at the start of `train_model_step`.
2. Clip log-scale predictions: `np.clip(y_pred_log, 0, 20)` before calling `expm1`.

---

### Challenge 3 — ZenML requires auth credentials for HTTP MLflow URIs

**What happened:** `zenml stack register` raised a `ValidationError` even though the MLflow server was running locally.

**Root cause:** ZenML 0.67.0 enforces that any HTTP tracking URI must have `tracking_username` and `tracking_password` set, regardless of whether the server actually requires auth.

**Fix:** Register the tracker with dummy credentials:
```bash
zenml experiment-tracker register house_price_mlflow_tracker \
    --flavor=mlflow \
    --tracking_uri="http://localhost:5055" \
    --tracking_username="user" \
    --tracking_password="password"
```

---

### Challenge 4 — Docker container permission denied on MLflow artifacts

**What happened:** The API container started but `model_ready: false`. Logs showed `[Errno 13] Permission denied: .../registered_model_meta`.

**Root cause:** The container runs as `appuser` (uid=1001). The MLflow artifact directory on the host was created by `skyie` but with permissions that excluded world-write (`o=r-x`). MLflow needs to write `registered_model_meta` when loading a registered model.

**Fix:**
```bash
sudo chown -R skyie:skyie ~/end-to-end-mlops-pipeline/mlflow-artifacts
chmod -R o+w ~/end-to-end-mlops-pipeline/mlflow-artifacts
```

This recurs for every new MLflow run because the tracking server creates subdirectories as `skyie` but the artifact write path inside Docker re-creates them under `appuser`. A permanent fix would be to run the container with `--user skyie` or use a Docker volume with correct GID.

---

### Challenge 5 — MLflow server dies and takes the API down with it

**What happened:** After a server session ended, the `nohup` MLflow process was killed. The API container was still running but returned 503 on every prediction request because it could not reload the model.

**Root cause:** MLflow is started manually with `nohup bash start_mlflow.sh &`. This process doesn't survive SSH session endings on all configurations, and doesn't auto-restart on crashes.

**Fix (immediate):** Restart MLflow manually, then `docker compose restart house_price_api` so it reconnects.

**Proper fix (pending):** Register MLflow as a systemd service:
```bash
sudo systemctl enable mlflow
sudo systemctl start mlflow
```

---

### Challenge 6 — Pydantic `extra="allow"` needed for undeclared columns

**What happened:** The `HousePriceFeatures` Pydantic model only declared ~50 named fields. The Ames Housing dataset has 79 columns. Columns like `Neighborhood`, `MSZoning` etc. were silently dropped, causing the ColumnTransformer to complain about missing columns.

**Fix:** Added `extra="allow"` to `ConfigDict` and updated `to_dataframe()` to merge `model_extra` into the payload dict.

---

### Challenge 7 — Two separate server directories causing deployment confusion

**What happened:** The project lived in two places on the server:
- `~/end-to-end-mlops-pipeline` — the git repo (where ZenML runs, venv lives)
- `~/house_price_production` — the rsync target (where Docker Compose runs)

This caused repeated sync issues: `Dockerfile`, `requirements.txt`, `frontend/`, and `monitoring/prometheus.yml` all had to be manually copied across. The `prometheus.yml` was accidentally created as a directory (not a file) by a failed rsync, blocking Prometheus for several restarts.

**Fix:** Explicit `rsync` commands with `--exclude node_modules/` for each subdirectory, plus `sudo rm -rf` to clear the malformed directory before re-copying.

**Lesson:** A single source-of-truth directory is far cleaner. The two-directory approach exists because `remote_deploy.sh` was designed to rsync from the developer's machine, not from the server's own git clone.

---

### Challenge 8 — TypeScript build failure after adding `Location` to FormState

**What happened:** The Next.js Docker build failed with:
```
Type error: Property 'Location' does not exist on type
'{ readonly OverallQual: ...; readonly GrLivArea: ...; ... }'.
```

**Root cause:** `FIELD_ICONS` only maps the four numeric fields. When `Location` was added to `FormState`, `keyof FormState` started including `'Location'`, and the `FormField` component tried to look up `FIELD_ICONS['Location']` which TypeScript caught as an error.

**Fix:** Introduced a `NumericFieldKey = Exclude<keyof FormState, 'Location'>` type and narrowed `FieldProps.id` to that type, since `FormField` is only ever used for numeric inputs. `Location` gets its own separate `<select>` element.

---

## Key Learnings

### 1. ZenML's runtime type system is sensitive to Python annotation modes
`from __future__ import annotations` is a common import in modern Python for forward references, but it silently breaks any framework that inspects types at runtime (ZenML, some Pydantic validators, dataclass-based ORMs). Always test pipeline registration after touching imports.

### 2. ML pipelines need explicit NaN strategies for every column type
Numeric imputation is well-understood, but categorical NaN is easy to overlook. In the Ames Housing dataset, `NaN` in a categorical column means "no feature" (no pool, no alley) — not missing data. Treating it as truly missing and letting it pass through OHE produces all-zero rows that destabilise linear models. Always define a sentinel strategy (`"None"`, `"Unknown"`) for categorical NaN before encoding.

### 3. Log-transform overflow is a silent production failure
`np.expm1` silently returns `+inf` for inputs above ~709. sklearn propagates the infinity through the metric computation and raises an unhelpful `ValueError`. Always clip log-scale predictions (`np.clip(y_pred, 0, 20)`) before reversing the transform in production code.

### 4. Container user/host user permission mismatches need a deliberate strategy
Running containers as non-root (good security practice) creates friction when the container needs to write to host-mounted directories owned by a different user. The fix (`chmod o+w`) is a blunt instrument. The right approach is to match the container's UID to the host user's UID via `--user` or a `user:` key in `docker-compose.yml`.

### 5. Ephemeral background processes are not production infrastructure
`nohup ... &` is fine for local development. In production, any long-running process (MLflow server, model server) that isn't managed by systemd, supervisord, or a container restart policy will eventually disappear and take dependent services with it. The cost of writing a 10-line systemd unit file at setup time is far lower than diagnosing a 503 at 2am.

### 6. Synthetic data can be surprisingly effective if the generating model is grounded
The Indian housing dataset was entirely synthetic, but because the pricing formula was calibrated against real market anchors (PropTiger/99acres listings, known city-level PSF rates), the model learned meaningful relationships. R² = 0.95 on synthetic data isn't a real-world achievement, but the predicted values (₹1.30 Cr for a mid-quality Bangalore flat) are believable to domain experts. For prototyping an MLOps pipeline, calibrated synthetic data is far better than either random data or waiting for real data.

### 7. TypeScript's structural type system catches integration bugs at build time
The `Location` field addition exposed a real logical gap — `FormField` is only for numeric inputs, but its type signature didn't say so. The TypeScript error forced a cleaner design (`NumericFieldKey` type) that makes the distinction explicit. Treating TS build failures as design feedback rather than annoyances leads to better component boundaries.

### 8. End-to-end thinking matters more than any individual component
The hardest bugs in this project weren't in the ML code or the API code or the frontend code — they were at the seams: ZenML talking to MLflow, the API container talking to the host MLflow server, the frontend's type system reflecting the API schema. Keeping the whole system in mind (and having a working end-to-end test — a real HTTP prediction — as the acceptance criterion) is more valuable than perfecting any single layer.

---

## Current State (End of Day 3)

| Component | Status |
|---|---|
| Synthetic Indian dataset | 1,000 rows · 3 cities · calibrated pricing |
| ZenML pipeline | Trained on indian_housing.csv · R²=0.95 · MAE=$14k |
| MLflow model registry | HousePriceModel v2 (Indian data) |
| FastAPI | Running · model_ready=true · returns ₹ + USD |
| Next.js frontend | City dropdown · animated ₹ Cr counter · USD subtitle |
| Prometheus | Scraping /metrics |
| Grafana | Running on :3005 |
| CI/CD | GitHub Actions → SSH deploy |
| Git | All changes committed and pushed to main |

**Endpoints:**
- Frontend: `http://192.168.29.100:3001`
- API: `http://192.168.29.100:8085/api/v1/predict`
- API docs: `http://192.168.29.100:8085/docs`
- Prometheus: `http://192.168.29.100:9090`
- Grafana: `http://192.168.29.100:3005`
