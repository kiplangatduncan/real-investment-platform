from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.models import Transaction

main = Blueprint("main", __name__)


@main.route("/")
def index():
    if current_user.is_authenticated:
        return render_template(
            "dashboard.html",
            user=current_user
        )

    return render_template("index.html")


@main.route("/dashboard")
@login_required
def dashboard():
    transactions = (
        Transaction.query
        .filter_by(user_id=current_user.id)
        .order_by(Transaction.created_at.desc())
        .all()
    )

    total_deposits = sum(
        transaction.amount
        for transaction in transactions
        if transaction.transaction_type == "deposit"
        and transaction.status == "completed"
    )

    total_withdrawals = sum(
        transaction.amount
        for transaction in transactions
        if transaction.transaction_type == "withdrawal"
        and transaction.status == "completed"
    )

    investment_balance = sum(
        transaction.amount
        for transaction in transactions
        if transaction.transaction_type == "investment"
        and transaction.status == "completed"
    )

    return render_template(
        "dashboard.html",
        user=current_user,
        balance=current_user.balance,
        total_deposits=total_deposits,
        total_withdrawals=total_withdrawals,
        investment_balance=investment_balance,
        transactions=transactions[:10]
    )


@main.route("/transactions")
@login_required
def transactions():
    user_transactions = (
        Transaction.query
        .filter_by(user_id=current_user.id)
        .order_by(Transaction.created_at.desc())
        .all()
    )

    return render_template(
        "transactions.html",
        user=current_user,
        transactions=user_transactions
    )
