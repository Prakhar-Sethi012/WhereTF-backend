import logging
import nltk
from nltk.corpus import wordnet

logger = logging.getLogger(__name__)

# Ensure NLTK data is ready
nltk.download("wordnet", quiet=True)
nltk.download("punkt", quiet=True)
nltk.download("omw-1.4", quiet=True)

def generate_hypothetical_document(query: str) -> str:
    """
    Expands the query using WordNet synonyms instead of a heavy LLM.
    Boosts keyword and vector matches without consuming GPU/RAM.
    """
    try:
        words = nltk.word_tokenize(query)
        expanded_terms = set(words)

        for word in words:
            for syn in wordnet.synsets(word):
                for lemma in syn.lemmas():
                    expanded_terms.add(lemma.name().replace("_", " "))

        expanded_query = " ".join(expanded_terms)
        logger.info("[expansion] Expanded query: %s", expanded_query)
        return expanded_query

    except Exception as e:
        logger.warning("[expansion] Synonym expansion failed: %s. Using raw query.", e)
        return query