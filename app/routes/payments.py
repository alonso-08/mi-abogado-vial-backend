import mercadopago
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from uuid import uuid4
from app.database import get_db
from app.config import get_settings
from app.models.user import User, CreditTransaction, Payment
from app.schemas.credits import PaymentCreate, PaymentResponse, PaymentStatus, AVAILABLE_PACKAGES
from app.services.auth import get_current_user

settings = get_settings()
sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN) if settings.MERCADOPAGO_ACCESS_TOKEN else None

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("/create", response_model=PaymentResponse)
def create_payment(
    payment_data: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not sdk:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mercado Pago no configurado",
        )

    package = next((p for p in AVAILABLE_PACKAGES if p.id == payment_data.package_id), None)
    if not package:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Paquete no valido",
        )

    preference_data = {
        "items": [
            {
                "title": f"Credito Legal Vial - Paquete {package.name}",
                "quantity": 1,
                "unit_price": package.price,
                "currency_id": "MXN",
            }
        ],
        "external_reference": str(current_user.id),
        "metadata": {"credits": package.credits, "package_id": package.id},
        "back_urls": {
            "success": "http://localhost:4200/credits?status=success",
            "pending": "http://localhost:4200/credits?status=pending",
            "failure": "http://localhost:4200/credits?status=failure",
        },
        "auto_return": "approved",
    }

    try:
        preference_response = sdk.preference().create(preference_data)
        preference = preference_response["response"]

        payment = Payment(
            user_id=current_user.id,
            mp_preference_id=preference["id"],
            amount=package.price,
            credits=package.credits,
            status="pending",
            extra_data={"package_id": package.id},
        )
        db.add(payment)
        db.commit()

        return PaymentResponse(
            init_point=preference["init_point"],
            preference_id=preference["id"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando preferencia: {str(e)}",
        )


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.json()

    if body.get("type") == "payment":
        payment_id = body.get("data", {}).get("id")

        if sdk and payment_id:
            try:
                payment_info = sdk.payment().get(payment_id)
                payment_data = payment_info["response"]

                user_id = payment_data.get("external_reference")
                if user_id:
                    user = db.query(User).filter(User.id == user_id).first()
                    if user:
                        existing_payment = (
                            db.query(Payment)
                            .filter(Payment.mp_payment_id == str(payment_id))
                            .first()
                        )
                        if not existing_payment:
                            credits_to_add = payment_data.get("metadata", {}).get("credits", 0)

                            user.credits += credits_to_add

                            payment = Payment(
                                user_id=user.id,
                                mp_payment_id=str(payment_id),
                                amount=payment_data.get("transaction_amount", 0),
                                credits=credits_to_add,
                                status=payment_data.get("status", "pending"),
                                extra_data=payment_data,
                            )
                            db.add(payment)

                            transaction = CreditTransaction(
                                user_id=user.id,
                                amount=credits_to_add,
                                type="purchase",
                                description=f"Compra de paquete - Pago #{payment_id}",
                            )
                            db.add(transaction)

                            db.commit()
            except Exception as e:
                print(f"Error procesando webhook: {e}")

    return {"status": "ok"}


@router.get("/status/{preference_id}", response_model=PaymentStatus)
def get_payment_status(
    preference_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payment = (
        db.query(Payment)
        .filter(
            Payment.mp_preference_id == preference_id,
            Payment.user_id == current_user.id,
        )
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pago no encontrado",
        )

    return PaymentStatus(
        status=payment.status,
        credits_added=payment.credits if payment.status == "approved" else 0,
    )
