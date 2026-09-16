from app.extensions import db
from app.models import User, Transaction


def credit_balance(user, amount, reference=None, description="Deposit"):
    """
    Credit a user's balance after a deposit has been confirmed.
    """

    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")

    user.balance += amount

    transaction = Transaction(
        user_id=user.id,
        transaction_type="deposit",
        amount=amount,
        reference=reference,
        status="completed",
        description=description
    )

    db.session.add(transaction)
    db.session.commit()

    return transaction


def debit_balance(user, amount, reference=None, description="Withdrawal"):
    """
    Debit a user's balance after a withdrawal has been approved.
    """

    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")

    if user.balance < amount:
        raise ValueError("Insufficient balance.")

    user.balance -= amount

    transaction = Transaction(
        user_id=user.id,
        transaction_type="withdrawal",
        amount=amount,
        reference=reference,
        status="completed",
        description=description
    )

    db.session.add(transaction)
    db.session.commit()

    return transaction


def get_balance(user):
    """Return the user's current balance."""

    return user.balance


def get_transactions(user):
    """Return the user's transactions, newest first."""

    return (
        Transaction.query
        .filter_by(user_id=user.id)
        .order_by(Transaction.created_at.desc())
        .all()
    )
