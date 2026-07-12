import json
import urllib.request
import logging

logger = logging.getLogger(__name__)

# Ollama's url
OLLAMA_URL = "http://ollama:11434/api/generate"

MODEL_NAME = "qwen2:0.5b" 

def generate_hypothetical_document(query: str) -> str:
    """
    Uses a local LLM via Ollama to generate a hypothetical textbook answer 
    for the user's query. This is the core of the HyDE algorithm.
    """
    # The system prompt forces the LLM to write like a document in your database,
    # rather than acting like a chat assistant.
    prompt = (
        "You are an expert technical writer. Write a single, concise, factual, "
        "and highly technical textbook paragraph that directly answers the following "
        "search query. Do not include conversational filler, introductions, or conclusions. "
        f"Query: {query}"
    )

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3  # Low temperature forces deterministic, factual generation
        }
    }

    try:
        logger.info(f"[expansion] Requesting hypothetical document for: '{query}'")
        
        # Zero-dependency HTTP request using standard Python
        req = urllib.request.Request(
            OLLAMA_URL, 
            data=json.dumps(payload).encode('utf-8'), 
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode('utf-8'))
            hypothetical_doc = result.get("response", "").strip()
            
            logger.info(f"[expansion] HyDE Generated: {hypothetical_doc[:100]}...")
            return hypothetical_doc
            
    except Exception as e:
        logger.warning(f"[expansion] Local LLM failed: {e}. Falling back to original query.")
        return query