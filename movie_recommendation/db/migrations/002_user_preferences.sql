CREATE TABLE IF NOT EXISTS {{SCHEMA}}.user_preferences (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    content_id VARCHAR(64) NOT NULL,
    content_type VARCHAR(16) NOT NULL CHECK (content_type IN ('movie', 'series')),
    title VARCHAR(255) NOT NULL,
    genres TEXT,
    rating NUMERIC(3,1) DEFAULT 0,
    year INTEGER,
    director VARCHAR(255),
    actors TEXT,
    cover_url TEXT,
    comment TEXT,
    source VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_preferences UNIQUE (user_id, content_id, content_type)
);

ALTER TABLE {{SCHEMA}}.user_preferences
    ADD COLUMN IF NOT EXISTS comment TEXT;

ALTER TABLE {{SCHEMA}}.user_preferences
    ADD COLUMN IF NOT EXISTS source VARCHAR(64);

ALTER TABLE {{SCHEMA}}.user_preferences
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE {{SCHEMA}}.user_preferences
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_user_preferences_user_type
    ON {{SCHEMA}}.user_preferences (user_id, content_type, created_at DESC);
