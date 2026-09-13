from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import User

admin = Blueprint("admin", __name__, url_prefix="/admin")


@admin.route("/")
@login_required
def dashboard():
    users = User.query.all()

    return render_template(
        "admin.html",
        users=users
    )
