CREATE TABLE IF NOT EXISTS interaction_metrics (
    interaction_id UUID PRIMARY KEY,
    turn_count INTEGER NOT NULL DEFAULT 0,
    total_tokens BIGINT NOT NULL DEFAULT 0,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
