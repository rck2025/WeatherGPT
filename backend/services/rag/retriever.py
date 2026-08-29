import logging
from typing import List, Tuple
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

def retrieve_documents(vector_db, query: str, k: int = 3) -> List[Tuple[Document, float]]:
    """Retrieve relevant bulletins and return document-score pairs."""
    try:
        return vector_db.similarity_search_with_relevance_scores(query, k=k)
    except Exception:
        logger.exception("RAG retrieval failed.")
        return []
