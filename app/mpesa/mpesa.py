import base64
import os
from datetime import datetime

import requests
from flask import Blueprint, jsonify, request


mpesa_bp = Blueprint(
    "mpesa",
    __name__,
    url_prefix="/mpesa"
)


# =========================================================
# M-PESA BASE URL
# =========================================================

def get_mpesa_base_url():
    environment = os.getenv("MPESA_ENV", "sandbox").lower()

    if environment == "production":
        return "https://api.safaricom.co.ke"

    return "https://sandbox.safaricom.co.ke"


# =========================================================
# GET ACCESS TOKEN
# =========================================================

def get_access_token():
    consumer_key = os.getenv("MPESA_CONSUMER_KEY")
    consumer_secret = os.getenv("MPESA_CONSUMER_SECRET")

    if not consumer_key or not consumer_secret:
        raise RuntimeError(
            "M-Pesa consumer credentials are not configured."
        )

    credentials = f"{consumer_key}:{consumer_secret}"

    encoded_credentials = base64.b64encode(
        credentials.encode("utf-8")
    ).decode("utf-8")

    url = (
        f"{get_mpesa_base_url()}"
        "/oauth/v1/generate?grant_type=client_credentials"
    )

    response = requests.get(
        url,
        headers={
            "Authorization": f"Basic {encoded_credentials}"
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if "access_token" not in data:
        raise RuntimeError(
            "M-Pesa did not return an access token."
        )

    return data["access_token"]


# =========================================================
# GENERATE STK PASSWORD
# =========================================================

def generate_password(timestamp):
    shortcode = os.getenv("MPESA_SHORTCODE")
    passkey = os.getenv("MPESA_PASSKEY")

    if not shortcode or not passkey:
        raise RuntimeError(
            "M-Pesa shortcode or passkey is not configured."
        )

    raw = f"{shortcode}{passkey}{timestamp}"

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
    shortcode = os.getenv("MPESA_SHORTCODE")

    if not shortcode:
        raise RuntimeError(
            "MPESA_SHORTCODE is not configured."
        )

    timestamp = datetime.now().strftime(
        "%Y%m%d%H%M%S"
    )

    password = generate_password(timestamp)

    access_token = get_access_token()

    callback_url = os.getenv("MPESA_CALLBACK_URL")

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
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(float(amount)),
        "PartyA": phone_number,
        "PartyB": shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": callback_url,
        "AccountReference": str(account_reference)[:12],
        "TransactionDesc": str(transaction_description)[:13]
    }

    response = requests.post(
        url,
        json=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        },
        timeout=30
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# STK PUSH ROUTE
# =========================================================

@mpesa_bp.route("/stk-push", methods=["POST"])
def stk_push():

    data = request.get_json(
        silent=True
    ) or request.form

    phone = data.get("phone")
    amount = data.get("amount")
    reference = data.get(
        "reference",
        "INVESTMENT"
    )

    if not phone:
        return jsonify({
            "success": False,
            "message": "Phone number is required."
        }), 400

    if not amount:
        return jsonify({
            "success": False,
            "message": "Amount is required."
        }), 400

    try:
        amount = float(amount)

        if amount <= 0:
            raise ValueError

    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "message": "Invalid amount."
        }), 400

    try:

        result = initiate_stk_push(
            phone_number=phone,
            amount=amount,
            account_reference=reference
        )

        return jsonify({
            "success": True,
            "message": result.get(
                "CustomerMessage",
                "STK push sent successfully."
            ),
            "data": result
        })

    except Exception as exc:

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

    data = request.get_json(
        silent=True
    ) or {}

    print("M-Pesa callback received:")
    print(data)

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

    if result_code == 0:

        callback_metadata = (
            stk_callback
            .get("CallbackMetadata", {})
            .get("Item", [])
        )

        metadata = {}

        for item in callback_metadata:

            name = item.get("Name")

            if name:
                metadata[name] = item.get(
                    "Value"
                )

        amount = metadata.get("Amount")
        receipt = metadata.get(
            "MpesaReceiptNumber"
        )
        transaction_date = metadata.get(
            "TransactionDate"
        )
        phone = metadata.get(
            "PhoneNumber"
        )

        print("Successful M-Pesa payment")
        print("Amount:", amount)
        print("Receipt:", receipt)
        print("Phone:", phone)
        print(
            "Transaction Date:",
            transaction_date
        )
        print(
            "Checkout Request ID:",
            checkout_request_id
        )

        # Database/balance update will be connected
        # here after matching your existing
        # transaction and user models.

    else:

        print(
            "M-Pesa payment failed:",
            result_code,
            result_desc
        )

    return jsonify({
        "ResultCode": 0,
        "ResultDesc": "Accepted"
    })


# =========================================================
# QUERY STK PAYMENT STATUS
# =========================================================

def query_stk_status(checkout_request_id):

    shortcode = os.getenv("MPESA_SHORTCODE")

    if not shortcode:
        raise RuntimeError(
            "MPESA_SHORTCODE is not configured."
        )

    timestamp = datetime.now().strftime(
        "%Y%m%d%H%M%S"
    )

    password = generate_password(timestamp)

    access_token = get_access_token()

    url = (
        f"{get_mpesa_base_url()}"
        "/mpesa/stkpushquery/v1/query"
    )

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id
    }

    response = requests.post(
        url,
        json=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
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
def payment_status(checkout_request_id):

    try:

        result = query_stk_status(
            checkout_request_id
        )

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as exc:

        return jsonify({
            "success": False,
            "message": str(exc)
        }), 500
