# House Price Prediction — End-to-End MLOps Project

> **Status:** Deployed and serving predictions on `192.168.29.100:8085`

---

## The Problem

Accurately pricing a residential property is a multi-variable regression problem with real economic consequences. Listing too high means the property sits unsold; listing too low leaves money on the table. The classic **Ames Housing Dataset** (Ames, Iowa, USA — 2006–2010, ~1,460 records, 79 features) provides a rich ground truth for building and validating a predictive pricing model.

The technical challenge is not just building a model in a notebook. The real problem is:

> *"How do you take an ML experiment from a local Jupyter session to a tracked, versioned, API-served, containerised production system — without touching production infrastructure on every iteration?"*

This project answers that question from first principles.

---

## The Solution

A fully automated, strictly isolated, end-to-end MLOps pipeline that:

1. **Ingests** raw data from `.csv` or `.zip` sources using a pluggable Factory pattern.
2. **Cleans** the data using swappable Strategy-pattern imputers and outlier detectors.
3. **Trains** a Scikit-Learn pipeline (log-transform + scale + OHE → LinearRegression) tracked entirely in MLflow.
4. **Serves** predictions through a production-grade FastAPI REST API.
5. **Deploys** to a remote home server via a single `bash remote_deploy.sh` command, with zero compute load on the developer's laptop.

---

## System Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│  LOCAL LAPTOP  (zero compute — source of truth only)                       │
│                                                                            │
│  Source Code ──rsync──▶  skyie@192.168.29.100:~/house_price_production     │
└────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  HOME SERVER  192.168.29.100                                                │
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │  Docker Compose Stack                                              │   │
│  │                                                                    │   │
│  │  ┌──────────────────────────────────────────────────────────────┐ │   │
│  │  │  house_price_api  (python:3.10-slim, port 8085)              │ │   │
│  │  │                                                              │ │   │
│  │  │  FastAPI + Uvicorn                                           │ │   │
│  │  │    POST /api/v1/predict  ──▶  ModelRegistry.predict()       │ │   │
│  │  │    GET  /api/v1/health                                       │ │   │
│  │  │    GET  /api/v1/model-info                                   │ │   │
│  │  │                                                              │ │   │
│  │  │  Volume: fastapi_model_cache:/app/models                     │ │   │
│  │  └──────────────────────┬───────────────────────────────────────┘ │   │
│  │                         │ host.docker.internal:5055               │   │
│  └─────────────────────────┼───────────────────────────────────────--┘   │
│                             │                                             │
│  ┌──────────────────────────▼──────────────────────────────────────────┐  │
│  │  MLflow Tracking Server  (host process, port 5055)                  │  │
│  │                                                                     │  │
│  │  mlflow server --port 5055 --backend-store-uri postgresql://...     │  │
│  │                                                                     │  │
│  └──────────────────────────┬────────────────────────────────────────-┘  │
│                              │ SSL / postgresql+psycopg2                   │
└─────────────────────────────┼──────────────────────────────────────────--┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  NEON.TECH  (Serverless PostgreSQL)                                       │
│                                                                           │
│  MLflow backend store — runs, metrics, params, model registry             │
│  ep-xxxx.us-east-2.aws.neon.tech:5432                                    │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Training Pipeline (ZenML)

```
DataIngestorFactory.get_ingestor(file_path)
          │
          ▼  (ZenML artifact: raw_dataset)
DataCleaner.clean(raw_df)
  ├── MedianImputation          fills NaN with per-column median
  └── IQROutlierDetection       removes rows outside [Q1−1.5·IQR, Q3+1.5·IQR]
          │
          ▼  (ZenML artifact: clean_dataset)
SklearnPipeline.fit(X_train, log1p(y_train))
  ├── ColumnTransformer
  │     ├── skewed numericals  →  log1p  →  StandardScaler
  │     ├── non-skewed nums    →  StandardScaler
  │     └── categoricals       →  OneHotEncoder(handle_unknown="ignore")
  └── LinearRegression
          │
          ▼  (ZenML artifacts: trained_sklearn_pipeline, evaluation_metrics)
MLflow autolog → Neon.tech PostgreSQL
```

---

## Repository Structure

```
house_price_production/
├── src/
│   ├── __init__.py
│   ├── data_ingestion.py     Factory pattern — CSV / ZIP ingestors
│   ├── data_cleaning.py      Strategy pattern — imputation + outlier detection
│   ├── pipeline.py           ZenML steps + @pipeline definition
│   └── api.py                FastAPI application + ModelRegistry + schemas
├── notes/
│   ├── index.md              ← this file
│   ├── tech_stack.md         Technology choices and rationale
│   ├── plans.md              Future roadmap
│   ├── progress.md           Chronological build log
│   └── todays_session.md     Detailed session recap
├── Dockerfile                python:3.10-slim, port 8085
├── docker-compose.yml        Named volume, healthcheck, restart policy
├── remote_deploy.sh          rsync + SSH one-command deployment
├── start_mlflow.sh           Launches MLflow on port 5055 → Neon.tech
├── setup_env.sh              Creates isolated Python 3.10 venv
├── requirements.txt          Pinned dependencies
├── .env.example              Credential template
├── .dockerignore             Keeps venv and secrets out of image
└── .gitignore                Keeps venv, .env, and artefacts out of git
```

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/house-price-prediction.git
cd house-price-prediction

# 2. Create isolated Python 3.10 environment
bash setup_env.sh
source house_price_env/bin/activate

# 3. Configure credentials
cp .env.example .env
# Fill in Neon.tech PostgreSQL credentials

# 4. Start MLflow tracking server (port 5055)
bash start_mlflow.sh &

# 5. Run ZenML training pipeline
python -m src.pipeline --data-path data/train.csv

# 6. Deploy API to remote server
bash remote_deploy.sh

# 7. Test the API
curl -X POST http://192.168.29.100:8085/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"GrLivArea": 1500, "OverallQual": 7, "YearBuilt": 2003}'
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Liveness + model readiness |
| `GET` | `/api/v1/model-info` | Loaded model URI + version |
| `POST` | `/api/v1/predict` | Predict sale price in USD |
| `GET` | `/docs` | Interactive Swagger UI |
| `GET` | `/redoc` | ReDoc documentation |

### Minimal predict payload

```json
{
  "GrLivArea": 1500,
  "OverallQual": 7
}
```

### Full predict response

```json
{
  "predicted_price_usd": 208500.00,
  "predicted_price_formatted": "$208,500.00",
  "model_uri": "models:/HousePriceModel/Production"
}
```

---

*See [tech_stack.md](tech_stack.md) for technology choices, [plans.md](plans.md) for the roadmap, and [progress.md](progress.md) for the build history.*
