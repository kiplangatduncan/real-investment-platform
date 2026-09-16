import os
import base64
import requests
from datetime import datetime
from flask import Blueprint, request, jsonify

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")


# =========================================================
# CONFIGURATION
# =========================================================

MPESA_ENVIRONMENT = os.getenv("MPESA_ENVIRONMENT", "sandbox")

MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY")
MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET")

MPESA_SHORTCODE = os.getenv("MPESA_SHORTCODE")
MPESA_PASSKEY = os.getenv("MPESA_PASSKEY")

MPESA_CALLBACK_URL = os.getenv("MPESA_CALLBACK_URL")


# =========================================================
# M-PESA URLS
# =========================================================

if MPESA_ENVIRONMENT == "production":
    MPESA_BASE_URL = "https://api.safaricom.co.ke"
else:
    MPESA_BASE_URL = "https://sandbox.safaricom.co.ke"


# =========================================================
# GET M-PESA ACCESS TOKEN
# =========================================================

def get_mpesa_access_token():

    if not MPESA_CONSUMER_KEY or not MPESA_CONSUMER_SECRET:
        raise ValueError("M-PESA API credentials are missing.")

    credentials = f"{MPESA_CONSUMER_KEY}:{MPESA_CONSUMER_SECRET}"

    encoded_credentials = base64.b64encode(
        credentials.encode()
    ).decode()

    headers = {
        "Authorization": f"Basic {encoded_credentials}"
    }

    response = requests.get(
        f"{MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials",
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    return response.json()["access_token"]


# =========================================================
# INITIATE DEPOSIT
# =========================================================

@payments_bp.route("/deposit", methods=["POST"])
def initiate_deposit():

    data = request.get_json(silent=True) or {}

    phone = str(data.get("phone", "")).strip()
    amount = data.get("amount")

    if not phone:
        return jsonify({
            "success": False,
            "message": "Phone number is required."
        }), 400

    if not amount:
        return jsonify({
            "success": False,
            "message": "Deposit amount is required."
        }), 400

    try:
        amount = int(float(amount))
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid deposit amount."
        }), 400

    if amount <= 0:
        return jsonify({
            "success": False,
            "message": "Deposit amount must be greater than zero."
        }), 400

    # Convert Kenyan phone formats to 254XXXXXXXXX
    if phone.startswith("+254"):
        phone = phone[1:]

    elif phone.startswith("07") or phone.startswith("01"):
        phone = "254" + phone[1:]

    if not phone.startswith("254") or len(phone) != 12:
        return jsonify({
            "success": False,
            "message": "Enter a valid Kenyan M-PESA number."
        }), 400

    try:
        access_token = get_mpesa_access_token()

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        password_string = (
            f"{MPESA_SHORTCODE}"
            f"{MPESA_PASSKEY}"
            f"{timestamp}"
        )

        password = base64.b64encode(
            password_string.encode()
        ).decode()

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
            "AccountReference": "INVESTMENT",
            "TransactionDesc": "Investment platform deposit"
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(
            f"{MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers=headers,
            timeout=30
        )

        result = response.json()

        if response.status_code != 200:
            return jsonify({
                "success": False,
                "message": "M-PESA payment request failed.",
                "details": result
            }), 400

        return jsonify({
            "success": True,
            "message": "Payment request sent to your phone.",
            "checkout_request_id": result.get("CheckoutRequestID"),
            "merchant_request_id": result.get("MerchantRequestID"),
            "response_code": result.get("ResponseCode")
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": "Unable to initiate payment.",
            "error": str(e)
        }), 500


# =========================================================
# M-PESA CALLBACK
# =========================================================

@payments_bp.route("/callback", methods=["POST"])
def mpesa_callback():

    data = request.get_json(silent=True) or {}

    print("M-PESA CALLBACK RECEIVED:")
    print(data)

    try:

        stk_callback = (
            data
            .get("Body", {})
            .get("stkCallback", {})
        )

        result_code = stk_callback.get("ResultCode")

        checkout_request_id = stk_callback.get(
            "CheckoutRequestID"
        )

        # Payment was successful
        if result_code == 0:

            callback_items = (
                stk_callback
                .get("CallbackMetadata", {})
                .get("Item", [])
            )

            amount = None
            mpesa_receipt = None
            phone = None

            for item in callback_items:

                name = item.get("Name")
                value = item.get("Value")

                if name == "Amount":
                    amount = value

                elif name == "MpesaReceiptNumber":
                    mpesa_receipt = value

                elif name == "PhoneNumber":
                    phone = value

            # ------------------------------------------------
            # IMPORTANT:
            # CREDIT USER ACCOUNT HERE
            # ------------------------------------------------
            #
            # Example:
            #
            # user = User.query.filter_by(phone=phone).first()
            #
            # if user:
            #     user.balance += amount
            #
            #     transaction = Transaction(
            #         user_id=user.id,
            #         amount=amount,
            #         reference=mpesa_receipt,
            #         checkout_request_id=checkout_request_id,
            #         transaction_type="DEPOSIT",
            #         status="COMPLETED"
            #     )
            #
            #     db.session.add(transaction)
            #     db.session.commit()
            #
            # ------------------------------------------------

            print("SUCCESSFUL DEPOSIT")
            print("Amount:", amount)
            print("M-PESA Receipt:", mpesa_receipt)
            print("Phone:", phone)

        else:

            print("M-PESA PAYMENT FAILED")
            print(
                "Result:",
                stk_callback.get("ResultDesc")
            )

        return jsonify({
            "ResultCode": 0,
            "ResultDesc": "Callback received successfully"
        })

    except Exception as e:

        print("CALLBACK ERROR:", e)

        return jsonify({
            "ResultCode": 1,
            "ResultDesc": "Callback processing failed"
        }), 500
