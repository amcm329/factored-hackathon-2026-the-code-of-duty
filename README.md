# Hermes — FactoredAI Hackathon 2026

## Purpose

Hermes is a multilingual banking-dispute assistant. It authenticates customers, explains transactions, supports evidence, retrieves similar historical cases, resolves suitable requests with AI, and escalates higher-risk cases for human review.

## Architecture

```text
Customer
   |
   v
AWS Amplify — React/Vite frontend
   |
   v
Amazon Cognito — authentication
   |
   v
API Gateway -> VPC Link -> Internal ALB
   |
   +--> EC2 #1 — Chat/API backend
   |      +--> OpenAI
   |      +--> Amazon RDS PostgreSQL
   |      +--> Secrets Manager
   |      +--> EC2 #2 escalation/evidence
   |      +--> EC2 #3 retrieval
   |
   +--> EC2 #2 — Worker
          +--> S3 evidence/assets
          +--> VAD + Logistic Regression

EC2 #3 — Retrieval
   +--> multilingual-E5 embeddings
   +--> FAISS similar-case search
   +--> S3 retrieval assets

CloudWatch receives operational and model-quality metrics.
```

## Main runtime flow

```text
Login -> Chat -> Understand request -> Retrieve context
      -> Resolve automatically OR select transaction
      -> Create dispute -> Escalate when human review is required
```

## Main APIs

| Service | Important endpoints |
|---|---|
| EC2 #1 | `/health`, `/messages/welcome`, `/transactions`, `/chat`, `/disputes` |
| EC2 #2 | `/evidence/presign`, `/evidence/process`, `/internal/evidence/read`, `/internal/escalation/predict` |
| EC2 #3 | `/internal/retrieval/search` |

## Repository files

### Root

| File | Meaning |
|---|---|
| `.gitignore` | Excludes generated, local, secret, and temporary repository files. |
| `amplify.yml` | Builds and publishes the React frontend through AWS Amplify. |
| `LICENSE` | Defines legal permissions and restrictions for repository source code. |
| `README.md` | Documents project purpose, architecture, deployment, and repository organization. |
| `requirements/backend.txt` | Lists Python dependencies shared across backend, worker, and retrieval. |

### `backend/` — EC2 #1 and EC2 #2

| File | Meaning |
|---|---|
| `backend/app.py` | Runs customer chat, transactions, disputes, and core orchestration API. |
| `backend/auth.py` | Validates Cognito JWTs and extracts authenticated customer context securely. |
| `backend/database.py` | Reads and writes customers, transactions, disputes, evidence, metrics. |
| `backend/escalation.py` | Builds features and predicts whether human escalation is required. |
| `backend/evidence.py` | Uploads, extracts, sanitizes, and retrieves customer PDF evidence. |
| `backend/language.py` | Detects supported customer language using the packaged language model. |
| `backend/metrics.py` | Publishes operational resolution and escalation metrics into CloudWatch. |
| `backend/openai_client.py` | Sends minimized conversation context to OpenAI for responses. |
| `backend/privacy.py` | Detects and anonymizes sensitive personal information before model usage. |
| `backend/retrieval_client.py` | Calls private retrieval service for similar historical complaint cases. |
| `backend/secrets.py` | Loads runtime credentials, prompts, policies, and database configuration. |
| `backend/vad.py` | Extracts valence, arousal, dominance signals from customer language. |
| `backend/worker_app.py` | Exposes worker endpoints for evidence processing and escalation inference. |
| `backend/worker_client.py` | Calls private worker endpoints from the main backend service. |
| `backend/__init__.py` | Marks backend directory as an importable Python package. |

### `backend/sql/` — PostgreSQL schema

| File | Meaning |
|---|---|
| `001_create_customers.sql` | Creates customer master table and customer demographic attributes. |
| `002_create_products.sql` | Creates banking products table linked to customer relationships. |
| `003_create_transactions.sql` | Creates transaction table used for browsing and dispute selection. |
| `004_create_call_center_interactions.sql` | Creates historical customer-service interaction records for analysis. |
| `005_create_call_transcripts.sql` | Creates transcript table containing historical interaction conversation text. |
| `006_create_complaints.sql` | Creates historical complaints and claims used for retrieval. |
| `007_create_dispute_cases.sql` | Creates Hermes-generated dispute cases and their lifecycle fields. |
| `008_create_dispute_evidence.sql` | Creates evidence metadata linked to Hermes dispute cases. |
| `009_create_interaction_metrics.sql` | Creates runtime interaction metrics for monitoring automated resolution quality. |

### `frontend/` — Amplify React application

| File | Meaning |
|---|---|
| `frontend/api.js` | Wraps authenticated frontend requests to Hermes backend API endpoints. |
| `frontend/auth.js` | Handles Cognito sign-in, tokens, sessions, and customer logout. |
| `frontend/index.html` | Provides HTML entry document loaded by the Vite application. |
| `frontend/package.json` | Defines React dependencies, Vite scripts, and Node requirements. |
| `frontend/package-lock.json` | Locks exact frontend dependency versions for reproducible application builds. |
| `frontend/src/main.jsx` | Implements landing, chat, transactions, disputes, and interface behavior. |
| `frontend/src/styles.css` | Defines responsive Hermes visual design, layout, and component styling. |
| `frontend/src/assets/hermes-icon.png` | Raster Hermes icon used by the frontend visual interface. |
| `frontend/src/assets/hermes-icon.svg` | Vector Hermes icon supporting scalable frontend visual rendering. |
| `frontend/src/assets/hermes-logo.png` | Raster Hermes logo used in branded frontend presentation. |
| `frontend/src/assets/hermes-logo.svg` | Vector Hermes logo providing scalable branded interface presentation. |

### `ml_pipeline/` — training and data preparation

| File | Meaning |
|---|---|
| `ml_pipeline/ingest_s3_to_rds.py` | Loads organizer S3 datasets into normalized PostgreSQL database tables. |
| `ml_pipeline/train_escalation_model.py` | Trains Logistic Regression escalation model using engineered customer features. |
| `ml_pipeline/build_retrieval_index.py` | Builds E5 embeddings and FAISS indexes from historical complaints. |
| `ml_pipeline/__init__.py` | Marks machine-learning pipeline directory as an importable package. |

### `retrieval/` — EC2 #3

| File | Meaning |
|---|---|
| `retrieval/app.py` | Exposes private API endpoint for similar-case retrieval requests. |
| `retrieval/retrieval.py` | Embeds queries and searches country-specific FAISS complaint indexes. |
| `retrieval/sync_assets.py` | Downloads current retrieval index assets from private S3 storage. |
| `retrieval/__init__.py` | Marks retrieval directory as an importable Python package. |

### `deploy/` — Linux services

| File | Meaning |
|---|---|
| `deploy/factored-ai.service` | Runs EC2 #1 FastAPI chat backend through systemd. |
| `deploy/factored-worker.service` | Runs EC2 #2 evidence and escalation worker service. |
| `deploy/factored-retrieval.service` | Synchronizes assets and runs EC2 #3 retrieval service. |

### `performance_validation/`

| File | Meaning |
|---|---|
| `performance_validation/evaluate_hackathon.py` | Runs end-to-end evaluation, latency, safety, and CloudWatch reporting. |

## Core technologies

React, Vite, FastAPI, PostgreSQL/RDS, Cognito, S3, Secrets Manager, OpenAI, Presidio, spaCy, multilingual-E5, FAISS, VAD features, Logistic Regression, CloudWatch, API Gateway, ALB, and EC2.

## Security design

Secrets remain outside the repository. Cognito authenticates customers, private services communicate internally, evidence is sanitized before model use, and OpenAI receives minimized context rather than raw banking records.
