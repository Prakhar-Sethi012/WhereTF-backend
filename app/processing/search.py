"""
search.py
---------
Query-side search utilities for WhereTF.

This module is the mirror of pipeline.py: instead of indexing files it
turns a user query into everything the database layer needs to run a
search.

Three search modes are supported, all composable:

    VECTOR   – semantic similarity via pgvector cosine distance
    KEYWORD  – full-text search via PostgreSQL tsvector / tsquery
    HYBRID   – reciprocal-rank fusion of both lists (best for most UIs)

All functions return plain Python dicts / lists — no SQLAlchemy, no DB
connections anywhere in this file.  The backend engineer only needs to
paste the returned SQL + parameters into their session.execute() call.

Quick-start
~~~~~~~~~~~
    from processing.search import build_query

    payload = build_query("machine learning time series", mode="hybrid", top_k=10)

    # payload["vector"]  → list[float] (384 dims) — bind to :query_vec
    # payload["query"]   → str                    — bind to :query_text
    # payload["sql"]     → dict with keys vector / keyword / hybrid
    # payload["params"]  → dict ready for session.execute(text(sql), params)
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from .cache import ModelCache
from .expansion import generate_hypothetical_document

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

SearchMode = Literal["vector", "keyword", "hybrid"]

SearchPayload = dict[str, Any]
"""
{
    "query"  : str              – original user query string
    "vector" : list[float]      – 384-dim embedding of the query
    "mode"   : SearchMode
    "top_k"  : int
    "sql"    : {
        "vector"  : str,        – SQL for vector-only search
        "keyword" : str,        – SQL for keyword-only search
        "hybrid"  : str,        – SQL for hybrid RRF search
    }
    "params" : dict             – bind parameters for the chosen mode's SQL
}
"""


# ---------------------------------------------------------------------------
# Step 1 — embed the query
# ---------------------------------------------------------------------------

def embed_query(query: str) -> list[float]:
    """
    Encode a single query string with the same model used at index time.

    The vector is unit-normalised so cosine similarity == dot product,
    matching the normalisation applied during ingestion.

    Parameters
    ----------
    query : str
        Raw user query.  Preprocessing (lowercasing, stopword removal)
        is intentionally skipped — the model handles it internally.

    Returns
    -------
    list[float]
        384-dimensional unit vector, ready to be cast to pgvector's
        ``vector`` type.
    """
    model = ModelCache.get_encoder()
    vec = model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return vec[0].tolist()


# ---------------------------------------------------------------------------
# Step 2 — build SQL for each search mode
# ---------------------------------------------------------------------------

# ── 2a. Vector search ───────────────────────────────────────────────────────

def _sql_vector(top_k: int, file_filter: bool) -> str:
    """
    Pure cosine-similarity search using pgvector's <=> operator.

    The <=> operator returns cosine *distance* (0 = identical, 2 = opposite)
    so ORDER BY ASC gives the most similar results first.

    An HNSW or IVFFlat index on FileContent.embedding makes this O(log N).
    """
    where = "AND f.file_path LIKE :file_filter" if file_filter else ""
    return f"""
SELECT
    f.file_path,
    f.mime_type,
    f.tags,
    fc.chunk_index,
    fc.content_text,
    1 - (fc.embedding <=> CAST(:query_vec AS vector)) AS score
FROM file_content fc
JOIN files f ON f.id = fc.file_id
WHERE 1=1 {where}
ORDER BY fc.embedding <=> CAST(:query_vec AS vector) ASC
LIMIT :top_k;
""".strip()


# ── 2b. Keyword (full-text) search ──────────────────────────────────────────

def _sql_keyword(top_k: int, file_filter: bool) -> str:
    """
    PostgreSQL full-text search against the pre-computed tsvector column
    (keyword_tokens).

    ts_rank_cd weights term density and cover density, which works well
    for document search.  The plainto_tsquery() function handles natural
    language queries without requiring the user to know tsquery syntax.
    """
    where = "AND f.file_path LIKE :file_filter" if file_filter else ""
    return f"""
SELECT
    f.file_path,
    f.mime_type,
    f.tags,
    fc.chunk_index,
    fc.content_text,
    ts_rank_cd(fc.keyword_tokens, plainto_tsquery('english', :query_text)) AS score
FROM file_content fc
JOIN files f ON f.id = fc.file_id
WHERE fc.keyword_tokens @@ plainto_tsquery('english', :query_text) {where}
ORDER BY score DESC
LIMIT :top_k;
""".strip()


# ── 2c. Hybrid search (Reciprocal Rank Fusion) ──────────────────────────────

def _sql_hybrid(top_k: int, file_filter: bool, rrf_k: int = 60) -> str:
    """
    Hybrid search combining vector and keyword results via Reciprocal Rank
    Fusion (RRF).

    RRF score = 1/(k + rank_vector) + 1/(k + rank_keyword)

    rrf_k=60 is the standard value from the original RRF paper (Cormack
    et al., 2009).  It prevents very high-ranked results from dominating
    too strongly.

    Both sub-queries fetch top_k * 2 candidates so the fusion pool is
    large enough to surface good cross-list results before the final LIMIT.

    Chunks that appear in only one list still score; they just score lower
    than chunks that appear in both.
    """
    pool = top_k * 2
    where = "AND f.file_path LIKE :file_filter" if file_filter else ""
    return f"""
WITH vector_ranked AS (
    SELECT
        fc.id                                                          AS chunk_id,
        ROW_NUMBER() OVER (
            ORDER BY fc.embedding <=> CAST(:query_vec AS vector) ASC
        )                                                              AS rank
    FROM file_content fc
    JOIN files f ON f.id = fc.file_id
    WHERE 1=1 {where}
    LIMIT {pool}
),
keyword_ranked AS (
    SELECT
        fc.id                                                          AS chunk_id,
        ROW_NUMBER() OVER (
            ORDER BY ts_rank_cd(
                fc.keyword_tokens,
                plainto_tsquery('english', :query_text)
            ) DESC
        )                                                              AS rank
    FROM file_content fc
    JOIN files f ON f.id = fc.file_id
    WHERE fc.keyword_tokens @@ plainto_tsquery('english', :query_text) {where}
    LIMIT {pool}
),
fused AS (
    SELECT
        COALESCE(v.chunk_id, k.chunk_id)                              AS chunk_id,
        COALESCE(1.0 / ({rrf_k} + v.rank), 0)
        + COALESCE(1.0 / ({rrf_k} + k.rank), 0)                      AS rrf_score
    FROM vector_ranked  v
    FULL OUTER JOIN keyword_ranked k ON k.chunk_id = v.chunk_id
)
SELECT
    f.file_path,
    f.mime_type,
    f.tags,
    fc.chunk_index,
    fc.content_text,
    fused.rrf_score                                                    AS score
FROM fused
JOIN file_content fc ON fc.id = fused.chunk_id
JOIN files         f  ON f.id  = fc.file_id
ORDER BY fused.rrf_score DESC
LIMIT :top_k;
""".strip()


# ---------------------------------------------------------------------------
# Step 3 — public builder
# ---------------------------------------------------------------------------

def build_query(
    query: str,
    *,
    mode: SearchMode = "hybrid",
    top_k: int = 10,
    file_filter: str | None = None,
    rrf_k: int = 60,
) -> SearchPayload:
    """
    Turn a user query string into a ready-to-execute search payload.

    Parameters
    ----------
    query : str
        Natural-language search query from the user.
    mode : "vector" | "keyword" | "hybrid"
        Search strategy.  ``"hybrid"`` (default) works best for most
        queries; use ``"keyword"`` for exact-term or acronym lookups;
        use ``"vector"`` for conceptual / semantic queries.
    top_k : int
        Maximum number of results to return.  Default 10.
    file_filter : str | None
        Optional SQL LIKE pattern to restrict results to a subtree, e.g.
        ``"/home/user/Documents/%"`` or ``"%.py"``.
        Pass ``None`` (default) to search all files.
    rrf_k : int
        RRF constant.  60 is the standard value; increase to 120 to give
        lower-ranked results more weight (flatter distribution).

    Returns
    -------
    SearchPayload
        A dict containing:

        ``query``   – original query string
        ``vector``  – 384-dim list[float] embedding of the query
        ``mode``    – the requested mode
        ``top_k``   – the limit
        ``sql``     – dict with keys ``"vector"``, ``"keyword"``, ``"hybrid"``
                      containing the raw SQL strings for each mode
        ``params``  – bind-parameter dict for the *chosen* mode's SQL,
                      ready for ``session.execute(text(sql), params)``

    Example
    -------
    ::

        payload = build_query("authentication JWT", mode="hybrid", top_k=5)

        from sqlalchemy import text
        rows = db.execute(
            text(payload["sql"]["hybrid"]),
            payload["params"],
        ).mappings().all()
    """
    logger.info("[search] Building %s query: %r (top_k=%d)", mode, query, top_k)

    # ---> NEW: Intercept and Expand <---
    # Only generate a hypothetical document if we are doing vector math
    if mode in ("vector", "hybrid"):
        expanded_text_for_vector = generate_hypothetical_document(query)
    else:
        expanded_text_for_vector = query

    # 1. Embed (Using the HYPOTHETICAL document)
    vector = embed_query(expanded_text_for_vector)

    # 2. Build SQL variants
    has_filter = file_filter is not None
    sql = {
        "vector":  _sql_vector(top_k, has_filter),
        "keyword": _sql_keyword(top_k, has_filter),
        "hybrid":  _sql_hybrid(top_k, has_filter, rrf_k=rrf_k),
    }

    # 3. Build bind parameters
    params: dict[str, Any] = {"top_k": top_k}

    needs_vec  = mode in ("vector", "hybrid")
    needs_text = mode in ("keyword", "hybrid")

    if needs_vec:
        params["query_vec"] = str(vector)

    if needs_text:
        params["query_text"] = query

    if has_filter:
        params["file_filter"] = file_filter

    return SearchPayload(
        query=query,
        expanded_query=expanded_text_for_vector,
        vector=vector,
        mode=mode,
        top_k=top_k,
        sql=sql,
        params=params,
    )

# ---------------------------------------------------------------------------
# Convenience: just get the vector (for callers that run their own SQL)
# ---------------------------------------------------------------------------

def query_vector(query: str) -> list[float]:
    """
    Minimal helper — returns only the 384-dim embedding of *query*.

    Use this when you handle the SQL yourself and just need the vector::

        vec = query_vector("find python async examples")
        # hand vec to your ORM / raw psycopg2 cursor
    """
    return embed_query(query)