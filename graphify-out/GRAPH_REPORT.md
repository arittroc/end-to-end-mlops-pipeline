# Graph Report - OOP Ml project  (2026-05-04)

## Corpus Check
- 15 files · ~23,978 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 289 nodes · 350 edges · 42 communities detected
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 22 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]

## God Nodes (most connected - your core abstractions)
1. `Next.js Frontend Application` - 11 edges
2. `predict()` - 10 edges
3. `model_info()` - 9 edges
4. `DataCleaner` - 9 edges
5. `FastAPI REST API (Prediction Service)` - 9 edges
6. `PredictionResponse` - 8 edges
7. `HealthResponse` - 8 edges
8. `ModelInfoResponse` - 8 edges
9. `ErrorDetail` - 8 edges
10. `lifespan()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `MedianImputation` --uses--> `PipelineConfig`  [INFERRED]
  src\data_cleaning.py → src\pipeline.py
- `MedianImputation` --calls--> `clean_data_step()`  [INFERRED]
  src\data_cleaning.py → src\pipeline.py
- `IQROutlierDetection` --uses--> `PipelineConfig`  [INFERRED]
  src\data_cleaning.py → src\pipeline.py
- `IQROutlierDetection` --calls--> `clean_data_step()`  [INFERRED]
  src\data_cleaning.py → src\pipeline.py
- `DataCleaner` --uses--> `PipelineConfig`  [INFERRED]
  src\data_cleaning.py → src\pipeline.py

## Hyperedges (group relationships)
- **MLOps Training Pipeline: ZenML orchestrates DataIngestorFactory → DataCleaner → SklearnPipeline → MLflow tracking → Neon PostgreSQL** — index_zenml_pipeline, index_data_ingestor_factory, index_data_cleaner, index_sklearn_pipeline, dockercompose_mlflow_tracking_server, dockercompose_neon_postgresql [EXTRACTED 1.00]
- **FastAPI Serving Stack: ModelRegistry loads from MLflow, serves via FastAPI+Uvicorn in Docker container with persistent volume** — index_fastapi_rest_api, progress_model_registry_singleton, dockercompose_house_price_api_service, dockercompose_fastapi_model_cache_volume, dockercompose_mlflow_tracking_server [EXTRACTED 1.00]
- **OOP Strategy Pattern: DataCleaner context composes MedianImputation and IQROutlierDetection (swappable with ZScore) strategies** — index_strategy_pattern, index_data_cleaner, index_median_imputation, index_iqr_outlier_detection, todays_zscore_outlier [EXTRACTED 1.00]

## Communities

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (61): BaseModel, ErrorDetail, health_check(), HealthResponse, HousePriceFeatures, info(), is_ready(), lifespan() (+53 more)

### Community 1 - "Community 1"
Cohesion: 0.09
Nodes (24): ABC, detect(), DropMissingValues, handle(), IQROutlierDetection, MeanImputation, MedianImputation, MissingValueStrategy (+16 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (34): Ames Housing Dataset, DataCleaner, DataIngestorFactory, Factory Pattern (DataIngestorFactory), Home Server (192.168.29.100), House Price Prediction MLOps Project, IQROutlierDetection Strategy, MedianImputation Strategy (+26 more)

### Community 3 - "Community 3"
Cohesion: 0.1
Nodes (28): _build_preprocessor(), clean_data_step(), house_price_pipeline(), _identify_column_types(), ingest_data_step(), PipelineConfig, pipeline.py =========== ZenML production pipeline: End-to-End House Price Predic, Partition *df*'s columns (excluding the target) into numeric and     categorical (+20 more)

### Community 4 - "Community 4"
Cohesion: 0.14
Nodes (15): CSVDataIngestor, DataIngestor, DataIngestorFactory, get_ingestor(), ingest(), list_supported_extensions(), data_ingestion.py ================= Factory Design Pattern for dataset ingestion, Read a CSV file from disk into a DataFrame.          Parameters         -------- (+7 more)

### Community 5 - "Community 5"
Cohesion: 0.19
Nodes (14): Next.js Agent Rules, Frontend Claude Config, app/page.tsx Entry Point, create-next-app CLI Tool, Geist Font Family, next/font Optimization, Next.js Framework, Next.js Frontend Application (+6 more)

### Community 6 - "Community 6"
Cohesion: 0.23
Nodes (12): fastapi_model_cache Named Volume, host.docker.internal Host Gateway Bridge, house_price_api Docker Service, MLflow Tracking Server (Host Process port 5055), Neon.tech Serverless PostgreSQL, Evidently AI Data Monitoring (Phase 5), Prediction Logging (PostgreSQL feedback loop), Dockerfile (python:3.10-slim, port 8085, non-root appuser) (+4 more)

### Community 7 - "Community 7"
Cohesion: 0.18
Nodes (6): DataCleaner, Drop rows with missing values and return the reduced DataFrame.          Paramet, Orchestrates the full cleaning pipeline by composing one     :class:`MissingValu, Replace the active missing-value strategy.          Parameters         ---------, Replace the active outlier-detection strategy.          Parameters         -----, Apply the full cleaning pipeline to *df* in order:          1. Missing-value han

### Community 8 - "Community 8"
Cohesion: 0.29
Nodes (8): FastAPI REST API (Prediction Service), GET /api/v1/health Endpoint, GET /api/v1/model-info Endpoint, POST /api/v1/predict Endpoint, Next.js Glassmorphism Frontend (Phase 2), SHAP Value Endpoint /api/v1/explain, FastAPI 0.111.0, Uvicorn 0.30.1

### Community 9 - "Community 9"
Cohesion: 0.4
Nodes (3): generate_india_prices.py ======================== Generates a synthetic 1,000-ro, Newer construction commands a premium; ageing stock depreciates., _year_factor()

### Community 10 - "Community 10"
Cohesion: 0.67
Nodes (1): generate_data.py ================ Generates a synthetic 1,000-row dataset of Ind

### Community 11 - "Community 11"
Cohesion: 0.67
Nodes (1): RootLayout()

### Community 12 - "Community 12"
Cohesion: 0.67
Nodes (1): cn()

### Community 13 - "Community 13"
Cohesion: 0.67
Nodes (1): House Price Prediction — Core Data Pipeline Package.  Modules ------- data_inges

### Community 14 - "Community 14"
Cohesion: 1.0
Nodes (1): run_pipeline.py =============== Convenience entry point for the ZenML House Pric

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (2): HousePriceFeatures Pydantic Model, Pydantic v2 (Input Validation)

### Community 16 - "Community 16"
Cohesion: 1.0
Nodes (2): Python 3.10 Runtime, setup_env.sh (Python 3.10 venv with --copies)

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): Resolve and load the best available model from the MLflow server.          Appli

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): Run inference on a feature DataFrame and return prices in original $.          T

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Return ``True`` if a model has been successfully loaded.

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): Return a dict of loaded model metadata for the /model-info endpoint.

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): Coerce float ratings (e.g. 7.0) to int and reject out-of-range values.

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): Apply the missing-value strategy to *df*.          Parameters         ----------

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Identify outliers and return a boolean mask.          Parameters         -------

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): Load data from *file_path* and return it as a DataFrame.          Parameters

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): Inspect *file_path*'s extension and return the correct ingestor.          The fa

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): Register a new ingestor class for the given file extension.          Calling thi

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): Return a sorted list of all currently registered file extensions.          Retur

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): Resolve and load the best available model from the MLflow server.          Appli

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): Run inference on a feature DataFrame and return prices in original $.          T

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): Return ``True`` if a model has been successfully loaded.

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Return a dict of loaded model metadata for the /model-info endpoint.

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Coerce float ratings (e.g. 7.0) to int and reject out-of-range values.

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Coerce float ratings (e.g. 7.0) to int and reject out-of-range values.

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Resolve and load the best available model from the MLflow server.          Appli

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Run inference on a feature DataFrame and return prices in original $.          T

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Return ``True`` if a model has been successfully loaded.

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Return a dict of loaded model metadata for the /model-info endpoint.

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Coerce float ratings (e.g. 7.0) to int and reject out-of-range values.

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): numpy 1.26.4

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): python-dotenv 1.0.1

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Git + GitHub Version Control

## Knowledge Gaps
- **146 isolated node(s):** `generate_data.py ================ Generates a synthetic 1,000-row dataset of Ind`, `generate_india_prices.py ======================== Generates a synthetic 1,000-ro`, `Newer construction commands a premium; ageing stock depreciates.`, `run_pipeline.py =============== Convenience entry point for the ZenML House Pric`, `Singleton that owns the MLflow model lifecycle for this process.      Attributes` (+141 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 10`** (3 nodes): `generate_data.py`, `generate_data.py ================ Generates a synthetic 1,000-row dataset of Ind`, `_year_factor()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 11`** (3 nodes): `RootLayout()`, `layout.tsx`, `layout.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 12`** (3 nodes): `utils.ts`, `cn()`, `utils.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 13`** (3 nodes): `__init__.py`, `__init__.py`, `House Price Prediction — Core Data Pipeline Package.  Modules ------- data_inges`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 14`** (2 nodes): `run_pipeline.py =============== Convenience entry point for the ZenML House Pric`, `run_pipeline.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (2 nodes): `HousePriceFeatures Pydantic Model`, `Pydantic v2 (Input Validation)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (2 nodes): `Python 3.10 Runtime`, `setup_env.sh (Python 3.10 venv with --copies)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `Resolve and load the best available model from the MLflow server.          Appli`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `Run inference on a feature DataFrame and return prices in original $.          T`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `Return ``True`` if a model has been successfully loaded.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `Return a dict of loaded model metadata for the /model-info endpoint.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `Coerce float ratings (e.g. 7.0) to int and reject out-of-range values.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `Apply the missing-value strategy to *df*.          Parameters         ----------`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `Identify outliers and return a boolean mask.          Parameters         -------`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `Load data from *file_path* and return it as a DataFrame.          Parameters`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `Inspect *file_path*'s extension and return the correct ingestor.          The fa`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `Register a new ingestor class for the given file extension.          Calling thi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `Return a sorted list of all currently registered file extensions.          Retur`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `Resolve and load the best available model from the MLflow server.          Appli`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `Run inference on a feature DataFrame and return prices in original $.          T`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `Return ``True`` if a model has been successfully loaded.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `Return a dict of loaded model metadata for the /model-info endpoint.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Coerce float ratings (e.g. 7.0) to int and reject out-of-range values.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Coerce float ratings (e.g. 7.0) to int and reject out-of-range values.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Resolve and load the best available model from the MLflow server.          Appli`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Run inference on a feature DataFrame and return prices in original $.          T`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Return ``True`` if a model has been successfully loaded.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Return a dict of loaded model metadata for the /model-info endpoint.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Coerce float ratings (e.g. 7.0) to int and reject out-of-range values.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `numpy 1.26.4`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `python-dotenv 1.0.1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Git + GitHub Version Control`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PipelineConfig` connect `Community 3` to `Community 1`, `Community 4`, `Community 7`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Why does `DataCleaner` connect `Community 7` to `Community 1`, `Community 3`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Why does `clean_data_step()` connect `Community 3` to `Community 1`, `Community 7`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `Next.js Frontend Application` (e.g. with `File Icon SVG` and `Globe/Web Icon SVG`) actually correct?**
  _`Next.js Frontend Application` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `DataCleaner` (e.g. with `PipelineConfig` and `clean_data_step()`) actually correct?**
  _`DataCleaner` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `FastAPI REST API (Prediction Service)` (e.g. with `FastAPI 0.111.0` and `Uvicorn 0.30.1`) actually correct?**
  _`FastAPI REST API (Prediction Service)` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `generate_data.py ================ Generates a synthetic 1,000-row dataset of Ind`, `generate_india_prices.py ======================== Generates a synthetic 1,000-ro`, `Newer construction commands a premium; ageing stock depreciates.` to the rest of the system?**
  _146 weakly-connected nodes found - possible documentation gaps or missing edges._