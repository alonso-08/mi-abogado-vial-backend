from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class CreditBalance(BaseModel):
    amount: int


class CreditTransactionResponse(BaseModel):
    id: UUID
    amount: int
    transaction_type: str
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CreditHistory(BaseModel):
    transactions: List[CreditTransactionResponse]
    total: int


class PackageInfo(BaseModel):
    id: str
    name: str
    credits: int
    price: float
    price_per_credit: float


AVAILABLE_PACKAGES = [
    PackageInfo(id="basico", name="Basico", credits=20, price=49.0, price_per_credit=2.45),
    PackageInfo(id="estandar", name="Estandar", credits=50, price=99.0, price_per_credit=1.98),
    PackageInfo(id="premium", name="Premium", credits=100, price=179.0, price_per_credit=1.79),
    PackageInfo(id="ultra", name="Ultra", credits=250, price=399.0, price_per_credit=1.60),
]


class PaymentCreate(BaseModel):
    package_id: str


class PaymentResponse(BaseModel):
    init_point: str
    preference_id: str


class PaymentStatus(BaseModel):
    status: str
    credits_added: int
