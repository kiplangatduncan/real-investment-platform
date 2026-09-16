import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "K8v2pL9xQ4rT7wN6zM3aB8cF3"

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///investment.db"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Payment settings
    MPESA_CONSUMER_KEY = os.environ.get("MPESA_CONSUMER_KEY")
    MPESA_CONSUMER_SECRET = os.environ.get("MPESA_CONSUMER_SECRET")
    MPESA_SHORTCODE = os.environ.get("MPESA_SHORTCODE")
    MPESA_PASSKEY = os.environ.get("MPESA_PASSKEY")
    MPESA_CALLBACK_URL = os.environ.get("MPESA_CALLBACK_URL")
