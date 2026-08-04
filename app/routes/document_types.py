import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.document_type import DocumentType
from app.models.document import Document
from app.schemas.admin import (
    DocumentTypeCreate,
    DocumentTypeUpdate,
    DocumentTypeResponse,
    DocumentTypeDeleteResponse,
)
from app.services.auth import get_current_user
from app.services.document_service import delete_document_files
from app.services.pdf_analyzer import generate_type_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/document-types", tags=["document-types"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Se requiere rol de administrador.",
        )
    return current_user


@router.get("/{state}")
def get_document_types_by_state(
    state: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    types = (
        db.query(DocumentType)
        .filter(DocumentType.state == state, DocumentType.is_active == True)
        .order_by(DocumentType.priority.desc())
        .all()
    )
    return [
        DocumentTypeResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            state=t.state,
            level=t.level,
            priority=t.priority,
            is_active=t.is_active,
        )
        for t in types
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_document_type(
    data: DocumentTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if data.level not in ("estatal", "municipal"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nivel debe ser 'estatal' o 'municipal'",
        )

    type_id = generate_type_id(data.name, data.state)

    existing = db.query(DocumentType).filter(DocumentType.id == type_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un tipo con el nombre '{data.name}' en {data.state}",
        )

    doc_type = DocumentType(
        id=type_id,
        name=data.name,
        description=data.description,
        state=data.state,
        level=data.level,
        priority=data.priority,
        is_active=True,
    )
    db.add(doc_type)
    db.commit()
    db.refresh(doc_type)

    return DocumentTypeResponse(
        id=doc_type.id,
        name=doc_type.name,
        description=doc_type.description,
        state=doc_type.state,
        level=doc_type.level,
        priority=doc_type.priority,
        is_active=doc_type.is_active,
    )


@router.put("/{type_id}")
def update_document_type(
    type_id: str,
    data: DocumentTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    doc_type = db.query(DocumentType).filter(DocumentType.id == type_id).first()
    if not doc_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tipo de documento no encontrado",
        )

    if data.name is not None:
        new_id = generate_type_id(data.name, doc_type.state)
        if new_id != type_id:
            existing = db.query(DocumentType).filter(DocumentType.id == new_id).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ya existe un tipo con el nombre '{data.name}' en {doc_type.state}",
                )
            doc_type.id = new_id
        doc_type.name = data.name

    if data.description is not None:
        doc_type.description = data.description
    if data.level is not None:
        if data.level not in ("estatal", "municipal"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El nivel debe ser 'estatal' o 'municipal'",
            )
        doc_type.level = data.level
    if data.priority is not None:
        doc_type.priority = data.priority

    db.commit()
    db.refresh(doc_type)

    return DocumentTypeResponse(
        id=doc_type.id,
        name=doc_type.name,
        description=doc_type.description,
        state=doc_type.state,
        level=doc_type.level,
        priority=doc_type.priority,
        is_active=doc_type.is_active,
    )


@router.delete("/{type_id}")
def delete_document_type(
    type_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    doc_type = db.query(DocumentType).filter(DocumentType.id == type_id).first()
    if not doc_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tipo de documento no encontrado",
        )

    documents = (
        db.query(Document).filter(Document.document_type == doc_type.name).all()
    )

    response = DocumentTypeDeleteResponse(
        type_id=doc_type.id,
        name=doc_type.name,
        documents_count=len(documents),
        documents=[doc.title for doc in documents],
    )

    for doc in documents:
        delete_document_files(doc)
        db.delete(doc)

    db.delete(doc_type)
    db.commit()

    return response
