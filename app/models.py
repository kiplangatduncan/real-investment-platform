from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

from app.extensions import db


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

    balance = db.Column(
        db.Float,
        default=0.0,
        nullable=False
    )

    currency = db.Column(
        db.String(3),
        default="KES",
        nullable=False
    )

    is_admin = db.Column(
        db.Boolean,
        default=False,
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
        backref=db.backref("wallets", lazy=True)
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

    currency = db.Column(
        db.String(3),
        default="KES",
        nullable=False
    )

    reference = db.Column(
        db.String(150),
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

    payment_provider = db.Column(
        db.String(50),
        nullable=True
    )

    payment_method = db.Column(
        db.String(50),
        nullable=True
    )

    provider_reference = db.Column(
        db.String(150),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    user = db.relationship(
        "User",
        backref=db.backref("transactions", lazy=True)
    )

    def __repr__(self):
        return (
            f"<Transaction "
            f"{self.id} "
            f"{self.transaction_type} "
            f"{self.currency}>"
        )


class PaymentAccount(db.Model):
    __tablename__ = "payment_accounts"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    country = db.Column(
        db.String(100),
        nullable=False
    )

    currency = db.Column(
        db.String(3),
        nullable=False
    )

    payment_method = db.Column(
        db.String(80),
        nullable=False
    )

    provider_name = db.Column(
        db.String(120),
        nullable=False
    )

    account_name = db.Column(
        db.String(150),
        nullable=True
    )

    account_number = db.Column(
        db.String(150),
        nullable=True
    )

    phone_number = db.Column(
        db.String(50),
        nullable=True
    )

    branch = db.Column(
        db.String(150),
        nullable=True
    )

    additional_details = db.Column(
        db.Text,
        nullable=True
    )

    instructions = db.Column(
        db.Text,
        nullable=True
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    def __repr__(self):
        return (
            f"<PaymentAccount "
            f"{self.country} "
            f"{self.currency} "
            f"{self.payment_method}>"
        )


def get_or_create_wallet(user_id, currency):
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
