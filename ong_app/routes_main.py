# ong_app/routes_main.py
from flask import Blueprint, render_template, jsonify
from .odoo_connector import get_odoo_client # Importa la función de conexión
import logging
import odoorpc # Importamos para manejar sus excepciones específicas

# Crear el Blueprint 'main'
# El primer argumento 'main' es el nombre del blueprint (interno)
# __name__ ayuda a Flask a localizar el blueprint
# template_folder='templates' (opcional) si las plantillas de este BP estuvieran en una subcarpeta.
# Por ahora, Flask buscará en la carpeta 'templates' principal definida en create_app.
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    titulo = "Proyecto ONG - Integración SIE"
    client = get_odoo_client() # Usa la función importada
    odoo_status = "Conectado (Verificado!)" if client else "Desconectado (Revisa Logs!)"
    logging.info(f"Renderizando index desde main_bp con estado Odoo: {odoo_status}")
    # Asume que Flask encontrará 'index.html' en la carpeta templates global
    return render_template('index.html', page_title=titulo, odoo_connection_status=odoo_status)

@main_bp.route('/api/odoo_version')
def odoo_version_test():
    logging.info("Recibida petición para /api/odoo_version en main_bp")
    client = get_odoo_client() # Usa la función importada
    if client:
        try:
            logging.info("Cliente Odoo disponible, intentando obtener versión...")
            server_version_info = client.version
            logging.info(f"Versión de Odoo obtenida (odoorpc): {server_version_info}")
            return jsonify(server_version_info)
        except odoorpc.error.RPCError as e:
            logging.error(f"Error RPC API Odoo (version) en main_bp: {e}", exc_info=True)
            return jsonify({"error": f"Error RPC API Odoo: {e}"}), 500
        except Exception as e:
            logging.error(f"Error inesperado API call version en main_bp: {e}", exc_info=True)
            return jsonify({"error": f"Error inesperado: {e}"}), 500
    else:
        logging.warning("Intento de llamada a /api/odoo_version en main_bp fallido, no hay cliente Odoo.")
        return jsonify({"error": "No se pudo obtener cliente Odoo (revisar logs para detalles de conexión)."}), 503

# Podemos añadir aquí la ruta '/api/hello' si la queremos de vuelta
@main_bp.route('/api/hello')
def api_hello():
    return jsonify({"message": "Hola desde el Blueprint Principal!"})