# ong_app/scripts/list_locations.py 
# Script to list stock locations (stock.location) and their IDs 
# to run: python -m ong_app.scripts.list_locations

import odoorpc
import logging


try:
    from ..odoo_connector import get_odoo_client
except ImportError:
    # Fallback if run differently (less likely needed with -m)
    try:
        from ong_app.odoo_connector import get_odoo_client
    except ImportError:
         # Basic logging config to see the error Comment translated
        logging.basicConfig(level=logging.ERROR) 
         # Log messages translated
        logging.error("FATAL ERROR! Could not import get_odoo_client.")
        logging.error("Ensure ong_app/odoo_connector.py exists and you are running from the root directory (e.g., using python -m).")
        exit(1)

logging.basicConfig(level=logging.INFO)
# Log message translated
logging.info("--- Searching for stock locations ('stock.location') ---")

client = get_odoo_client()

if client:
    # Log message translated
    logging.info("Odoo connection obtained.")
    try:
        LocationModel = client.env['stock.location']

        # Search for all active locations to avoid listing archived ones Translated comment
        
        search_domain = [('active', '=', True)]
        # Sort by full name for easy finding 
        order = 'complete_name asc'
         # Log message translated
        logging.info("Executing search on 'stock.location'...")

        # Read important fields: id, full name, type, if scrap/return location 
        fields_to_read = ['id', 'complete_name', 'usage', 'scrap_location', 'return_location']
        location_data = LocationModel.search_read(search_domain, fields=fields_to_read, order=order)

        if location_data:
             # Print messages translated
            print("\n===============================================")
            print("         Locations Found:")
            print("===============================================")
            for loc in location_data:
                # Format output slightly Translated comment
                loc_id = loc.get('id')
                loc_name = loc.get('complete_name', 'N/A')
                loc_usage = loc.get('usage', 'N/A')
                 # Print messages translated
                print(f"  ID: {loc_id:<5} | Name: '{loc_name}'  (Type: {loc_usage})")
            print("===============================================\n")
             # Print messages translated
            print("Look for the IDs of:")
            # Example location names kept as they are specific identifiers
            print("  - 'WH/Stock/Stock Books Approved ONG'") 
            print("  - 'Ecuador Branche/EC - Quito' (or similar for Ecuador)")
            print("  - 'Venezuela Branche/...' (or similar for Venezuela)")

        else:
            # Print message translated
            print("\nERROR: No active locations found.")

    except odoorpc.error.RPCError as e:
        # Print/Log messages translated
        print(f"\nOdoo RPC Error: {e}")
        logging.error("RPC Error", exc_info=True)
    except Exception as e:
         # Print/Log messages translated
        print(f"\nUnexpected error: {e}")
        logging.error("Unexpected error", exc_info=True)
else:
     # Print/Log messages translated
    print("\nCritical Error: Could not obtain Odoo client.")
    logging.error("Failed to get Odoo client")

# Print message translated
print("--- Script finished ---")