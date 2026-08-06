import os
import logging
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from app.models.document import Document
from app.config import get_settings
from app.services.storage import (
    upload_file,
    delete_file,
    get_temp_file_for_processing,
    cleanup_temp_file,
    get_local_path,
    USE_S3,
)

logger = logging.getLogger(__name__)
settings = get_settings()

CHROMA_DB_DIR = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "chroma_db")

_embeddings_instance = None


def _get_embeddings():
    global _embeddings_instance
    if _embeddings_instance is None:
        _embeddings_instance = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embeddings_instance


def save_uploaded_file(file_content: bytes, filename: str, state: str,
                       municipality: Optional[str] = None) -> str:
    """
    Save uploaded file to storage.

    Returns:
        str: S3 key (production) or local file path (development)
    """
    return upload_file(file_content, state, filename, municipality)


def process_pdf(document_id: UUID, file_path: str, state: str,
                municipality: Optional[str], db: Session) -> bool:
    """
    Process PDF: extract text, split into chunks, store in ChromaDB.

    Args:
        file_path: S3 key or local file path
    """
    temp_file = None

    try:
        logger.info(f"Processing PDF for document {document_id}...")

        # Get local file path for PyPDFLoader
        # If S3, download to temp file first
        if USE_S3:
            temp_file = get_temp_file_for_processing(file_path)
            local_path = temp_file
        else:
            local_path = file_path

        # Process PDF
        loader = PyPDFLoader(local_path)
        documents = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        docs = text_splitter.split_documents(documents)
        logger.info(f"Document split into {len(docs)} chunks.")

        embeddings = _get_embeddings()

        # Inject metadata for ChromaDB filtering
        for doc in docs:
            doc.metadata["state"] = state
            doc.metadata["municipality"] = municipality if municipality else "general"

        logger.info(f"Saving chunks to ChromaDB...")
        vector_store = Chroma(
            collection_name="legal_documents",
            embedding_function=embeddings,
            persist_directory=CHROMA_DB_DIR
        )
        vector_store.add_documents(docs)
        logger.info(f"Chunks saved successfully to ChromaDB.")

        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.index_path = CHROMA_DB_DIR
            document.status = "active"
            db.commit()

        return True
    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        db.rollback()
        return False
    finally:
        # Clean up temp file if it was created
        if temp_file:
            cleanup_temp_file(temp_file)


def delete_document_files(document: Document) -> bool:
    """Delete document files from storage."""
    try:
        if document.file_path:
            delete_file(document.file_path)

        return True
    except Exception as e:
        logger.error(f"Error deleting files: {e}")
        return False
