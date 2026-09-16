from flask import Flask
from app.extensions import db, login_manager
from app.settings import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)

    # Load logged-in users
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return db.session.get(User, int(user_id))

    # Register routes
    from app.routes.auth import auth
    from app.routes.main import main
    from app.routes.payments import payments
    from app.routes.admin import admin
    from app.mpesa import mpesa_bp

    app.register_blueprint(auth)
    app.register_blueprint(main)
    app.register_blueprint(payments)
    app.register_blueprint(admin)
    app.register_blueprint(mpesa_bp)

    # Create database tables
    with app.app_context():
        db.create_all()

    return app
