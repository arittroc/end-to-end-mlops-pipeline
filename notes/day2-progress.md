# Day 2 — CI/CD, Observability & Production Routing

**Date:** 2026-05-03  
**Engineer:** carittro@gmail.com  
**Duration:** Single extended session  
**Outcome:** Automated deployment pipeline live, full observability stack deployed, API reachable via Traefik at `api.houseprice.local`

---

## What Was Accomplished

| # | Area | Result |
|---|------|--------|
| 1 | GitHub Actions CI/CD | Self-hosted runner triggered on `git push` → `docker compose up --build` |
| 2 | Prometheus + Grafana | Metrics stack deployed alongside the API; `/metrics` endpoint live |
| 3 | Traefik routing | Root cause diagnosed (K3s, not Docker Traefik) — fixed via K8s Ingress |
| 4 | Frontend env refactor | Hardcoded IP replaced with `NEXT_PUBLIC_API_URL` environment variable |
| 5 | CI/CD runner setup | New `actions-runner-mlops` registered and running as a service |
| 6 | Deployment verification | `curl -H "Host: api.houseprice.local"` → `HTTP 200`, all containers healthy |

---

## 1. GitHub Actions CI/CD Pipeline

### Problem

Deploying changes required manual SSH + rsync + `docker compose up` every time. Not sustainable.

### Solution

Created `.github/workflows/deploy.yml` with a self-hosted runner that executes directly on the home server.

```yaml
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Server
        run: |
          cp /home/skyie/end-to-end-mlops-pipeline/.env .
          docker compose up -d --build
```

**Key design decisions:**

- **Self-hosted runner** — the runner lives on `192.168.29.100`. No cloud VM needed. `docker compose` runs directly against the host's Docker daemon.
- **`.env` copy pattern** — secrets live in a fixed path outside the runner workspace (`~/end-to-end-mlops-pipeline/.env`). The workflow copies them in at deploy time. This means secrets are never in git, never in CI environment variables, and never sent over the network.
- **`--build` on every deploy** — always rebuilds the image. Slightly slower (~2 min) but guarantees no stale layer cache surprises in production.

**Runner setup:**

A dedicated `actions-runner-mlops` directory was created separately from the existing `actions-runner` (which belongs to the `release-pilot` repo). Both runners run as services simultaneously — one per repo.

```bash
mkdir ~/actions-runner-mlops && cd ~/actions-runner-mlops
# configure with token from GitHub repo settings
./config.sh --url https://github.com/arittroc/end-to-end-mlops-pipeline --token <TOKEN>
# install and start as service
sudo ./svc.sh install && sudo ./svc.sh start
```

---

## 2. Prometheus + Grafana Observability Stack

### Problem

No visibility into API behaviour in production — request rates, latency percentiles, error rates were all invisible.

### Solution

Added `prometheus-fastapi-instrumentator` to the API, deployed Prometheus and Grafana as new Compose services.

**`requirements.txt` addition:**
```
prometheus-fastapi-instrumentator==6.1.0
```

**`src/api.py` addition (after CORS middleware):**
```python
from prometheus_fastapi_instrumentator import Instrumentator
# ...
Instrumentator().instrument(app).expose(app)
```

This single call instruments every route automatically and exposes a `/metrics` endpoint in Prometheus text format. No manual counter/histogram code needed.

**`monitoring/prometheus.yml`:**
```yaml
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: "house_price_api"
    static_configs:
      - targets: ["house_price_api:8085"]
    metrics_path: /metrics
```

Target is the **Docker service name** `house_price_api`, not `localhost` or an IP. Docker's internal DNS resolves service names within the Compose network automatically.

**`docker-compose.yml` additions:**

```yaml
prometheus:
  image: prom/prometheus:latest
  ports: ["9090:9090"]
  volumes:
    - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro

grafana:
  image: grafana/grafana:latest
  ports: ["3005:3000"]   # 3000 is already used by other services on this server
```

**Access:**

| Service | URL |
|---------|-----|
| Prometheus | `http://192.168.29.100:9090` |
| Grafana | `http://192.168.29.100:3005` |
| Raw metrics | `http://192.168.29.100:8085/metrics` |

In Grafana: add `http://prometheus:9090` as a Prometheus datasource (uses the internal Docker DNS name).

---

## 3. Traefik Routing — Root Cause Investigation

### The Symptom

```bash
curl -H "Host: api.houseprice.local" http://192.168.29.100/api/v1/health
# 404 page not found
```

Traefik was alive (responding) but couldn't see the container.

### Initial (Wrong) Hypothesis

Port 80 is responding → Traefik is running as a Docker container → add an external Docker network.

Added `traefik_proxy` external network + Docker labels to `docker-compose.yml`. Did not work — the network didn't exist.

### The Real Cause (Found via SSH Recon)

```bash
docker network ls      # no traefik network anywhere
kubectl get pods -A    # traefik-c5c8bf4ff running in kube-system
```

**Traefik is the K3s ingress controller, not a Docker container.**

The server runs K3s (Kubernetes) as a separate process. K3s Traefik owns port 80 via `svclb-traefik` (a K3s ServiceLB pod that binds directly to the host network). It routes traffic using Kubernetes `Ingress` resources — Docker labels are completely invisible to it.

The `traefik_proxy` external Docker network approach was the wrong tool entirely.

### The Fix — Kubernetes Ingress

Created `k8s/house-price-api.yaml` with three resources:

```
K3s Traefik (port 80)
    → Ingress rule (Host: api.houseprice.local)
        → Service/house-price-api (no pod selector)
            → Endpoints (192.168.29.100:8085)
                → Docker container
```

**Service** (no pod selector — manually backed):
```yaml
apiVersion: v1
kind: Service
metadata:
  name: house-price-api
  namespace: default
spec:
  ports:
    - name: http
      port: 8085
      targetPort: 8085
```

**Endpoints** (bridges Kubernetes to Docker):
```yaml
apiVersion: v1
kind: Endpoints
metadata:
  name: house-price-api
subsets:
  - addresses:
      - ip: 192.168.29.100
    ports:
      - name: http
        port: 8085
```

**Ingress** (matches existing pattern from `releasepilot-ingress`):
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: house-price-api-ingress
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web
spec:
  ingressClassName: traefik
  rules:
    - host: api.houseprice.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: house-price-api
                port:
                  number: 8085
```

Applied live via SSH: `kubectl apply -f -`. Ingress immediately received `ADDRESS: 192.168.29.100`.

**Also removed from `docker-compose.yml`:** the Docker labels block and `traefik_proxy` external network — both are dead code against a K3s Traefik.

---

## 4. Frontend Environment Variable Refactor

### Problem

`src/app/page.tsx` contained:
```typescript
const API_URL = 'http://192.168.29.100:8085/api/v1/predict'
```

A hardcoded LAN IP is not deployable — it breaks the moment the server IP changes, a domain is configured, or the frontend is served to a user outside the local network.

### Solution

**`frontend/src/app/page.tsx`:**
```typescript
const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8085/api/v1/predict'
```

- `NEXT_PUBLIC_` prefix: Next.js inlines this variable at **build time** into the client bundle. No server-side rendering trick needed — the value is baked in when the frontend image is built.
- `?? fallback`: local development without a `.env.local` still works against `localhost:8085`. The fallback is `localhost`, not the hardcoded LAN IP, so it works on any machine.

**`frontend/.env.example`:**
```env
NEXT_PUBLIC_API_URL=http://api.houseprice.local/api/v1/predict
```

**`frontend/.gitignore` fix:**

The default Next.js `.gitignore` includes `.env*` which matched `.env.example`. Added:
```
!.env.example
```
This is the standard pattern: ignore all env files except the committed example template.

---

## 5. Deployment — Debugging Log

The deployment sequence uncovered and resolved three issues in order:

### Issue 1: Wrong `.env` path in workflow

Initial workflow:
```bash
cp /home/skyie/house_price_production/.env .
```

The directory `house_price_production` does not exist. The repo lives at `~/end-to-end-mlops-pipeline/`.

**Fix:**
```bash
cp /home/skyie/end-to-end-mlops-pipeline/.env .
```

### Issue 2: Stale server repo with untracked frontend files

The server's local clone was from before the `frontend/` directory was committed. Git refused to pull because untracked files would be overwritten:

```
error: The following untracked working tree files would be overwritten by merge
```

**Fix:** Clean untracked files (preserving `.env`) then hard-reset to remote:
```bash
git clean -fd --exclude='.env' --exclude='.env.template' frontend/
git reset --hard origin/main
```

### Issue 3: Missing `.env` file

The workflow's `cp` step hard-failed because `~/end-to-end-mlops-pipeline/.env` didn't exist yet. The `.env.template` was present but the user needed to populate and rename it.

```bash
cp ~/end-to-end-mlops-pipeline/.env.template ~/end-to-end-mlops-pipeline/.env
nano ~/end-to-end-mlops-pipeline/.env   # fill in Neon DB credentials
```

---

## End State

```
Push to main
    └── actions-runner-mlops picks up job
            ├── checkout@v4
            ├── cp ~/.../end-to-end-mlops-pipeline/.env .
            └── docker compose up -d --build
                    ├── house_price_api  :8085  (health: starting → healthy)
                    ├── prometheus       :9090
                    └── grafana          :3005

K3s Traefik (port 80)
    └── Ingress: api.houseprice.local
            └── Endpoints: 192.168.29.100:8085
                    └── house_price_api container
```

**Verification:**
```bash
curl -H "Host: api.houseprice.local" http://192.168.29.100/api/v1/health
# {"status":"ok","model_ready":false,"version":"1.0.0"}
```

`model_ready: false` — expected. The ZenML pipeline has not run against this environment yet. No model is registered in MLflow. The API is healthy and will serve predictions once a training run completes and promotes a model.

---

## Files Created or Modified

| File | Change |
|------|--------|
| `.github/workflows/deploy.yml` | New — CI/CD pipeline |
| `monitoring/prometheus.yml` | New — Prometheus scrape config |
| `k8s/house-price-api.yaml` | New — K8s Service + Endpoints + Ingress |
| `docker-compose.yml` | Added Prometheus + Grafana services; removed dead Docker-label/traefik_proxy blocks |
| `requirements.txt` | Added `prometheus-fastapi-instrumentator==6.1.0` |
| `src/api.py` | Added `Instrumentator().instrument(app).expose(app)` |
| `frontend/src/app/page.tsx` | Replaced hardcoded IP with `process.env.NEXT_PUBLIC_API_URL` |
| `frontend/.env.example` | New — documents `NEXT_PUBLIC_API_URL` |
| `frontend/.gitignore` | Added `!.env.example` negation |

---

## Key Engineering Insights

1. **`docker network ls` before assuming Traefik is Docker-based.** On a server running Kubernetes, Traefik is almost certainly the K3s ingress controller, not a standalone Docker container. Docker labels are for the Docker provider only.

2. **Bridging Kubernetes and Docker Compose** is done with a selector-less Service backed by a manual Endpoints object pointing at the node IP. This is the standard K8s pattern for routing to out-of-cluster services.

3. **`NEXT_PUBLIC_` is a build-time bake, not a runtime inject.** The value must be present when `next build` runs. Changing it requires a rebuild — it cannot be hot-swapped via Docker environment variables like a backend config.

4. **Never store secrets in the runner workspace.** The `.env` copy-from-fixed-path pattern keeps credentials off git, off GitHub's servers, and off any ephemeral checkout directory. The fixed path is outside the repo so a `git clean` can never delete it.

5. **A self-hosted runner per repo is safer than a shared runner.** If `release-pilot` CI does something destructive (e.g. `docker system prune`), it won't affect the MLOps runner workspace or vice versa.

---

## Commits This Session

| Hash | Message |
|------|---------|
| `1788644` | `feat: implement CI/CD pipeline and Prometheus/Grafana monitoring` |
| `7b8b2ce` | `feat: implement traefik routing and frontend env vars` |
| `5815b8e` | `fix: correct Traefik external network name for remote routing` |
| `a5a6cba` | `fix: correct .env source path in deploy workflow` |

---

## Next Steps

- Run the ZenML pipeline end-to-end to register a model → `model_ready` flips to `true`
- Add Grafana dashboard: import FastAPI dashboard ID `17175` from grafana.com (works with `prometheus-fastapi-instrumentator` out of the box)
- Add `websecure` entrypoint + cert-manager TLS to the K8s Ingress (matches `releasepilot-ingress` pattern already on the server)
- Build and deploy the Next.js frontend container

---

*See [[progress]] for the full chronological log · [[tech_stack]] for technology rationale · [[plans]] for the roadmap*
