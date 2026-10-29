-- ============================================================
-- ARIA RAG Schema  (rag_schema.sql)
-- Run as arya_migrator on arya_dev (and arya_test)
-- ============================================================
-- Prerequisites (run once as service admin, not arya_migrator):
--   CREATE EXTENSION IF NOT EXISTS vector;
-- ============================================================

-- Enable pgvector (IF NOT EXISTS is safe even if admin already ran it)
CREATE EXTENSION IF NOT EXISTS vector;

-- ------------------------------------------------------------
-- documents
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        TEXT        NOT NULL,                -- Clerk user ID, e.g. "user_2abc123XYZ"
    filename        TEXT        NOT NULL,                -- display-only, sanitised before storage
    file_type       TEXT        NOT NULL
                    CHECK (file_type IN ('pdf', 'txt', 'md')),
    content_sha256  TEXT        NOT NULL,                -- hex SHA-256 of raw bytes
    storage_key     TEXT        NOT NULL,                -- opaque path in the file store
    status          TEXT        NOT NULL DEFAULT 'uploaded'
                    CHECK (status IN ('uploaded', 'processing', 'ready', 'failed')),
    chunk_count     INTEGER,                             -- NULL until status = ready
    error_code      TEXT,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Prevent the same user uploading the same file twice
CREATE UNIQUE INDEX IF NOT EXISTS documents_owner_hash_idx
    ON documents (owner_id, content_sha256);

-- Fast lookup by owner (list_documents, ownership checks)
CREATE INDEX IF NOT EXISTS documents_owner_idx ON documents (owner_id);

-- ------------------------------------------------------------
-- chunks
-- Embedding dimension MUST match your model:
--   all-MiniLM-L6-v2  -> 384
--   text-embedding-3-small (OpenAI) -> 1536
-- Change 384 below if you use a different model.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chunks (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID        NOT NULL
                    REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INTEGER     NOT NULL,
    text            TEXT        NOT NULL,
    token_count     INTEGER     NOT NULL DEFAULT 0,
    page            INTEGER,
    section         TEXT,
    embedding       vector(384) NOT NULL,
    UNIQUE (document_id, chunk_index)
);

-- ANN index using cosine similarity (matches InMemoryRagRepository._cosine)
-- lists=100 is a safe starting value; tune upward as the table grows.
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ------------------------------------------------------------
-- Verify
-- ------------------------------------------------------------
SELECT
    c.table_name,
    c.column_name,
    c.data_type,
    c.column_default
FROM information_schema.columns c
WHERE c.table_schema = 'public'
  AND c.table_name IN ('documents', 'chunks')
ORDER BY c.table_name, c.ordinal_position;
