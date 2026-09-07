import logging
from typing import List, Tuple
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

def retrieve_documents(
    vector_db,
    query: str,
    k: int = 3,
    exclude_keywords: list[str] | None = None,
) -> List[Tuple[Document, float]]:
    """Retrieve relevant bulletins and return document-score pairs, optionally filtering out unwanted keywords."""
    try:
        fetch_k = k * 2 if exclude_keywords else k
        raw_results = vector_db.similarity_search_with_relevance_scores(query, k=fetch_k)
        if not exclude_keywords:
            return raw_results[:k]

        filtered: List[Tuple[Document, float]] = []
        for doc, score in raw_results:
            content_lower = doc.page_content.lower()
            if any(kw.lower() in content_lower for kw in exclude_keywords):
                continue
            filtered.append((doc, score))
            if len(filtered) >= k:
                break
        return filtered
    except Exception:
        logger.exception("RAG retrieval failed.")
        return []
