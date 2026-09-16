from flask import (
    Blueprint,
    render_template,
    request,
    jsonify
)

from flask_login import (
    login_required,
    current_user
)

from app.extensions import db
from app.models import Transaction
from app.mpesa import initiate_stk_push


payments = Blueprint(
    "payments",
    __name__
)


# =========================================================
# PHONE NORMALIZATION
# =========================================================

def normalize_phone(phone):

    phone = str(phone or "").strip()

    phone = (
        phone
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
        .replace("+", "")
    )

    if phone.startswith("07") and len(phone) == 10:

        phone = "254" + phone[1:]

    elif phone.startswith("01") and len(phone) == 10:

        phone = "254" + phone[1:]

    elif phone.startswith("7") and len(phone) == 9:

        phone = "254" + phone

    elif phone.startswith("1") and len(phone) == 9:

        phone = "254" + phone

    return phone


# =========================================================
# PHONE VALIDATION
# =========================================================

def valid_kenyan_phone(phone):

    return (
        len(phone) == 12
        and phone.startswith("254")
        and phone[3] in ("7", "1")
        and phone.isdigit()
    )


# =========================================================
# DEPOSIT PAGE
# =========================================================

@payments.route(
    "/deposit",
    methods=["GET", "POST"]
)
@login_required
def deposit():

    if request.method == "GET":

        return render_template(
            "deposit.html"
        )


    data = (
        request.get_json(
            silent=True
        )
        or request.form
    )


    raw_amount = data.get(
        "amount"
    )

    raw_phone = data.get(
        "phone"
    )


    # =====================================================
    # VALIDATE AMOUNT
    # =====================================================

    try:

        amount = float(
            raw_amount
        )

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message":
                "Enter a valid amount."
        }), 400


    if amount < 10:

        return jsonify({
            "success": False,
            "message":
                "Minimum deposit is KSh 10."
        }), 400


    if amount != int(amount):

        return jsonify({
            "success": False,
            "message":
                "Deposit amount must be a whole number."
        }), 400


    amount = int(amount)


    # =====================================================
    # VALIDATE PHONE
    # =====================================================

    phone = normalize_phone(
        raw_phone
    )


    if not valid_kenyan_phone(phone):

        return jsonify({
            "success": False,
            "message":
                "Enter a valid Kenyan M-PESA number."
        }), 400


    # =====================================================
    # CREATE PENDING TRANSACTION
    # =====================================================

    transaction = Transaction(

        user_id=current_user.id,

        transaction_type="deposit",

        amount=amount,

        status="pending",

        description=(
            f"M-PESA deposit from {phone}"
        )
    )


    db.session.add(
        transaction
    )

    db.session.commit()


    # =====================================================
    # SEND STK PUSH
    # =====================================================

    try:

        result = initiate_stk_push(

            phone_number=phone,

            amount=amount,

            account_reference=(
                f"DEP{transaction.id}"
            ),

            transaction_description=(
                "Investment deposit"
            )
        )


        checkout_request_id = (
            result.get(
                "CheckoutRequestID"
            )
        )


        if not checkout_request_id:

            transaction.status = "failed"

            transaction.description = (
                "M-PESA did not return "
                "a CheckoutRequestID."
            )

            db.session.commit()


            return jsonify({
                "success": False,
                "message":
                    "M-PESA did not return a valid payment request."
            }), 502


        # Save CheckoutRequestID
        transaction.reference = (
            checkout_request_id
        )

        transaction.description = (
            f"M-PESA STK request for {phone}"
        )


        db.session.commit()


        return jsonify({

            "success": True,

            "message": result.get(
                "CustomerMessage",
                "STK Push sent successfully. "
                "Check your phone and enter "
                "your M-PESA PIN."
            ),

            "checkout_request_id":
                checkout_request_id
        })


    except Exception as exc:

        print(
            "PAYMENT ERROR:",
            repr(exc)
        )


        transaction.status = "failed"

        transaction.description = (
            f"M-PESA request failed: "
            f"{str(exc)[:200]}"
        )


        db.session.commit()


        return jsonify({

            "success": False,

            "message":
                "Unable to start the M-PESA payment request."
        }), 500
