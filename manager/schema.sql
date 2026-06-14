-- Schema cho phần mềm quản lý corpus bản án.
-- Idempotent: chạy lại an toàn.

CREATE EXTENSION IF NOT EXISTS unaccent;   -- bỏ dấu khi search
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- fuzzy / substring trên filename
-- CREATE EXTENSION IF NOT EXISTS vector;  -- Phiên 2: pgvector cho embedding

CREATE TABLE IF NOT EXISTS documents (
    id                serial PRIMARY KEY,
    filename          text UNIQUE NOT NULL,
    route             text,              -- clean / glued / scanned
    full_text         text,
    bucket            text,              -- clean / minor / reocr (tính khi ingest)
    reocr_reason      text,              -- empty / legacy_char / low_density / legacy_body
    legacy_density    real,
    diacritic_density real,
    char_count        int,
    page_count        int,               -- để null ở P0 (backfill sau nếu cần)
    tsv               tsvector,          -- to_tsvector('simple', unaccent(full_text))
    updated_at        timestamptz DEFAULT now()
    -- embedding      vector(1024)       -- Phiên 2
);

CREATE INDEX IF NOT EXISTS idx_docs_tsv        ON documents USING gin(tsv);
CREATE INDEX IF NOT EXISTS idx_docs_fname_trgm ON documents USING gin(filename gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_docs_bucket     ON documents(bucket);
CREATE INDEX IF NOT EXISTS idx_docs_route      ON documents(route);
