CREATE TABLE IF NOT EXISTS {{SCHEMA}}.negative_feedback (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    content_id VARCHAR(64) NOT NULL,
    content_type VARCHAR(16) NOT NULL CHECK (content_type IN ('movie', 'series')),
    reason TEXT,
    expire_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE {{SCHEMA}}.negative_feedback
    ADD COLUMN IF NOT EXISTS expire_at TIMESTAMP NULL;

ALTER TABLE {{SCHEMA}}.negative_feedback
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE {{SCHEMA}}.negative_feedback
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_negative_feedback_user_type
    ON {{SCHEMA}}.negative_feedback (user_id, content_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_negative_feedback_content
    ON {{SCHEMA}}.negative_feedback (content_id, content_type);
