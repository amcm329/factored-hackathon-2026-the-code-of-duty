CREATE TABLE IF NOT EXISTS dispute_evidence (
    evidence_id UUID PRIMARY KEY,
    dispute_id UUID NULL,
    s3_key TEXT NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    processing_status VARCHAR(30) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dispute_evidence_dispute_id
    ON dispute_evidence (dispute_id);

CREATE INDEX IF NOT EXISTS idx_dispute_evidence_processing_status
    ON dispute_evidence (processing_status);
