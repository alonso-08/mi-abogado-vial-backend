from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.config import get_settings
from app.routes import auth_router, credits_router, payments_router, assistant_router, admin_router, document_types_router
from app.services.rag import init_all_states

settings = get_settings()

app = FastAPI(
    title="Asistente Legal Vial API",
    description="API para asistencia legal vial en Mexico",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(credits_router)
app.include_router(payments_router)
app.include_router(assistant_router)
app.include_router(admin_router)
app.include_router(document_types_router)


@app.on_event("startup")
async def startup_event():
    init_all_states()


@app.get("/")
async def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health():
    return {"status": "ok"}
