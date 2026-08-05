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

    class Config:
        from_attributes = True


class PaymentCreate(BaseModel):
    package_id: str


class PaymentResponse(BaseModel):
    init_point: str
    preference_id: str


class PaymentStatus(BaseModel):
    status: str
    credits_added: int
