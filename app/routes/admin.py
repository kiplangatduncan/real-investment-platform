from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
import os

from app.models import User, Transaction

admin = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin"
)


def admin_required():
    admin_username = os.environ.get("ADMIN_USERNAME")

    if not admin_username:
        abort(403)

    if not current_user.is_authenticated:
        abort(403)

    if current_user.username != admin_username:
        abort(403)


@admin.route("/")
@login_required
def dashboard():
    admin_required()

    users = User.query.order_by(
        User.created_at.desc()
    ).all()

    transactions = Transaction.query.order_by(
        Transaction.created_at.desc()
    ).limit(100).all()

    return render_template(
        "admin.html",
        users=users,
        transactions=transactions
    )
