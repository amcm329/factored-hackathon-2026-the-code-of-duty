CREATE TABLE IF NOT EXISTS call_transcripts (
    transcript_id VARCHAR(30) PRIMARY KEY,
    interaction_id VARCHAR(30) NOT NULL,
    process_date DATE NOT NULL,
    customer_id VARCHAR(20) NOT NULL,
    agent_id VARCHAR(20) NOT NULL,
    full_text TEXT NOT NULL,
    customer_text TEXT,
    agent_text TEXT,
    detected_language VARCHAR(10) NOT NULL,
    detected_accent VARCHAR(50),
    accent_confidence DECIMAL(3,2),
    detected_keywords VARCHAR(500),
    mentioned_entities TEXT,
    detected_intents VARCHAR(300),
    main_topics VARCHAR(300),
    transcription_model VARCHAR(50) NOT NULL,
    audio_quality VARCHAR(20),
    duration_seconds INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_call_transcripts_interaction_id
    ON call_transcripts (interaction_id);

CREATE INDEX IF NOT EXISTS idx_call_transcripts_customer_id
    ON call_transcripts (customer_id);

CREATE INDEX IF NOT EXISTS idx_call_transcripts_process_date
    ON call_transcripts (process_date);
