# ong_app/scripts/list_operation_types.py
# command to run: python -m ong_app.scripts.list_operation_types

import odoorpc
import logging
# Use relative import assuming execution as a module
try:
    from ..odoo_connector import get_odoo_client
except ImportError:
    # Fallback (less likely needed)
    from ong_app.odoo_connector import get_odoo_client

logging.basicConfig(level=logging.INFO)
# Log message translated
logging.info("--- Searching for Operation Types ('stock.picking.type') ---")
client = get_odoo_client()
if client:
    try:
        OpTypeModel = client.env['stock.picking.type']
        op_types = OpTypeModel.search_read([], fields=['id', 'name', 'code', 'warehouse_id', 'default_location_src_id', 'default_location_dest_id'])
        # Print messages translated
        print("\n================ Found Operation Types ================")
        for ot in op_types:
            # Format strings translated where applicable (Nombre -> Name, Código -> Code, etc.)
            print(f" ID: {ot.get('id'):<4} | Name: '{ot.get('name')}' | Code: {ot.get('code')}")
            print(f"     └─ Def. Source: {ot.get('default_location_src_id')} | Def. Dest: {ot.get('default_location_dest_id')} | Warehouse: {ot.get('warehouse_id')}")
        print("============================================================\n")
        # Print message translated
        print("Look for the ID of the operation type you created ('Branch Shipments').")
    except Exception as e:
         # Error message translated
        print(f"Error: {e}")
else:
    # Error message translated
    print("Error: Could not connect to Odoo.")
# Print message translated
print("--- Script finished ---")