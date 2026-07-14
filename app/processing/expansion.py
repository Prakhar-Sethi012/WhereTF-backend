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

    prompt = (
        "You are an expert search engine query expander. Your task is to take a short user query "
        "and generate a highly detailed, technical and non technical extended description that represents what the ideal "
        "target document would look like. \n\n"
        "Rules:\n"
        "1.If the query is technical,write a 2-3 sentence technical paragraph exlpaining the core concepts of the query. \n"
        "2.If its non-technical , generate a description/intoduction of the query. \n"
        "3. Naturally weave in relevant synonyms, alternate phrasing, and associated technical and non technical keywords.\n"
        "4. Output ONLY the extended description. Do not include introductory phrases, labels, or conversational filler.\n\n"
        f"User Query: {query}"
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