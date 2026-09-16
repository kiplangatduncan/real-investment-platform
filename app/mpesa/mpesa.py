import os
import base64
from datetime import datetime

import requests
from requests.auth import HTTPBasicAuth

from flask import (
    Blueprint,
    request,
    jsonify
)

from flask_login import (
    login_required,
    current_user
)

from app.extensions import db
from app.models import (
    User,
    Transaction,
    SUPPORTED_CURRENCIES,
    get_or_create_wallet
)


mpesa_bp = Blueprint(
    "mpesa",
    __name__,
    url_prefix="/mpesa"
)


# ---------------------------------------------------------
# M-PESA SETTINGS
# ---------------------------------------------------------

MPESA_ENV = os.getenv(
    "MPESA_ENV",
    "sandbox"
).lower()

if MPESA_ENV == "production":
    MPESA_BASE_URL = "https://api.safaricom.co.ke"
else:
    MPESA_BASE_URL = "https://sandbox.safaricom.co.ke"


MPESA_CONSUMER_KEY = os.getenv(
    "MPESA_CONSUMER_KEY"
)

MPESA_CONSUMER_SECRET = os.getenv(
    "MPESA_CONSUMER_SECRET"
)

MPESA_SHORTCODE = os.getenv(
    "MPESA_SHORTCODE"
)

MPESA_PASSKEY = os.getenv(
    "MPESA_PASSKEY"
)

MPESA_CALLBACK_URL = os.getenv(
    "MPESA_CALLBACK_URL"
)


# ---------------------------------------------------------
# PHONE NUMBER
# ---------------------------------------------------------

def normalize_phone(phone):
    """
    Converts:

    0712345678
    0112345678
    +254712345678
    254712345678

    into:

    254712345678
    """

    phone = str(phone).strip()

    phone = phone.replace(
        " ",
        ""
    )

    phone = phone.replace(
        "-",
        ""
    )

    if phone.startswith("+"):
        phone = phone[1:]

    if phone.startswith("07") or phone.startswith("01"):
        phone = "254" + phone[1:]

    if not phone.startswith("254"):
        raise ValueError(
            "Enter a valid Kenyan M-PESA number."
        )

    if len(phone) != 12:
        raise ValueError(
            "Enter a valid Kenyan M-PESA number."
        )

    return phone


# ---------------------------------------------------------
# ACCESS TOKEN
# ---------------------------------------------------------

def get_access_token():

    if not MPESA_CONSUMER_KEY:
        raise ValueError(
            "MPESA_CONSUMER_KEY is not configured."
        )

    if not MPESA_CONSUMER_SECRET:
        raise ValueError(
            "MPESA_CONSUMER_SECRET is not configured."
        )

    url = (
        MPESA_BASE_URL +
        "/oauth/v1/generate"
        "?grant_type=client_credentials"
    )

    response = requests.get(
        url,
        auth=HTTPBasicAuth(
            MPESA_CONSUMER_KEY,
            MPESA_CONSUMER_SECRET
        ),
        timeout=30
    )

    if response.status_code != 200:
        raise RuntimeError(
            "M-PESA authorization failed: "
            + response.text
        )

    data = response.json()

    token = data.get(
        "access_token"
    )

    if not token:
        raise RuntimeError(
            "M-PESA did not return an access token."
        )

    return token


# ---------------------------------------------------------
# PASSWORD / STK TIMESTAMP
# ---------------------------------------------------------

def generate_password(timestamp):

    if not MPESA_SHORTCODE:
        raise ValueError(
            "MPESA_SHORTCODE is not configured."
        )

    if not MPESA_PASSKEY:
        raise ValueError(
            "MPESA_PASSKEY is not configured."
        )

    raw = (
        MPESA_SHORTCODE +
        MPESA_PASSKEY +
        timestamp
    )

    return base64.b64encode(
        raw.encode("utf-8")
    ).decode("utf-8")


# ---------------------------------------------------------
# STK PUSH
# ---------------------------------------------------------

@mpesa_bp.route(
    "/stk-push",
    methods=["POST"]
)
@login_required
def stk_push():

    try:

        data = request.get_json(
            silent=True
        ) or request.form

        amount = data.get(
            "amount"
        )

        phone = data.get(
            "phone"
        )

        currency = data.get(
            "currency",
            "KES"
        ).upper()

        # ---------------------------------------------
        # Currency validation
        # ---------------------------------------------

        if currency not in SUPPORTED_CURRENCIES:
            return jsonify({
                "success": False,
                "message": "Unsupported currency."
            }), 400

        # ---------------------------------------------
        # M-PESA only works with KES
        # ---------------------------------------------

        if currency != "KES":
            return jsonify({
                "success": False,
                "message": (
                    "M-PESA payments are currently "
                    "available only in KES."
                )
            }), 400

        # ---------------------------------------------
        # Amount validation
        # ---------------------------------------------

        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return jsonify({
                "success": False,
                "message": "Enter a valid amount."
            }), 400

        if amount <= 0:
            return jsonify({
                "success": False,
                "message": (
                    "Amount must be greater than zero."
                )
            }), 400

        # M-PESA amount should be a whole number
        amount = int(round(amount))

        # ---------------------------------------------
        # Phone validation
        # ---------------------------------------------

        try:
            phone = normalize_phone(phone)
        except ValueError as exc:
            return jsonify({
                "success": False,
                "message": str(exc)
            }), 400

        # ---------------------------------------------
        # Check settings
        # ---------------------------------------------

        if not MPESA_CALLBACK_URL:
            return jsonify({
                "success": False,
                "message": (
                    "MPESA_CALLBACK_URL is not configured."
                )
            }), 500

        if not MPESA_SHORTCODE:
            return jsonify({
                "success": False,
                "message": (
                    "MPESA_SHORTCODE is not configured."
                )
            }), 500

        # ---------------------------------------------
        # Get access token
        # ---------------------------------------------

        token = get_access_token()

        # ---------------------------------------------
        # Timestamp
        # ---------------------------------------------

        timestamp = datetime.now().strftime(
            "%Y%m%d%H%M%S"
        )

        password = generate_password(
            timestamp
        )

        # ---------------------------------------------
        # STK request
        # ---------------------------------------------

        url = (
            MPESA_BASE_URL +
            "/mpesa/stkpush/v1/processrequest"
        )

        payload = {
            "BusinessShortCode": MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": MPESA_SHORTCODE,
            "PhoneNumber": phone,
            "CallBackURL": MPESA_CALLBACK_URL,
            "AccountReference": (
                "INV-" +
                str(current_user.id)
            ),
            "TransactionDesc": (
                "Investment platform deposit"
            )
        }

        headers = {
            "Authorization": (
                "Bearer " + token
            ),
            "Content-Type": (
                "application/json"
            )
        }

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30
        )

        # ---------------------------------------------
        # Safaricom response
        # ---------------------------------------------

        try:
            result = response.json()
        except ValueError:
            result = {
                "error": response.text
            }

        if response.status_code != 200:

            print(
                "M-PESA HTTP ERROR:",
                response.status_code,
                result
            )

            return jsonify({
                "success": False,
                "message": (
                    result.get(
                        "errorMessage"
                    )
                    or result.get(
                        "error"
                    )
                    or "M-PESA request failed."
                )
            }), 400

        response_code = str(
            result.get(
                "ResponseCode",
                ""
            )
        )

        if response_code != "0":

            return jsonify({
                "success": False,
                "message": (
                    result.get(
                        "ResponseDescription"
                    )
                    or "M-PESA rejected the request."
                )
            }), 400

        # ---------------------------------------------
        # Save pending transaction
        # ---------------------------------------------

        checkout_id = result.get(
            "CheckoutRequestID"
        )

        transaction = Transaction(
            user_id=current_user.id,
            transaction_type="deposit",
            amount=amount,
            currency="KES",
            reference=checkout_id,
            status="pending",
            description="M-PESA deposit"
        )

        db.session.add(transaction)

        # Make sure KES wallet exists
        get_or_create_wallet(
            current_user.id,
            "KES"
        )

        db.session.commit()

        return jsonify({
            "success": True,
            "message": (
                "M-PESA payment request sent. "
                "Please check your phone."
            ),
            "checkout_request_id": checkout_id
        })

    except requests.exceptions.RequestException as exc:

        print(
            "M-PESA CONNECTION ERROR:",
            str(exc)
        )

        return jsonify({
            "success": False,
            "message": (
                "Unable to connect to the "
                "M-PESA payment server."
            )
        }), 503

    except Exception as exc:

        db.session.rollback()

        print(
            "M-PESA ERROR:",
            repr(exc)
        )

        return jsonify({
            "success": False,
            "message": str(exc)
        }), 500


# ---------------------------------------------------------
# M-PESA CALLBACK
# ---------------------------------------------------------

@mpesa_bp.route(
    "/callback",
    methods=["POST"]
)
def mpesa_callback():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        print(
            "M-PESA CALLBACK:",
            data
        )

        body = data.get(
            "Body",
            {}
        )

        stk_callback = body.get(
            "stkCallback",
            {}
        )

        checkout_request_id = (
            stk_callback.get(
                "CheckoutRequestID"
            )
        )

        result_code = stk_callback.get(
            "ResultCode"
        )

        result_description = (
            stk_callback.get(
                "ResultDesc",
                ""
            )
        )

        if not checkout_request_id:
            return jsonify({
                "ResultCode": 0,
                "ResultDesc": "Accepted"
            })

        transaction = Transaction.query.filter_by(
            reference=checkout_request_id
        ).first()

        if not transaction:
            print(
                "Transaction not found:",
                checkout_request_id
            )

            return jsonify({
                "ResultCode": 0,
                "ResultDesc": "Accepted"
            })

        # Prevent double credit
        if transaction.status == "completed":
            return jsonify({
                "ResultCode": 0,
                "ResultDesc": "Already processed"
            })

        # ---------------------------------------------
        # Successful payment
        # ---------------------------------------------

        if str(result_code) == "0":

            transaction.status = "completed"

            transaction.description = (
                "M-PESA deposit completed"
            )

            wallet = get_or_create_wallet(
                transaction.user_id,
                transaction.currency
            )

            wallet.balance += (
                transaction.amount
            )

            # Keep old balance working for existing
            # parts of the application.
            if transaction.currency == "KES":

                user = db.session.get(
                    User,
                    transaction.user_id
                )

                if user:
                    user.balance += (
                        transaction.amount
                    )
                    user.currency = "KES"

            db.session.commit()

            print(
                "M-PESA payment completed:",
                checkout_request_id
            )

        else:

            transaction.status = "failed"

            transaction.description = (
                "M-PESA failed: " +
                result_description
            )

            db.session.commit()

            print(
                "M-PESA payment failed:",
                result_description
            )

        return jsonify({
            "ResultCode": 0,
            "ResultDesc": "Accepted"
        })

    except Exception as exc:

        db.session.rollback()

        print(
            "CALLBACK ERROR:",
            repr(exc)
        )

        return jsonify({
            "ResultCode": 0,
            "ResultDesc": "Accepted"
        })


# ---------------------------------------------------------
# SUPPORTED CURRENCIES API
# ---------------------------------------------------------

@mpesa_bp.route(
    "/currencies",
    methods=["GET"]
)
def currencies():

    return jsonify({
        "success": True,
        "currencies": SUPPORTED_CURRENCIES
    })
