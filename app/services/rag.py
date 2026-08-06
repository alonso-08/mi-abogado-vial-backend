import time
import logging
from typing import List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from operator import itemgetter
from app.config import get_settings
from app.prompts import get_prompt
from app.database import SessionLocal
from app.services.embeddings import search_similar

logger = logging.getLogger(__name__)
settings = get_settings()

session_store: dict[str, tuple[ChatMessageHistory, float]] = {}

SESSION_TTL_SECONDS = 3600

_embeddings_instance = None


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


def _get_embeddings():
    global _embeddings_instance
    if _embeddings_instance is None:
        _embeddings_instance = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embeddings_instance


def get_qa_chain(official_type: str, state: str, municipality: Optional[str] = None):
    embeddings = _get_embeddings()

    model_name = "gemini-2.5-flash-lite" if settings.ENVIRONMENT in ["development", "local"] else "gemini-2.5-flash"
    llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.2, google_api_key=settings.GEMINI_API_KEY, streaming=True)

    state_key = f"{state}_{municipality}" if municipality else state
    template = get_prompt(official_type, state_key)

    prompt = ChatPromptTemplate.from_messages([
        ("system", template),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "Contexto legal:\n{context}\n\nLo que dice el usuario: {question}")
    ])

    def retrieve_docs(input_dict):
        question = input_dict["question"]
        query_embedding = embeddings.embed_query(question)
        db = SessionLocal()
        try:
            results = search_similar(db, query_embedding, state, municipality, k=6)
            return "\n\n".join(row[0] for row in results) if results else "No se encontraron documentos legales relevantes."
        finally:
            db.close()

    chain = (
        {
            "context": itemgetter("question") | retrieve_docs,
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
