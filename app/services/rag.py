import os
import time
import logging
from typing import Dict, List, Optional
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from operator import itemgetter
from app.config import get_settings
from app.prompts import get_prompt

logger = logging.getLogger(__name__)
settings = get_settings()

vector_store: Optional[Chroma] = None
session_store: dict[str, tuple[ChatMessageHistory, float]] = {}

SESSION_TTL_SECONDS = 3600
CHROMA_DB_DIR = "chroma_db"

def _cleanup_expired_sessions() -> None:
    now = time.time()
    expired = [sid for sid, (_, created) in session_store.items() if now - created > SESSION_TTL_SECONDS]
    for sid in expired:
        del session_store[sid]
    if expired:
        logger.debug(f"Sesiones RAG limpiadas: {len(expired)}")

def get_session_history(session_id: str):
    _cleanup_expired_sessions()
    if session_id not in session_store:
        session_store[session_id] = (ChatMessageHistory(), time.time())
    return session_store[session_id][0]

_embeddings_instance = None

def _get_embeddings():
    global _embeddings_instance
    if _embeddings_instance is None:
        _embeddings_instance = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embeddings_instance

def init_all_states() -> None:
    logger.info("Inicializando sistema RAG con ChromaDB...")
    global vector_store
    
    embeddings = _get_embeddings()
    vector_store = Chroma(
        collection_name="legal_documents",
        embedding_function=embeddings,
        persist_directory=CHROMA_DB_DIR
    )
    logger.info("ChromaDB inicializado y listo para búsquedas con filtros.")

def get_qa_chain(official_type: str, state: str, municipality: Optional[str] = None):
    global vector_store
    if vector_store is None:
        init_all_states()
        
    model_name = "gemini-2.5-flash-lite" if settings.ENVIRONMENT in ["development", "local"] else "gemini-2.5-flash"
    llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.2, google_api_key=settings.GEMINI_API_KEY, streaming=True)
    
    # Construir el filtro jerárquico para ChromaDB
    if municipality:
        filter_dict = {
            "$and": [
                {"state": state},
                {"municipality": {"$in": [municipality, "general"]}}
            ]
        }
    else:
        filter_dict = {
            "$and": [
                {"state": state},
                {"municipality": "general"}
            ]
        }
        
    retriever = vector_store.as_retriever(
        search_kwargs={
            "k": 6,  # Traemos más fragmentos para combinar ley estatal y municipal
            "filter": filter_dict
        }
    )

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    state_key = f"{state}_{municipality}" if municipality else state
    template = get_prompt(official_type, state_key)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", template),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "Contexto legal:\n{context}\n\nLo que dice el usuario: {question}")
    ])
    
    chain = (
        {
            "context": itemgetter("question") | retriever | format_docs,
            "question": itemgetter("question"),
            "chat_history": itemgetter("chat_history")
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="question",
        history_messages_key="chat_history",
    )

def get_available_states() -> List[str]:
    try:
        from app.database import SessionLocal
        from app.models.document import Document
        
        db = SessionLocal()
        try:
            states = db.query(Document.state).filter(
                Document.status == "active", 
                Document.index_path.isnot(None)
            ).distinct().all()
            return [state[0] for state in states]
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error consultando estados en DB: {e}")
        return []
