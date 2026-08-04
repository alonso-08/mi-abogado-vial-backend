from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    UserUpdate,
    EmailVerification,
    ResendVerificationRequest,
    MessageResponse,
)
from app.services.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
)
from app.services.email import email_service
from app.utils import generate_verification_token
from app.config import get_settings
from app.middleware import (
    rate_limit_check,
    login_limiter,
    register_limiter,
    resend_limiter,
)

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["auth"])

VERIFICATION_TOKEN_EXPIRE_HOURS = 24


def _is_token_expired(verification_token: str, user: User) -> bool:
    """Verificar si el token de verificacion expiro."""
    if user.created_at is None:
        return True
    token_age = datetime.now(timezone.utc) - user.created_at.replace(tzinfo=timezone.utc)
    return token_age > timedelta(hours=VERIFICATION_TOKEN_EXPIRE_HOURS)


@router.post("/register", response_model=MessageResponse)
async def register(request: Request, user_data: UserCreate, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    rate_limit_check(register_limiter, f"register:{client_ip}")

    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya esta registrado",
        )

    verification_token = generate_verification_token()

    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        credits=5,
        is_verified=False,
        verification_token=verification_token,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    await email_service.send_verification_email(
        to_email=user.email,
        full_name=user.full_name or user.email,
        verification_token=verification_token,
    )

    return MessageResponse(
        message="Cuenta creada. Revisa tu correo para verificar tu cuenta."
    )


@router.post("/login", response_model=TokenResponse)
def login(request: Request, credentials: UserLogin, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    rate_limit_check(login_limiter, f"login:{client_ip}")

    user = db.query(User).filter(User.email == credentials.email).first()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o password incorrectos",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes verificar tu email antes de iniciar sesion. Revisa tu correo electronico.",
        )

    token = create_access_token(data={"sub": str(user.id), "email": user.email})

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(data: EmailVerification, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.verification_token == data.token).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de verificacion invalido",
        )

    if _is_token_expired(data.token, user):
        user.verification_token = None
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de verificacion expirado. Solicita uno nuevo.",
        )

    user.is_verified = True
    user.verification_token = None
    db.commit()

    return MessageResponse(message="Email verificado correctamente. Ya puedes iniciar sesion.")


@router.get("/verify-email/{token}")
def verify_email_get(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.verification_token == token).first()

    if not user:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/verify-email?status=error&message=Token+invalido"
        )

    if _is_token_expired(token, user):
        user.verification_token = None
        db.commit()
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/verify-email?status=error&message=Token+expirado"
        )

    user.is_verified = True
    user.verification_token = None
    db.commit()

    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/verify-email?status=success"
    )


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    request: Request,
    data: ResendVerificationRequest,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    rate_limit_check(resend_limiter, f"resend:{client_ip}")

    user = db.query(User).filter(User.email == data.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email no encontrado",
        )

    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya esta verificado",
        )

    verification_token = generate_verification_token()
    user.verification_token = verification_token
    db.commit()

    await email_service.send_verification_email(
        to_email=user.email,
        full_name=user.full_name or user.email,
        verification_token=verification_token,
    )

    return MessageResponse(message="Correo de verificacion reenviado.")


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
def update_me(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user_data.full_name is not None:
        current_user.full_name = user_data.full_name
    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)
