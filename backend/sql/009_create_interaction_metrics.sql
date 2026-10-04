CREATE TABLE IF NOT EXISTS interaction_metrics (
    interaction_id UUID PRIMARY KEY,
    turn_count INTEGER NOT NULL DEFAULT 0,
    total_tokens BIGINT NOT NULL DEFAULT 0,
    successful_automated_resolution BOOLEAN,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE interaction_metrics
    ADD COLUMN IF NOT EXISTS successful_automated_resolution BOOLEAN;
