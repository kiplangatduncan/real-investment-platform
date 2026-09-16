import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask import session


# ==========================================================
# DATABASE
# ==========================================================

db = SQLAlchemy()


# ==========================================================
# CREATE APPLICATION
# ==========================================================

def create_app():

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static"
    )

    # ------------------------------------------------------
    # SECRET KEY
    # ------------------------------------------------------

    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY",
        "change-this-secret-key"
    )

    # ------------------------------------------------------
    # DATABASE
    # ------------------------------------------------------

    database_url = os.environ.get(
        "DATABASE_URL"
    )

    if database_url:

        # Render/PostgreSQL sometimes provides postgres://
        # instead of postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace(
                "postgres://",
                "postgresql://",
                1
            )

        app.config["SQLALCHEMY_DATABASE_URI"] = database_url

    else:

        app.config["SQLALCHEMY_DATABASE_URI"] = (
            "sqlite:///investment.db"
        )

    app.config[
        "SQLALCHEMY_TRACK_MODIFICATIONS"
    ] = False


    # ------------------------------------------------------
    # INITIALIZE DATABASE
    # ------------------------------------------------------

    db.init_app(app)


    # ------------------------------------------------------
    # REGISTER PAYMENT SYSTEM
    # ------------------------------------------------------

    try:

        from .payments import payments_bp

        app.register_blueprint(
            payments_bp
        )

    except ImportError:

        pass


    # ------------------------------------------------------
    # MAIN ROUTES
    # ------------------------------------------------------

    @app.route("/")
    def home():

        from flask import render_template

        return render_template(
            "index.html"
        )


    # ------------------------------------------------------
    # LOGIN
    # ------------------------------------------------------

    @app.route("/login", methods=["GET", "POST"])
    def login():

        from flask import (
            render_template,
            request,
            redirect,
            url_for,
            flash
        )

        if request.method == "POST":

            email = request.form.get(
                "email",
                ""
            ).strip()

            password = request.form.get(
                "password",
                ""
            )

            # ----------------------------------------------
            # Temporary login check
            # ----------------------------------------------
            #
            # The real database authentication should be
            # connected here once your User model is added.
            #

            if not email or not password:

                flash(
                    "Please enter your login details."
                )

                return render_template(
                    "login.html"
                )

            # Temporary session
            session["logged_in"] = True
            session["user_email"] = email

            return redirect(
                url_for("dashboard")
            )

        return render_template(
            "login.html"
        )


    # ------------------------------------------------------
    # REGISTER
    # ------------------------------------------------------

    @app.route("/register", methods=["GET", "POST"])
    def register():

        from flask import (
            render_template,
            request,
            redirect,
            url_for,
            flash
        )

        if request.method == "POST":

            name = request.form.get(
                "name",
                ""
            ).strip()

            email = request.form.get(
                "email",
                ""
            ).strip()

            phone = request.form.get(
                "phone",
                ""
            ).strip()

            password = request.form.get(
                "password",
                ""
            )

            confirm_password = request.form.get(
                "confirm_password",
                ""
            )

            if not name or not email or not phone:

                flash(
                    "Please fill in all required fields."
                )

                return render_template(
                    "register.html"
                )

            if password != confirm_password:

                flash(
                    "Passwords do not match."
                )

                return render_template(
                    "register.html"
                )

            if len(password) < 6:

                flash(
                    "Password must contain at least 6 characters."
                )

                return render_template(
                    "register.html"
                )

            # ----------------------------------------------
            # Temporary registration session
            # ----------------------------------------------

            session["logged_in"] = True
            session["user_name"] = name
            session["user_email"] = email
            session["user_phone"] = phone

            return redirect(
                url_for("dashboard")
            )

        return render_template(
            "register.html"
        )


    # ------------------------------------------------------
    # DASHBOARD
    # ------------------------------------------------------

    @app.route("/dashboard")
    def dashboard():

        from flask import (
            render_template,
            redirect,
            url_for
        )

        if not session.get("logged_in"):

            return redirect(
                url_for("login")
            )

        return render_template(
            "dashboard.html",
            balance=0,
            total_deposits=0,
            investment_balance=0,
            transactions=[]
        )


    # ------------------------------------------------------
    # DEPOSIT PAGE
    # ------------------------------------------------------

    @app.route("/deposit")
    def deposit():

        from flask import (
            render_template,
            redirect,
            url_for
        )

        if not session.get("logged_in"):

            return redirect(
                url_for("login")
            )

        return render_template(
            "deposit.html"
        )


    # ------------------------------------------------------
    # TRANSACTIONS
    # ------------------------------------------------------

    @app.route("/transactions")
    def transactions():

        from flask import (
            render_template,
            redirect,
            url_for
        )

        if not session.get("logged_in"):

            return redirect(
                url_for("login")
            )

        return render_template(
            "transactions.html",
            transactions=[]
        )


    # ------------------------------------------------------
    # INVESTMENT PAGE
    # ------------------------------------------------------

    @app.route("/invest")
    def invest():

        from flask import (
            render_template,
            redirect,
            url_for
        )

        if not session.get("logged_in"):

            return redirect(
                url_for("login")
            )

        return render_template(
            "invest.html"
        )


    # ------------------------------------------------------
    # LOGOUT
    # ------------------------------------------------------

    @app.route("/logout")
    def logout():

        session.clear()

        return redirect(
            url_for("home")
        )


    # ------------------------------------------------------
    # CREATE DATABASE TABLES
    # ------------------------------------------------------

    with app.app_context():

        db.create_all()


    return app
