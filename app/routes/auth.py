from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, logout_user
from app.extensions import db
from app.models import User

auth = Blueprint("auth", __name__)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter your username and password.", "error")
            return redirect(url_for("auth.login"))

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for("main.dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@auth.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.", "error")
            return redirect(url_for("auth.register"))

        if len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
            return redirect(url_for("auth.register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect(url_for("auth.register"))

        existing_user = User.query.filter_by(
            username=username
        ).first()

        if existing_user:
            flash("Username already exists.", "error")
            return redirect(url_for("auth.register"))

        user = User(username=username)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash(
            "Registration successful. Please log in.",
            "success"
        )

        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
