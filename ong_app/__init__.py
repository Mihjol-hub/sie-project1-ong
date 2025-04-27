# ong_app/__init__.py 
import os
from flask import Flask
import logging

# Import blueprints from other files Comment translated
from .routes_main import main_bp
from .routes_books import books_bp
from .routes_donors import donors_bp
from .routes_donations import donations_bp

# (We'll add more imports here if we create more blueprints) Comment translated

def create_app(test_config=None):
    """Factory function to create and configure the Flask app.""" # Docstring translated

    # Create and configure the app Comment translated
    app = Flask(__name__, instance_relative_config=True)

    # Default configuration Comment translated
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev_secret_key_change_this_later!') # Default kept in English
    )

    # Ensure the 'instance' folder exists Comment translated
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Configure basic logging Comment translated
    # It's important to do this BEFORE starting to use logging within the app Comment translated
    logging.basicConfig(level=logging.INFO)
    # Log message translated
    logging.info("Flask application created (create_app start).")

    # --- Register Blueprints (with detailed logs) --- Comment translated
    try:
        # Log message translated
        logging.info("Attempting to register main_bp...")
        app.register_blueprint(main_bp)
        # Log message translated
        logging.info(">>> main_bp registered successfully.")

        # Log message translated
        logging.info("Attempting to register books_bp...")
        app.register_blueprint(books_bp) 
        # Log message translated
        logging.info(">>> books_bp registered successfully.")

        # Log message translated
        logging.info("Attempting to register donors_bp...")
        app.register_blueprint(donors_bp) 
        # Log message translated
        logging.info(">>> donors_bp registered successfully.")

        # Log message translated
        logging.info("Attempting to register donations_bp...")
        app.register_blueprint(donations_bp, url_prefix='/donations') 
        # Log message translated
        logging.info(">>> donations_bp registered successfully with prefix /donations.")
        
    except Exception as e:
        # If something fails here, it's CRITICAL to know Comment translated
        # Log message translated
        logging.error(f"FATAL ERROR REGISTERING BLUEPRINT!!!: {e}", exc_info=True)

    # Optional test route Comment translated
    @app.route('/hello-init')
    def hello():
        # Message translated
        return 'Hello from create_app()!'

    # Log message translated
    logging.info("create_app finished, returning app instance.")
    return app