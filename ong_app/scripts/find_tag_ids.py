# ong_app/scripts/find_tag_ids.py
# to run this scripts with the command : python -m ong_app.scripts.find_tag_ids

import os
import sys
import logging
import odoorpc
from urllib.parse import urlparse # Keep urlparse for connection setup in this script

logging.basicConfig(level=logging.INFO)

# --- Odoo Configuration --- Translated comment
odoo_url = os.environ.get('ODOO_URL', 'http://odoo:8069') 
odoo_db = os.environ.get('ODOO_DB', 'ong_db')
odoo_user = os.environ.get('ODOO_USER') 
odoo_password = os.environ.get('ODOO_PASSWORD')

if not odoo_user or not odoo_password:
    # Log/Error messages translated
    logging.error("ERROR! ODOO_USER and ODOO_PASSWORD environment variables must be defined.")
 
    sys.exit(1) 

# Log messages translated
logging.info(f"Attempting to connect to Odoo:")
logging.info(f"  URL: {odoo_url}")
logging.info(f"  DB:  {odoo_db}")
logging.info(f"  User: {odoo_user}")

odoo = None
try:
    # Connection logic is part of this script, kept as is
    parsed_url = urlparse(odoo_url)
    protocol = 'jsonrpc+ssl' if parsed_url.scheme == 'https' else 'jsonrpc'
    host = parsed_url.hostname
    port = parsed_url.port if parsed_url.port else (443 if protocol == 'jsonrpc+ssl' else 8069)

    # Log message translated
    logging.info(f"  Connecting to host={host}, port={port}, protocol={protocol}")
    odoo = odoorpc.ODOO(host, protocol=protocol, port=port, timeout=60)
    
    # Log message translated
    logging.info(f"Attempting login to DB '{odoo_db}' with user '{odoo_user}'...")
    odoo.login(odoo_db, odoo_user, odoo_password)
    # Log message translated
    logging.info("Login successful!")

    # --- Find and list tags --- Translated comment
    # Log message translated
    logging.info("Searching for ALL 'product.tag' tags...")
    tag_ids = odoo.env['product.tag'].search([])

    if not tag_ids:
        # Log message translated
        logging.warning("No product tags ('product.tag') found in Odoo.")
    else:
        # Log message translated
        logging.info(f"Tag IDs found: {tag_ids}")
        tags_data = odoo.env['product.tag'].read(tag_ids, ['id', 'name'])
        
        # Print messages translated
        print("\n--- Product Tags Found ---")
        for tag in tags_data:
            # Formatting unchanged, text translated
            print(f"  ID: {tag['id']:<5} Name: '{tag['name']}'") 
        print("-----------------------------------------\n")

except odoorpc.error.RPCError as e:
    # Log message translated (set True for full traceback if it fails)
    logging.error(f"Odoo RPC ERROR: {e}", exc_info=False) 
except Exception as e:
    # Log message translated (set True for full traceback if it fails)
    logging.error(f"Unexpected ERROR: {e}", exc_info=False) 
finally:
    # Log message translated
    logging.info("Script finished.")