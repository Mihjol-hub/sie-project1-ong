# find_tag_ids.py
import os
import sys
import logging
import odoorpc
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)

# --- Configuración Odoo ---
odoo_url = os.environ.get('ODOO_URL', 'http://odoo:8069') 
odoo_db = os.environ.get('ODOO_DB', 'ong_db')
odoo_user = os.environ.get('ODOO_USER') 
odoo_password = os.environ.get('ODOO_PASSWORD')

if not odoo_user or not odoo_password:
    logging.error("¡ERROR! Las variables de entorno ODOO_USER y ODOO_PASSWORD deben estar definidas.")
    # Comentar el sys.exit si necesitas ponerlas manualmente abajo
    # QUITALO o ponlas aqui para que funcione el script:
    # odoo_user = "miguel.romero.3@etu.unige.ch" 
    # odoo_password = "simplepassword"         
    sys.exit(1) # Salir si faltan credenciales (¡DESCOMENTA si las variables no funcionan!)

logging.info(f"Intentando conectar a Odoo:")
logging.info(f"  URL: {odoo_url}")
logging.info(f"  DB:  {odoo_db}")
logging.info(f"  User: {odoo_user}")

odoo = None
try:
    parsed_url = urlparse(odoo_url)
    protocol = 'jsonrpc+ssl' if parsed_url.scheme == 'https' else 'jsonrpc'
    host = parsed_url.hostname
    port = parsed_url.port if parsed_url.port else (443 if protocol == 'jsonrpc+ssl' else 8069)

    logging.info(f"  Conectando a host={host}, port={port}, protocol={protocol}")
    odoo = odoorpc.ODOO(host, protocol=protocol, port=port, timeout=60)
    
    logging.info(f"Intentando login en DB '{odoo_db}' con usuario '{odoo_user}'...")
    odoo.login(odoo_db, odoo_user, odoo_password)
    logging.info("¡Login exitoso!")

    # --- Buscar y listar etiquetas ---
    logging.info("Buscando TODAS las etiquetas 'product.tag'...")
    tag_ids = odoo.env['product.tag'].search([])

    if not tag_ids:
        logging.warning("No se encontró NINGUNA etiqueta de producto ('product.tag') en Odoo.")
    else:
        logging.info(f"IDs de etiquetas encontradas: {tag_ids}")
        tags_data = odoo.env['product.tag'].read(tag_ids, ['id', 'name'])
        
        print("\n--- Etiquetas de Producto Encontradas ---")
        for tag in tags_data:
            print(f"  ID: {tag['id']:<5} Nombre: '{tag['name']}'") 
        print("-----------------------------------------\n")

except odoorpc.error.RPCError as e:
    logging.error(f"ERROR RPC Odoo: {e}", exc_info=False) # Poner True para traceback completo si falla
except Exception as e:
    logging.error(f"ERROR inesperado: {e}", exc_info=False) # Poner True para traceback completo si falla
finally:
    logging.info("Script finalizado.")