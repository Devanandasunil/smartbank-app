from flask import Flask, session, redirect, request, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
import os
import json

# Initialize extensions (do this once at module level)
db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)

    # Config
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///smartbank.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.secret_key = 'your-very-secret-key'  # Replace with env var in production!

    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    migrate = Migrate(app, db)

    # Login Manager setup
    login_manager.login_view = 'customer.login'
    login_manager.login_message_category = 'info'

    # Import models so SQLAlchemy registers them
    from . import models

    # Register blueprints
    from .routes import main as main_blueprint
    from .customer_routes import customer_bp
    from .staff_routes import staff_bp

    app.register_blueprint(main_blueprint)
    app.register_blueprint(customer_bp)
    app.register_blueprint(staff_bp)
    
    
    return app


    
