from sqlalchemy.orm import Session
from app.models.user import User, CreditTransaction


def deduct_credit(user: User, db: Session, description: str = "Consulta legal") -> bool:
    if user.credits <= 0:
        return False

    user.credits -= 1

    transaction = CreditTransaction(
        user_id=user.id,
        amount=-1,
        transaction_type="usage",
        description=description,
    )
    db.add(transaction)
    db.commit()

    return True


def add_credits(user: User, db: Session, amount: int, description: str = "Compra de creditos") -> None:
    user.credits += amount

    transaction = CreditTransaction(
        user_id=user.id,
        amount=amount,
        transaction_type="purchase",
        description=description,
    )
    db.add(transaction)
    db.commit()
