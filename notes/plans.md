# Roadmap & Future Plans

This document tracks planned enhancements, organised by phase. Each phase builds directly on the previous one — no phase assumes work that hasn't been completed.

---

## Current State (Completed ✅)

- [x] Isolated Python 3.10 virtual environment
- [x] Factory pattern data ingestion (CSV + ZIP)
- [x] Strategy pattern data cleaning (imputation + outlier detection)
- [x] ZenML pipeline with artifact versioning and step caching
- [x] MLflow experiment tracking on custom port 5055
- [x] Neon.tech serverless PostgreSQL as MLflow backend store
- [x] Scikit-Learn Pipeline with ColumnTransformer (log1p + scale + OHE → LinearRegression)
- [x] FastAPI prediction API with Pydantic v2 schema and three-tier model resolution
- [x] Dockerised deployment (python:3.10-slim, non-root user, named volume)
- [x] One-command remote deployment via rsync + SSH

---

## Phase 2 — Frontend (Next Priority)

### Next.js Glassmorphism Frontend

Build a visually polished, interactive house price calculator that calls the FastAPI backend.

**Stack:**
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS + `backdrop-filter: blur()` for glassmorphism cards
- Framer Motion for entrance animations
- shadcn/ui component library

**Features:**
- Input form with sliders for numerical features (OverallQual, GrLivArea)
- Dropdown selects for categorical features (Neighborhood, KitchenQual)
- Real-time price preview as sliders are adjusted (debounced API calls)
- Animated price reveal card
- Feature importance bar chart (requires the API to expose SHAP values — see Phase 3)
- Responsive mobile layout

**Deployment:**
- Static export served by Nginx on the home server
- Traefik reverse-proxy routing: `house-price.local` → Next.js frontend → FastAPI backend

**Integration point:**
```typescript
const response = await fetch('http://192.168.29.100:8085/api/v1/predict', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(features),
});
const { predicted_price_formatted } = await response.json();
```

---

## Phase 3 — Model Improvement

### Replace LinearRegression with an Ensemble

The current LinearRegression is intentionally the simplest possible model. The roadmap is to benchmark against:

| Model | Expected R² gain | Notes |
|-------|------------------|-------|
| Ridge / Lasso | +0.01–0.02 | Regularisation reduces overfitting on high-cardinality OHE features |
| Random Forest | +0.04–0.07 | Captures non-linear interactions (e.g. Neighborhood × OverallQual) |
| XGBoost | +0.06–0.10 | Gold standard for tabular regression; handles skew natively |
| LightGBM | +0.06–0.10 | Faster than XGBoost; better on high-cardinality categoricals |
| Stacking Ensemble | +0.02–0.04 | LinearRegression meta-learner over XGBoost + LightGBM base |

**Process:** Each model gets its own ZenML pipeline run tracked in MLflow. Promotion to `Production` requires beating the incumbent on hold-out RMSE.

### Feature Engineering Expansion

- **Polynomial features:** `GrLivArea²`, `OverallQual × YearBuilt` interaction terms
- **Age features:** `HouseAge = YearSold - YearBuilt`, `YearsSinceRemodel`
- **Area aggregates:** `TotalSF = TotalBsmtSF + 1stFlrSF + 2ndFlrSF`
- **Rare-category encoding:** Group Neighborhoods with < 10 samples into "Other"

### SHAP Value Endpoint

Add `GET /api/v1/explain/{prediction_id}` that returns per-feature SHAP values for the most recent prediction, enabling the frontend feature importance chart.

```python
import shap
explainer = shap.LinearExplainer(model["regressor"], X_train_transformed)
shap_values = explainer.shap_values(X_test_transformed)
```

---

## Phase 4 — CI/CD Pipeline

### GitHub Actions Workflow

Automate testing, building, and deployment on every push to `main`.

**`.github/workflows/deploy.yml`:**

```
push to main
    │
    ├── Job: test
    │     ├── pytest src/ (unit tests for data_ingestion + data_cleaning)
    │     └── ruff / mypy (lint + type check)
    │
    ├── Job: build  (depends on: test)
    │     ├── docker build -t house_price_api:$SHA .
    │     └── docker push ghcr.io/username/house_price_api:$SHA
    │
    └── Job: deploy  (depends on: build)
          └── ssh skyie@192.168.29.100
                docker compose pull
                docker compose up -d
```

**Secrets required in GitHub:**
- `SERVER_HOST`, `SERVER_USER`, `SERVER_SSH_KEY`
- `NEON_DB_*` credentials injected as environment variables during the ZenML pipeline run

### Automated Retraining Trigger

Add a GitHub Actions schedule that:
1. Downloads the latest Kaggle House Prices dataset
2. Runs the ZenML pipeline
3. Compares the new model's RMSE against the current `Production` model
4. Auto-promotes if RMSE improves by > 1%
5. Opens a GitHub Issue if the new model is worse (drift alert)

---

## Phase 5 — Data & Model Monitoring

### Evidently AI Integration

Add a scheduled monitoring step that computes:
- **Data drift:** Kolmogorov-Smirnov test on feature distributions (training vs. recent predictions)
- **Target drift:** Jensen-Shannon divergence on predicted price distributions
- **Model performance degradation:** Track R² on labelled feedback data

Reports are logged to MLflow as HTML artefacts and sent as Slack/email alerts when drift exceeds thresholds.

### Prediction Logging

Store every prediction request in a PostgreSQL table (same Neon.tech instance, separate schema):

```sql
CREATE TABLE predictions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    features    JSONB NOT NULL,
    predicted_price NUMERIC(12, 2) NOT NULL,
    model_uri   TEXT NOT NULL,
    model_version TEXT
);
```

This creates a labelled feedback loop: if a listing sells at a known price, that row is updated and used to compute live RMSE.

---

## Phase 6 — Infrastructure Hardening

### Traefik Integration

Route `house-price.local` through the existing Traefik ingress on the server:

```yaml
# docker-compose.yml addition
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.house-price.rule=Host(`house-price.local`)"
  - "traefik.http.services.house-price.loadbalancer.server.port=8085"
```

### Horizontal Scaling

Replace the single Docker container with a Compose `scale` directive:

```bash
docker compose up -d --scale house_price_api=3
```

Each replica needs a shared artifact cache (current named volume works for single-host) or an S3/MinIO artifact store for multi-host.

### Secret Management

Migrate from a `.env` file on the server to **HashiCorp Vault** or **Docker Secrets** so credentials are never stored as plaintext on the filesystem.

---

## Phase 7 — Advanced MLOps

### DVC (Data Version Control)

Track dataset versions alongside model versions so any historical model can be reproduced from the exact data it was trained on:

```bash
dvc init
dvc add data/train.csv
dvc push  # push to S3/GCS remote
```

### ZenML Model Control Plane

Migrate the model registry from MLflow to ZenML's built-in Model Control Plane, unifying artifact tracking and model lifecycle management in a single UI.

### Kubernetes Deployment (K3s)

The home server already runs K3s. A future phase migrates the Docker Compose deployment to a K3s Deployment + Service + HorizontalPodAutoscaler — using the existing Traefik ingress for routing.

---

*Last updated: 2026-05-02*
