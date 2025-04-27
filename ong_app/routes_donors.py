# ong_app/routes_donors.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
# We need to import this now! Comment translated
from .odoo_connector import get_odoo_client 
import logging
# Import for RPC exceptions Comment translated
import odoorpc 

donors_bp = Blueprint('donors', __name__)

# Route to DISPLAY the add donor form Comment translated
@donors_bp.route('/add_donor', methods=['GET'])
def add_donor_form():
    # Log message translated
    logging.info("[donors_bp] Displaying form to add donor.")
    # Renders the empty template Comment translated
    return render_template('add_donor.html') 


# --- ROUTE TO PROCESS the add donor form --- Comment translated
@donors_bp.route('/add_donor', methods=['POST'])
def add_donor_submit():
    # 1. Get form data Comment translated
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')

    # 2. Basic validation (name required) Comment translated
    if not name:
        # Flash message translated
        flash('Full Name is mandatory.', 'error')
        # Redirect to GET Comment translated
        return redirect(url_for('donors.add_donor_form')) 

    # Log message translated
    logging.info(f"[donors_bp] Data received for new donor: Name='{name}', Email='{email}', Phone='{phone}'")

    # 3. Get Odoo connection Comment translated
    client = get_odoo_client()
    if not client:
        # Flash message translated
        flash('Odoo connection error. Could not add donor.', 'error')
        return redirect(url_for('donors.add_donor_form'))

    # 4. Try to create the contact (res.partner) in Odoo Comment translated
    try:
        # Model for contacts in Odoo: res.partner Comment translated

        # Simple search to avoid duplicates by email if provided Comment translated
        existing_partner_ids = []
        if email:
            search_criteria = [('email', '=', email)]
             # Log message translated
            logging.info(f"[donors_bp] Searching for existing partner by email: {email}")
            existing_partner_ids = client.env['res.partner'].search(search_criteria)
             # Log message translated
            logging.info(f"[donors_bp] IDs found: {existing_partner_ids}")

        if existing_partner_ids:
            # Take the first one found Comment translated
            partner_id = existing_partner_ids[0] 
             # Log message translated
            logging.warning(f"[donors_bp] Partner already exists with email {email}. ID: {partner_id}. Not creating new one.")
             # Flash message translated
            flash(f'A contact with email {email} already exists (ID: {partner_id}). Not added again.', 'warning')
            # We could redirect to a "view donor" page in the future Comment translated
            return redirect(url_for('donors.add_donor_form'))

        # If it doesn't exist, create a new one Comment translated
         # Log message translated
        logging.info("[donors_bp] Partner not found by email, creating new...")
        partner_data = {
            'name': name,
             # Odoo expects False if empty, not '' Comment translated
            'email': email if email else False, 
            'phone': phone if phone else False,
            # How to mark as Donor/Volunteer: Comment translated
            # Option 1 (Simple): Use internal notes Comment translated
            # Comment translated
            'comment': 'Contact registered from ONG Flask App', 
            # Option 2 (Better for future): Add Tags/Categories. Comment translated
            # Would require finding or creating IDs for 'Donor'/'Volunteer' categories Comment translated
            # 'category_id': [(6, 0, [id_categoria_donante])],
            # Option 3 (More advanced): Custom fields (e.g., x_is_donor = True) Comment translated

            # Other useful fields for contacts: Comment translated
             # Indicate it's a person, not a company Comment translated
            'company_type': 'person', 
            # 'is_company': False,   # Another way to indicate it in some versions/views Comment translated
        }

        new_partner_id = client.env['res.partner'].create(partner_data)
        # Log message translated
        logging.info(f"[donors_bp] Partner created successfully in Odoo! ID: {new_partner_id}")
         # Flash message translated
        flash(f'Donor/Volunteer "{name}" added successfully to Odoo (ID: {new_partner_id}).', 'success')

    except odoorpc.error.RPCError as e:
         # Log message translated
        logging.error(f"[donors_bp] RPC Error creating partner: {e}", exc_info=True)
         # Flash message translated
        flash(f'RPC Error communicating with Odoo: {e}', 'error')
    except Exception as e:
         # Log message translated
        logging.error(f"[donors_bp] Unexpected error creating partner: {e}", exc_info=True)
         # Flash message translated
        flash(f'Unexpected server error: {e}', 'error')

    # Redirect back to the form to see the flash message Comment translated
    return redirect(url_for('donors.add_donor_form'))


# --- NEW ROUTE TO LIST DONORS --- Comment translated
@donors_bp.route('/list_donors')
def list_donors():
    donors = []
    error_message = None

    client = get_odoo_client()
    if not client:
        # Flash message translated
        flash('Odoo connection error. Cannot list donors.', 'error')
         # Error message translated
        error_message = "Odoo connection error."
        # Render anyway to show error in list template Comment translated
        return render_template('list_donors.html', donors=donors, error_message=error_message)

    try:
        # Log message translated
        logging.info("[donors_bp] Attempting to search and read donors (partners) from Odoo...")
        # Search for partners who are individuals Comment translated
        # Read id, name, email, phone fields. Limit just in case. Comment translated
        # Note: We could sort from the search with 'order="name asc"' Comment translated
        partner_ids = client.env['res.partner'].search([('company_type', '=', 'person')], limit=100, order="name asc")
        # Log message translated
        logging.info(f"[donors_bp] Partner IDs found: {partner_ids}")

        if partner_ids:
            donors = client.env['res.partner'].read(partner_ids, ['id', 'name', 'email', 'phone'])
             # Log message translated
            logging.info(f"[donors_bp] Partner data read: {donors}")
            # Search already sorted them by name if 'order' was specified Comment translated
        else:
            # Log message translated
            logging.info("[donors_bp] No partners of type 'person' found.")
            # Flash message translated
            flash('No donors/contacts registered found.', 'info')

    except odoorpc.error.RPCError as e:
         # Log message translated
        logging.error(f"[donors_bp] RPC Error listing partners: {e}", exc_info=True)
         # Error message translated
        error_message = f"RPC Error communicating with Odoo: {e}"
        flash(error_message, 'error')
    except Exception as e:
         # Log message translated
        logging.error(f"[donors_bp] Unexpected error listing partners: {e}", exc_info=True)
         # Error message translated
        error_message = f"Unexpected server error: {e}"
        flash(error_message, 'error')

    # Render template passing donor list and possible error Comment translated
    return render_template('list_donors.html', donors=donors, error_message=error_message)