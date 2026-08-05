from pydantic import model_validator, Field
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Environment``
    ENVIRONMENT: str = Field(
        ...,
        description="Entorno de ejecución (LOCAL, DEV, PROD)",
    )

    # Database
    DATABASE_URL: str = Field(
        ...,
        description="URL de conexión a PostgreSQL (formato: postgresql://user:password@host:port/dbname)",
    )
    # JWT
    JWT_SECRET: str = Field(
        ...,
        description="Secreto para firmar tokens JWT",
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # Mercado Pago
    MERCADOPAGO_ACCESS_TOKEN: str = Field(
        ...,
        description="Token de acceso a Mercado Pago",
    )
    MERCADOPAGO_PUBLIC_KEY: str = Field(
        ...,
        description="Public key de Mercado Pago",
    )
    WEBHOOK_SECRET: str = Field(
        ...,
        description="Secreto para verificar firmas de webhooks",
    )
    # Si es True, el webhook rechaza (401) firmas invalidas.
    # Con pagos Legacy (notification_url) la firma no es confiable: mantener False.
    # La seguridad se apoya en consultar el pago a la API de MP, acreditar solo al
    # external_reference del pago, dedup por mp_payment_id y check de status=approved.
    WEBHOOK_VERIFY_SIGNATURE: bool = Field(
        ...,
        description="Verifica la firma de los webhooks de Mercado Pago",
    )
    # URL publica del webhook (ngrok/tunnel). Si se define, se usa como notification_url
    # en la preferencia; si no, MercadoPago usara la webhook configurada en el dashboard.
    WEBHOOK_URL: str = Field(
        ...,
        description="URL publica del webhook de Mercado Pago",
    )
    
    # Gemini
    GEMINI_API_KEY: str = Field(
        ...,
        description="Clave de API de Gemini",
    )
    
    # CORS
    ALLOWED_ORIGINS: str = Field(
        ...,
        description="Origins permitidas para CORS",
    )
    
    # Email (Resend)
    RESEND_API_KEY: str = Field(
        ...,
        description="Clave de API de Resend",
    )
    EMAILS_FROM_NAME: str = Field(
        "TiagoVial",
        description="Nombre del remitente de correos",
    )
    EMAILS_FROM_EMAIL: str = Field(
        "noreply@tiagovial.com",
        description="Email del remitente de correos",
    )
    BACKEND_URL: str = Field(
        ...,
        description="URL del backend",
    )
    FRONTEND_URL: str = Field(
        ...,
        description="URL del frontend",
    )

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        default_jwt = "tu-secreto-super-seguro-cambiar-en-produccion"
        if self.ENVIRONMENT == "PROD":
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
