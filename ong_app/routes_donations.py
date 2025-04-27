# ong_app/routes_donations.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from .odoo_connector import get_odoo_client # Needed to talk to Odoo
from datetime import datetime # To handle dates
import logging
import odoorpc # To handle Odoo specific exceptions

# Create the Blueprint specific for monetary donations
# 'donations' is the internal name of the blueprint
# __name__ helps Flask find associated resources
donations_bp = Blueprint('donations', __name__)

# --- KEY CONSTANT: ODOO PRODUCT ID ---
# This is the ID of the "Monetary Donation" Service product we created in Odoo.
DONATION_PRODUCT_ID = 11 # Confirmed ID!

# --- Route to DISPLAY the add monetary donation form (GET) ---
@donations_bp.route('/add_monetary', methods=['GET'])
def add_monetary_donation_form():
    """
    Displays the form to register a new monetary donation.
    Loads the list of existing donors from Odoo for the dropdown.
    """
    # Log message translated
    logging.info("[donations_bp GET /add_monetary] Accessing monetary donation form.")

    # Critical initial check
    # If the ID is invalid (<=0 instead of -1)
    if DONATION_PRODUCT_ID <= 0: 
        # Flash message translated
         flash("Critical Error: The monetary donation product ID (DONATION_PRODUCT_ID) is invalid in routes_donations.py.", "error")
        # Log message translated
         logging.error("[donations_bp GET /add_monetary] DONATION_PRODUCT_ID is invalid.")
         # Better to redirect home if basic config fails
         return redirect(url_for('main.index'))

    # List to store donors for the <select>
    donors = [] 
    # Variable for specific errors during this load
    error_message = None 
    # Get Odoo connection
    client = get_odoo_client() 

    if not client:
        # Flash message translated
        flash('Odoo connection error. Cannot load donors for the form.', 'error')
        # Log message translated
        logging.warning("[donations_bp GET /add_monetary] Could not get Odoo client.")
        # Error message translated
        error_message = "Odoo connection error while loading donors."
        # The form will be rendered, but the dropdown will be empty and the error shown
    else:
        # If connection exists, try getting donors
        try:
            # Log message translated
            logging.info("[donations_bp GET /add_monetary] Odoo connection OK. Searching for donors (res.partner type person)...")
            # Search for partners (contacts) that are 'person' (company_type='person')
            # Sort them by name for the dropdown
            partner_ids = client.env['res.partner'].search([('company_type', '=', 'person')], order="name asc")
            if partner_ids:
                # Read only ID and Name, which is what's needed for the <select>
                donors = client.env['res.partner'].read(partner_ids, ['id', 'name'])
                # Log message translated
                logging.info(f"[donations_bp GET /add_monetary] {len(donors)} donors found and read.")
            else:
                 # If no registered donors are found
                 # Log message translated
                 logging.info("[donations_bp GET /add_monetary] No partners of type 'person' found.")
                 # Inform the user, but it's not a critical system error
                 # Flash message translated
                 flash('No donors registered in the system to select. You can add them first.', 'info')

        except odoorpc.error.RPCError as e:
            # Log message translated
            logging.error(f"[donations_bp GET /add_monetary] Odoo RPC Error searching donors: {e}", exc_info=True)
            # Error message translated
            error_message = f"Odoo error getting donor list: {e}"
            flash(error_message, 'error')
        except Exception as e:
            # Log message translated
            logging.error(f"[donations_bp GET /add_monetary] Unexpected error searching donors: {e}", exc_info=True)
            # Error message translated
            error_message = f"Unexpected server error getting donors: {e}"
            flash(error_message, 'error')

    # Render the HTML form template
    # Pass the 'donors' list (can be empty) and 'error_message' (can be None)
    # Log message translated
    logging.info("[donations_bp GET /add_monetary] Rendering template add_monetary_donation.html.")
    return render_template('add_monetary_donation.html',
                           donors=donors,
                           error_message=error_message)


# --- ROUTE TO PROCESS the add monetary donation form (POST) ---
@donations_bp.route('/add_monetary', methods=['POST'])
def add_monetary_donation_submit():
    """
    Processes data submitted from the monetary donation form.
    Validates data and creates a 'sale.order' record in Odoo.
    """
    # Log message translated
    logging.info("[donations_bp POST /add_monetary] Received request to register monetary donation.")

    # Critical initial check (again, just in case)
    if DONATION_PRODUCT_ID <= 0:
        # Flash message translated
        flash("Critical Error: Monetary donation product ID is not configured or invalid.", "error")
        # Log message translated
        logging.error("[donations_bp POST /add_monetary] DONATION_PRODUCT_ID is invalid.")
        # Return to the form to show the error
        return redirect(url_for('donations.add_monetary_donation_form'))

    # 1. Get data from the HTML form
    donor_id_str = request.form.get('donor_id')
    amount_str = request.form.get('amount')
    # Input type 'date', might be empty
    donation_date_str = request.form.get('donation_date') 
     # Optional textarea, default to empty string if not present
    description = request.form.get('description', '')

    # Log message translated
    logging.debug(f"[donations_bp POST /add_monetary] Raw data received: donor_id='{donor_id_str}', amount='{amount_str}', date='{donation_date_str}', desc='{description}'")

    # 2. Data validation and conversion
    if not donor_id_str or not amount_str:
        # Flash message translated
        flash('Donor and Amount are mandatory fields.', 'error')
         # Go back to the form
        return redirect(url_for('donations.add_monetary_donation_form')) 

    try:
         # Convert donor ID to integer
        donor_id = int(donor_id_str)
        # Convert amount to float (replace comma with dot just in case)
        amount = float(amount_str.replace(',', '.')) 
        if amount <= 0:
            # Flash message translated
            flash('Amount must be a positive number.', 'error')
            return redirect(url_for('donations.add_monetary_donation_form'))
    except ValueError:
        # Flash message translated
        flash('Donor ID or Amount do not have a valid numeric format.', 'error')
        return redirect(url_for('donations.add_monetary_donation_form'))

    # Date Processing
    # Format Odoo expects (string 'YYYY-MM-DD HH:MM:SS' or False)
    donation_date_odoo_format = None 
    if donation_date_str:
        try:
            # Try converting 'YYYY-MM-DD' to 'YYYY-MM-DD HH:MM:SS' (Odoo prefers this for Datetime fields)
            dt_obj = datetime.strptime(donation_date_str, '%Y-%m-%d')
            donation_date_odoo_format = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
             # Log message translated
            logging.debug(f"Provided date '{donation_date_str}' converted to '{donation_date_odoo_format}' for Odoo.")
        except ValueError:
             # If format is invalid, inform and use current date/time
             # Flash message translated
             flash('Invalid date format. Using current date and time.', 'warning')
             donation_date_odoo_format = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
             # Log message translated
             logging.warning(f"Invalid date format received: '{donation_date_str}'. Using now: '{donation_date_odoo_format}'.")
    else:
         # If no date provided, use current
         donation_date_odoo_format = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
          # Log message translated
         logging.debug(f"No date provided. Using now: '{donation_date_odoo_format}'.")

    # Log message translated
    logging.info(f"[donations_bp POST /add_monetary] Validated data: Donor ID={donor_id}, Amount={amount}, Date='{donation_date_odoo_format}', Desc='{description}'")

    # 3. Get Odoo connection
    client = get_odoo_client()
    if not client:
        # Flash message translated
        flash('Odoo connection error. Could not register the donation at this time.', 'error')
        # Log message translated
        logging.error("[donations_bp POST /add_monetary] Could not get Odoo client.")
        return redirect(url_for('donations.add_monetary_donation_form'))

    # 4. Attempt to create the Sale Order ('sale.order') in Odoo
    try:
        # Log message translated
        logging.info("[donations_bp POST /add_monetary] Odoo connection OK. Preparing data to create sale.order...")

        # (Optional but useful) Get donor name to include in description
        donor_name = ""
        try:
            donor_info = client.env['res.partner'].read(donor_id, ['name'])
            if donor_info and 'name' in donor_info[0]:
                 donor_name = donor_info[0]['name']
                 logging.debug(f"Donor name retrieved: '{donor_name}'")
        except Exception as e:
             # Log message translated
             logging.warning(f"[donations_bp POST /add_monetary] Could not retrieve name for donor ID {donor_id}. Error: {e}", exc_info=True)


        # Build the data dictionary for the 'create' call to 'sale.order'
        order_data = {
             # Contact ID (Donor)
            'partner_id': donor_id,            
            # Order date (donation)
            'date_order': donation_date_odoo_format, 
             # Initial state: Draft (could be 'sale' to confirm automatically)
            'state': 'draft',                 
            # 'note' field: useful for general description visible in Odoo
            # String translated
            'note': description or f"Monetary donation registered from Flask application on {datetime.now().strftime('%Y-%m-%d')}.",

            # --- ORDER LINES ('order_line') ---
            # Uses a list of tuples. Each tuple represents an operation on the lines.
            # (0, 0, {values}) means "create a new line with these values"
            'order_line': [
                (0, 0, {
                    # Product ID "Monetary Donation" (Service type)
                    'product_id': DONATION_PRODUCT_ID, 
                    # Free text field for the line description.
                    # Make it descriptive, including donor name if available. String translated.
                    'name': f"Monetary Donation - {donor_name}" if donor_name else f"Monetary Donation (Product ID: {DONATION_PRODUCT_ID})",
                    # Quantity: Always 1 for a simple donation
                    'product_uom_qty': 1,       
                     # Unit Price: The donated amount
                    'price_unit': amount,       
                    # Unit of Measure ID. Usually 1 for "Units".
                    # If Odoo complains about this field, we might omit it or find the correct ID.
                    'product_uom': 1,
                    # Other fields might be required depending on Odoo configuration
                    # (taxes, analytic accounts, etc.), but trying minimum first.
                })
            ]
            # Optional fields that might be useful if we had users/teams configured:
            # 'user_id': ID of the responsible Odoo user (if app had Odoo login)
            # 'team_id': Sales Team ID (if configured and relevant)
        }
         # Log message translated
        logging.debug(f"[donations_bp POST /add_monetary] Data to be sent to Odoo 'sale.order.create': {order_data}")

        # THE KEY CALL TO CREATE THE RECORD IN ODOO!
         # A list containing one dictionary is passed
        new_order_id = client.env['sale.order'].create([order_data]) 

        if new_order_id:
            # Log message translated
            logging.info(f"[donations_bp POST /add_monetary] Sale order (Donation) created successfully in Odoo! New ID: {new_order_id}")
             # Flash message translated
            flash(f'Monetary donation of €{amount:.2f} registered successfully (Odoo Reference: {new_order_id}).', 'success') # Changed currency symbol

            
            try:
                client.env['sale.order'].action_confirm(new_order_id)
                 # Log message translated
                logging.info(f"[donations_bp POST /add_monetary] Order {new_order_id} confirmed automatically in Odoo.")
                 # Flash message translated (additional message)
                flash(f'Odoo Order ID:{new_order_id} automatically confirmed.', 'info') 
            except Exception as confirm_err:
                 # Log message translated
                logging.error(f"[donations_bp POST /add_monetary] Error auto-confirming Odoo order ID {new_order_id}: {confirm_err}", exc_info=True)
                # Donation created, but confirmation failed. Inform as warning.
                 # Flash message translated
                flash(f'Donation registered (ID:{new_order_id}), but there was a problem confirming it automatically in Odoo.', 'warning')

        else:
             # Should not happen without exception, but just in case
             # Log message translated
             logging.error("[donations_bp POST /add_monetary] Odoo call 'sale.order.create' returned no ID, but no exception was raised.")
             # Flash message translated
             flash('Donation seems registered in Odoo, but confirmation of the ID was not received.', 'warning')


    except odoorpc.error.RPCError as e:
        # Specific Odoo communication error (e.g., missing required field, permission, etc.)
        # Log message translated
        logging.error(f"[donations_bp POST /add_monetary] Odoo RPC Error creating sale.order: {e}", exc_info=True)
        # Try getting a more detailed error message from the exception object
         # Try getting 'fault' if it exists, otherwise generic error
        error_details = str(getattr(e, 'fault', e)) 
         # Flash message translated
        flash(f'Odoo error trying to register the donation ({type(e).__name__}): {error_details}. Check the data and try again.', 'error')
        # Return to the form so user can correct and retry
        return redirect(url_for('donations.add_monetary_donation_form'))

    except Exception as e:
        # Other unexpected error type (e.g., network issue, error in our Python code)
         # Log message translated
        logging.error(f"[donations_bp POST /add_monetary] Unexpected error processing the donation: {e}", exc_info=True)
         # Flash message translated
        flash(f'Unexpected server error processing the donation: {e}', 'error')
        # Return to the form
        return redirect(url_for('donations.add_monetary_donation_form'))

    # If everything went well (creation successful), redirect to the donation list page
    # Log message translated
    logging.info("[donations_bp POST /add_monetary] Redirecting to donation list.")
    return redirect(url_for('donations.list_monetary_donations'))


# --- ROUTE TO LIST REGISTERED MONETARY DONATIONS (GET) ---
@donations_bp.route('/list_monetary')
def list_monetary_donations():
    """
    Displays a list of registered monetary donations (sale orders in Odoo).
    """
    # Log message translated
    logging.info("[donations_bp GET /list_monetary] Accessing the monetary donation list.")
     # List to store donations read from Odoo
    donations_list = [] 
    error_message = None
    client = get_odoo_client()

    if not client:
        # Flash message translated
        flash('Odoo connection error. Cannot list donations.', 'error')
         # Log message translated
        logging.warning("[donations_bp GET /list_monetary] Could not get Odoo client.")
         # Error message translated
        error_message = "Odoo connection error."
    else:
        try:
            # Log message translated
            logging.info("[donations_bp GET /list_monetary] Odoo connection OK. Searching for sale orders...")
            # Define which fields we want to read from each 'sale.order'
            fields_to_read = ['id', 'name', 'partner_id', 'amount_total', 'date_order', 'state']
            # Search ALL sale.orders.
            # NOTE: If the app managed normal sales besides donations, we would need to filter
            #       (e.g., search only those using DONATION_PRODUCT_ID in their lines, more complex).
            #       For now, assume all 'sale.order' are donations.
            # Sort by date descending to see most recent first. Limit to 100 just in case.
            order_ids = client.env['sale.order'].search([], order="date_order desc", limit=100)
             # Log message translated
            logging.info(f"[donations_bp GET /list_monetary] sale.order IDs found: {order_ids}")

            if order_ids:
                # If IDs found, read data for those records
                donations_list = client.env['sale.order'].read(order_ids, fields_to_read)
                # Log message translated
                logging.info(f"[donations_bp GET /list_monetary] {len(donations_list)} donations (orders) read from Odoo.")
                # 'partner_id' comes as a tuple [ID, Name], so in template access partner_id[1]
            else:
                 # Log message translated
                logging.info("[donations_bp GET /list_monetary] No sale orders (donations) found in Odoo.")
                 # Flash message translated
                flash('No monetary donations registered in the system yet.', 'info')

        except odoorpc.error.RPCError as e:
             # Log message translated
            logging.error(f"[donations_bp GET /list_monetary] Odoo RPC Error listing sale.order: {e}", exc_info=True)
             # Error message translated
            error_message = f"Odoo error getting donation list: {e}"
            flash(error_message, 'error')
        except Exception as e:
             # Log message translated
            logging.error(f"[donations_bp GET /list_monetary] Unexpected error listing sale.order: {e}", exc_info=True)
             # Error message translated
            error_message = f"Unexpected server error getting donations: {e}"
            flash(error_message, 'error')

    # Render the HTML template showing the list
    # Pass 'donations_list' (can be empty) and 'error_message' (can be None)
    # Log message translated
    logging.info("[donations_bp GET /list_monetary] Rendering template list_monetary_donations.html.")
    return render_template('list_monetary_donations.html',
                           # Consistent variable name with the template
                           donations=donations_list, 
                           error_message=error_message)