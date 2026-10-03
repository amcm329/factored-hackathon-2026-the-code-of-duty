# FactoredAI

FactoredAI is a transaction-dispute assistant with a React frontend, FastAPI chat backend, worker service, Cognito authentication, PostgreSQL/RDS, private S3 evidence handling, OpenAI, Presidio, multilingual-E5 + FAISS retrieval, VAD features, Logistic Regression escalation, and CloudWatch metrics.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend reads its API and Cognito configuration from Vite environment variables.

## Chat backend

EC2 #1 runs:

```text
deploy/factored-ai.service
```

Runtime values are loaded from:

```text
/etc/factored-ai.env
```

## Worker

EC2 #2 runs:

```text
deploy/factored-worker.service
```

Runtime values are loaded from:

```text
/etc/factored-worker.env
```

No passwords, API keys, Cognito IDs, ALB DNS names, organizer credentials, or database credentials are stored in the repository.
