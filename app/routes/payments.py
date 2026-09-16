from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Transaction
from app.mpesa.mpesa import initiate_stk_push


payments = Blueprint("payments", __name__)


def normalize_phone(phone):
    phone = str(phone or "").strip().replace(" ", "").replace("-", "")

    if phone.startswith("+254"):
        phone = phone[1:]

    if phone.startswith("254"):
        return phone

    if phone.startswith("07") or phone.startswith("01"):
        return "254" + phone[1:]

    if phone.startswith("7") or phone.startswith("1"):
        return "254" + phone

    return phone


def valid_kenyan_phone(phone):
    phone = normalize_phone(phone)
    return len(phone) == 12 and phone.startswith("254")


@payments.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():

    if request.method == "POST":

        amount_raw = request.form.get("amount", "").strip()
        phone_raw = request.form.get("phone", "").strip()

        if not amount_raw:
            flash("Please enter the deposit amount.", "danger")
            return redirect(url_for("payments.deposit"))

        try:
            amount = int(float(amount_raw))
        except (ValueError, TypeError):
            flash("Please enter a valid amount.", "danger")
            return redirect(url_for("payments.deposit"))

        if amount < 10:
            flash("Minimum deposit is $10.", "danger")
            return redirect(url_for("payments.deposit"))

        if amount != float(amount_raw):
            flash("Deposit amount must be a whole number.", "danger")
            return redirect(url_for("payments.deposit"))

        phone = normalize_phone(phone_raw)

        if not valid_kenyan_phone(phone):
            flash(
                "Please enter a valid Kenyan M-PESA number, for example 0712345678.",
                "danger",
            )
            return redirect(url_for("payments.deposit"))

        transaction = Transaction(
            user_id=current_user.id,
            transaction_type="deposit",
            amount=amount,
            status="pending",
            description="M-PESA investment deposit",
        )

        db.session.add(transaction)
        db.session.commit()

        try:
            response = initiate_stk_push(
                phone_number=phone,
                amount=amount,
                account_reference=f"DEP{transaction.id}",
                transaction_description="Investment deposit",
            )

            checkout_request_id = response.get("CheckoutRequestID")

            if not checkout_request_id:
                transaction.status = "failed"
                db.session.commit()

                flash(
                    response.get("errorMessage", "M-PESA STK Push failed."),
                    "danger",
                )

                return redirect(url_for("payments.deposit"))

            transaction.reference = checkout_request_id
            transaction.status = "pending"

            db.session.commit()

            flash(
                "STK Push sent. Check your phone and enter your M-PESA PIN.",
                "success",
            )

            return redirect(url_for("main.index"))

        except Exception as e:

            transaction.status = "failed"
            transaction.description = f"M-PESA error: {str(e)[:200]}"

            db.session.commit()

            flash(
                "Unable to start the M-PESA payment. Please try again.",
                "danger",
            )

            return redirect(url_for("payments.deposit"))

    return render_template("deposit.html")
