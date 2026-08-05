from pydantic import model_validator
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
    WEBHOOK_SECRET: str = ""
    # Si es True, el webhook rechaza (401) firmas invalidas.
    # Con pagos Legacy (notification_url) la firma no es confiable: mantener False.
    # La seguridad se apoya en consultar el pago a la API de MP, acreditar solo al
    # external_reference del pago, dedup por mp_payment_id y check de status=approved.
    WEBHOOK_VERIFY_SIGNATURE: bool = False
    # URL publica del webhook (ngrok/tunnel). Si se define, se usa como notification_url
    # en la preferencia; si no, MercadoPago usara la webhook configurada en el dashboard.
    WEBHOOK_URL: str = ""
    
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

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        default_jwt = "tu-secreto-super-seguro-cambiar-en-produccion"
        if self.ENVIRONMENT == "production":
            if self.JWT_SECRET == default_jwt:
                raise ValueError(
                    "JWT_SECRET no puede ser el valor por defecto en producción. "
                    "Genera un secreto seguro y agrégalo a tu variable de entorno."
                )
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
