from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/asistente_vial"
    
    # JWT
    JWT_SECRET: str = "tu-secreto-super-seguro-cambiar-en-produccion"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # Mercado Pago
    MERCADOPAGO_ACCESS_TOKEN: str = ""
    MERCADOPAGO_PUBLIC_KEY: str = ""
    
    # Gemini
    GEMINI_API_KEY: str = ""
    
    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:4200"
    
    # Email (Resend)
    RESEND_API_KEY: str = ""
    EMAILS_FROM_NAME: str = "Asistente Legal Vial"
    EMAILS_FROM_EMAIL: str = "noreply@asistentelegalvial.com"
    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:4200"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
