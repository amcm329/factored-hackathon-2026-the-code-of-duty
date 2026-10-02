CREATE TABLE IF NOT EXISTS call_center_interactions (
    interaction_id VARCHAR(30) PRIMARY KEY,
    interaction_date TIMESTAMP NOT NULL,
    process_date DATE NOT NULL,
    customer_id VARCHAR(20) NOT NULL,
    agent_id VARCHAR(20),
    interaction_type VARCHAR(30) NOT NULL,
    channel VARCHAR(30) NOT NULL,
    contact_reason VARCHAR(100) NOT NULL,
    reason_category VARCHAR(50) NOT NULL,
    duration_seconds INTEGER,
    wait_time_seconds INTEGER,
    was_resolved BOOLEAN,
    requires_followup BOOLEAN NOT NULL,
    detected_sentiment VARCHAR(20),
    sentiment_score DECIMAL(3,2),
    customer_detected_accent VARCHAR(50),
    agent_used_accent VARCHAR(50),
    was_escalated BOOLEAN NOT NULL,
    mentioned_products VARCHAR(200),
    has_transcript BOOLEAN NOT NULL,
    has_recording BOOLEAN NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_call_center_interactions_customer_id
    ON call_center_interactions (customer_id);

CREATE INDEX IF NOT EXISTS idx_call_center_interactions_process_date
    ON call_center_interactions (process_date);
