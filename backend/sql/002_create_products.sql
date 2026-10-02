CREATE TABLE IF NOT EXISTS products (
    product_id VARCHAR(20) PRIMARY KEY,
    customer_id VARCHAR(20) NOT NULL,
    product_type VARCHAR(50) NOT NULL,
    product_number VARCHAR(30) NOT NULL UNIQUE,
    currency VARCHAR(3) NOT NULL,
    current_balance DECIMAL(15,2) NOT NULL,
    credit_limit DECIMAL(15,2),
    interest_rate DECIMAL(5,2),
    opening_date DATE NOT NULL,
    expiration_date DATE,
    opening_branch_id VARCHAR(20) NOT NULL,
    product_status VARCHAR(20) NOT NULL,
    opening_channel VARCHAR(30) NOT NULL,
    has_linked_app BOOLEAN NOT NULL,
    days_past_due INTEGER,
    last_transaction_date TIMESTAMP,
    last_updated TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_products_customer_id
    ON products (customer_id);
