import os
import re
import time
import json
import uuid
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models.user import User
from app.schemas.assistant import ConsultationRequest, ConsultationResponse, get_available_states
from app.services.auth import get_current_user
from app.services.credits import deduct_credit
from app.services import rag

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

logger = logging.getLogger(__name__)


@router.get("/estados")
def get_estados(current_user: User = Depends(get_current_user)):
    rag_states = rag.get_available_states()
    
    from app.models.document import Document
    db = next(get_db())
    try:
        db_states = (
            db.query(Document.state)
            .filter(Document.status == "active")
            .distinct()
            .all()
        )
        db_state_ids = [s[0] for s in db_states]
    finally:
        db.close()
    
    all_available = list(set(rag_states + db_state_ids))
    return get_available_states(all_available)


def get_active_municipalities(db: Session, state: str) -> list:
    from sqlalchemy import select
    from app.models.document import Document
    from app.models.document_municipality import DocumentMunicipality

    active_docs = select(Document.id).where(
        Document.state == state,
        Document.status == "active",
    )
    rows = (
        db.query(DocumentMunicipality.municipality)
        .filter(DocumentMunicipality.document_id.in_(active_docs))
        .distinct()
        .all()
    )
    return sorted(m[0] for m in rows)


@router.get("/municipios")
def get_municipios(
    state: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Municipios con documentos activos para un estado, con centroides GPS si existen."""
    munis = get_active_municipalities(db, state)

    try:
        centroids_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "municipality_centroids.json"
        )
        with open(centroids_path, "r") as f:
            centroids = json.load(f)
    except Exception as e:
        logger.warning(f"Error cargando centroides de municipios: {e}")
        centroids = {}

    state_centroids = centroids.get(state, {})
    result = [
        {
            "name": m,
            "lat": state_centroids.get(m, [None, None])[0],
            "lng": state_centroids.get(m, [None, None])[1],
        }
        for m in munis
    ]
    return result


@router.get("/health")
def health_check():
    available = rag.get_available_states()
    return {"status": "ok", "available_states": available}


@router.post("/consultar", response_model=ConsultationResponse)
def consultar(
    request: ConsultationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    available = rag.get_available_states()

    if not available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sistema RAG no inicializado",
        )

    if request.state not in available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Estado '{request.state}' no disponible. Estados disponibles: {available}",
        )

    if len(request.text) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La consulta debe tener al menos 10 caracteres",
        )

    if len(request.text) > 2500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La consulta no puede exceder 2500 caracteres",
        )

    if request.official_type not in ["transito", "preventivo"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de oficial no valido. Use 'transito' o 'preventivo'",
        )

    if current_user.credits <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="No tienes creditos suficientes. Compra mas en la seccion de creditos.",
        )

    if not deduct_credit(current_user, db, f"Consulta: {request.text[:50]}..."):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Error al descontar creditos",
        )

    try:
        start_time = time.time()

        chain = rag.get_qa_chain(request.official_type, request.state, request.municipality)

        answer = chain.invoke(
            {"question": request.text},
            config={"configurable": {"session_id": request.session_id}}
        )

        response_time_ms = int((time.time() - start_time) * 1000)

        guion_match = re.search(r'---GUION---\s*(.*?)\s*(?:---FUNDAMENTO---|---ACCION---|$)', answer, re.DOTALL)
        fundamento_match = re.search(r'---FUNDAMENTO---\s*(.*?)\s*(?:---ACCION---|$)', answer, re.DOTALL)
        accion_match = re.search(r'---ACCION---\s*(.*?)\s*$', answer, re.DOTALL)

        guion = guion_match.group(1).strip() if guion_match else ""
        fundamento_raw = fundamento_match.group(1).strip() if fundamento_match else ""
        accion_raw = accion_match.group(1).strip() if accion_match else ""

        fundamento = [line.strip() for line in fundamento_raw.split("\n") if line.strip() and line.strip() != "-"]
        accion = [line.strip() for line in accion_raw.split("\n") if line.strip() and line.strip() != "-"]

        if not fundamento:
            fundamento = [fundamento_raw] if fundamento_raw else []
        if not accion:
            accion = [accion_raw] if accion_raw else ["Sigue las instrucciones generales de seguridad."]

        db.refresh(current_user)

        return ConsultationResponse(
            guion=guion,
            fundamento=fundamento,
            accion=accion,
            credits_used=1,
            credits_remaining=current_user.credits,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando la consulta: {str(e)}",
        )


@router.post("/consultar-stream")
async def consultar_stream(
    request: ConsultationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    available = rag.get_available_states()

    if not available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sistema RAG no inicializado",
        )

    if request.state not in available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Estado '{request.state}' no disponible. Estados disponibles: {available}",
        )

    if len(request.text) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La consulta debe tener al menos 10 caracteres",
        )

    if len(request.text) > 2500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La consulta no puede exceder 2500 caracteres",
        )

    if request.official_type not in ["transito", "preventivo"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de oficial no valido. Use 'transito' o 'preventivo'",
        )

    if current_user.credits <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="No tienes creditos suficientes. Compra mas en la seccion de creditos.",
        )

    if not deduct_credit(current_user, db, f"Consulta: {request.text[:50]}..."):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Error al descontar creditos",
        )

    user_id = current_user.id
    credits_after_deduct = current_user.credits

    async def generate_stream():
        try:
            chain = rag.get_qa_chain(request.official_type, request.state, request.municipality)

            full_text = ""
            async for event in chain.astream_events(
                {"question": request.text},
                config={"configurable": {"session_id": request.session_id}},
                version="v2",
            ):
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    token = chunk.content if hasattr(chunk, "content") else ""
                    if token:
                        full_text += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            guion_match = re.search(r'---GUION---\s*(.*?)\s*(?:---FUNDAMENTO---|---ACCION---|$)', full_text, re.DOTALL)
            fundamento_match = re.search(r'---FUNDAMENTO---\s*(.*?)\s*(?:---ACCION---|$)', full_text, re.DOTALL)
            accion_match = re.search(r'---ACCION---\s*(.*?)\s*$', full_text, re.DOTALL)

            guion = guion_match.group(1).strip() if guion_match else ""
            fundamento_raw = fundamento_match.group(1).strip() if fundamento_match else ""
            accion_raw = accion_match.group(1).strip() if accion_match else ""

            fundamento = [line.strip() for line in fundamento_raw.split("\n") if line.strip() and line.strip() != "-"]
            accion = [line.strip() for line in accion_raw.split("\n") if line.strip() and line.strip() != "-"]

            if not fundamento:
                fundamento = [fundamento_raw] if fundamento_raw else []
            if not accion:
                accion = [accion_raw] if accion_raw else ["Sigue las instrucciones generales de seguridad."]

            try:
                fresh_db = next(get_db())
                fresh_user = fresh_db.query(User).filter(User.id == user_id).first()
                final_credits = fresh_user.credits if fresh_user else credits_after_deduct
                fresh_db.close()
            except Exception:
                final_credits = credits_after_deduct

            yield f"data: {json.dumps({'type': 'done', 'result': {'guion': guion, 'fundamento': fundamento, 'accion': accion, 'credits_used': 1, 'credits_remaining': final_credits}})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )



