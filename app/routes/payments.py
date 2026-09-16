from flask import (
    Blueprint,
    render_template,
    request,
    flash,
    redirect,
    url_for
)

from flask_login import (
    login_required,
    current_user
)

from app.extensions import db

from app.models import (
    Transaction,
    SUPPORTED_CURRENCIES,
    get_or_create_wallet
)

from app.mpesa.mpesa import initiate_stk_push


payments = Blueprint(
    "payments",
    __name__
)


# ---------------------------------------------------------
# PHONE NUMBER
# ---------------------------------------------------------

def normalize_phone(phone):
    phone = str(
        phone or ""
    ).strip()

    phone = phone.replace(
        " ",
        ""
    )

    phone = phone.replace(
        "-",
        ""
    )

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

    phone = normalize_phone(
        phone
    )

    return (
        len(phone) == 12
        and phone.startswith("254")
    )


# ---------------------------------------------------------
# DEPOSIT
# ---------------------------------------------------------

@payments.route(
    "/deposit",
    methods=["GET", "POST"]
)
@login_required
def deposit():

    if request.method == "POST":

        # ---------------------------------------------
        # Get form values
        # ---------------------------------------------

        amount_raw = request.form.get(
            "amount",
            ""
        ).strip()

        phone_raw = request.form.get(
            "phone",
            ""
        ).strip()

        currency = request.form.get(
            "currency",
            "KES"
        ).strip().upper()


        # ---------------------------------------------
        # Validate currency
        # ---------------------------------------------

        if currency not in SUPPORTED_CURRENCIES:

            flash(
                "Unsupported currency selected.",
                "danger"
            )

            return redirect(
                url_for(
                    "payments.deposit"
                )
            )


        # ---------------------------------------------
        # Current payment method
        # ---------------------------------------------

        # M-PESA is currently supported for KES only.

        if currency != "KES":

            flash(
                f"{currency} is supported as an "
                "account currency, but M-PESA "
                "deposits are currently available "
                "only for KES.",
                "warning"
            )

            return redirect(
                url_for(
                    "payments.deposit"
                )
            )


        # ---------------------------------------------
        # Validate amount
        # ---------------------------------------------

        if not amount_raw:

            flash(
                "Please enter the deposit amount.",
                "danger"
            )

            return redirect(
                url_for(
                    "payments.deposit"
                )
            )


        try:

            amount_float = float(
                amount_raw
            )

        except (
            ValueError,
            TypeError
        ):

            flash(
                "Please enter a valid amount.",
                "danger"
            )

            return redirect(
                url_for(
                    "payments.deposit"
                )
            )


        if amount_float <= 0:

            flash(
                "Deposit amount must be greater than zero.",
                "danger"
            )

            return redirect(
                url_for(
                    "payments.deposit"
                )
            )


        # M-PESA amount is kept as a whole number.
        amount = int(
            round(amount_float)
        )


        if amount < 10:

            flash(
                "Minimum deposit is 10 KES.",
                "danger"
            )

            return redirect(
                url_for(
                    "payments.deposit"
                )
            )


        # ---------------------------------------------
        # Validate phone
        # ---------------------------------------------

        phone = normalize_phone(
            phone_raw
        )


        if not valid_kenyan_phone(
            phone
        ):

            flash(
                "Please enter a valid Kenyan "
                "M-PESA number, for example "
                "0712345678.",
                "danger"
            )

            return redirect(
                url_for(
                    "payments.deposit"
                )
            )


        # ---------------------------------------------
        # Create pending transaction
        # ---------------------------------------------

        transaction = Transaction(
            user_id=current_user.id,
            transaction_type="deposit",
            amount=amount,
            currency="KES",
            status="pending",
            description=(
                "M-PESA investment deposit"
            )
        )


        db.session.add(
            transaction
        )

        db.session.commit()


        # ---------------------------------------------
        # Send M-PESA STK Push
        # ---------------------------------------------

        try:

            response = initiate_stk_push(
                phone_number=phone,
                amount=amount,
                account_reference=(
                    f"DEP{transaction.id}"
                ),
                transaction_description=(
                    "Investment deposit"
                )
            )


            # Make sure response is a dictionary
            if not isinstance(
                response,
                dict
            ):

                transaction.status = "failed"

                transaction.description = (
                    "M-PESA returned an invalid response."
                )

                db.session.commit()

                flash(
                    "M-PESA returned an invalid response.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "payments.deposit"
                    )
                )


            # -----------------------------------------
            # Get CheckoutRequestID
            # -----------------------------------------

            checkout_request_id = response.get(
                "CheckoutRequestID"
            )


            # -----------------------------------------
            # STK Push failed
            # -----------------------------------------

            if not checkout_request_id:

                transaction.status = "failed"

                error_message = (
                    response.get(
                        "errorMessage"
                    )
                    or response.get(
                        "ResponseDescription"
                    )
                    or response.get(
                        "error"
                    )
                    or "M-PESA STK Push failed."
                )

                transaction.description = (
                    "M-PESA failed: "
                    + str(error_message)[:200]
                )

                db.session.commit()

                flash(
                    str(error_message),
                    "danger"
                )

                return redirect(
                    url_for(
                        "payments.deposit"
                    )
                )


            # -----------------------------------------
            # STK Push successfully initiated
            # -----------------------------------------

            transaction.reference = (
                checkout_request_id
            )

            transaction.status = "pending"

            transaction.description = (
                "M-PESA STK Push sent"
            )

            db.session.commit()


            flash(
                "STK Push sent. Check your phone "
                "and enter your M-PESA PIN.",
                "success"
            )


            return redirect(
                url_for(
                    "main.index"
                )
            )


        # ---------------------------------------------
        # M-PESA exception
        # ---------------------------------------------

        except Exception as e:

            db.session.rollback()


            # Try to mark transaction as failed.
            try:

                transaction = Transaction.query.get(
                    transaction.id
                )

                if transaction:

                    transaction.status = "failed"

                    transaction.description = (
                        "M-PESA error: "
                        + str(e)[:200]
                    )

                    db.session.commit()

            except Exception:

                db.session.rollback()


            print(
                "M-PESA PAYMENT ERROR:",
                repr(e)
            )


            flash(
                "Unable to start the M-PESA payment. "
                "Please try again.",
                "danger"
            )


            return redirect(
                url_for(
                    "payments.deposit"
                )
            )


    # -------------------------------------------------
    # GET REQUEST
    # -------------------------------------------------

    return render_template(
        "deposit.html"
    )
