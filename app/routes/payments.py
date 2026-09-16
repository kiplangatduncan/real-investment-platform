from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app import db
from app.models import Transaction


payments = Blueprint("payments", __name__)


@payments.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", 0))
        except (ValueError, TypeError):
            amount = 0

        if amount <= 0:
            flash("Enter a valid amount.")
            return redirect(url_for("payments.deposit"))

        # IMPORTANT:
        # Do NOT add money to the user's balance here.
        #
        # The balance must only be updated after M-PESA
        # has confirmed that the payment was successfully received.
        #
        # M-PESA confirmation/callback handling should be
        # responsible for crediting the user's balance.

        flash(
            "Payment request received. "
            "Your balance will be updated after M-PESA confirms the payment."
        )

        return redirect(url_for("main.dashboard"))

    return render_template("deposit.html")
