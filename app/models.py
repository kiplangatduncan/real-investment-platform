from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db


# Supported currencies
SUPPORTED_CURRENCIES = {
    "KES": "Kenyan Shilling",
    "USD": "US Dollar",
    "GBP": "British Pound",
    "EUR": "Euro",
    "UGX": "Ugandan Shilling",
    "TZS": "Tanzanian Shilling",
    "RWF": "Rwandan Franc",
    "ZAR": "South African Rand",
    "NGN": "Nigerian Naira",
}


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    # Legacy balance field kept so your existing routes continue working.
    balance = db.Column(
        db.Float,
        default=0.0,
        nullable=False
    )

    # Default/account currency
    currency = db.Column(
        db.String(3),
        default="KES",
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password
        )

    def __repr__(self):
        return f"<User {self.username}>"


class Wallet(db.Model):
    """
    Allows one user to have balances in multiple currencies.
    Example:

    User
      KES  10,000
      USD  100
      EUR  50
    """

    __tablename__ = "wallets"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    currency = db.Column(
        db.String(3),
        nullable=False
    )

    balance = db.Column(
        db.Float,
        default=0.0,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "wallets",
            lazy=True
        )
    )

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "currency",
            name="unique_user_currency"
        ),
    )

    def __repr__(self):
        return f"<Wallet {self.user_id} {self.currency}>"


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    transaction_type = db.Column(
        db.String(50),
        nullable=False
    )

    amount = db.Column(
        db.Float,
        nullable=False
    )

    # Currency used for this transaction
    currency = db.Column(
        db.String(3),
        default="KES",
        nullable=False
    )

    reference = db.Column(
        db.String(100),
        unique=True,
        nullable=True
    )

    status = db.Column(
        db.String(30),
        default="pending",
        nullable=False
    )

    description = db.Column(
        db.String(255),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "transactions",
            lazy=True
        )
    )

    def __repr__(self):
        return (
            f"<Transaction "
            f"{self.id} "
            f"{self.transaction_type} "
            f"{self.currency}>"
        )


def get_or_create_wallet(user_id, currency):
    """
    Get a user's wallet for a currency.
    Creates it if it does not exist.
    """

    currency = currency.upper()

    if currency not in SUPPORTED_CURRENCIES:
        raise ValueError("Unsupported currency.")

    wallet = Wallet.query.filter_by(
        user_id=user_id,
        currency=currency
    ).first()

    if wallet is None:
        wallet = Wallet(
            user_id=user_id,
            currency=currency,
            balance=0.0
        )

        db.session.add(wallet)
        db.session.flush()

    return wallet
