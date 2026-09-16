import os
import base64
from datetime import datetime

import requests


def get_mpesa_access_token():
    consumer_key = os.environ.get("MPESA_CONSUMER_KEY")
    consumer_secret = os.environ.get("MPESA_CONSUMER_SECRET")

    if not consumer_key or not consumer_secret:
        raise RuntimeError(
            "M-PESA API credentials are not configured."
        )

    credentials = f"{consumer_key}:{consumer_secret}"
    encoded = base64.b64encode(
        credentials.encode()
    ).decode()

    response = requests.get(
        "https://api.safaricom.co.ke/oauth/v1/generate"
        "?grant_type=client_credentials",
        headers={
            "Authorization": f"Basic {encoded}"
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    access_token = data.get("access_token")

    if not access_token:
        raise RuntimeError(
            "M-PESA access token was not returned."
        )

    return access_token


def initiate_stk_push(
    phone_number,
    amount,
    account_reference,
    transaction_description="Investment deposit"
):
    shortcode = os.environ.get("MPESA_SHORTCODE")
    passkey = os.environ.get("MPESA_PASSKEY")
    callback_url = os.environ.get("MPESA_CALLBACK_URL")

    if not shortcode:
        raise RuntimeError("MPESA_SHORTCODE is not configured.")

    if not passkey:
        raise RuntimeError("MPESA_PASSKEY is not configured.")

    if not callback_url:
        raise RuntimeError(
            "MPESA_CALLBACK_URL is not configured."
        )

    if amount <= 0:
        raise ValueError(
            "Payment amount must be greater than zero."
        )

    access_token = get_mpesa_access_token()

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    password_string = (
        f"{shortcode}{passkey}{timestamp}"
    )

    password = base64.b64encode(
        password_string.encode()
    ).decode()

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone_number,
        "PartyB": shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": callback_url,
        "AccountReference": account_reference,
        "TransactionDesc": transaction_description
    }

    response = requests.post(
        "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        },
        timeout=30
    )

    response.raise_for_status()

    return response.json()
