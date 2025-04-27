# ong_app/odoo_inventory_utils.py
import logging
from odoorpc.error import RPCError

def find_virtual_location_id(odoo_client, usage_type='inventory'):
    """
    Finds the ID of a virtual location by its usage type ('inventory' or 'production').
    Returns the ID of the first one found or None.

    :param odoo_client: Connected odoorpc client instance.
    :param usage_type: Usage type to search for ('inventory' or 'production').
    :return: Location ID or None.
    """
    #
    StockLocation = odoo_client.env['stock.location']
    domain = [('usage', '=', usage_type)]
    location_ids = StockLocation.search(domain, limit=1)
    if location_ids:
        # Log message translated
        logging.info(f"Virtual location found with usage '{usage_type}': ID {location_ids[0]}")
        return location_ids[0]
    else:
        # Log messages translated
        logging.warning(f"Could not find a virtual location with usage '{usage_type}'.")
        if usage_type == 'inventory':
            logging.info("Attempting to find location with usage 'production'...")
            return find_virtual_location_id(odoo_client, 'production')
        return None

def add_initial_stock_via_receipt(odoo_client, product_id, quantity, target_location_id):
    """
    Adds initial stock by simulating a Receipt (stock.picking).
    Uses public API methods for confirmation and validation.

    :param odoo_client: Connected odoorpc client instance.
    :param product_id: ID of the product.product.
    :param quantity: Quantity to add (float).
    :param target_location_id: ID of the destination stock.location (internal).
    :return: True if successful, False otherwise.
    """
    # Log message translated
    logging.info(f"Attempting to add initial stock (via Receipt Picking) for product ID {product_id} in location ID {target_location_id}")

    # Picking type ID for Receipts (stock.picking.type)
    # ID confirmed as 1
    RECEIPT_PICKING_TYPE_ID = 1 
    
    picking_id = None  # Initialize for error logging
    source_location_id = None # Initialize for error logging

    try:
        ProductProduct = odoo_client.env['product.product']
        
        # 1. Get product info (UoM and Name)
        product_info = ProductProduct.read(product_id, ['uom_id', 'display_name'])
        if not product_info or not product_info[0].get('uom_id') or not product_info[0].get('display_name'):
            # Log message translated
            logging.error(f"Could not retrieve complete information (UoM/Name) for product ID {product_id}")
            return False
        product_uom_id = product_info[0]['uom_id'][0]
        product_display_name = product_info[0]['display_name']
        # Log message translated
        logging.info(f"Product ID {product_id} - Name: '{product_display_name}', UoM ID: {product_uom_id}")

        # 2. Find virtual source location (as before)
        source_location_id = find_virtual_location_id(odoo_client)
        if not source_location_id:
            # Log message translated
            logging.error("Critical Error! Could not find a virtual source location ('inventory' or 'production').")
            return False
        # Log message translated
        logging.info(f"Using virtual source location ID: {source_location_id}")
            
        # 3. Prepare data to create the stock.picking (RECEIPT)
        # Note: Locations in the picking define the general flow,
        #       and move lines inherit this if not specified otherwise.
        picking_vals = {
            'picking_type_id': RECEIPT_PICKING_TYPE_ID,   # Picking type ID for Receipts (stock.picking.type)
            'location_id': source_location_id,            # Source (Virtual)
            'location_dest_id': target_location_id,       # Destination (Where you want the final stock)
            # Descriptive text translated
            'origin': f'Initial Stock Entry Auto (Flask): {product_display_name}', 
            'move_ids_without_package': [
                # Command to create a new move line translated
                (0, 0, { 
                    # Line description translated
                    'name': product_display_name,         
                    # The product
                    'product_id': product_id,           
                    # Expected quantity
                    'product_uom_qty': quantity,        
                    # The unit of measure
                    'product_uom': product_uom_id,      
                    # Line source (can inherit)
                    'location_id': source_location_id,    
                    # Line destination (can inherit)
                    'location_dest_id': target_location_id 
                })
            ]
        }
        # Log message translated
        logging.info(f"Values to create stock.picking (Receipt): {picking_vals}")

        # 4. Create the stock.picking
        picking_id = odoo_client.execute_kw('stock.picking', 'create', [picking_vals])
        if not picking_id:
             # Log message translated
             logging.error("Stock picking creation (Receipt) did not return an ID.")
             return False
        if isinstance(picking_id, list): # Handle if it returns a list
             if not picking_id:
                 # Log message translated
                 logging.error("Stock picking creation (Receipt) returned an empty list.")
                 return False
             picking_id = picking_id[0]
        # Log message translated
        logging.info(f"Stock Picking (Receipt) created with ID: {picking_id}")

        # 5. Confirm the Picking (public action)
        # Log message translated
        logging.info(f"Calling action_confirm for picking ID {picking_id}...")
        odoo_client.execute_kw('stock.picking', 'action_confirm', [[picking_id]])
        # Log message translated
        logging.info(f"Picking ID {picking_id} confirmed.")

        # 6. Reserve/Assign the Picking (public action)
        # Log message translated
        logging.info(f"Calling action_assign for picking ID {picking_id}...")
        odoo_client.execute_kw('stock.picking', 'action_assign', [[picking_id]])
        # Log message translated
        logging.info(f"Assignment attempt sent for picking ID {picking_id}.")
        
        # 7. Update the qty_done for the move line (stock.move.line)
        logging.info(f"Setting 'qty_done' = {quantity} for the lines of picking ID {picking_id}")
        
        # Read the detailed move lines (stock.move.line) associated with the picking
        move_lines_data = odoo_client.execute_kw(
            'stock.move.line', 'search_read',
            # Search for the line of our product
            [[('picking_id', '=', picking_id), ('product_id', '=', product_id)]],
            {'fields': ['id'], 'limit': 1} # need 'id'
        )
        
        if not move_lines_data:
            # Log message translated
            logging.error(f"Could not find stock.move.line for product {product_id} in picking {picking_id} after assigning. Cannot validate!")
            # could try to cancel the picking here if desired...
            return False
            
        move_line_id = move_lines_data[0]['id']
        # Log message translated
        logging.info(f"Detailed move line found (stock.move.line) ID: {move_line_id}. Updating qty_done...")
        
        # Write the done quantity to the found line
        write_ok = odoo_client.execute_kw(
            'stock.move.line', 'write',
            [[move_line_id], {'qty_done': quantity}]
        )
        if not write_ok:
            
             logging.error(f"Failed to write qty_done on stock.move.line ID {move_line_id}.")
             return False
        # Log message translated
        logging.info(f"qty_done updated on stock.move.line ID {move_line_id}.")
        # --- END EXTRA STEP ---

        # 8. Validate/Process the Picking (public action of the "Validate" button)
        # Log message translated
        logging.info(f"Attempting to validate picking ID {picking_id} by calling button_validate...")
        # button_validate can return True or an action dictionary if extra steps are needed (e.g., backorder)
        validation_result = odoo_client.execute_kw('stock.picking', 'button_validate', [[picking_id]])
        # Log message translated
        logging.info(f"Result of button_validate for picking ID {picking_id}: {validation_result}")

        # We consider it a success if there were no RPC errors and button_validate didn't explicitly return False
        # (An action dictionary as a result often means partial success or backorder, which is OK for our initial stock purpose)
        if validation_result is False: # Explicit check in case it returns False
             # Log message translated
             logging.error(f"button_validate for picking ID {picking_id} returned False.")
             return False

        # Verify final picking state (optional, but good)
        final_picking_state_data = odoo_client.execute_kw('stock.picking', 'read', [[picking_id]], {'fields': ['state']})
        final_picking_state = final_picking_state_data[0]['state'] if final_picking_state_data else 'unknown'
        # Log message translated
        logging.info(f"Stock Picking ID {picking_id}: Final state verified as '{final_picking_state}'.")
        
        if final_picking_state == 'done':
            # Log message translated
            logging.info(f"Success! Stock added correctly via Receipt Picking for product {product_id}.")
            return True
        else:
            # If not 'done' but validation didn't raise a direct error, it might be waiting for a backorder.
            # For the purpose of adding initial stock, this might be sufficient, but it's good to log.
            # Log message translated
            logging.warning(f"Final state of picking {picking_id} is '{final_picking_state}' (not 'done'). Stock might be available, but review the picking in Odoo.")
            # Decide whether to return True or False here. If the goal is ONLY available stock, True might be okay.
            # If we want the entire flow to complete perfectly, it would be False. Let's be optimistic for now:
            return True # Assume success if validation didn't explicitly fail


    except RPCError as e:
        # Log messages translated, error handling unchanged
        error_msg = f"Odoo RPC Error"
        if picking_id: error_msg += f" (Picking ID {picking_id})"
        error_msg += f" while trying to add stock via Receipt for product {product_id}: {e}"
        logging.error(error_msg, exc_info=True)
        # We could try to cancel the picking here too
        # if picking_id:
        #    try: odoo_client.execute_kw('stock.picking', 'action_cancel', [[picking_id]])
        #    except: pass
        return False
    except Exception as e:
        # Log messages translated, error handling unchanged
        error_msg = f"Unexpected error"
        if picking_id: error_msg += f" (Picking ID {picking_id})"
        error_msg += f" while trying to add stock via Receipt for product {product_id}: {e}"
        logging.error(error_msg, exc_info=True)
        return False