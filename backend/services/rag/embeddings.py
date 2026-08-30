import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

EMBEDDING_MODEL = "models/gemini-embedding-001"

def get_embeddings(gemini_api_key: str | None = None, model: str = EMBEDDING_MODEL) -> GoogleGenerativeAIEmbeddings:
    """Initialize GoogleGenerativeAIEmbeddings."""
    api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    
    return GoogleGenerativeAIEmbeddings(
        model=model,
        google_api_key=api_key,
    )
