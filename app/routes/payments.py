import logging
import mercadopago
from fastapi import APIRouter, Depends, HTTPException, Request, status
from mercadopago.webhook import InvalidWebhookSignatureError, WebhookSignatureValidator
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import get_settings
from app.models.user import User, CreditTransaction, Payment, CreditPackage
from app.schemas.credits import PaymentCreate, PaymentResponse, PaymentStatus
from app.services.auth import get_current_user

settings = get_settings()
logger = logging.getLogger(__name__)
sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN) if settings.MERCADOPAGO_ACCESS_TOKEN else None

router = APIRouter(prefix="/api/payments", tags=["payments"])


def _parse_signature_values(x_signature: str) -> tuple[str, str]:
    """Extrae ts y v1 crudos del header x-signature para diagnostico."""
    ts = ""
    v1 = ""
    for part in x_signature.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "ts":
            ts = value
        elif key == "v1":
            v1 = value
    return ts, v1


def verify_webhook_signature(request: Request, secret: str) -> bool:
    """
    Verifica firma HMAC-SHA256 de MercadoPago (webhook moderno con x-signature).
    Los IPN Legacy (sin x-signature) no son firmados por MP → se permiten sin verificar.
    """
    x_signature = request.headers.get("x-signature", "")
    x_request_id = request.headers.get("x-request-id", "")
    # Según docs oficiales de MP: solo usar data.id del query param.
    # Para IPN legacy (?id=xxx&topic=payment), data.id no existe → None.
    # El SDK omite el campo id del manifest cuando es None.
    data_id = request.query_params.get("data.id")

    fmt = (
        "webhook-moderno"
        if request.query_params.get("data.id")
        else "ipn-legacy" if request.query_params.get("id") else "otro"
    )

    # IPN Legacy no incluye x-signature por diseño de Mercado Pago → se permite pasar
    if not x_signature:
        logger.info(
            "Webhook IPN-Legacy sin firma (esperado para este formato): formato=%s data_id=%s",
            fmt, data_id,
        )
        return True

    if not secret:
        logger.warning("WEBHOOK_SECRET no configurado, firma no verificable")
        return True  # Si no hay secreto configurado, no bloquear

    try:
        WebhookSignatureValidator.validate(x_signature, x_request_id, data_id, secret)
        logger.info("Webhook firma VALIDA: formato=%s data_id=%s", fmt, data_id)
        return True
    except InvalidWebhookSignatureError as e:
        ts, v1 = _parse_signature_values(x_signature)
        logger.warning(
            "Webhook firma INVALIDA: formato=%s data_id=%s request_id=%s ts=%s v1=%s motivo=%s",
            fmt, data_id, x_request_id, ts or e.timestamp, v1, e.reason,
        )
        return False


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

    package = db.query(CreditPackage).filter(
        CreditPackage.id == payment_data.package_id,
        CreditPackage.is_active,
    ).first()

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
                "unit_price": float(package.price),
                "currency_id": "MXN",
            }
        ],
        "external_reference": str(current_user.id),
        "metadata": {"credits": package.credits, "package_id": package.id},
        "back_urls": {
            "success": f"{settings.FRONTEND_URL}/credits?status=success",
            "pending": f"{settings.FRONTEND_URL}/credits?status=pending",
            "failure": f"{settings.FRONTEND_URL}/credits?status=failure",
        }
    }

    if settings.WEBHOOK_URL:
        preference_data["notification_url"] = settings.WEBHOOK_URL

    try:
        preference_response = sdk.preference().create(preference_data)
        
        if preference_response["status"] not in (200, 201):
            error_msg = preference_response.get("response", {}).get("message", "Error desconocido de MercadoPago")
            raise Exception(f"MercadoPago API Error: {error_msg} - {preference_response['response']}")

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
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando preferencia: {str(e)}",
        )


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    logger.info(
        "Webhook HTTP: query=%s x-signature=%r x-request-id=%r",
        dict(request.query_params),
        request.headers.get("x-signature"),
        request.headers.get("x-request-id"),
    )
    if settings.WEBHOOK_SECRET and not verify_webhook_signature(request, settings.WEBHOOK_SECRET):
        if settings.WEBHOOK_VERIFY_SIGNATURE:
            logger.warning("Webhook rechazado por firma invalida (401): MercadoPago reintentara")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )
        logger.debug(
            "Webhook con firma no verificada (WEBHOOK_VERIFY_SIGNATURE=False): se procesa igual"
        )

    body = await request.json()
    logger.info("Webhook recibido: %s", body)

    # Determinar el tipo de evento (Webhooks modernos vs IPN legacy)
    event_type = body.get("type") or body.get("topic") or request.query_params.get("topic")
    
    if event_type == "payment":
        # Extraer el ID del pago
        payment_id = None
        if "data" in body and "id" in body["data"]:
            payment_id = body["data"]["id"]
        elif "resource" in body:
            # En IPN, resource puede ser la URL completa o solo el ID
            res = body["resource"]
            payment_id = res.split('/')[-1] if '/' in res else res
        else:
            payment_id = request.query_params.get("id")

        logger.info("Webhook PAYMENT ID: %s", payment_id)

        if sdk and payment_id:
            try:
                payment_info = sdk.payment().get(payment_id)
                payment_data = payment_info.get("response", {})
                logger.info(
                    "Pago obtenido: external_reference=%s status=%s",
                    payment_data.get("external_reference"),
                    payment_data.get("status"),
                )

                payment_status = payment_data.get("status")
                if payment_status != "approved":
                    logger.info(
                        "Pago %s no aprobado (status=%s): no se acreditan creditos",
                        payment_id, payment_status,
                    )
                    return {"status": "ok"}

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
                            if credits_to_add <= 0:
                                logger.warning(
                                    "Pago %s sin creditos validos (credits=%s): no se acredita",
                                    payment_id, credits_to_add,
                                )
                                return {"status": "ok"}

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
                                transaction_type="purchase",
                                description=f"Compra de paquete - Pago #{payment_id}",
                            )
                            db.add(transaction)

                            db.commit()
            except Exception as e:
                logger.error("Error procesando webhook: %s", e, exc_info=True)

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
