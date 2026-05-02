# Graph Report - .  (2026-05-03)

## Corpus Check
- Corpus is ~18,256 words - fits in a single context window. You may not need a graph.

## Summary
- 214 nodes · 248 edges · 27 communities detected
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 22 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Project Overview & Notes|Project Overview & Notes]]
- [[_COMMUNITY_FastAPI Prediction Service|FastAPI Prediction Service]]
- [[_COMMUNITY_Data Cleaning Pipeline|Data Cleaning Pipeline]]
- [[_COMMUNITY_Data Ingestion Abstractions|Data Ingestion Abstractions]]
- [[_COMMUNITY_ML Training Pipeline|ML Training Pipeline]]
- [[_COMMUNITY_Imputation Strategies|Imputation Strategies]]
- [[_COMMUNITY_DataCleaner Core|DataCleaner Core]]
- [[_COMMUNITY_Frontend Next.js App|Frontend Next.js App]]
- [[_COMMUNITY_Docker & Infrastructure|Docker & Infrastructure]]
- [[_COMMUNITY_API Endpoints & Plans|API Endpoints & Plans]]
- [[_COMMUNITY_Package Init|Package Init]]
- [[_COMMUNITY_Pydantic & Type Stack|Pydantic & Type Stack]]
- [[_COMMUNITY_Python Environment|Python Environment]]
- [[_COMMUNITY_API Rationale|API Rationale]]
- [[_COMMUNITY_API Rationale|API Rationale]]
- [[_COMMUNITY_API Rationale|API Rationale]]
- [[_COMMUNITY_API Rationale|API Rationale]]
- [[_COMMUNITY_API Rationale|API Rationale]]
- [[_COMMUNITY_Cleaning Rationale|Cleaning Rationale]]
- [[_COMMUNITY_Cleaning Rationale|Cleaning Rationale]]
- [[_COMMUNITY_Ingestion Rationale|Ingestion Rationale]]
- [[_COMMUNITY_Ingestion Rationale|Ingestion Rationale]]
- [[_COMMUNITY_Ingestion Rationale|Ingestion Rationale]]
- [[_COMMUNITY_Ingestion Rationale|Ingestion Rationale]]
- [[_COMMUNITY_NumPy Dependency|NumPy Dependency]]
- [[_COMMUNITY_Dotenv Dependency|Dotenv Dependency]]
- [[_COMMUNITY_Git & GitHub|Git & GitHub]]

## God Nodes (most connected - your core abstractions)
1. `Next.js Frontend Application` - 11 edges
2. `FastAPI REST API (Prediction Service)` - 9 edges
3. `DataCleaner` - 8 edges
4. `MLflow Tracking Server (Host Process port 5055)` - 8 edges
5. `Scikit-Learn Pipeline (log1p + scale + OHE + LinearRegression)` - 8 edges
6. `MedianImputation` - 7 edges
7. `IQROutlierDetection` - 7 edges
8. `House Price Prediction MLOps Project` - 7 edges
9. `ZenML Training Pipeline (house_price_pipeline)` - 7 edges
10. `predict()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `MedianImputation` --calls--> `clean_data_step()`  [INFERRED]
  data_cleaning.py → pipeline.py
- `IQROutlierDetection` --uses--> `PipelineConfig`  [INFERRED]
  data_cleaning.py → pipeline.py
- `IQROutlierDetection` --calls--> `clean_data_step()`  [INFERRED]
  data_cleaning.py → pipeline.py
- `DataCleaner` --uses--> `PipelineConfig`  [INFERRED]
  data_cleaning.py → pipeline.py
- `DataCleaner` --calls--> `clean_data_step()`  [INFERRED]
  data_cleaning.py → pipeline.py

## Hyperedges (group relationships)
- **MLOps Training Pipeline: ZenML orchestrates DataIngestorFactory → DataCleaner → SklearnPipeline → MLflow tracking → Neon PostgreSQL** — index_zenml_pipeline, index_data_ingestor_factory, index_data_cleaner, index_sklearn_pipeline, dockercompose_mlflow_tracking_server, dockercompose_neon_postgresql [EXTRACTED 1.00]
- **FastAPI Serving Stack: ModelRegistry loads from MLflow, serves via FastAPI+Uvicorn in Docker container with persistent volume** — index_fastapi_rest_api, progress_model_registry_singleton, dockercompose_house_price_api_service, dockercompose_fastapi_model_cache_volume, dockercompose_mlflow_tracking_server [EXTRACTED 1.00]
- **OOP Strategy Pattern: DataCleaner context composes MedianImputation and IQROutlierDetection (swappable with ZScore) strategies** — index_strategy_pattern, index_data_cleaner, index_median_imputation, index_iqr_outlier_detection, todays_zscore_outlier [EXTRACTED 1.00]

## Communities

### Community 0 - "Project Overview & Notes"
Cohesion: 0.07
Nodes (34): Ames Housing Dataset, DataCleaner, DataIngestorFactory, Factory Pattern (DataIngestorFactory), Home Server (192.168.29.100), House Price Prediction MLOps Project, IQROutlierDetection Strategy, MedianImputation Strategy (+26 more)

### Community 1 - "FastAPI Prediction Service"
Cohesion: 0.1
Nodes (28): BaseModel, ErrorDetail, health_check(), HealthResponse, HousePriceFeatures, info(), is_ready(), lifespan() (+20 more)

### Community 2 - "Data Cleaning Pipeline"
Cohesion: 0.13
Nodes (11): IQROutlierDetection, OutlierDetectionStrategy, data_cleaning.py ================ Strategy Design Pattern for dataset cleaning., Abstract strategy for detecting outliers in numerical columns.      Concrete sub, Remove rows flagged as outliers in any of *columns*.          Delegates outlier, Flag outliers whose Z-Score magnitude exceeds a given threshold.      The Z-Scor, Compute Z-Scores and build a boolean outlier mask.          NaN values are exclu, Flag outliers using the Interquartile Range (IQR) fence method.      Bounds are (+3 more)

### Community 3 - "Data Ingestion Abstractions"
Cohesion: 0.12
Nodes (10): ABC, CSVDataIngestor, DataIngestor, data_ingestion.py ================= Factory Design Pattern for dataset ingestion, Read a CSV file from disk into a DataFrame.          Parameters         --------, Ingestor for ``.zip`` archives that contain one or more CSV files.      By defau, Extract the target CSV from a ZIP archive and load it.          The archive is o, Abstract contract that every concrete ingestor must satisfy.      All subclasses (+2 more)

### Community 4 - "ML Training Pipeline"
Cohesion: 0.16
Nodes (17): _build_preprocessor(), clean_data_step(), house_price_pipeline(), _identify_column_types(), ingest_data_step(), pipeline.py =========== ZenML production pipeline: End-to-End House Price Predic, Partition *df*'s columns (excluding the target) into numeric and     categorical, Split *numerical_cols* into high-skew and low-skew buckets.      Absolute skewne (+9 more)

### Community 5 - "Imputation Strategies"
Cohesion: 0.12
Nodes (12): MeanImputation, MedianImputation, MissingValueStrategy, Replace NaN entries with per-column means.          Parameters         ---------, Fill missing numeric values with the column median.      Preferred over mean imp, Replace NaN entries with per-column medians.          Parameters         -------, Abstract strategy for handling missing values in a DataFrame.      Each concrete, Fill missing numeric values with the column arithmetic mean.      Non-numeric co (+4 more)

### Community 6 - "DataCleaner Core"
Cohesion: 0.14
Nodes (8): DataCleaner, DropMissingValues, Remove rows that contain NaN values.      Parameters     ----------     columns, Drop rows with missing values and return the reduced DataFrame.          Paramet, Orchestrates the full cleaning pipeline by composing one     :class:`MissingValu, Replace the active missing-value strategy.          Parameters         ---------, Replace the active outlier-detection strategy.          Parameters         -----, Apply the full cleaning pipeline to *df* in order:          1. Missing-value han

### Community 7 - "Frontend Next.js App"
Cohesion: 0.19
Nodes (14): Next.js Agent Rules, Frontend Claude Config, app/page.tsx Entry Point, create-next-app CLI Tool, Geist Font Family, next/font Optimization, Next.js Framework, Next.js Frontend Application (+6 more)

### Community 8 - "Docker & Infrastructure"
Cohesion: 0.23
Nodes (12): fastapi_model_cache Named Volume, host.docker.internal Host Gateway Bridge, house_price_api Docker Service, MLflow Tracking Server (Host Process port 5055), Neon.tech Serverless PostgreSQL, Evidently AI Data Monitoring (Phase 5), Prediction Logging (PostgreSQL feedback loop), Dockerfile (python:3.10-slim, port 8085, non-root appuser) (+4 more)

### Community 9 - "API Endpoints & Plans"
Cohesion: 0.29
Nodes (8): FastAPI REST API (Prediction Service), GET /api/v1/health Endpoint, GET /api/v1/model-info Endpoint, POST /api/v1/predict Endpoint, Next.js Glassmorphism Frontend (Phase 2), SHAP Value Endpoint /api/v1/explain, FastAPI 0.111.0, Uvicorn 0.30.1

### Community 10 - "Package Init"
Cohesion: 1.0
Nodes (1): House Price Prediction — Core Data Pipeline Package.  Modules ------- data_inges

### Community 11 - "Pydantic & Type Stack"
Cohesion: 1.0
Nodes (2): HousePriceFeatures Pydantic Model, Pydantic v2 (Input Validation)

### Community 12 - "Python Environment"
Cohesion: 1.0
Nodes (2): Python 3.10 Runtime, setup_env.sh (Python 3.10 venv with --copies)

### Community 15 - "API Rationale"
Cohesion: 1.0
Nodes (1): Resolve and load the best available model from the MLflow server.          Appli

### Community 16 - "API Rationale"
Cohesion: 1.0
Nodes (1): Run inference on a feature DataFrame and return prices in original $.          T

### Community 17 - "API Rationale"
Cohesion: 1.0
Nodes (1): Return ``True`` if a model has been successfully loaded.

### Community 18 - "API Rationale"
Cohesion: 1.0
Nodes (1): Return a dict of loaded model metadata for the /model-info endpoint.

### Community 19 - "API Rationale"
Cohesion: 1.0
Nodes (1): Coerce float ratings (e.g. 7.0) to int and reject out-of-range values.

### Community 20 - "Cleaning Rationale"
Cohesion: 1.0
Nodes (1): Apply the missing-value strategy to *df*.          Parameters         ----------

### Community 21 - "Cleaning Rationale"
Cohesion: 1.0
Nodes (1): Identify outliers and return a boolean mask.          Parameters         -------

### Community 22 - "Ingestion Rationale"
Cohesion: 1.0
Nodes (1): Load data from *file_path* and return it as a DataFrame.          Parameters

### Community 23 - "Ingestion Rationale"
Cohesion: 1.0
Nodes (1): Inspect *file_path*'s extension and return the correct ingestor.          The fa

### Community 24 - "Ingestion Rationale"
Cohesion: 1.0
Nodes (1): Register a new ingestor class for the given file extension.          Calling thi

### Community 25 - "Ingestion Rationale"
Cohesion: 1.0
Nodes (1): Return a sorted list of all currently registered file extensions.          Retur

### Community 26 - "NumPy Dependency"
Cohesion: 1.0
Nodes (1): numpy 1.26.4

### Community 27 - "Dotenv Dependency"
Cohesion: 1.0
Nodes (1): python-dotenv 1.0.1

### Community 28 - "Git & GitHub"
Cohesion: 1.0
Nodes (1): Git + GitHub Version Control

## Knowledge Gaps
- **96 isolated node(s):** `api.py ====== Production FastAPI application for serving the House Price Predict`, `Singleton that owns the MLflow model lifecycle for this process.      Attributes`, `Resolve and load the best available model from the MLflow server.          Appli`, `Run inference on a feature DataFrame and return prices in original $.          T`, `Return ``True`` if a model has been successfully loaded.` (+91 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Package Init`** (2 nodes): `__init__.py`, `House Price Prediction — Core Data Pipeline Package.  Modules ------- data_inges`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Pydantic & Type Stack`** (2 nodes): `HousePriceFeatures Pydantic Model`, `Pydantic v2 (Input Validation)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Python Environment`** (2 nodes): `Python 3.10 Runtime`, `setup_env.sh (Python 3.10 venv with --copies)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `API Rationale`** (1 nodes): `Resolve and load the best available model from the MLflow server.          Appli`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `API Rationale`** (1 nodes): `Run inference on a feature DataFrame and return prices in original $.          T`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `API Rationale`** (1 nodes): `Return ``True`` if a model has been successfully loaded.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `API Rationale`** (1 nodes): `Return a dict of loaded model metadata for the /model-info endpoint.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `API Rationale`** (1 nodes): `Coerce float ratings (e.g. 7.0) to int and reject out-of-range values.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Cleaning Rationale`** (1 nodes): `Apply the missing-value strategy to *df*.          Parameters         ----------`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Cleaning Rationale`** (1 nodes): `Identify outliers and return a boolean mask.          Parameters         -------`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Ingestion Rationale`** (1 nodes): `Load data from *file_path* and return it as a DataFrame.          Parameters`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Ingestion Rationale`** (1 nodes): `Inspect *file_path*'s extension and return the correct ingestor.          The fa`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Ingestion Rationale`** (1 nodes): `Register a new ingestor class for the given file extension.          Calling thi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Ingestion Rationale`** (1 nodes): `Return a sorted list of all currently registered file extensions.          Retur`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `NumPy Dependency`** (1 nodes): `numpy 1.26.4`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Dotenv Dependency`** (1 nodes): `python-dotenv 1.0.1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Git & GitHub`** (1 nodes): `Git + GitHub Version Control`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PipelineConfig` connect `Imputation Strategies` to `Data Cleaning Pipeline`, `ML Training Pipeline`, `DataCleaner Core`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Why does `DataCleaner` connect `DataCleaner Core` to `Data Cleaning Pipeline`, `ML Training Pipeline`, `Imputation Strategies`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Why does `clean_data_step()` connect `ML Training Pipeline` to `Data Cleaning Pipeline`, `Imputation Strategies`, `DataCleaner Core`?**
  _High betweenness centrality (0.026) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `Next.js Frontend Application` (e.g. with `File Icon SVG` and `Globe/Web Icon SVG`) actually correct?**
  _`Next.js Frontend Application` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `FastAPI REST API (Prediction Service)` (e.g. with `FastAPI 0.111.0` and `Uvicorn 0.30.1`) actually correct?**
  _`FastAPI REST API (Prediction Service)` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `DataCleaner` (e.g. with `PipelineConfig` and `clean_data_step()`) actually correct?**
  _`DataCleaner` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `api.py ====== Production FastAPI application for serving the House Price Predict`, `Singleton that owns the MLflow model lifecycle for this process.      Attributes`, `Resolve and load the best available model from the MLflow server.          Appli` to the rest of the system?**
  _96 weakly-connected nodes found - possible documentation gaps or missing edges._