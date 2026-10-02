CREATE TABLE IF NOT EXISTS transactions (
    transaction_id VARCHAR(30) PRIMARY KEY,
    transaction_date TIMESTAMP NOT NULL,
    process_date DATE NOT NULL,
    product_id VARCHAR(20) NOT NULL,
    customer_id VARCHAR(20) NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,
    transaction_category VARCHAR(50),
    amount DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    amount_usd DECIMAL(15,2),
    channel VARCHAR(30) NOT NULL,
    branch_id VARCHAR(20),
    merchant_name VARCHAR(150),
    merchant_category VARCHAR(50),
    transaction_country VARCHAR(50) NOT NULL,
    transaction_city VARCHAR(100),
    transaction_status VARCHAR(20) NOT NULL,
    response_code VARCHAR(10),
    is_fraud BOOLEAN NOT NULL,
    fraud_score DECIMAL(5,2),
    latitude DECIMAL(10,7),
    longitude DECIMAL(10,7)
);

CREATE INDEX IF NOT EXISTS idx_transactions_customer_id
    ON transactions (customer_id);

CREATE INDEX IF NOT EXISTS idx_transactions_product_id
    ON transactions (product_id);

CREATE INDEX IF NOT EXISTS idx_transactions_process_date
    ON transactions (process_date);
