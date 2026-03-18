CREATE TABLE IF NOT EXISTS {{SCHEMA}}.recommendation_snapshots (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL DEFAULT 'user_default',
    content_type VARCHAR(16) NOT NULL CHECK (content_type IN ('movie', 'series')),
    signature VARCHAR(128),
    snapshot_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    count_weights JSONB,
    recommend_reasons_summary JSONB,
    rotation_count INTEGER DEFAULT 0,
    algorithm_version VARCHAR(64),
    refresh_reason VARCHAR(64),
    candidate_pool_size INTEGER,
    generated_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE {{SCHEMA}}.recommendation_snapshots
    ADD COLUMN IF NOT EXISTS snapshot_data JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE {{SCHEMA}}.recommendation_snapshots
    ADD COLUMN IF NOT EXISTS count_weights JSONB;

ALTER TABLE {{SCHEMA}}.recommendation_snapshots
    ADD COLUMN IF NOT EXISTS recommend_reasons_summary JSONB;

ALTER TABLE {{SCHEMA}}.recommendation_snapshots
    ADD COLUMN IF NOT EXISTS rotation_count INTEGER DEFAULT 0;

ALTER TABLE {{SCHEMA}}.recommendation_snapshots
    ADD COLUMN IF NOT EXISTS algorithm_version VARCHAR(64);

ALTER TABLE {{SCHEMA}}.recommendation_snapshots
    ADD COLUMN IF NOT EXISTS refresh_reason VARCHAR(64);

ALTER TABLE {{SCHEMA}}.recommendation_snapshots
    ADD COLUMN IF NOT EXISTS candidate_pool_size INTEGER;

ALTER TABLE {{SCHEMA}}.recommendation_snapshots
    ADD COLUMN IF NOT EXISTS generated_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE {{SCHEMA}}.recommendation_snapshots
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_recommendation_snapshots_type_generated
    ON {{SCHEMA}}.recommendation_snapshots (content_type, generated_time DESC);

CREATE INDEX IF NOT EXISTS idx_recommendation_snapshots_user_type
    ON {{SCHEMA}}.recommendation_snapshots (user_id, content_type, created_at DESC);
