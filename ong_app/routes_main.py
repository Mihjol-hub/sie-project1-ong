# ong_app/routes_main.py
from flask import Blueprint, render_template, jsonify, redirect, url_for
# Import the connection function Translated comment
from .odoo_connector import get_odoo_client 
import logging
# Import to handle specific Odoo exceptions Translated comment
import odoorpc 

# Create the 'main' Blueprint

main_bp = Blueprint('main', __name__)


# Renaming these later (e.g., TAG_ID_PENDING) would be consistent
TAG_ID_PENDIENTE_MAIN = 4 # ID for Pending (as used in routes_books)
TAG_ID_APROBADO_MAIN = 5  # ID for Approved
TAG_ID_RECHAZADO_MAIN = 6 # ID for Rejected



@main_bp.route('/')
def index():
    # Page title translated
    page_title_en = "ONG Project - SIE Integration" 
    client = get_odoo_client()
    # Status message translated 
    odoo_status_en = "Connected (Verified!)" if client else "Disconnected (Check Logs!)" 
    
    # Initialize counters Comment translated
    counts = {
        'pending': 0,
        'approved': 0,
        'rejected': 0
    }
     # For specific counting errors Translated comment
    count_error = None 

    if client:
        # Log messages translated
        logging.info("[main_bp index] **VERIFYING LOCAL IDs TO USE:**") 
        logging.info(f"  - PENDING_MAIN = {TAG_ID_PENDIENTE_MAIN}")
        logging.info(f"  - APPROVED_MAIN  = {TAG_ID_APROBADO_MAIN}")
        logging.info(f"  - REJECTED_MAIN = {TAG_ID_RECHAZADO_MAIN}")
        
        logging.info("[main_bp index] Odoo client connected, getting counts...")
        try:
            # Using product.template to count, as tags are there
            ProductTemplateModel = client.env['product.template'] 
            
            # Use LOCAL '_MAIN' constants
            counts['pending'] = ProductTemplateModel.search_count([('product_tag_ids', '=', TAG_ID_PENDIENTE_MAIN)])
            logging.info(f"[main_bp index] >> RESULT search_count Pending (ID={TAG_ID_PENDIENTE_MAIN}): {counts['pending']}")

            counts['approved'] = ProductTemplateModel.search_count([('product_tag_ids', '=', TAG_ID_APROBADO_MAIN)])
            logging.info(f"[main_bp index] >> RESULT search_count Approved (ID={TAG_ID_APROBADO_MAIN}): {counts['approved']}")
            
            counts['rejected'] = ProductTemplateModel.search_count([('product_tag_ids', '=', TAG_ID_RECHAZADO_MAIN)])
            logging.info(f"[main_bp index] >> RESULT search_count Rejected (ID={TAG_ID_RECHAZADO_MAIN}): {counts['rejected']}")

        except odoorpc.error.RPCError as e:
             # Log message translated
            logging.error(f"[main_bp index] RPC Error getting counts: {e}", exc_info=True)
             # Error message translated
            count_error = f"Odoo RPC Error getting counts: {e}"
            # Counts will remain 0, show the error Comment translated
        
        except Exception as e:
             # Log message translated
             logging.error(f"[main_bp index] Unexpected error getting counts: {e}", exc_info=True)
              # Error message translated
             count_error = f"Unexpected error getting counts: {e}"
             # Counts will remain 0, show the error Comment translated
    
    else:
        # Log message translated
        logging.warning("[main_bp index] No Odoo client, cannot get counts.")
        # We already have odoo_status, no need for another error here Comment translated
         # Counts will remain 0 Comment translated
        pass 

    # Log message translated
    logging.info(f"Rendering index from main_bp with Odoo status: {odoo_status_en}, Counts: {counts}")
    
    # Pass counts and possible count error to template Comment translated
    return render_template('index.html', 
                           page_title=page_title_en, # Pass translated title 
                           odoo_connection_status=odoo_status_en, # Pass translated status
                           book_counts=counts,          # Dictionary with counts <-- Pass counts dictionary
                           count_fetch_error=count_error # Specific count error <-- Pass count error
                           )

# --- ODOO TEST ROUTE --- Translated comment
@main_bp.route('/api/odoo_version')
def odoo_version_test():
    # Log message translated
    logging.info("Received request for /api/odoo_version in main_bp")
     # Use imported function Comment translated
    client = get_odoo_client() 
    if client:
        try:
            # Log message translated
            logging.info("Odoo client available, attempting to get version...")
            server_version_info = client.version
             # Log message translated
            logging.info(f"Odoo version obtained (odoorpc): {server_version_info}")
            return jsonify(server_version_info)
        except odoorpc.error.RPCError as e:
            # Log message translated
            logging.error(f"Odoo RPC API Error (version) in main_bp: {e}", exc_info=True)
             # Error message translated
            return jsonify({"error": f"Odoo RPC API Error: {e}"}), 500
        except Exception as e:
            # Log message translated
            logging.error(f"Unexpected error API call version in main_bp: {e}", exc_info=True)
             # Error message translated
            return jsonify({"error": f"Unexpected error: {e}"}), 500
    else:
         # Log message translated
        logging.warning("Attempted call to /api/odoo_version in main_bp failed, no Odoo client.")
         # Error message translated
        return jsonify({"error": "Could not get Odoo client (check logs for connection details)."}), 503

# We can add the '/api/hello' route here if we want it back Comment translated
@main_bp.route('/api/hello')
def api_hello():
     # JSON message translated
    return jsonify({"message": "Hello from the Main Blueprint!"})

# Add route to search for tag ID (Comment section removed as it was example code/instructions)

@main_bp.route('/list_all_tags') 
def list_all_tags():
     # Route kept simple as per original modification - message translated
    return "Test route /list_all_tags works!" 

