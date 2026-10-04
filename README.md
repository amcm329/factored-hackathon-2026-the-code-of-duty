# FactoredAI

FactoredAI is a transaction-dispute assistant with a React frontend, three separated EC2 application roles, Cognito authentication, PostgreSQL/RDS, private S3 evidence handling, OpenAI, Presidio, multilingual-E5 + FAISS retrieval, VAD features, Logistic Regression escalation, and CloudWatch metrics.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend reads its API and Cognito configuration from Vite environment variables.

## EC2 #1 — Chat backend

Runs:

```text
deploy/factored-ai.service
backend.app:app
```

Responsibilities:

```text
FastAPI chat/API
OpenAI API client
Cognito verification
RDS queries
business/dispute logic
sanitized/minimized OpenAI context
```

Runtime values are loaded from:

```text
/etc/factored-ai.env
```

EC2 #1 calls EC2 #2 through `WORKER_BASE_URL` and EC2 #3 through `RETRIEVAL_BASE_URL`.

## EC2 #2 — Worker / training / preprocessing

Runs:

```text
deploy/factored-worker.service
backend.worker_app:app
```

Responsibilities:

```text
PDF extraction and sanitization
VAD extraction
Logistic Regression inference
organizer S3 -> RDS ingestion
FAISS index construction
Logistic Regression training
heavy/offline preprocessing
```

Runtime values are loaded from:

```text
/etc/factored-worker.env
```

`python -m ml_pipeline.build_retrieval_index` builds `complaints.faiss` and `complaint_ids.json` on EC2 #2 and publishes them to private S3 for EC2 #3.

Required retrieval-asset values on EC2 #2:

```text
RUNTIME_ASSET_BUCKET=<private S3 bucket>
RETRIEVAL_ASSET_PREFIX=runtime-assets/retrieval
```

## EC2 #3 — Retrieval

Runs:

```text
deploy/factored-retrieval.service
retrieval.app:app
```

Responsibilities:

```text
multilingual-E5 query embeddings
FAISS similar-case search
```

Runtime values are loaded from:

```text
/etc/factored-retrieval.env
```

Before the retrieval API starts, EC2 #3 downloads the current FAISS index and complaint-ID mapping from private S3.

Required retrieval values on EC2 #3:

```text
RUNTIME_ASSET_BUCKET=<same private S3 bucket used by EC2 #2>
RETRIEVAL_ASSET_PREFIX=runtime-assets/retrieval
FAISS_INDEX_PATH=/opt/factored-ai/retrieval_assets/complaints.faiss
FAISS_MAPPING_PATH=/opt/factored-ai/retrieval_assets/complaint_ids.json
E5_MODEL=intfloat/multilingual-e5-base
```

## Runtime connections

```text
Frontend
   |
API Gateway -> internal ALB
   |
   +--> EC2 #1 Chat backend
   |       |
   |       +--> EC2 #2 Worker: evidence + escalation inference
   |       |
   |       +--> EC2 #3 Retrieval: E5 + FAISS live search
   |
   +--> EC2 #2 Worker: public evidence routes

EC2 #2 --build/publish--> private S3 retrieval assets --startup sync--> EC2 #3
```

No passwords, API keys, Cognito IDs, ALB DNS names, organizer credentials, database credentials, generated FAISS assets, or model artifacts are stored in the repository.
