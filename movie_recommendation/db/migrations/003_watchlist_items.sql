CREATE TABLE IF NOT EXISTS {{SCHEMA}}.watchlist_items (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    content_id VARCHAR(64) NOT NULL,
    content_type VARCHAR(16) NOT NULL CHECK (content_type IN ('movie', 'series')),
    title VARCHAR(255) NOT NULL,
    genres TEXT,
    rating NUMERIC(3,1) DEFAULT 0,
    cover_url TEXT,
    year INTEGER,
    director VARCHAR(255),
    added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_watchlist_items UNIQUE (user_id, content_id, content_type)
);

ALTER TABLE {{SCHEMA}}.watchlist_items
    ADD COLUMN IF NOT EXISTS added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE {{SCHEMA}}.watchlist_items
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_watchlist_items_user_type
    ON {{SCHEMA}}.watchlist_items (user_id, content_type, added_at DESC);
