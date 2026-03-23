CREATE TABLE IF NOT EXISTS {{SCHEMA}}.admin_users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP NULL
);

ALTER TABLE {{SCHEMA}}.admin_users
    ADD COLUMN IF NOT EXISTS username VARCHAR(64);

ALTER TABLE {{SCHEMA}}.admin_users
    ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);

ALTER TABLE {{SCHEMA}}.admin_users
    ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);

ALTER TABLE {{SCHEMA}}.admin_users
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active';

ALTER TABLE {{SCHEMA}}.admin_users
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE {{SCHEMA}}.admin_users
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE {{SCHEMA}}.admin_users
    ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_admin_users_username'
    ) THEN
        ALTER TABLE {{SCHEMA}}.admin_users
            ADD CONSTRAINT uq_admin_users_username UNIQUE (username);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_admin_users_status
    ON {{SCHEMA}}.admin_users (status);
