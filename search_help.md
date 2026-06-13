# WhereTF — Backend Integration Guide

This document is for the backend engineer wiring the `processing` package
into the FastAPI + SQLAlchemy + PostgreSQL stack.

---

## Table of contents

1. [PostgreSQL setup](#1-postgresql-setup)
2. [SQLAlchemy models](#2-sqlalchemy-models)
3. [Indexing files (ingestion)](#3-indexing-files-ingestion)
4. [Searching (query side)](#4-searching-query-side)
5. [FastAPI route examples](#5-fastapi-route-examples)
6. [Performance & index tuning](#6-performance--index-tuning)
7. [End-to-end request flow](#7-end-to-end-request-flow)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. PostgreSQL setup

### 1.1 Enable pgvector

```sql
-- Run once per database, as a superuser.
CREATE EXTENSION IF NOT EXISTS vector;
```

### 1.2 Create the tables

```sql
CREATE TABLE IF NOT EXISTS file (
    id            SERIAL PRIMARY KEY,
    file_path     TEXT        NOT NULL UNIQUE,
    file_hash     VARCHAR(64) NOT NULL,
    mime_type     VARCHAR(128),
    last_modified TIMESTAMP,
    tags          TEXT[]      DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS file_content (
    id             SERIAL PRIMARY KEY,
    file_id        INTEGER     NOT NULL REFERENCES file(id) ON DELETE CASCADE,
    chunk_index    INTEGER     NOT NULL,
    content_text   TEXT        NOT NULL,

    -- 384-dim vector from sentence-transformers/all-MiniLM-L6-v2
    embedding      vector(384),

    -- Full-text search column: auto-generated from content_text.
    -- PostgreSQL fills this for you — never insert it from Python.
    keyword_tokens TSVECTOR
        GENERATED ALWAYS AS (to_tsvector('english', content_text)) STORED,

    UNIQUE (file_id, chunk_index)
);
```

### 1.3 Create indexes

```sql
-- ── Full-text search index (GIN) ─────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_fc_keyword
    ON file_content USING GIN (keyword_tokens);

-- ── Vector similarity index (HNSW — fastest for cosine, pgvector ≥ 0.5) ─
-- m=16 ef_construction=64 are sensible defaults for up to ~1 M vectors.
-- Increase ef_construction (e.g. 128) for higher recall at indexing cost.
CREATE INDEX IF NOT EXISTS idx_fc_embedding_hnsw
    ON file_content
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ── Alternatively, IVFFlat (older, less RAM) ─────────────────────────────
-- Use after you have at least a few thousand rows.
-- lists ≈ sqrt(row_count) is a common heuristic.
-- CREATE INDEX idx_fc_embedding_ivf
--     ON file_content
--     USING ivfflat (embedding vector_cosine_ops)
--     WITH (lists = 100);
```

---

## 2. SQLAlchemy models

```python
# app/models.py
from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY, Column, DateTime, ForeignKey,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class File(Base):
    __tablename__ = "file"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    file_path     = Column(Text,    nullable=False, unique=True)
    file_hash     = Column(String(64), nullable=False)
    mime_type     = Column(String(128))
    last_modified = Column(DateTime)
    tags          = Column(ARRAY(Text), default=list)

    chunks: list["FileContent"] = relationship(
        "FileContent", back_populates="file", cascade="all, delete-orphan"
    )


class FileContent(Base):
    __tablename__ = "file_content"
    __table_args__ = (UniqueConstraint("file_id", "chunk_index"),)

    id           = Column(Integer, primary_key=True, autoincrement=True)
    file_id      = Column(Integer, ForeignKey("file.id", ondelete="CASCADE"), nullable=False)
    chunk_index  = Column(Integer, nullable=False)
    content_text = Column(Text,    nullable=False)
    embedding    = Column(Vector(384))
    # keyword_tokens is a GENERATED ALWAYS column — omit from INSERT.

    file: "File" = relationship("File", back_populates="chunks")
```

> **Install pgvector's SQLAlchemy adapter:**
> ```bash
> pip install pgvector
> ```

---

## 3. Indexing files (ingestion)

```python
# app/services/indexer.py
from sqlalchemy.orm import Session
from sqlalchemy import select

from processing import process         # top-level pipeline
from app.models import File, FileContent


def index_path(root: str, db: Session, *, incremental: bool = True) -> dict:
    """
    Walk *root*, extract + embed all content, and persist to the DB.

    Set incremental=True (default) to skip files whose SHA-256 hash
    already exists in the database (unchanged files).
    """
    skip_hashes: set[str] = set()
    if incremental:
        skip_hashes = {
            row.file_hash
            for row in db.execute(select(File.file_hash)).scalars()
        }

    file_rows, content_rows = process(root, skip_hashes=skip_hashes)

    # ── Upsert File rows ──────────────────────────────────────────────────
    for fr in file_rows:
        existing = db.scalar(select(File).where(File.file_path == fr["file_path"]))
        if existing:
            # Re-index: drop old chunks, update metadata
            existing.file_hash     = fr["file_hash"]
            existing.mime_type     = fr["mime_type"]
            existing.last_modified = fr["last_modified"]
            existing.tags          = fr["tags"]
        else:
            db.add(File(**fr))

    db.flush()   # assign IDs before inserting FK rows

    # ── Insert FileContent rows ───────────────────────────────────────────
    for cr in content_rows:
        file_path = cr["file_path"]
        file_obj  = db.scalar(select(File).where(File.file_path == file_path))
        if file_obj is None:
            continue  # shouldn't happen, but guard anyway

        db.add(FileContent(
            file_id      = file_obj.id,
            chunk_index  = cr["chunk_index"],
            content_text = cr["content_text"],
            embedding    = cr["embedding"],
            # keyword_tokens: DO NOT pass — PostgreSQL generates it
        ))

    db.commit()
    return {"files": len(file_rows), "chunks": len(content_rows)}
```

---

## 4. Searching (query side)

### 4.1 Build the search payload

```python
from processing.search import build_query

payload = build_query(
    "async file processing python",
    mode="hybrid",    # "vector" | "keyword" | "hybrid"
    top_k=10,
    file_filter=None, # e.g. "/home/user/Documents/%" to restrict scope
)

# payload["vector"]       → list[float] (384 dims)
# payload["sql"]["hybrid"]→ raw SQL string
# payload["params"]       → {"query_vec": "...", "query_text": "...", "top_k": 10}
```

### 4.2 Execute the search

```python
from sqlalchemy import text
from sqlalchemy.orm import Session


def run_search(payload: dict, db: Session) -> list[dict]:
    mode = payload["mode"]
    sql  = payload["sql"][mode]

    rows = db.execute(
        text(sql),
        payload["params"],
    ).mappings().all()

    return [dict(row) for row in rows]
```

### 4.3 Raw SQL reference (copy-paste ready)

All three queries join `file_content` → `file` and return the same five columns:
`file_path`, `mime_type`, `tags`, `chunk_index`, `content_text`, `score`.

#### Vector search (semantic similarity)

```sql
SELECT
    f.file_path,
    f.mime_type,
    f.tags,
    fc.chunk_index,
    fc.content_text,
    1 - (fc.embedding <=> CAST(:query_vec AS vector)) AS score
FROM file_content fc
JOIN file f ON f.id = fc.file_id
ORDER BY fc.embedding <=> CAST(:query_vec AS vector) ASC
LIMIT :top_k;
```

**Bind parameters:** `:query_vec` (string form of 384-dim vector, e.g. `"[0.12, -0.34, …]"`), `:top_k` (int).

The `<=>` operator is **cosine distance** (0 = identical).
`1 - distance` converts it to cosine **similarity** (1 = identical) for the `score` column.

#### Keyword search (full-text)

```sql
SELECT
    f.file_path,
    f.mime_type,
    f.tags,
    fc.chunk_index,
    fc.content_text,
    ts_rank_cd(fc.keyword_tokens, plainto_tsquery('english', :query_text)) AS score
FROM file_content fc
JOIN file f ON f.id = fc.file_id
WHERE fc.keyword_tokens @@ plainto_tsquery('english', :query_text)
ORDER BY score DESC
LIMIT :top_k;
```

**Bind parameters:** `:query_text` (raw query string), `:top_k`.

`plainto_tsquery` handles natural-language input — no special syntax needed from users.
`@@` is the tsvector-match operator; it filters non-matching rows before ranking.

#### Hybrid search — Reciprocal Rank Fusion (recommended)

```sql
WITH vector_ranked AS (
    SELECT
        fc.id AS chunk_id,
        ROW_NUMBER() OVER (
            ORDER BY fc.embedding <=> CAST(:query_vec AS vector) ASC
        ) AS rank
    FROM file_content fc
    JOIN file f ON f.id = fc.file_id
    LIMIT 20   -- fetch 2× top_k candidates per arm
),
keyword_ranked AS (
    SELECT
        fc.id AS chunk_id,
        ROW_NUMBER() OVER (
            ORDER BY ts_rank_cd(
                fc.keyword_tokens,
                plainto_tsquery('english', :query_text)
            ) DESC
        ) AS rank
    FROM file_content fc
    JOIN file f ON f.id = fc.file_id
    WHERE fc.keyword_tokens @@ plainto_tsquery('english', :query_text)
    LIMIT 20
),
fused AS (
    SELECT
        COALESCE(v.chunk_id, k.chunk_id) AS chunk_id,
        COALESCE(1.0 / (60 + v.rank), 0)
        + COALESCE(1.0 / (60 + k.rank), 0) AS rrf_score
    FROM vector_ranked  v
    FULL OUTER JOIN keyword_ranked k ON k.chunk_id = v.chunk_id
)
SELECT
    f.file_path,
    f.mime_type,
    f.tags,
    fc.chunk_index,
    fc.content_text,
    fused.rrf_score AS score
FROM fused
JOIN file_content fc ON fc.id = fused.chunk_id
JOIN file         f  ON f.id  = fc.file_id
ORDER BY fused.rrf_score DESC
LIMIT :top_k;
```

**Bind parameters:** `:query_vec`, `:query_text`, `:top_k`.

**Why RRF works:** A result appearing at rank 3 in vector search AND rank 5 in keyword
search gets score `1/(60+3) + 1/(60+5) ≈ 0.031`, outranking a result that only appears
at rank 1 in one list (score `1/(60+1) ≈ 0.016`). Consensus between both retrieval
methods surfaces the most reliably relevant chunks.

---

## 5. FastAPI route examples

```python
# app/routers/search.py
from __future__ import annotations

from fastapi            import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy         import text
from sqlalchemy.orm     import Session
from typing             import Annotated, Literal

from app.database       import get_db
from app.services.indexer import index_path
from processing.search  import build_query

router = APIRouter(prefix="/api", tags=["search"])


# ── GET /api/search ──────────────────────────────────────────────────────────

@router.get("/search")
def search(
    q:           Annotated[str,  Query(description="Natural-language query")],
    mode:        Annotated[Literal["vector","keyword","hybrid"], Query()] = "hybrid",
    top_k:       Annotated[int,  Query(ge=1, le=100)] = 10,
    file_filter: Annotated[str | None, Query(
                     description="SQL LIKE pattern, e.g. /home/user/docs/%"
                 )] = None,
    db: Session = Depends(get_db),
):
    """
    Search indexed files.  Returns the top *top_k* matching chunks.

    - **vector**  — semantic / conceptual queries ("how to handle auth errors")
    - **keyword** — exact-term queries ("JWT", "ECONNREFUSED", acronyms)
    - **hybrid**  — best of both (default)
    """
    payload = build_query(q, mode=mode, top_k=top_k, file_filter=file_filter)
    sql     = payload["sql"][mode]
    rows    = db.execute(text(sql), payload["params"]).mappings().all()

    return {
        "query":   q,
        "mode":    mode,
        "results": [dict(r) for r in rows],
    }


# ── POST /api/index ──────────────────────────────────────────────────────────

@router.post("/index")
def trigger_index(
    path:               str,
    background_tasks:   BackgroundTasks,
    db: Session       = Depends(get_db),
):
    """
    Kick off background indexing of *path* (file or directory).
    Returns immediately; indexing runs asynchronously.
    """
    background_tasks.add_task(index_path, path, db)
    return {"status": "indexing started", "path": path}


# ── GET /api/search/vector-only ──────────────────────────────────────────────

@router.get("/search/vector-only")
def search_vector(
    q:     Annotated[str, Query()],
    top_k: Annotated[int, Query(ge=1, le=100)] = 10,
    db:    Session = Depends(get_db),
):
    """Pure cosine-similarity search.  Good for 'what is X about' queries."""
    payload = build_query(q, mode="vector", top_k=top_k)
    rows    = db.execute(
        text(payload["sql"]["vector"]), payload["params"]
    ).mappings().all()
    return {"query": q, "results": [dict(r) for r in rows]}


# ── GET /api/search/keyword-only ─────────────────────────────────────────────

@router.get("/search/keyword-only")
def search_keyword(
    q:     Annotated[str, Query()],
    top_k: Annotated[int, Query(ge=1, le=100)] = 10,
    db:    Session = Depends(get_db),
):
    """Full-text search only.  Best for exact terms, error codes, acronyms."""
    payload = build_query(q, mode="keyword", top_k=top_k)
    rows    = db.execute(
        text(payload["sql"]["keyword"]), payload["params"]
    ).mappings().all()
    return {"query": q, "results": [dict(r) for r in rows]}
```

### Response shape

Every search endpoint returns:

```json
{
  "query": "JWT authentication",
  "mode": "hybrid",
  "results": [
    {
      "file_path":    "/home/user/docs/auth_guide.pdf",
      "mime_type":    "application/pdf",
      "tags":         [],
      "chunk_index":  3,
      "content_text": "…the JWT is signed with RS256 and validated on every request…",
      "score":        0.0312
    }
  ]
}
```

---

## 6. Performance & index tuning

### HNSW search-time parameter

```python
# Set per-session before running vector queries for higher recall
# (at the cost of slightly slower queries).
db.execute(text("SET hnsw.ef_search = 100"))
```

Default is 40. For a local desktop app, 100–200 is fine.

### IVFFlat: set probes at query time

```python
# Only needed if you used IVFFlat instead of HNSW.
db.execute(text("SET ivfflat.probes = 10"))
```

### pgvector operators quick reference

| Operator | Distance metric | Index ops class |
|---|---|---|
| `<=>` | Cosine distance | `vector_cosine_ops` |
| `<->` | L2 (Euclidean) | `vector_l2_ops` |
| `<#>` | Negative inner product | `vector_ip_ops` |

Use `<=>` with unit-normalised embeddings (which WhereTF produces).

### Useful diagnostic queries

```sql
-- How many files and chunks are indexed?
SELECT
    (SELECT COUNT(*) FROM file)         AS total_files,
    (SELECT COUNT(*) FROM file_content) AS total_chunks;

-- Which file types are most common?
SELECT mime_type, COUNT(*) AS n
FROM file
GROUP BY mime_type
ORDER BY n DESC;

-- Largest files by chunk count
SELECT f.file_path, COUNT(fc.id) AS chunks
FROM file_content fc
JOIN file f ON f.id = fc.file_id
GROUP BY f.file_path
ORDER BY chunks DESC
LIMIT 20;

-- Verify the HNSW index exists
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'file_content';

-- Inspect a vector search plan (should show "Index Scan using idx_fc_embedding_hnsw")
EXPLAIN (ANALYZE, BUFFERS)
SELECT id FROM file_content
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;
```

---

## 7. End-to-end request flow

```
User types query in UI
        │
        ▼
GET /api/search?q=...&mode=hybrid&top_k=10
        │
        ▼
build_query(q, mode="hybrid", top_k=10)          ← processing.search
  ├── embed_query(q)                              ← sentence-transformers model
  │     └── returns list[float] (384 dims)
  ├── _sql_hybrid(top_k, ...)                     ← builds parametrised SQL
  └── returns SearchPayload {vector, sql, params}
        │
        ▼
db.execute(text(sql["hybrid"]), params)           ← SQLAlchemy Session
  ├── vector_ranked CTE  →  HNSW index scan
  ├── keyword_ranked CTE →  GIN  index scan
  ├── fused CTE          →  FULL OUTER JOIN + RRF score
  └── final SELECT       →  ORDER BY rrf_score DESC, LIMIT 10
        │
        ▼
Return JSON list of {file_path, chunk_index, content_text, score}
```

---

## 8. Troubleshooting

### `operator does not exist: vector <=> unknown`

The query vector is being passed as a plain Python list, not cast to `vector`.
Make sure the SQL contains `CAST(:query_vec AS vector)` — WhereTF's generated SQL
always does this, so the error usually means you wrote custom SQL without the cast.

### `column "keyword_tokens" does not exist`

The `GENERATED ALWAYS … STORED` syntax requires **PostgreSQL 12+**.
Run `SELECT version();` to confirm. If you're on an older version, replace the
generated column with a trigger or compute the tsvector in the application.

### Hybrid search returns zero results

The keyword arm of RRF requires at least one full-text match. If your query contains
only stopwords or very rare terms, `keyword_ranked` will be empty. The vector arm will
still return results; the hybrid score will just reflect vector rank only. This is
correct behaviour — RRF handles one empty arm gracefully via `COALESCE(…, 0)`.

### Slow vector queries (no HNSW index used)

Run `EXPLAIN ANALYZE` on your vector query. If you see `Seq Scan` instead of
`Index Scan using idx_fc_embedding_hnsw`, the planner decided a sequential scan is
cheaper (common when the table is small — under ~1,000 rows). This is fine and
actually faster at small scale. The HNSW index becomes beneficial above ~10,000 rows.

### `pgvector` not found

```bash
# Ubuntu / Debian
sudo apt install postgresql-16-pgvector   # adjust version number

# macOS (Homebrew)
brew install pgvector

# Then in psql:
CREATE EXTENSION vector;
```