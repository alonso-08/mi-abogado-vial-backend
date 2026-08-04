from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User, CreditTransaction, Payment
from app.schemas.credits import (
    CreditBalance,
    CreditHistory,
    CreditTransactionResponse,
    PaymentCreate,
    PaymentResponse,
    AVAILABLE_PACKAGES,
)
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/credits", tags=["credits"])


@router.get("", response_model=CreditBalance)
def get_balance(current_user: User = Depends(get_current_user)):
    return CreditBalance(amount=current_user.credits)


@router.get("/history", response_model=CreditHistory)
def get_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    transactions = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.user_id == current_user.id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(50)
        .all()
    )
    return CreditHistory(
        transactions=[CreditTransactionResponse.model_validate(t) for t in transactions],
        total=len(transactions),
    )


@router.get("/packages")
def get_packages():
    return AVAILABLE_PACKAGES
