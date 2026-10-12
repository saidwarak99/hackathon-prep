-- schema_datasets.sql - Dynamic Dataset Ingestion & Isolation Schema
-- Creates metadata and record storage tables for user-uploaded datasets.
-- Non-destructive migration preserving existing baseline synthetic tables.

CREATE TABLE IF NOT EXISTS datasets (
    dataset_id VARCHAR(64) PRIMARY KEY,
    restaurant_id VARCHAR(64) NOT NULL DEFAULT 'default_restaurant',
    dataset_name VARCHAR(255) NOT NULL,
    detected_section VARCHAR(64) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    upload_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ingestion_status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    row_count INTEGER NOT NULL DEFAULT 0,
    schema_mapping JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    data_origin VARCHAR(64) NOT NULL DEFAULT 'UPLOADED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dataset_records (
    record_id BIGSERIAL PRIMARY KEY,
    dataset_id VARCHAR(64) NOT NULL REFERENCES datasets(dataset_id) ON DELETE CASCADE,
    restaurant_id VARCHAR(64) NOT NULL DEFAULT 'default_restaurant',
    section VARCHAR(64) NOT NULL,
    record_key VARCHAR(128),
    data JSONB NOT NULL,
    row_index INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Fast lookup indexes
CREATE INDEX IF NOT EXISTS idx_datasets_content_hash ON datasets(content_hash);
CREATE INDEX IF NOT EXISTS idx_datasets_restaurant_id ON datasets(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_datasets_status ON datasets(ingestion_status);
CREATE INDEX IF NOT EXISTS idx_dataset_records_dataset_section ON dataset_records(dataset_id, section);
CREATE INDEX IF NOT EXISTS idx_dataset_records_dataset_id ON dataset_records(dataset_id);
CREATE INDEX IF NOT EXISTS idx_dataset_records_section ON dataset_records(section);
