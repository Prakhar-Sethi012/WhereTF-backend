from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db 
from app.processing.search import build_query
router = APIRouter(tags=["Search Engine"])

@router.post("/search/")
def search_documents(
    query: str = Query(..., description="The search text from the user"),
    mode: str = Query("hybrid", description="Search strategy: 'vector', 'keyword', or 'hybrid'"),
    top_k: int = Query(5, description="Number of results to return"),
    db: Session = Depends(get_db)
):
    """
    Executes a high-performance search against the pgvector database.
    Defaults to Hybrid Search (Reciprocal Rank Fusion).
    """
    #  Validation
    valid_modes = ["vector", "keyword", "hybrid"]
    if mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Mode must be one of {valid_modes}")

    try:
        # embedding generation
        payload = build_query(query, mode=mode, top_k=top_k)
        
        # Exact sql string extraction
        sql_string = text(payload["sql"][mode])
        
        #  Extracting parameters
        params = payload["params"]
    
        raw_results = db.execute(sql_string, params).mappings().all()
        
        # Formatting and returning the results
        return {
            "status": "success",
            "query": query,
            "expanded_query": payload.get("expanded_query"),
            "mode": mode,
            "results": [dict(row) for row in raw_results]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search Engine Error: {str(e)}")


