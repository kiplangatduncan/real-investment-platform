from flask import Flask
from flask_wtf.csrf import CSRFProtect

from .extensions import db, login_manager

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = "change-this-secret-key"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from .routes.auth import auth
    from .routes.main import main
    from .routes.payments import payments
    from .routes.admin import admin

    app.register_blueprint(auth)
    app.register_blueprint(main)
    app.register_blueprint(payments)
    app.register_blueprint(admin)

    with app.app_context():
        db.create_all()

    return app


@login_manager.user_loader
def load_user(user_id):
    from .models import User
    return User.query.get(int(user_id))
    
