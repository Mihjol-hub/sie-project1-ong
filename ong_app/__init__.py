# ong_app/__init__.py 
import os
from flask import Flask
import logging

# Importar los blueprints desde los otros archivos
from .routes_main import main_bp
from .routes_books import books_bp
from .routes_donors import donors_bp
from .routes_donations import donations_bp

# (Añadiremos más imports aquí si creamos más blueprints)

def create_app(test_config=None):
    """Factory function para crear y configurar la app Flask."""

    # Crear e configurar la app
    app = Flask(__name__, instance_relative_config=True)

    # Configuración por defecto
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev_secret_key_change_this_later!')
    )

    # Asegurar que la carpeta 'instance' exista
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Configurar el logging básico
    # Es importante hacerlo ANTES de empezar a usar logging dentro de la app
    logging.basicConfig(level=logging.INFO)
    logging.info("Aplicación Flask creada (create_app inicio).")

    # --- Registrar los Blueprints (con logs detallados) ---
    try:
        logging.info("Intentando registrar main_bp...")
        app.register_blueprint(main_bp)
        logging.info(">>> main_bp registrado con éxito.")

        logging.info("Intentando registrar books_bp...")
        app.register_blueprint(books_bp) 
        logging.info(">>> books_bp registrado con éxito.")

        logging.info("Intentando registrar donors_bp...")
        app.register_blueprint(donors_bp) 
        logging.info(">>> donors_bp registrado con éxito.")

        logging.info("Intentando registrar donations_bp...")
        app.register_blueprint(donations_bp, url_prefix='/donations') 
        logging.info(">>> donations_bp registrado con éxito con prefijo /donations.")
    
    
    
    except Exception as e:
        # Si algo falla aquí, es CRÍTICO saberlo
        logging.error(f"¡¡¡ERROR FATAL AL REGISTRAR BLUEPRINT!!!: {e}", exc_info=True)

    # Ruta de prueba opcional
    @app.route('/hello-init')
    def hello():
        return '¡Hola desde create_app()!'

    logging.info("create_app finalizado, devolviendo instancia de app.")
    return app