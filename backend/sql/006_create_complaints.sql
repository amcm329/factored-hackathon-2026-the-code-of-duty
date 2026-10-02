CREATE TABLE IF NOT EXISTS complaints (
    complaint_id VARCHAR(30) PRIMARY KEY,
    creation_date TIMESTAMP NOT NULL,
    process_date DATE NOT NULL,
    customer_id VARCHAR(20) NOT NULL,
    case_type VARCHAR(30) NOT NULL,
    category VARCHAR(100) NOT NULL,
    subcategory VARCHAR(100),
    reception_channel VARCHAR(30) NOT NULL,
    affected_product_id VARCHAR(20),
    related_branch_id VARCHAR(20),
    origin_interaction_id VARCHAR(30),
    description TEXT NOT NULL,
    claimed_amount DECIMAL(15,2),
    currency VARCHAR(3),
    priority VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL,
    assigned_agent_id VARCHAR(20),
    assignment_date TIMESTAMP,
    first_response_date TIMESTAMP,
    resolution_date TIMESTAMP,
    closing_date TIMESTAMP,
    sla_breached BOOLEAN NOT NULL,
    resolution_days INTEGER,
    resolution TEXT,
    compensation_granted DECIMAL(15,2),
    resolution_satisfaction INTEGER,
    is_repeat_complainer BOOLEAN NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_complaints_customer_id
    ON complaints (customer_id);

CREATE INDEX IF NOT EXISTS idx_complaints_affected_product_id
    ON complaints (affected_product_id);

CREATE INDEX IF NOT EXISTS idx_complaints_origin_interaction_id
    ON complaints (origin_interaction_id);

CREATE INDEX IF NOT EXISTS idx_complaints_process_date
    ON complaints (process_date);
