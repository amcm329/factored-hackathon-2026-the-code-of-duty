CREATE TABLE IF NOT EXISTS dispute_cases (
    dispute_id UUID PRIMARY KEY,
    customer_id VARCHAR(20) NOT NULL,
    transaction_id VARCHAR(30) NOT NULL,
    product_id VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL,
    reason TEXT NOT NULL,
    claimed_amount DECIMAL(15,2),
    currency VARCHAR(3),
    escalation_probability DECIMAL(6,5),
    requires_human_review BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dispute_cases_customer_id
    ON dispute_cases (customer_id);

CREATE INDEX IF NOT EXISTS idx_dispute_cases_transaction_id
    ON dispute_cases (transaction_id);

CREATE INDEX IF NOT EXISTS idx_dispute_cases_status
    ON dispute_cases (status);
