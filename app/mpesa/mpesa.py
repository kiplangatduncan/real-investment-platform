import os
import base64
from datetime import datetime

import requests
from requests.auth import HTTPBasicAuth

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models import (
    User,
    Transaction,
    SUPPORTED_CURRENCIES,
    get_or_create_wallet,
)


# =========================================================
# M-PESA BLUEPRINT
# =========================================================

mpesa_bp = Blueprint(
    "mpesa",
    __name__,
    url_prefix="/mpesa"
)


# =========================================================
# M-PESA SETTINGS
# =========================================================

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


# =========================================================
# PHONE NUMBER NORMALIZATION
# =========================================================

def normalize_phone(phone):
    """
    Convert common Kenyan phone formats to:

    254712345678
    """

    phone = str(phone or "").strip()

    phone = phone.replace(" ", "")
    phone = phone.replace("-", "")

    if phone.startswith("+254"):
        phone = phone[1:]

    elif phone.startswith("07") or phone.startswith("01"):
        phone = "254" + phone[1:]

    elif phone.startswith("7") or phone.startswith("1"):
        phone = "254" + phone

    if not phone.startswith("254"):
        raise ValueError(
            "Enter a valid Kenyan M-PESA number."
        )

    if len(phone) != 12:
        raise ValueError(
            "Enter a valid Kenyan M-PESA number."
        )

    return phone


# =========================================================
# GET M-PESA ACCESS TOKEN
# =========================================================

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
        MPESA_BASE_URL
        + "/oauth/v1/generate"
        + "?grant_type=client_credentials"
    )

    response = requests.get(
        url,
        auth=HTTPBasicAuth(
            MPESA_CONSUMER_KEY,
            MPESA_CONSUMER_SECRET
        ),
        timeout=30
    )

    try:
        result = response.json()
    except ValueError:
        result = {}

    if response.status_code != 200:

        raise RuntimeError(
            "M-PESA authorization failed: "
            + str(
                result.get(
                    "errorMessage",
                    response.text
                )
            )
        )

    token = result.get(
        "access_token"
    )

    if not token:
        raise RuntimeError(
            "M-PESA did not return an access token."
        )

    return token


# =========================================================
# GENERATE STK PASSWORD
# =========================================================

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
        MPESA_SHORTCODE
        + MPESA_PASSKEY
        + timestamp
    )

    password = base64.b64encode(
        raw.encode("utf-8")
    ).decode("utf-8")

    return password


# =========================================================
# INITIATE STK PUSH
# =========================================================

def initiate_stk_push(
    phone_number,
    amount,
    account_reference,
    transaction_description
):
    """
    Send an M-PESA STK Push.

    This function is used by:

        app/routes/payments.py
    """

    # -----------------------------------------------------
    # Validate configuration
    # -----------------------------------------------------

    if not MPESA_SHORTCODE:
        raise ValueError(
            "MPESA_SHORTCODE is not configured."
        )

    if not MPESA_CALLBACK_URL:
        raise ValueError(
            "MPESA_CALLBACK_URL is not configured."
        )

    # -----------------------------------------------------
    # Validate amount
    # -----------------------------------------------------

    try:
        amount = float(amount)
    except (TypeError, ValueError):

        raise ValueError(
            "Enter a valid deposit amount."
        )

    if amount <= 0:

        raise ValueError(
            "Amount must be greater than zero."
        )

    # M-PESA accepts whole KES amounts
    amount = int(round(amount))

    # -----------------------------------------------------
    # Validate phone
    # -----------------------------------------------------

    phone_number = normalize_phone(
        phone_number
    )

    # -----------------------------------------------------
    # Get access token
    # -----------------------------------------------------

    token = get_access_token()

    # -----------------------------------------------------
    # Generate timestamp
    # -----------------------------------------------------

    timestamp = datetime.now().strftime(
        "%Y%m%d%H%M%S"
    )

    password = generate_password(
        timestamp
    )

    # -----------------------------------------------------
    # STK Push URL
    # -----------------------------------------------------

    url = (
        MPESA_BASE_URL
        + "/mpesa/stkpush/v1/processrequest"
    )

    # -----------------------------------------------------
    # STK Push payload
    # -----------------------------------------------------

    payload = {
        "BusinessShortCode": MPESA_SHORTCODE,

        "Password": password,

        "Timestamp": timestamp,

        "TransactionType":
            "CustomerPayBillOnline",

        "Amount": amount,

        "PartyA": phone_number,

        "PartyB": MPESA_SHORTCODE,

        "PhoneNumber": phone_number,

        "CallBackURL": MPESA_CALLBACK_URL,

        "AccountReference":
            str(account_reference)[:12],

        "TransactionDesc":
            str(transaction_description)[:20],
    }

    headers = {
        "Authorization":
            "Bearer " + token,

        "Content-Type":
            "application/json",
    }

    # -----------------------------------------------------
    # Send request to Safaricom
    # -----------------------------------------------------

    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=30
    )

    # -----------------------------------------------------
    # Read response
    # -----------------------------------------------------

    try:
        result = response.json()

    except ValueError:

        result = {
            "errorMessage": response.text
        }

    print(
        "M-PESA STK RESPONSE:",
        result
    )

    # -----------------------------------------------------
    # HTTP error
    # -----------------------------------------------------

    if response.status_code != 200:

        raise RuntimeError(
            result.get(
                "errorMessage",
                result.get(
                    "error",
                    "M-PESA request failed."
                )
            )
        )

    # -----------------------------------------------------
    # Safaricom response code
    # -----------------------------------------------------

    response_code = str(
        result.get(
            "ResponseCode",
            ""
        )
    )

    if response_code != "0":

        raise RuntimeError(
            result.get(
                "ResponseDescription",
                result.get(
                    "errorMessage",
                    "M-PESA rejected the request."
                )
            )
        )

    # -----------------------------------------------------
    # Checkout Request ID
    # -----------------------------------------------------

    checkout_request_id = result.get(
        "CheckoutRequestID"
    )

    if not checkout_request_id:

        raise RuntimeError(
            "M-PESA did not return a CheckoutRequestID."
        )

    return result


# =========================================================
# DIRECT STK PUSH API
# =========================================================

@mpesa_bp.route(
    "/stk-push",
    methods=["POST"]
)
@login_required
def stk_push():

    try:

        # -------------------------------------------------
        # Accept JSON or normal form data
        # -------------------------------------------------

        data = (
            request.get_json(
                silent=True
            )
            or request.form
        )

        amount = data.get(
            "amount"
        )

        phone = data.get(
            "phone"
        )

        currency = data.get(
            "currency",
            "KES"
        )

        currency = str(
            currency
        ).upper()

        # -------------------------------------------------
        # Currency validation
        # -------------------------------------------------

        if currency not in SUPPORTED_CURRENCIES:

            return jsonify({
                "success": False,
                "message": "Unsupported currency."
            }), 400

        # -------------------------------------------------
        # M-PESA only accepts KES
        # -------------------------------------------------

        if currency != "KES":

            return jsonify({
                "success": False,
                "message":
                    "M-PESA payments are currently "
                    "available only in KES."
            }), 400

        # -------------------------------------------------
        # Amount validation
        # -------------------------------------------------

        try:
            amount = float(amount)

        except (TypeError, ValueError):

            return jsonify({
                "success": False,
                "message":
                    "Enter a valid amount."
            }), 400

        if amount <= 0:

            return jsonify({
                "success": False,
                "message":
                    "Amount must be greater than zero."
            }), 400

        amount = int(
            round(amount)
        )

        # -------------------------------------------------
        # Phone validation
        # -------------------------------------------------

        try:

            phone = normalize_phone(
                phone
            )

        except ValueError as exc:

            return jsonify({
                "success": False,
                "message": str(exc)
            }), 400

        # -------------------------------------------------
        # Create pending transaction first
        # -------------------------------------------------

        transaction = Transaction(
            user_id=current_user.id,
            transaction_type="deposit",
            amount=amount,
            currency="KES",
            status="pending",
            description="M-PESA deposit"
        )

        db.session.add(
            transaction
        )

        db.session.flush()

        # -------------------------------------------------
        # Account reference
        # -------------------------------------------------

        account_reference = (
            "DEP"
            + str(transaction.id)
        )

        # -------------------------------------------------
        # Send STK Push
        # -------------------------------------------------

        response = initiate_stk_push(
            phone_number=phone,
            amount=amount,
            account_reference=account_reference,
            transaction_description=
                "Investment deposit"
        )

        checkout_request_id = response.get(
            "CheckoutRequestID"
        )

        # -------------------------------------------------
        # Check CheckoutRequestID
        # -------------------------------------------------

        if not checkout_request_id:

            transaction.status = "failed"

            transaction.description = (
                "M-PESA did not return "
                "CheckoutRequestID."
            )

            db.session.commit()

            return jsonify({
                "success": False,
                "message":
                    "M-PESA did not return a checkout ID."
            }), 400

        # -------------------------------------------------
        # Save checkout ID
        # -------------------------------------------------

        transaction.reference = (
            checkout_request_id
        )

        transaction.status = "pending"

        db.session.commit()

        return jsonify({
            "success": True,
            "message":
                "M-PESA payment request sent. "
                "Please check your phone.",
            "checkout_request_id":
                checkout_request_id
        })

    except requests.exceptions.RequestException as exc:

        db.session.rollback()

        print(
            "M-PESA CONNECTION ERROR:",
            str(exc)
        )

        return jsonify({
            "success": False,
            "message":
                "Unable to connect to the "
                "M-PESA payment server."
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


# =========================================================
# M-PESA CALLBACK
# =========================================================

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

        # -------------------------------------------------
        # Get callback body
        # -------------------------------------------------

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

        # -------------------------------------------------
        # No checkout ID
        # -------------------------------------------------

        if not checkout_request_id:

            return jsonify({
                "ResultCode": 0,
                "ResultDesc":
                    "Accepted"
            })

        # -------------------------------------------------
        # Find transaction
        # -------------------------------------------------

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
                "ResultDesc":
                    "Accepted"
            })

        # -------------------------------------------------
        # Prevent duplicate processing
        # -------------------------------------------------

        if transaction.status == "completed":

            return jsonify({
                "ResultCode": 0,
                "ResultDesc":
                    "Already processed"
            })

        # -------------------------------------------------
        # Successful payment
        # -------------------------------------------------

        if str(result_code) == "0":

            transaction.status = "completed"

            transaction.description = (
                "M-PESA deposit completed"
            )

            # ---------------------------------------------
            # Get KES wallet
            # ---------------------------------------------

            wallet = get_or_create_wallet(
                transaction.user_id,
                "KES"
            )

            # ---------------------------------------------
            # Credit wallet
            # ---------------------------------------------

            wallet.balance += (
                transaction.amount
            )

            # ---------------------------------------------
            # Keep legacy User.balance updated
            # ---------------------------------------------

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
                "M-PESA PAYMENT COMPLETED:",
                checkout_request_id,
                "Amount:",
                transaction.amount
            )

        # -------------------------------------------------
        # Failed / cancelled payment
        # -------------------------------------------------

        else:

            transaction.status = "failed"

            transaction.description = (
                "M-PESA failed: "
                + str(result_description)[:200]
            )

            db.session.commit()

            print(
                "M-PESA PAYMENT FAILED:",
                checkout_request_id,
                result_description
            )

        return jsonify({
            "ResultCode": 0,
            "ResultDesc":
                "Accepted"
        })

    except Exception as exc:

        db.session.rollback()

        print(
            "M-PESA CALLBACK ERROR:",
            repr(exc)
        )

        # Always acknowledge the callback
        return jsonify({
            "ResultCode": 0,
            "ResultDesc":
                "Accepted"
        })


# =========================================================
# SUPPORTED CURRENCIES
# =========================================================

@mpesa_bp.route(
    "/currencies",
    methods=["GET"]
)
def currencies():

    return jsonify({
        "success": True,
        "currencies":
            SUPPORTED_CURRENCIES
    })
