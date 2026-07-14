from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db 
from app.processing.search import build_query, build_normal_query  # <-- Import both

router = APIRouter(tags=["Search Engine"])

# ---------------------------------------------------------
# POWER SEARCH (Untouched - Uses LLM Expansion)
# ---------------------------------------------------------
@router.post("/search/power/")
def power_search_documents(
    query: str = Query(..., description="The search text from the user"),
    mode: str = Query("hybrid", description="Search strategy: 'vector', 'keyword', or 'hybrid'"),
    top_k: int = Query(5, description="Number of results to return"),
    db: Session = Depends(get_db)
):
    """
    POWER SEARCH: Expands the query using an LLM (HyDE) before performing the search.
    """
    valid_modes = ["vector", "keyword", "hybrid"]
    if mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Mode must be one of {valid_modes}")

    try:
        # Uses your original builder with the LLM call
        payload = build_query(query, mode=mode, top_k=top_k)
        
        sql_string = text(payload["sql"][mode])
        params = payload["params"]
        raw_results = db.execute(sql_string, params).mappings().all()
        
        return {
            "status": "success",
            "search_type": "power",
            "query": query,
            "expanded_query": payload.get("expanded_query"),
            "mode": mode,
            "results": [dict(row) for row in raw_results]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Power Search Error: {str(e)}")


# ---------------------------------------------------------
# NORMAL SEARCH (Direct Cosine Vector/Hybrid)
# ---------------------------------------------------------
@router.post("/search/normal/")
def normal_search_documents(
    query: str = Query(..., description="The exact search text from the user"),
    mode: str = Query("vector", description="Search strategy: 'vector', 'keyword', or 'hybrid'"),
    top_k: int = Query(5, description="Number of results to return"),
    db: Session = Depends(get_db)
):
    """
    NORMAL SEARCH: Fast search using the exact text provided, bypassing LLM query expansion.
    """
    valid_modes = ["vector", "keyword", "hybrid"]
    if mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Mode must be one of {valid_modes}")

    try:
        # Uses the new normal builder
        payload = build_normal_query(query, mode=mode, top_k=top_k)
        
        sql_string = text(payload["sql"][mode])
        params = payload["params"]
        raw_results = db.execute(sql_string, params).mappings().all()
        
        return {
            "status": "success",
            "search_type": "normal",
            "query": query,
            "mode": mode,
            "results": [dict(row) for row in raw_results]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Normal Search Error: {str(e)}")