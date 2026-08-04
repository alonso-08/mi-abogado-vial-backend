from pydantic import BaseModel
from typing import Optional


class DocumentTypeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    state: str
    level: str
    priority: int = 5


class DocumentTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    level: Optional[str] = None
    priority: Optional[int] = None


class DocumentTypeResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    state: str
    level: str
    priority: int
    is_active: bool

    class Config:
        from_attributes = True


class DocumentTypeDeleteResponse(BaseModel):
    type_id: str
    name: str
    documents_count: int
    documents: list[str]
