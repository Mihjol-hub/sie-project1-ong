# ong_app/odoo_connector.py
import os
import odoorpc
import logging

# Configuración de Odoo desde variables de entorno (movida aquí)
odoo_url = os.environ.get('ODOO_URL')
odoo_db = os.environ.get('ODOO_DB')
odoo_user = os.environ.get('ODOO_USER')
odoo_password = os.environ.get('ODOO_PASSWORD')

_odoo_client = None # Variable "global" a este módulo

def get_odoo_client():
    """Función para obtener o crear la conexión a Odoo (vive aquí ahora)."""
    global _odoo_client
    logging.info("Llamada a get_odoo_client()")

    # Forzaremos el intento de conexión siempre para depuración inicial
    # if _odoo_client is not None:
    #    logging.info("Devolviendo cliente Odoo existente.")
    #    return _odoo_client

    logging.info(f"Variables Odoo: URL={odoo_url}, DB={odoo_db}, User={odoo_user}, Pwd={'Set' if odoo_password else 'None'}")

    if not all([odoo_url, odoo_db, odoo_user, odoo_password]):
        logging.error("Faltan una o más variables de entorno para la conexión a Odoo.")
        _odoo_client = None
        return None

    try:
        host = odoo_url.replace('http://', '').split(':')[0]
        port = int(odoo_url.split(':')[-1])
        protocol = 'jsonrpc+ssl' if port == 443 else 'jsonrpc'

        logging.info(f"Paso 1: Intentando crear instancia odoorpc.ODOO(host='{host}', protocol='{protocol}', port={port}, timeout=60)")
        client_instance = odoorpc.ODOO(host, protocol=protocol, port=port, timeout=60)
        logging.info("Paso 1.1: Instancia odoorpc.ODOO creada.")

        logging.info(f"Paso 2: Intentando login en DB '{odoo_db}' con usuario '{odoo_user}'")
        client_instance.login(odoo_db, odoo_user, odoo_password)
        logging.info("Paso 3: ¡Login exitoso!")
        _odoo_client = client_instance # Guardamos la instancia exitosa
        return _odoo_client

    except odoorpc.error.RPCError as e:
        logging.error(f"ERROR RPC al conectar/autenticar con Odoo (odoorpc): {e}", exc_info=True)
        _odoo_client = None # Aseguramos que no quede una instancia fallida
        return None
    except Exception as e:
        logging.error(f"ERROR INESPERADO al inicializar/conectar con odoorpc: {e}", exc_info=True)
        _odoo_client = None
        return None