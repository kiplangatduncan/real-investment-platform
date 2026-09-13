from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Transaction

payments = Blueprint("payments", __name__)


@payments.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            amount = 0

        if amount <= 0:
            flash("Enter a valid amount.")
            return redirect(url_for("payments.deposit"))

        current_user.balance += amount

        transaction = Transaction(
            user_id=current_user.id,
            transaction_type="Deposit",
            amount=amount,
            description="Account deposit"
        )

        db.session.add(transaction)
        db.session.commit()

        flash("Deposit recorded successfully.")
        return redirect(url_for("main.dashboard"))

    return render_template("deposit.html")
