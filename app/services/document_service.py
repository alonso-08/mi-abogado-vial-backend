import os
import logging
import shutil
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from app.models.document import Document
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

UPLOAD_BASE_DIR = "uploads/documents"
CHROMA_DB_DIR = "chroma_db"

_embeddings_instance = None


def _get_embeddings():
    global _embeddings_instance
    if _embeddings_instance is None:
        _embeddings_instance = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embeddings_instance


def get_document_dir(state: str, municipality: Optional[str] = None) -> str:
    if municipality:
        return os.path.join(UPLOAD_BASE_DIR, state, municipality)
    return os.path.join(UPLOAD_BASE_DIR, state)


def save_uploaded_file(file_content: bytes, filename: str, state: str, municipality: Optional[str] = None) -> str:
    doc_dir = get_document_dir(state, municipality)
    os.makedirs(doc_dir, exist_ok=True)
    
    file_path = os.path.join(doc_dir, filename)
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    return file_path


def process_pdf(document_id: UUID, file_path: str, state: str, municipality: Optional[str], db: Session) -> bool:
    try:
        logger.info(f"Procesando PDF para documento {document_id}...")
        
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        docs = text_splitter.split_documents(documents)
        logger.info(f"Documento dividido en {len(docs)} fragmentos.")
        
        embeddings = _get_embeddings()
        
        # Inject metadata for ChromaDB filtering
        for doc in docs:
            doc.metadata["state"] = state
            doc.metadata["municipality"] = municipality if municipality else "general"
            
        logger.info(f"Guardando fragmentos en ChromaDB...")
        vector_store = Chroma(
            collection_name="legal_documents",
            embedding_function=embeddings,
            persist_directory=CHROMA_DB_DIR
        )
        vector_store.add_documents(docs)
        logger.info(f"Fragmentos guardados exitosamente en ChromaDB.")
        
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.index_path = CHROMA_DB_DIR
            document.status = "active"
            db.commit()
        
        return True
    except Exception as e:
        logger.error(f"Error procesando PDF: {e}")
        db.rollback()
        return False


def delete_document_files(document: Document) -> bool:
    try:
        if document.file_path and os.path.exists(document.file_path):
            os.remove(document.file_path)
        
        # Con ChromaDB no borramos el directorio completo, requeriría vector_store.delete()
        # Para el MVP, mantenemos los vectores en DB o los ignoramos (ya que se sobrescriben).
        # if document.index_path and os.path.exists(document.index_path):
        #     shutil.rmtree(document.index_path)
        
        return True
    except Exception as e:
        logger.error(f"Error eliminando archivos: {e}")
        return False
