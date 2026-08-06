from app.routes.auth import router as auth_router
from app.routes.credits import router as credits_router
from app.routes.payments import router as payments_router
from app.routes.assistant import router as assistant_router
from app.routes.admin import router as admin_router
from app.routes.document_types import router as document_types_router
from app.routes.tts import router as tts_router

__all__ = [
    "auth_router",
    "credits_router",
    "payments_router",
    "assistant_router",
    "admin_router",
    "document_types_router",
    "tts_router",
]
