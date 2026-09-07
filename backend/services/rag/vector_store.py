import logging
import json
from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader
try:
    from langchain_chroma import Chroma
except ImportError:
    from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
DB_DIR = BACKEND_DIR / "vector_db"
DATA_DIR = BACKEND_DIR / "data"
INGESTION_MARKER = ".weathergpt_ingested.json"


def is_ingested(db_path: Path = DB_DIR) -> bool:
    """Whether this application's bulletin index was successfully built."""
    return (Path(db_path) / INGESTION_MARKER).is_file()

def load_vector_db(db_path: Path = DB_DIR, embeddings = None) -> Chroma | None:
    """Load an already-ingested local database when one is available."""
    if not db_path.is_dir():
        return None
    try:
        return Chroma(
            persist_directory=str(db_path),
            embedding_function=embeddings,
        )
    except Exception:
        logger.exception("Could not load the RAG vector database.")
        return None

def ingest_bulletins(data_path: Path = DATA_DIR, db_path: Path = DB_DIR, embeddings = None) -> int:
    """Build or refresh the local Chroma database from PDFs in data_path."""
    if embeddings is None:
        raise RuntimeError("Embeddings are not configured.")

    bulletin_dir = Path(data_path)
    pdf_files = sorted(bulletin_dir.glob("*.pdf")) if bulletin_dir.is_dir() else []

    if not pdf_files:
        raise FileNotFoundError(
            f"No PDF bulletins found in {bulletin_dir}."
        )

    documents = []
    for pdf_file in pdf_files:
        documents.extend(PyPDFLoader(str(pdf_file)).load())

    if not documents:
        raise RuntimeError("PDF bulletins were found, but no text could be extracted.")

    chunks = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
    ).split_documents(documents)

    if not chunks:
        raise RuntimeError("No RAG chunks could be created from the PDF bulletins.")

    db_path.mkdir(parents=True, exist_ok=True)
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(db_path),
    )
    (db_path / INGESTION_MARKER).write_text(
        json.dumps({"pdf_count": len(pdf_files)}), encoding="utf-8"
    )
    logger.info(
        "Ingested %d PDF bulletin(s) into %s.",
        len(pdf_files),
        db_path,
    )
    return len(pdf_files)
