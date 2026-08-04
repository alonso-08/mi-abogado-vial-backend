import os
import json
import logging
from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.document import Document
from app.models.document_type import DocumentType
from app.models.document_municipality import DocumentMunicipality
from app.schemas.auth import MessageResponse
from app.services.auth import get_current_user
from app.services.document_service import save_uploaded_file, process_pdf, delete_document_files
from app.services.pdf_analyzer import analyze_pdf, log_gemini_correction, generate_type_id, normalize_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Se requiere rol de administrador.",
        )
    return current_user


@router.get("/catalog/municipalities/{state}")
def get_municipalities(state: str):
    """Retorna TODOS los municipios oficiales disponibles para un estado."""
    try:
        catalog_path = os.path.join(os.path.dirname(__file__), "..", "data", "municipalities.json")
        with open(catalog_path, "r") as f:
            catalog = json.load(f)
    except Exception as e:
        logger.error(f"Error loading municipalities catalog: {e}")
        return []

    norm_state = normalize_text(state.replace("_", " "))
    for k, v in catalog.items():
        if normalize_text(k) == norm_state:
            return v
    return []


@router.post("/documents/analyze")
async def analyze_document(
    file: UploadFile = File(...),
    state: str = Form(...),
    current_user: User = Depends(require_admin),
):
    """Analiza un PDF con Gemini sin subirlo. Retorna metadatos detectados."""
    logger.info(f"Analyzing document: {file.filename}, size: {file.size}")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        logger.warning(f"Invalid file type: {file.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos PDF",
        )

    file_content = await file.read()
    if len(file_content) > 100 * 1024 * 1024:
        logger.warning(f"File too large: {len(file_content)} bytes")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no puede exceder 100MB",
        )

    try:
        analysis = analyze_pdf(file_content, file.filename, state)
        logger.info(f"Analysis result: {analysis}")
        return analysis
    except Exception as e:
        logger.error(f"Error in analyze_document: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al analizar el PDF: {str(e)}",
        )


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    state: str = Form(...),
    municipalities: str = Form("[]"),
    title: str = Form(None),
    description: str = Form(None),
    type_name: str = Form(None),
    level: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos PDF",
        )

    file_content = await file.read()
    if len(file_content) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no puede exceder 50MB",
        )

    analysis = analyze_pdf(file_content, file.filename, state)

    if title:
        analysis["title"] = title
    if description:
        analysis["description"] = description
    if type_name:
        analysis["type_name"] = type_name
    if level:
        analysis["level"] = level

    was_corrected = bool(title or description or type_name or level)
    if was_corrected:
        log_gemini_correction(
            filename=file.filename,
            gemini_result=analysis,
            corrections={
                "title": title,
                "description": description,
                "type_name": type_name,
                "level": level,
            },
        )

    type_id = generate_type_id(analysis["type_name"], state)
    doc_type = db.query(DocumentType).filter(DocumentType.id == type_id).first()
    if not doc_type:
        doc_type = DocumentType(
            id=type_id,
            name=analysis["type_name"],
            description=analysis["description"],
            state=state,
            level=analysis["level"],
            priority=5,
        )
        db.add(doc_type)
        db.commit()

    parsed_municipalities = json.loads(municipalities) if municipalities else []

    # Verificar si ya existe un documento de este tipo para los mismos municipios
    existing_docs = db.query(Document).filter(
        Document.document_type == analysis.get("type_name", ""),
        Document.state == state
    ).all()
    
    for doc in existing_docs:
        doc_munis = [m.municipality for m in db.query(DocumentMunicipality).filter(DocumentMunicipality.document_id == doc.id).all()]
        if sorted(doc_munis) == sorted(parsed_municipalities):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un documento del tipo '{analysis.get('type_name')}' registrado para estos municipios."
            )

    filename = file.filename.replace(" ", "_")
    file_path = save_uploaded_file(file_content, filename, state)

    document = Document(
        title=analysis["title"],
        state=state,
        document_type=doc_type.name,
        description=analysis["description"],
        source="admin",
        file_path=file_path,
        status="pending",
        uploaded_by=current_user.id,
    )
    db.add(document)
    db.flush()

    for m in parsed_municipalities:
        db.add(DocumentMunicipality(document_id=document.id, municipality=m))

    db.commit()
    db.refresh(document)

    success = process_pdf(document.id, file_path, state, None, db)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al procesar el PDF",
        )

    return {
        "id": str(document.id),
        "title": document.title,
        "state": document.state,
        "document_type": document.document_type,
        "description": document.description,
        "status": document.status,
        "municipalities": parsed_municipalities,
        "message": "Documento subido y procesado correctamente",
    }


@router.get("/documents")
def list_documents(
    state: str = None,
    municipality: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    query = db.query(Document)

    if state:
        query = query.filter(Document.state == state)

    if municipality:
        doc_ids = (
            db.query(DocumentMunicipality.document_id)
            .filter(DocumentMunicipality.municipality == municipality)
            .subquery()
        )
        query = query.filter(Document.id.in_(doc_ids))

    documents = query.order_by(Document.created_at.desc()).all()

    result = []
    for doc in documents:
        muni_rows = (
            db.query(DocumentMunicipality.municipality)
            .filter(DocumentMunicipality.document_id == doc.id)
            .all()
        )
        result.append(
            {
                "id": str(doc.id),
                "title": doc.title,
                "state": doc.state,
                "document_type": doc.document_type,
                "description": doc.description,
                "source": doc.source,
                "status": doc.status,
                "version": doc.version,
                "municipalities": [m[0] for m in muni_rows],
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            }
        )
    return result


@router.get("/documents/{document_id}/municipalities")
def get_document_municipalities(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado",
        )

    rows = (
        db.query(DocumentMunicipality.municipality)
        .filter(DocumentMunicipality.document_id == document_id)
        .all()
    )
    return [r[0] for r in rows]


@router.put("/documents/{document_id}/municipalities")
def update_document_municipalities(
    document_id: UUID,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado",
        )

    db.query(DocumentMunicipality).filter(
        DocumentMunicipality.document_id == document_id
    ).delete()

    new_municipalities = data.get("municipalities", [])
    for m in new_municipalities:
        db.add(DocumentMunicipality(document_id=document_id, municipality=m))

    db.commit()
    return {"municipalities": new_municipalities}


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado",
        )

    delete_document_files(document)
    db.query(DocumentMunicipality).filter(
        DocumentMunicipality.document_id == document_id
    ).delete()
    db.delete(document)
    db.commit()

    return MessageResponse(message="Documento eliminado correctamente")


@router.get("/document-types")
def get_document_types(
    state: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    query = db.query(DocumentType).filter(DocumentType.is_active == True)
    if state:
        query = query.filter(DocumentType.state == state)
    types = query.order_by(DocumentType.priority.desc()).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "state": t.state,
            "level": t.level,
            "priority": t.priority,
        }
        for t in types
    ]


@router.get("/coverage/{state}")
def get_state_coverage(
    state: str,
    current_user: User = Depends(get_current_user),
):
    from app.services import rag

    db = next(get_db())
    try:
        municipalities = (
            db.query(DocumentMunicipality.municipality)
            .join(Document, Document.id == DocumentMunicipality.document_id)
            .filter(Document.state == state, Document.status == "active")
            .distinct()
            .all()
        )

        return {
            "state": state,
            "state_available": state in rag.get_available_states(),
            "municipalities": [m[0] for m in municipalities],
            "has_municipal_coverage": len(municipalities) > 0,
        }
    finally:
        db.close()


@router.get("/coverage/details/{state}")
def get_coverage_details(
    state: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Retorna un resumen de municipios cubiertos y sus tipos de documentos."""
    query_result = (
        db.query(DocumentMunicipality.municipality, Document.document_type)
        .join(Document, Document.id == DocumentMunicipality.document_id)
        .filter(Document.state == state)
        .all()
    )

    coverage = {}
    for muni, doc_type in query_result:
        if muni not in coverage:
            coverage[muni] = set()
        coverage[muni].add(doc_type)

    result = []
    for muni, types in coverage.items():
        result.append({
            "municipality": muni,
            "document_types": list(types)
        })

    # Sort alphabetically by municipality name
    result.sort(key=lambda x: x["municipality"])
    return result
