-- 002: per-thread chat history + automatic users.updated_at

-- 1. Chat messages belong to a session (thread). Old rows keep NULL.
ALTER TABLE aria.chat_messages
    ADD COLUMN IF NOT EXISTS session_id VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_chat_messages_user_session
    ON aria.chat_messages (user_id, session_id, created_at);

-- 2. Keep users.updated_at current on every update.
CREATE OR REPLACE FUNCTION aria.set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_updated_at ON aria.users;
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON aria.users
    FOR EACH ROW EXECUTE FUNCTION aria.set_updated_at();