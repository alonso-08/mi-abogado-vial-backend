import os
import subprocess
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.config import get_settings
from app.routes import auth_router, credits_router, payments_router, assistant_router, admin_router, document_types_router
from app.services.rag import init_all_states


class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response


settings = get_settings()

app = FastAPI(
    title="Asistente Legal Vial API",
    description="API para asistencia legal vial en Mexico",
    version="0.1.0",
    docs_url="/docs" if settings.DOCS_ENABLED else None,
    redoc_url="/redoc" if settings.DOCS_ENABLED else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(NoCacheMiddleware)

app.include_router(auth_router)
app.include_router(credits_router)
app.include_router(payments_router)
app.include_router(assistant_router)
app.include_router(admin_router)
app.include_router(document_types_router)


@app.on_event("startup")
async def startup_event():
    # Ejecutar migraciones automáticamente si estamos en Railway
    if settings.DATABASE_URL:
        print("🔧 Detectado entorno de producción, ejecutando migraciones...")

        try:
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                capture_output=True,
                text=True,
                check=True,
                env={**os.environ},
            )
            print("✅ Migraciones ejecutadas exitosamente")
            if result.stdout:
                print(f"📋 Alembic output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error en migraciones: {e}")
            if e.stderr:
                print(f"Error details: {e.stderr}")
        except Exception as e:
            print(f"⚠️  Error ejecutando migraciones: {e}")

    now = datetime.now()
    print("🚀 Asistente Legal Vial API iniciada correctamente")
    print(f"🕰️ Fecha y hora actual: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    if settings.DOCS_ENABLED:
        print("📚 Documentación disponible en: http://localhost:8000/docs")
    else:
        print("📚 Documentación deshabilitada (DOCS_ENABLED=False)")

    init_all_states()


@app.get("/")
async def root():
    if settings.DOCS_ENABLED:
        return RedirectResponse(url="/docs")
    return RedirectResponse(url="/health")


@app.get("/health")
async def health():
    return {"status": "ok"}
