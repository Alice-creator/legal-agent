-- Schema cho phần mềm quản lý corpus bản án.
-- Idempotent: chạy lại an toàn.

CREATE EXTENSION IF NOT EXISTS unaccent;   -- bỏ dấu khi search
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- fuzzy / substring trên filename
CREATE EXTENSION IF NOT EXISTS vector;     -- Phiên 2: pgvector (dense + halfvec)

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

-- nhãn loại bản án để lọc (điền ở E1): ban_an có tình tiết / quyet_dinh thủ tục
ALTER TABLE documents ADD COLUMN IF NOT EXISTS doc_type text;

-- ===== Phiên 2: SEARCH (embedding) =====
-- 1 doc -> nhiều chunk. Tìm trên chunk, trả về parent (documents) + dedupe.
CREATE TABLE IF NOT EXISTS chunks (
    id           serial PRIMARY KEY,
    doc_id       int NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section      text,                 -- noi_dung / nhan_dinh / quyet_dinh / full
    chunk_index  int,
    chunk_text   text,
    embedding    halfvec(1024),        -- AITeamVN; điền ở E2 (NULL tới lúc đó)
    tsv          tsvector              -- to_tsvector('simple', unaccent(chunk_text))
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON chunks USING gin(tsv);
-- HNSW build SAU khi embed xong (E2) cho nhanh:
--   SET maintenance_work_mem='2GB'; SET max_parallel_maintenance_workers=4;
--   CREATE INDEX idx_chunks_hnsw ON chunks USING hnsw (embedding halfvec_cosine_ops)
--     WITH (m=16, ef_construction=64);
