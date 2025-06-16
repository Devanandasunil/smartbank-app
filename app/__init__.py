from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
import os

# Initialize the extensions
db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = 'supersecret'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../instance/smartbank.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate = Migrate(app, db)

    # Login Manager setup
    login_manager.login_view = 'customer.login'
    login_manager.login_message_category = 'info'

    # 👇👇👇 THIS is the critical line
    from . import models

    # Register blueprints
    from .routes import main as main_blueprint
    from .customer_routes import customer_bp
    from .staff_routes import staff_bp

    app.register_blueprint(main_blueprint)
    app.register_blueprint(customer_bp)
    app.register_blueprint(staff_bp)

    return app
