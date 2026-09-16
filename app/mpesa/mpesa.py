import base64
import os
from datetime import datetime

import requests
from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import Transaction, User


# =========================================================
# M-PESA BLUEPRINT
# =========================================================

mpesa_bp = Blueprint(
    "mpesa",
    __name__,
    url_prefix="/mpesa"
)


# =========================================================
# M-PESA BASE URL
# =========================================================

def get_mpesa_base_url():
    environment = os.getenv(
        "MPESA_ENV",
        "sandbox"
    ).strip().lower()

    if environment == "production":
        return "https://api.safaricom.co.ke"

    return "https://sandbox.safaricom.co.ke"


# =========================================================
# GET M-PESA ACCESS TOKEN
# =========================================================

def get_access_token():

    consumer_key = os.getenv(
        "MPESA_CONSUMER_KEY"
    )

    consumer_secret = os.getenv(
        "MPESA_CONSUMER_SECRET"
    )

    if not consumer_key:
        raise RuntimeError(
            "MPESA_CONSUMER_KEY is not configured."
        )

    if not consumer_secret:
        raise RuntimeError(
            "MPESA_CONSUMER_SECRET is not configured."
        )

    credentials = (
        f"{consumer_key}:{consumer_secret}"
    )

    encoded_credentials = base64.b64encode(
        credentials.encode("utf-8")
    ).decode("utf-8")

    url = (
        f"{get_mpesa_base_url()}"
        "/oauth/v1/generate"
        "?grant_type=client_credentials"
    )

    response = requests.get(
        url,
        headers={
            "Authorization":
                f"Basic {encoded_credentials}"
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    access_token = data.get(
        "access_token"
    )

    if not access_token:
        raise RuntimeError(
            "M-PESA did not return an access token."
        )

    return access_token


# =========================================================
# GENERATE STK PASSWORD
# =========================================================

def generate_password(timestamp):

    shortcode = os.getenv(
        "MPESA_SHORTCODE"
    )

    passkey = os.getenv(
        "MPESA_PASSKEY"
    )

    if not shortcode:
        raise RuntimeError(
            "MPESA_SHORTCODE is not configured."
        )

    if not passkey:
        raise RuntimeError(
            "MPESA_PASSKEY is not configured."
        )

    raw = (
        f"{shortcode}"
        f"{passkey}"
        f"{timestamp}"
    )

    return base64.b64encode(
        raw.encode("utf-8")
    ).decode("utf-8")


# =========================================================
# INITIATE STK PUSH
# =========================================================

def initiate_stk_push(
    phone_number,
    amount,
    account_reference="INVESTMENT",
    transaction_description="Investment deposit"
):

    shortcode = os.getenv(
        "MPESA_SHORTCODE"
    )

    if not shortcode:
        raise RuntimeError(
            "MPESA_SHORTCODE is not configured."
        )

    if not phone_number:
        raise ValueError(
            "Phone number is required."
        )

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise ValueError(
            "Invalid payment amount."
        )

    if amount <= 0:
        raise ValueError(
            "Payment amount must be greater than zero."
        )

    timestamp = datetime.now().strftime(
        "%Y%m%d%H%M%S"
    )

    password = generate_password(
        timestamp
    )

    access_token = get_access_token()

    callback_url = os.getenv(
        "MPESA_CALLBACK_URL"
    )

    if not callback_url:
        raise RuntimeError(
            "MPESA_CALLBACK_URL is not configured."
        )

    url = (
        f"{get_mpesa_base_url()}"
        "/mpesa/stkpush/v1/processrequest"
    )

    payload = {
        "BusinessShortCode": shortcode,

        "Password": password,

        "Timestamp": timestamp,

        "TransactionType":
            "CustomerPayBillOnline",

        "Amount": int(amount),

        "PartyA": str(phone_number),

        "PartyB": shortcode,

        "PhoneNumber": str(phone_number),

        "CallBackURL": callback_url,

        "AccountReference":
            str(account_reference)[:12],

        "TransactionDesc":
            str(transaction_description)[:13]
    }

    response = requests.post(
        url,
        json=payload,
        headers={
            "Authorization":
                f"Bearer {access_token}",
            "Content-Type":
                "application/json"
        },
        timeout=30
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# STK PUSH ROUTE
# =========================================================

@mpesa_bp.route(
    "/stk-push",
    methods=["POST"]
)
def stk_push():

    data = (
        request.get_json(
            silent=True
        )
        or request.form
    )

    phone = data.get("phone")
    amount = data.get("amount")

    reference = data.get(
        "reference",
        "INVESTMENT"
    )

    if not phone:
        return jsonify({
            "success": False,
            "message":
                "Phone number is required."
        }), 400

    if not amount:
        return jsonify({
            "success": False,
            "message":
                "Amount is required."
        }), 400

    try:

        amount = float(amount)

        if amount <= 0:
            raise ValueError

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message":
                "Invalid amount."
        }), 400

    try:

        result = initiate_stk_push(
            phone_number=phone,
            amount=amount,
            account_reference=reference,
            transaction_description=
                "Investment deposit"
        )

        return jsonify({
            "success": True,

            "message":
                result.get(
                    "CustomerMessage",
                    "STK push sent successfully."
                ),

            "data": result
        })

    except Exception as error:

        print(
            "M-PESA STK PUSH ERROR:",
            repr(error)
        )

        return jsonify({
            "success": False,

            "message":
                "Unable to send the M-PESA payment request.",

            "error":
                str(error)
        }), 500


# =========================================================
# M-PESA CALLBACK
# =========================================================

@mpesa_bp.route(
    "/callback",
    methods=["POST"]
)
def mpesa_callback():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    print(
        "M-PESA callback received:",
        data
    )

    stk_callback = (
        data
        .get("Body", {})
        .get("stkCallback", {})
    )

    result_code = stk_callback.get(
        "ResultCode"
    )

    result_desc = stk_callback.get(
        "ResultDesc"
    )

    checkout_request_id = (
        stk_callback.get(
            "CheckoutRequestID"
        )
    )

    if not checkout_request_id:

        return jsonify({
            "ResultCode": 0,
            "ResultDesc":
                "Accepted"
        })


    # =====================================================
    # SUCCESSFUL PAYMENT
    # =====================================================

    if result_code == 0:

        callback_metadata = (
            stk_callback
            .get(
                "CallbackMetadata",
                {}
            )
            .get(
                "Item",
                []
            )
        )

        metadata = {}

        for item in callback_metadata:

            name = item.get("Name")

            if name:
                metadata[name] = item.get(
                    "Value"
                )

        amount = metadata.get(
            "Amount"
        )

        receipt = metadata.get(
            "MpesaReceiptNumber"
        )

        phone = metadata.get(
            "PhoneNumber"
        )

        transaction_date = metadata.get(
            "TransactionDate"
        )

        print(
            "Successful M-PESA payment"
        )

        print(
            "Amount:",
            amount
        )

        print(
            "Receipt:",
            receipt
        )

        print(
            "Phone:",
            phone
        )

        print(
            "Transaction Date:",
            transaction_date
        )

        print(
            "Checkout Request ID:",
            checkout_request_id
        )


        # =================================================
        # FIND TRANSACTION
        # =================================================

        transaction = (
            Transaction.query
            .filter_by(
                reference=
                    checkout_request_id
            )
            .first()
        )

        if not transaction:

            print(
                "No matching transaction found:",
                checkout_request_id
            )

            return jsonify({
                "ResultCode": 0,
                "ResultDesc":
                    "Accepted"
            })


        # =================================================
        # PREVENT DOUBLE CREDIT
        # =================================================

        if transaction.status == "completed":

            print(
                "Transaction already completed:",
                transaction.id
            )

            return jsonify({
                "ResultCode": 0,
                "ResultDesc":
                    "Already processed"
            })


        # =================================================
        # VERIFY PAYMENT AMOUNT
        # =================================================

        try:

            callback_amount = float(
                amount
            )

        except (TypeError, ValueError):

            print(
                "Invalid callback amount."
            )

            return jsonify({
                "ResultCode": 0,
                "ResultDesc":
                    "Accepted"
            })


        if callback_amount != float(
            transaction.amount
        ):

            transaction.status = "failed"

            transaction.description = (
                "M-PESA callback amount "
                "did not match transaction amount."
            )

            db.session.commit()

            print(
                "Payment amount mismatch."
            )

            return jsonify({
                "ResultCode": 0,
                "ResultDesc":
                    "Accepted"
            })


        # =================================================
        # FIND USER
        # =================================================

        user = db.session.get(
            User,
            transaction.user_id
        )

        if not user:

            print(
                "User not found:",
                transaction.user_id
            )

            return jsonify({
                "ResultCode": 0,
                "ResultDesc":
                    "Accepted"
            })


        # =================================================
        # CREDIT USER BALANCE
        # =================================================

        user.balance = (
            float(
                user.balance or 0
            )
            +
            float(
                transaction.amount
            )
        )


        # =================================================
        # MARK TRANSACTION COMPLETED
        # =================================================

        transaction.status = "completed"

        transaction.description = (
            "M-PESA payment confirmed. "
            f"Receipt: {receipt}"
        )

        db.session.commit()

        print(
            "Balance successfully credited."
        )


    # =====================================================
    # FAILED / CANCELLED PAYMENT
    # =====================================================

    else:

        print(
            "M-PESA payment failed:",
            result_code,
            result_desc
        )

        transaction = (
            Transaction.query
            .filter_by(
                reference=
                    checkout_request_id
            )
            .first()
        )

        if transaction:

            if transaction.status != "completed":

                transaction.status = "failed"

                transaction.description = (
                    "M-PESA payment failed: "
                    f"{result_desc}"
                )

                db.session.commit()


    # =====================================================
    # ACKNOWLEDGE CALLBACK
    # =====================================================

    return jsonify({
        "ResultCode": 0,
        "ResultDesc":
            "Accepted"
    })


# =========================================================
# QUERY STK PAYMENT STATUS
# =========================================================

def query_stk_status(
    checkout_request_id
):

    if not checkout_request_id:
        raise ValueError(
            "Checkout Request ID is required."
        )

    shortcode = os.getenv(
        "MPESA_SHORTCODE"
    )

    if not shortcode:
        raise RuntimeError(
            "MPESA_SHORTCODE is not configured."
        )

    timestamp = datetime.now().strftime(
        "%Y%m%d%H%M%S"
    )

    password = generate_password(
        timestamp
    )

    access_token = get_access_token()

    url = (
        f"{get_mpesa_base_url()}"
        "/mpesa/stkpushquery/v1/query"
    )

    payload = {

        "BusinessShortCode":
            shortcode,

        "Password":
            password,

        "Timestamp":
            timestamp,

        "CheckoutRequestID":
            checkout_request_id
    }

    response = requests.post(
        url,
        json=payload,
        headers={
            "Authorization":
                f"Bearer {access_token}",

            "Content-Type":
                "application/json"
        },
        timeout=30
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# PAYMENT STATUS ROUTE
# =========================================================

@mpesa_bp.route(
    "/status/<checkout_request_id>",
    methods=["GET"]
)
def payment_status(
    checkout_request_id
):

    try:

        result = query_stk_status(
            checkout_request_id
        )

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as error:

        print(
            "M-PESA STATUS ERROR:",
            repr(error)
        )

        return jsonify({
            "success": False,
            "message":
                "Unable to query M-PESA payment status.",
            "error":
                str(error)
        }), 500
