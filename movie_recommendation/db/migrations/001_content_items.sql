CREATE TABLE IF NOT EXISTS {{SCHEMA}}.content_items (
    id BIGSERIAL PRIMARY KEY,
    source_item_id VARCHAR(64) NOT NULL,
    content_type VARCHAR(16) NOT NULL CHECK (content_type IN ('movie', 'series')),
    title VARCHAR(255) NOT NULL,
    original_title VARCHAR(255),
    genres TEXT,
    rating NUMERIC(3,1) DEFAULT 0,
    year INTEGER,
    director VARCHAR(255),
    actors TEXT,
    cover_url TEXT,
    plot TEXT,
    popularity NUMERIC(10,4) DEFAULT 0,
    region VARCHAR(100),
    language VARCHAR(100),
    duration VARCHAR(100),
    episodes VARCHAR(100),
    status VARCHAR(100),
    raw_source JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_content_items UNIQUE (source_item_id, content_type)
);

CREATE INDEX IF NOT EXISTS idx_content_items_type_rating
    ON {{SCHEMA}}.content_items (content_type, rating DESC);

CREATE INDEX IF NOT EXISTS idx_content_items_type_year
    ON {{SCHEMA}}.content_items (content_type, year DESC);
