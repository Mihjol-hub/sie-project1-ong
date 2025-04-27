# ong_app/routes_books.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from .odoo_connector import get_odoo_client
from .odoo_inventory_utils import add_initial_stock_via_receipt # Correct function imported
import logging
import odoorpc

# --- DEFINE ACTUAL TAG IDs (Updated!) ---

TAG_ID_PENDIENTE = 4  # Renaming to TAG_ID_PENDING later might be good, but keeping for safety now
TAG_ID_APROBADO  = 5  # Renaming to TAG_ID_APPROVED later might be good
TAG_ID_RECHAZADO = 6  # Renaming to TAG_ID_REJECTED later might be good

# --- CONSTANT IDs FOR LOGISTICS TAGS ---

TAG_ID_LOGISTICS_READY = 7
TAG_ID_LOGISTICS_TRANSIT_EC = 10
TAG_ID_LOGISTICS_TRANSIT_VE = 11
TAG_ID_LOGISTICS_DELIVERED = 9

# (We could use the generic 'In Transit' ID 8 if we wanted to simplify later)
LIST_ALL_LOGISTICS_TAGS = [TAG_ID_LOGISTICS_READY, TAG_ID_LOGISTICS_TRANSIT_EC,
                           TAG_ID_LOGISTICS_TRANSIT_VE, TAG_ID_LOGISTICS_DELIVERED, 8]


books_bp = Blueprint('books', __name__)

# --- Route to DISPLAY the add book form (WITH DONOR LOADING) ---
@books_bp.route('/add_book', methods=['GET'])
def add_book_form():
    donors = [] # Initialize as an empty list
    error_message = None

    client = get_odoo_client()
    if not client:
        # Flash message translated
        flash('Odoo connection error. Donors cannot be loaded.', 'error')
        # Error message translated
        error_message = "Odoo connection error when loading donors." 
        # We don't return here yet, to render the form even without donors
    else:
        # Try to get the donor list ONLY if the connection was successful
        try:
            # Search for partners of type 'person' (assuming they are donors/volunteers)
            # Sort by name ascending for the dropdown
            donor_ids = client.env['res.partner'].search(
                [('company_type', '=', 'person')],
                limit=150,  # Increased limit just in case
                order="name asc"
            )
            # Log message translated
            logging.info(f"[books_bp GET /add_book] Donor IDs found: {donor_ids}")

            if donor_ids:
                # Read only ID and name for the dropdown
                donors = client.env['res.partner'].read(donor_ids, ['id', 'name'])
                # Log message translated
                logging.info(f"[books_bp GET /add_book] Donor data (id, name) read: {len(donors)} found.")
            else:
                # Log message translated
                logging.info("[books_bp GET /add_book] No partners of type 'person' found.")
        
                # flash('No registered donors found to select.', 'info')

        except odoorpc.error.RPCError as e:
            # Log message translated
            logging.error(f"[books_bp GET /add_book] RPC Error loading donors: {e}", exc_info=True)
            # Error message translated
            error_message = f"RPC Error loading donor list: {e}"
            flash(error_message, 'error')
        except Exception as e:
            # Log message translated
            logging.error(f"[books_bp GET /add_book] Unexpected error loading donors: {e}", exc_info=True)
            # Error message translated
            error_message = f"Unexpected error loading donors: {e}"
            flash(error_message, 'error')

    # ALWAYS render the template, passing the 'donors' list (which will be full or empty)
    return render_template('add_book.html', donors=donors, error_message=error_message)


# --- Route to PROCESS the add book form ---
@books_bp.route('/add_book', methods=['POST'])
def add_book_submit():
    title = request.form.get('title')
    author = request.form.get('author')
    isbn = request.form.get('isbn')
    donor_id_str = request.form.get('donor_id')

    # Constants (no changes)
    TARGET_STOCK_LOCATION_ID = 30
    # It's good practice to use float for Odoo quantities
    INITIAL_STOCK_QTY = 1.0 

    # Simple title validation (no changes)
    if not title:
        # Flash message translated
        flash('Book title is mandatory.', 'error')
        return redirect(url_for('books.add_book_form'))

    # Log message translated
    logging.info(f"[books_bp POST /add_book] Data: T={title}, A={author}, I={isbn}, D={donor_id_str}")

    # Odoo connection (no changes)
    client = get_odoo_client()
    if not client:
        # Flash message translated
        flash('Odoo connection error. Could not add book.', 'error')
        return redirect(url_for('books.add_book_form'))

    # --- Prepare donor info (no changes from your original code) ---
    donor_name = None
    # Variable name is fine, translating the created string below
    donor_info_text = "" 
    if donor_id_str:
        try:
            donor_id = int(donor_id_str)
            # Log message translated
            logging.info(f"[books_bp] Searching name for Donor ID: {donor_id}")
            donor_data = client.env['res.partner'].read(donor_id, ['name'])
            if donor_data and isinstance(donor_data, list):
                donor_name = donor_data[0].get('name')
                if donor_name:
                    # String translated
                    donor_info_text = f"Donor: {donor_name} (ID: {donor_id})"
                    # Log message translated
                    logging.info(f"[books_bp] Donor found: {donor_name}")
                else:
                    # Log message translated
                    logging.warning(f"[books_bp] Donor ID {donor_id} read but no name found.")
            else:
                 # Log message translated
                 logging.warning(f"[books_bp] Donor ID {donor_id} not found or unexpected return: {donor_data}")
        except ValueError:
            # Log message translated
            logging.error(f"[books_bp] Donor ID '{donor_id_str}' invalid.")
            # Flash message translated (more useful)
            flash("Error: The selected donor ID is invalid.", "error") 
            return redirect(url_for('books.add_book_form'))
        except Exception as e: # General catch for donor reading
            # Log message translated
            logging.error(f"[books_bp] Error reading donor {donor_id_str}: {e}", exc_info=True)
            # Flash message translated
            flash(f"Internal error searching for donor information: {e}", "error")
            return redirect(url_for('books.add_book_form'))

    # --- Create book in Odoo ---
    new_book_id = None
    # Flag to know if the book was created
    product_creation_successful = False 

    # MAIN TRY BLOCK FOR BOOK CREATION, TAG, AND STOCK
    try: 
        ProductModel = client.env['product.product']

        # Search for duplicates (no changes)
        search_criteria = []
        if isbn:
             search_criteria.append(('default_code', '=', isbn))
        elif title:
             search_criteria.append(('name', '=', title))
        existing_books_ids = ProductModel.search(search_criteria) if search_criteria else []

        if existing_books_ids:
             # Log message translated
             logging.warning(f"[books_bp] Book might already exist: {title}/{isbn}. IDs: {existing_books_ids}")
             # Flash message translated (clearer)
             flash(f'The book "{title}" (or its ISBN) already exists in Odoo. Duplicate not created.', 'warning')
             # Important to exit here to not continue to the tag/stock block
             return redirect(url_for('books.add_book_form'))

        # Prepare book data (no changes)
        # Log message translated
        logging.info("[books_bp] Book not found, creating...")
        description_parts = []
        # String translated
        if author: description_parts.append(f"Author: {author}")
        if donor_info_text: description_parts.append(donor_info_text)
        full_description = ". ".join(description_parts) if description_parts else False

        product_data = {
            'name': title,
            'default_code': isbn if isbn else False,
            'description_sale': full_description,
            'standard_price': 0.0,
            'list_price': 1.0,
            'type': 'product',
            'categ_id': 1,
            'uom_id': 1,
            'uom_po_id': 1,
            'sale_ok': False,
            'purchase_ok': False,
        }

        # --- Attempt to Create the product ---
        new_book_id = ProductModel.create(product_data)
        # Log message translated
        logging.info(f"[books_bp] Book created with ID (product.product): {new_book_id}!")
        # Mark creation success
        product_creation_successful = True 

        # === IF creation was successful, NOW try to add Tag and Stock ===
        tag_added_successfully = False
        stock_added_successfully = False

        # Only proceed if new_book_id is valid
        if product_creation_successful: 
            # --- Block to add PENDING TAG ---
            try:
                product_info_tmpl = ProductModel.read(new_book_id, ['product_tmpl_id'])
                if product_info_tmpl and product_info_tmpl[0].get('product_tmpl_id'):
                    template_id = product_info_tmpl[0]['product_tmpl_id'][0]
                    # Log message translated
                    logging.info(f"[books_bp] Product ID={new_book_id} has Template ID={template_id}")
                    update_data_template = {'product_tag_ids': [(4, TAG_ID_PENDIENTE)]}
                    client.env['product.template'].write([template_id], update_data_template)
                    # Log message translated
                    logging.info(f"[books_bp] Pending Tag (ID={TAG_ID_PENDIENTE}) added to Template ID={template_id}.")
                    # Mark tag success
                    tag_added_successfully = True 
                else:
                    # Log message translated
                    logging.warning(f"[books_bp] Template ID not found for Prod ID={new_book_id}. Pending tag not added.")
                    # Not a fatal error, we could continue

            except Exception as e_tag:
                # Log message translated
                logging.error(f"[books_bp] Error adding TAG for book ID {new_book_id}: {e_tag}", exc_info=True)
                # Show warning, but don't necessarily stop the attempt to add stock
                # Flash message translated
                flash(f'Book "{title}" (ID: {new_book_id}) created, but failed to add the Pending tag.', 'warning')
                # Mark tag failure
                tag_added_successfully = False 


            # --- Block to add INITIAL STOCK (INDEPENDENT OF TAG) ---
            # Always try to add stock if the book was created, even if the tag failed
            try:
                # Log message translated
                logging.info(f"[books_bp] Attempting to call add_initial_stock_via_receipt for ID {new_book_id}...")
                # CORRECT FUNCTION CALL
                stock_added_successfully = add_initial_stock_via_receipt(client, new_book_id, INITIAL_STOCK_QTY, TARGET_STOCK_LOCATION_ID) 
                
                if stock_added_successfully:
                    # Log message translated
                    logging.info(f"[books_bp] add_initial_stock_via_receipt for ID {new_book_id} RETURNED True.")
                    # Total success flash message will be set at the end if both tag (or non-critical) and stock worked
                else:
                    # If it returns False WITHOUT exception
                    # Log message translated
                    logging.error(f"[books_bp] add_initial_stock_via_receipt for ID {new_book_id} RETURNED False. STOCK NOT ADDED!")
                    # Flash message translated (set warning here if it returns False)
                    flash(f'Book "{title}" (ID: {new_book_id}) created, but THERE WAS A PROBLEM registering the initial stock. Check logs and Odoo.', 'warning')

            except Exception as e_stock:
                # If add_initial_stock_via_receipt raises an EXCEPTION
                # Log message translated
                logging.error(f"[books_bp] EXCEPTION calling add_initial_stock_via_receipt for book ID {new_book_id}: {e_stock}", exc_info=True)
                # Flash message translated
                flash(f'Book "{title}" (ID: {new_book_id}) created, but an UNEXPECTED ERROR occurred registering initial stock. Check logs.', 'danger')
                 # Ensure it's False if there was an exception
                stock_added_successfully = False

            # --- Combined Final Flash Message ---
            if stock_added_successfully:
                # Only if stock was successfully added
                # Flash message translated
                 flash(f'Book "{title}" (ID: {new_book_id}) added, marked Pending, and initial stock ({int(INITIAL_STOCK_QTY)} unit(s)) registered.', 'success')
            # else: The error/warning messages were already set earlier if stock_added is False

    # === HANDLING ERRORS FROM THE MAIN TRY BLOCK ===
    # Handle error if book CREATION failed
    except odoorpc.error.RPCError as e_create:
        # Log message translated
        logging.error(f"[books_bp] RPC Error attempting to create book: {e_create}", exc_info=True)
        # Flash message translated
        flash(f'Odoo RPC Error creating book: {e_create}', 'error')
    # Handle any other unexpected GENERAL error (during creation, tag, or stock if something weird happens)
    except Exception as e_general:
        # Translated error context logic
        error_context_en = "creation/tag/stock"
        if not product_creation_successful:
             error_context_en = "book creation"
        elif not tag_added_successfully and not stock_added_successfully:
            error_context_en = "adding tag and stock"
        elif not tag_added_successfully:
            error_context_en = "adding tag"
        elif not stock_added_successfully:
            error_context_en = "adding stock"
            
        # Log message translated
        logging.error(f"[books_bp] Unexpected error during {error_context_en}: {e_general}", exc_info=True)
        # Flash message translated
        flash(f'Unexpected server error during {error_context_en}: {e_general}', 'error')

    # ALWAYS redirect to the form
    return redirect(url_for('books.add_book_form'))


# --- Route to list books (list_books) ---
@books_bp.route('/list_books')
def list_books():
    books = []
    error_message = None
    client = get_odoo_client()
    if not client:
        # Flash message translated
        flash('Odoo connection error. Cannot list books.', 'error')
        # Error message translated
        error_message = "Odoo connection error."
        # Now, even if connection fails, books exists (as empty list)
        # So the final return will work.

    
    try:
        if client: # Only try if client exists
            product_ids = client.env['product.product'].search([], limit=80)
            if product_ids:
                # books gets overwritten here if products are found
                books = client.env['product.product'].read(product_ids, ['name', 'default_code', 'description_sale', 'id'])
            else:
                # If no products, books remains [] (defined at the start)
                # Flash message translated
                flash('No registered books found in Odoo.', 'info')
    except odoorpc.error.RPCError as e:
        # Log message translated
        logging.error(f"[books_bp] RPC Error listing books: {e}", exc_info=True)
        # Error message translated
        error_message = f"RPC Error communicating with Odoo: {e}"
        flash(error_message, 'error')
        # books remains [] if error occurs here
    except Exception as e:
        # Log message translated
        logging.error(f"[books_bp] Unexpected error listing books: {e}", exc_info=True)
        # Error message translated
        error_message = f"Unexpected server error: {e}"
        flash(error_message, 'error')
        # books remains [] if error occurs here

    # This return now always has 'books' defined (as empty list or with data)
    return render_template('list_books.html', books=books, error_message=error_message)

# --- Route to VIEW PENDING REVIEW BOOKS ---
# (UPDATED to search by TAG_ID_PENDIENTE = 4)
@books_bp.route('/review_books')
def review_books():
    pending_books = []
    error_message = None

    # Use the constant defined above (TAG_ID_PENDIENTE = 4)
    # Variable name translated
    tag_id_to_search = TAG_ID_PENDIENTE 

    client = get_odoo_client()
    if not client:
        # Flash message translated
        flash('Odoo connection error. Cannot list pending books.', 'error')
        # Error message translated
        error_message = "Odoo connection error."
    else:
        try:
            # Log message translated
            logging.info(f"[books_bp GET /review] Searching for books with tag ID={tag_id_to_search}...")

            # Search domain: find products (variants) that HAVE tag ID 4
            # We try searching directly on product.product using its Many2many field 'product_tag_ids'
            # This field DOES exist on product.product and inherits/reflects tags from the template
            search_domain = [('product_tag_ids', '=', tag_id_to_search)]

            product_ids = client.env['product.product'].search(search_domain, limit=100)
            # Log message translated
            logging.info(f"[books_bp GET /review] Pending product (variant) IDs found: {product_ids}")

            if product_ids:
                pending_books = client.env['product.product'].read(product_ids, ['id', 'name', 'default_code', 'description'])
                # Log message translated
                logging.info(f"[books_bp GET /review] Pending book data read: {pending_books}")
            else:
                # Log message translated
                logging.info(f"[books_bp GET /review] No pending review books found with ID={tag_id_to_search}.")
                # Flash message is now more dynamic (if no books and no connection error)
                if not error_message:
                    # Flash message translated
                    flash('There are currently no books pending review.', 'info')

        except odoorpc.error.RPCError as e:
            # Log message translated
            logging.error(f"[books_bp GET /review] RPC Error: {e}", exc_info=True)
            error_message = f"Odoo RPC Error: {e}"
            flash(error_message, 'error')
        except Exception as e:
            # Log message translated
            logging.error(f"[books_bp GET /review] Unexpected error: {e}", exc_info=True)
            # Error message translated
            error_message = f"Unexpected error: {e}"
            flash(error_message, 'error')

    # Render the template
    return render_template('review_books.html', books=pending_books, error_message=error_message)

# --- NEW ROUTE TO APPROVE A BOOK (POST) ---
@books_bp.route('/approve_book/<int:book_id>', methods=['POST'])
def approve_book(book_id):
    # Log message translated
    logging.info(f"[books_bp POST /approve] Request to APPROVE product.product ID: {book_id}")

    # Validate configured IDs
    # Only check Approved
    if TAG_ID_APROBADO <= 0: 
         # Flash message translated
         flash('Config Error: Approved tag ID not configured.', 'error')
         # Log message translated
         logging.error("[books_bp approve] Error: TAG_ID_APROBADO ID not configured.")
         return redirect(url_for('books.review_books'))

    client = get_odoo_client()
    if not client:
        # Flash message translated
        flash('Odoo connection error.', 'error')
        return redirect(url_for('books.review_books'))

    # Initialize for logs
    template_id = None 
    try:
        # 1. Get Template ID and name from Product ID
        product_info = client.env['product.product'].read(book_id, ['product_tmpl_id', 'name'])
        if not product_info or not product_info[0]['product_tmpl_id']:
            # Flash message translated
            flash(f'Error: Template not found for product ID={book_id}.', 'error')
            # Log message translated
            logging.error(f"[books_bp approve] Template not found for product.product ID={book_id}.")
            return redirect(url_for('books.review_books'))
        template_id = product_info[0]['product_tmpl_id'][0]
        book_name = product_info[0].get('name', f'ID {book_id}')
        # Log message translated
        logging.info(f"[books_bp approve] Product ID={book_id} (Name:'{book_name}') has Template ID={template_id}.")

        # 2. Prepare data to UPDATE tags on the TEMPLATE:
        #    - Remove Pending (ID 4) -> (3, id)
        #    - Add Approved (ID 5)   -> (4, id)
        update_data = {
            'product_tag_ids': [
                 # Unlink ID 4
                (3, TAG_ID_PENDIENTE), 
                # Link ID 5
                (4, TAG_ID_APROBADO)    
            ]
        }
        # Log message translated
        logging.info(f"[books_bp approve] Attempting write on template ID={template_id} with data: {update_data}")

        # 3. Execute write on product.template
        write_ok = client.env['product.template'].write([template_id], update_data)

        # Odoo 16 write returns True on success
        if write_ok:
            # Log message translated
            logging.info(f"[books_bp approve] Book '{book_name}' (Template ID: {template_id}) approved successfully!")
            # Flash message translated
            flash(f'Book "{book_name}" approved.', 'success')
        else:
            # This would be rare without an exception, but just in case
            # Log message translated
            logging.warning(f"[books_bp approve] Odoo write on template ID={template_id} returned False/None.")
            # Flash message translated
            flash(f'Attempted to approve Book "{book_name}", but Odoo did not confirm the change.', 'warning')

    except odoorpc.error.RPCError as e:
        # Log message translated
        logging.error(f"[books_bp approve] RPC Error: {e}", exc_info=True)
        # Flash message translated
        flash(f'RPC Error while approving: {e}', 'error')
    except Exception as e:
        # Log message translated
        logging.error(f"[books_bp approve] Unexpected error: {e}", exc_info=True)
        # Flash message translated
        flash(f'Unexpected error while approving: {e}', 'error')

    return redirect(url_for('books.review_books'))

# --- NEW ROUTE TO REJECT A BOOK (POST) ---
@books_bp.route('/reject_book/<int:book_id>', methods=['POST'])
def reject_book(book_id):
    # Log message translated
    logging.info(f"[books_bp POST /reject] Request to REJECT product.product ID: {book_id}")

    # Only check Rejected
    if TAG_ID_RECHAZADO <= 0: 
         # Flash message translated
         flash('Config Error: Rejected tag ID not configured.', 'error')
         # Log message translated
         logging.error("[books_bp reject] Error: TAG_ID_RECHAZADO ID not configured.")
         return redirect(url_for('books.review_books'))

    client = get_odoo_client()
    if not client:
        # Flash message translated
        flash('Odoo connection error.', 'error')
        return redirect(url_for('books.review_books'))

    # Initialize
    template_id = None 
    try:
        # 1. Get Template ID and name from Product ID
        product_info = client.env['product.product'].read(book_id, ['product_tmpl_id', 'name'])
        if not product_info or not product_info[0]['product_tmpl_id']:
            # Flash message translated
            flash(f'Error: Template not found for product ID={book_id}.', 'error')
            # Log message translated
            logging.error(f"[books_bp reject] Template not found for product.product ID={book_id}.")
            return redirect(url_for('books.review_books'))
        template_id = product_info[0]['product_tmpl_id'][0]
        book_name = product_info[0].get('name', f'ID {book_id}')
        # Log message translated
        logging.info(f"[books_bp reject] Product ID={book_id} (Name:'{book_name}') has Template ID={template_id}.")

        # 2. Prepare data to UPDATE tags on the TEMPLATE:
        #    - Remove Pending (ID 4) -> (3, id)
        #    - Add Rejected (ID 6)  -> (4, id)
        update_data = {
            'product_tag_ids': [
                # Unlink ID 4
                (3, TAG_ID_PENDIENTE), 
                # Link ID 6
                (4, TAG_ID_RECHAZADO)   
            ]
        }
        # Log message translated
        logging.info(f"[books_bp reject] Attempting write on template ID={template_id} with data: {update_data}")

        # 3. Execute write on product.template
        write_ok = client.env['product.template'].write([template_id], update_data)

        if write_ok:
            # Log message translated
            logging.info(f"[books_bp reject] Book '{book_name}' (Template ID: {template_id}) rejected successfully!")
            # Flash message translated
            flash(f'Book "{book_name}" rejected.', 'success')
        else:
            # Log message translated
            logging.warning(f"[books_bp reject] Odoo write on template ID={template_id} returned False/None.")
            # Flash message translated
            flash(f'Attempted to reject Book "{book_name}", but Odoo did not confirm the change.', 'warning')

    except odoorpc.error.RPCError as e:
        # Log message translated
        logging.error(f"[books_bp reject] RPC Error: {e}", exc_info=True)
        # Flash message translated
        flash(f'RPC Error while rejecting: {e}', 'error')
    except Exception as e:
        # Log message translated
        logging.error(f"[books_bp reject] Unexpected error: {e}", exc_info=True)
        # Flash message translated
        flash(f'Unexpected error while rejecting: {e}', 'error')

    return redirect(url_for('books.review_books'))


# --- NEW ROUTE TO VIEW APPROVED BOOKS ---
@books_bp.route('/approved_books')
def approved_books():
    # This view will now show books that are approved BUT NOT YET in the logistics flow.

    # Using a more descriptive variable name
    eligible_for_shipping_list = [] 
    error_message = None

    # APPROVED tag ID (already defined as constant)
    # Variable name translated
    approved_tag_id = TAG_ID_APROBADO # Is 5
    # List of logistics IDs to exclude (already defined as constant)
    # Variable name translated
    logistics_tags_to_exclude = LIST_ALL_LOGISTICS_TAGS

    client = get_odoo_client()
    if not client:
        # Flash message translated
        flash('Odoo connection error. Cannot list approved books.', 'error')
        # Error message translated
        error_message = "Odoo connection error."
    else:
        try:
            # Update log to reflect new logic
            # Log message translated
            logging.info(f"[books_bp GET /approved] Searching for APPROVED books (ID={approved_tag_id}) that DO NOT HAVE logistics tags {logistics_tags_to_exclude}...")

            # === START OF KEY MODIFICATION ===
            # Build the compound search domain:
            # 1. MUST have the 'Approved' tag (ID 5)
            # 2. MUST NOT have ANY of the logistics tags (IDs 7, 10, 11, 9, 8)
            search_domain = [
                ('product_tag_ids', '=', approved_tag_id),
                ('product_tag_ids', 'not in', logistics_tags_to_exclude)
            ]
            # Log message translated
            logging.debug(f"[books_bp GET /approved] Final search domain: {search_domain}")

            # Execute search with the new domain
             # Sort by name
            product_ids = client.env['product.product'].search(search_domain, limit=100, order="name asc")
            # === END OF KEY MODIFICATION ===

            # Log message translated
            logging.info(f"[books_bp GET /approved] Product IDs (approved, not in logistics) found: {product_ids}")

            if product_ids:
                # Read necessary fields. You can add 'author', 'isbn' if you want to show them here
                eligible_for_shipping_list = client.env['product.product'].read(product_ids, ['id', 'name', 'default_code', 'description'])
                # Log message translated
                logging.info(f"[books_bp GET /approved] Data for books ready for shipment preparation read.")
            else:
                # Log message translated
                logging.info(f"[books_bp GET /approved] No approved books found that are not already in logistics.")
                 # Only show if there's no other error
                if not error_message:
                    # Flash message translated
                    flash('No approved books are pending to start the shipping process.', 'info')

        except odoorpc.error.RPCError as e:
            # Log message translated
            logging.error(f"[books_bp GET /approved] RPC Error: {e}", exc_info=True)
            # Error message translated
            error_message = f"Odoo RPC Error searching approved/pending shipment: {e}"
            flash(error_message, 'error')
        except Exception as e:
            # Log message translated
            logging.error(f"[books_bp GET /approved] Unexpected error: {e}", exc_info=True)
            # Error message translated
            error_message = f"Unexpected error searching approved/pending shipment: {e}"
            flash(error_message, 'error')

    # Render the template, passing the list named 'books' as expected by the template
    # (Template expects 'books')
    return render_template('approved_books.html',
                           books=eligible_for_shipping_list, 
                           error_message=error_message)


# --- NEW ROUTE TO VIEW REJECTED BOOKS ---
@books_bp.route('/rejected_books')
def rejected_books():
    # Different variable name
    rejected_books_list = [] 
    error_message = None

    # We will use the ID of the REJECTED tag
    # Variable name translated
    tag_id_to_search = TAG_ID_RECHAZADO 

    client = get_odoo_client()
    if not client:
        # Flash message translated
        flash('Odoo connection error. Cannot list rejected books.', 'error')
        # Error message translated
        error_message = "Odoo connection error."
    else:
        try:
            # Log message translated
            logging.info(f"[books_bp GET /rejected] Searching for books with Rejected tag ID={tag_id_to_search}...")

            # Search domain now searches for TAG_ID_RECHAZADO
            search_domain = [('product_tag_ids', '=', tag_id_to_search)]

            product_ids = client.env['product.product'].search(search_domain, limit=100)
            # Log message translated
            logging.info(f"[books_bp GET /rejected] Rejected product IDs found: {product_ids}")

            if product_ids:
                rejected_books_list = client.env['product.product'].read(product_ids, ['id', 'name', 'default_code', 'description'])
                # Log message translated
                logging.info(f"[books_bp GET /rejected] Rejected book data read.")
            else:
                # Log message translated
                logging.info(f"[books_bp GET /rejected] No rejected books found with ID={tag_id_to_search}.")
                if not error_message:
                    # Flash message translated
                    flash('There are currently no books marked as rejected.', 'info')

        except odoorpc.error.RPCError as e:
            # Log message translated
            logging.error(f"[books_bp GET /rejected] RPC Error: {e}", exc_info=True)
            # Error message translated
            error_message = f"Odoo RPC Error searching rejected: {e}"
            flash(error_message, 'error')
        except Exception as e:
            # Log message translated
            logging.error(f"[books_bp GET /rejected] Unexpected error: {e}", exc_info=True)
            # Error message translated
            error_message = f"Unexpected error searching rejected: {e}"
            flash(error_message, 'error')

    # Render another NEW template
    # Pass the correct list
    return render_template('rejected_books.html',
                           books=rejected_books_list, 
                           error_message=error_message)


# --- NEW LOGISTICS ROUTE: Mark as Ready for Shipment (POST) ---
@books_bp.route('/mark_ready_for_shipment/<int:book_id>', methods=['POST'])
def mark_ready_for_shipment(book_id):
    """
    Handles the action of marking an approved book as 'Ready for Shipment'.
    Removes the 'Approved' tag (ID 5) and adds 'Logistics: Ready for Shipment' (ID 7).
    """
    # Log message translated
    logging.info(f"[books_bp POST /mark_ready] Request to MARK READY FOR SHIPMENT for product.product ID: {book_id}")

    # Validate required configuration IDs (Approved and Ready for Shipment)
    if TAG_ID_APROBADO <= 0 or TAG_ID_LOGISTICS_READY <= 0:
         # Flash message translated
         flash('Configuration Error: Invalid Approved/ReadyForShipment tag IDs.', 'error')
         # Log message translated
         logging.error(f"[books_bp mark_ready] Error: Invalid IDs TAG_ID_APROBADO ({TAG_ID_APROBADO}) or TAG_ID_LOGISTICS_READY ({TAG_ID_LOGISTICS_READY}).")
         # Redirect to the approved view where the button was
         return redirect(url_for('books.approved_books'))

    client = get_odoo_client()
    if not client:
        # Flash message translated
        flash('Odoo connection error. Could not update logistics status.', 'error')
        return redirect(url_for('books.approved_books'))

    # For logging in case of error
    template_id = None 
    try:
        # 1. Get Template ID and name from Product ID (as in approve/reject)
        product_info = client.env['product.product'].read(book_id, ['product_tmpl_id', 'name'])
        if not product_info or not product_info[0]['product_tmpl_id']:
            # Flash message translated
            flash(f'Error: Template not found for product ID={book_id}.', 'error')
            # Log message translated
            logging.error(f"[books_bp mark_ready] Template not found for product.product ID={book_id}.")
            return redirect(url_for('books.approved_books'))
        template_id = product_info[0]['product_tmpl_id'][0]
        book_name = product_info[0].get('name', f'ID {book_id}')
        # Log message translated
        logging.info(f"[books_bp mark_ready] Product ID={book_id} ('{book_name}') has Template ID={template_id}.")

        # 2. Prepare data to UPDATE tags on the TEMPLATE:
        #    - Remove 'Approved' (ID 5)       -> (3, TAG_ID_APROBADO)
        #    - Add 'Ready for Shipment' (ID 7) -> (4, TAG_ID_LOGISTICS_READY)
        update_data = {
            'product_tag_ids': [
                # Unlink ID 5
                (3, TAG_ID_APROBADO),
                # Link ID 7           
                (4, TAG_ID_LOGISTICS_READY)    
            ]
        }
        # Log message translated
        logging.info(f"[books_bp mark_ready] Attempting write on template ID={template_id} with data: {update_data}")

        # 3. Execute write on product.template
        write_ok = client.env['product.template'].write([template_id], update_data)

        if write_ok:
            # Log message translated
            logging.info(f"[books_bp mark_ready] Book '{book_name}' (Template ID: {template_id}) marked as Ready for Shipment successfully!")
            # Flash message translated
            flash(f'Book "{book_name}" marked as Ready for Shipment.', 'success')
        else:
            # Log message translated
            logging.warning(f"[books_bp mark_ready] Odoo write on template ID={template_id} returned False/None.")
            # Flash message translated
            flash(f'Attempted to mark Book "{book_name}" as Ready, but Odoo did not confirm.', 'warning')

    except odoorpc.error.RPCError as e:
        # Log message translated
        logging.error(f"[books_bp mark_ready] RPC Error marking ready: (Tmpl ID: {template_id}) {e}", exc_info=True)
        # Flash message translated
        flash(f'RPC Error updating status: {e}', 'error')
    except Exception as e:
        # Log message translated
        logging.error(f"[books_bp mark_ready] Unexpected error marking ready: (Tmpl ID: {template_id}) {e}", exc_info=True)
        # Flash message translated
        flash(f'Unexpected error updating status: {e}', 'error')

    # Always redirect back to the approved list
    # The book will NO LONGER appear there if the operation was successful (due to the filter we added)
    return redirect(url_for('books.approved_books'))


# --- NEW ROUTE: Logistics Pipeline View ---
@books_bp.route('/shipping_management') # Keep the route
def shipping_management(): # Keep the function name
    """
    Displays a list of Transfers (stock.picking) created
    for branch shipments (Operation Type ID 7).
    """
    # List to store the read transfers
    shipments_list = [] 
    error_message = None

    # ID of the Operation Type we want to list
    # Variable name translated
    SHIPMENT_OPERATION_TYPE_ID = 7 # 'Branch Shipments'
    # Log message translated
    logging.info(f"[books_bp GET /shipping_management] Searching for transfers (stock.picking) of type ID={SHIPMENT_OPERATION_TYPE_ID}")

    client = get_odoo_client()
    if not client:
        # Flash message translated
        flash('Odoo connection error. Cannot display shipment list.', 'error')
        # Error message translated
        error_message = "Odoo connection error."
    else:
        try:
            PickingModel = client.env['stock.picking']

            # Search domain: ONLY transfers of our type
            search_domain = [('picking_type_id', '=', SHIPMENT_OPERATION_TYPE_ID)]

            # Fields we want to read from each transfer
            # 'name' is the reference (e.g., BS/00001)
            # 'state' is the status (draft, waiting, confirmed, assigned, done, cancel)
            # 'origin' is the text we set when creating it
            # 'location_id' and 'location_dest_id' will give us origin/destination (come as [id, 'Name'])
            # 'scheduled_date' is the planned date (Odoo sets it automatically)
            fields_to_read = [
                'id', 'name', 'state', 'origin',
                'location_id', 'location_dest_id', 'scheduled_date'
            ]
            # Sort by ID descending to see the newest first
            order = 'id desc'

            logging.debug(f"Domain: {search_domain}, Fields: {fields_to_read}")
            shipments_list = PickingModel.search_read(
                search_domain,
                fields=fields_to_read,
                order=order,
                # Limit in case there are many
                limit=50 
            )
            # Log message translated
            logging.info(f"{len(shipments_list)} shipment transfers found.")

            if not shipments_list and not error_message:
                # Flash message translated
                flash('No batch shipments registered yet.', 'info')

        except odoorpc.error.RPCError as e:
            # Log message translated
            logging.error(f"[books_bp GET /shipping_management] RPC Error: {e}", exc_info=True)
            # Error message translated
            error_message = f"Odoo RPC Error searching shipments: {e}"
            flash(error_message, 'error')
        except Exception as e:
            # Log message translated
            logging.error(f"[books_bp GET /shipping_management] Unexpected error: {e}", exc_info=True)
            # Error message translated
            error_message = f"Unexpected error searching shipments: {e}"
            flash(error_message, 'error')

    # Render the template, now passing the list of *transfers*
    # Renamed variable passed to template for clarity
    return render_template('shipping_management.html',
                           shipments=shipments_list, 
                           # We no longer pass TAG_IDs because logic will be based on 'state'
                           error_message=error_message)


# --- NEW LOGISTICS ROUTE: Mark as In Transit (POST) ---
# NOTE: This route currently only changes product tags, it doesn't interact with stock.picking state.
# You might want to update this later to ALSO update the stock.picking if applicable.
@books_bp.route('/mark_in_transit/<int:destination_tag_id>/<int:book_id>', methods=['POST'])
def mark_in_transit(destination_tag_id, book_id):
    """
    Handles the action of marking a book as 'In Transit' to a specific destination.
    Removes the 'Ready for Shipment' tag (ID 7) and adds the destination tag (ID 10 or 11).
    """
    # Log message translated
    logging.info(f"[books_bp POST /mark_in_transit] Request to MARK IN TRANSIT (Dest ID: {destination_tag_id}) for product.product ID: {book_id}")

    # Validate necessary IDs: Ready (which we remove) and Destination (which we add)
    # Variable name translated
    valid_destination_tags = [TAG_ID_LOGISTICS_TRANSIT_EC, TAG_ID_LOGISTICS_TRANSIT_VE, 8] # Include general ID 8 in case we use it later
    if TAG_ID_LOGISTICS_READY <= 0 or destination_tag_id not in valid_destination_tags:
         # Flash message translated
         flash(f'Config Error: Invalid Ready ({TAG_ID_LOGISTICS_READY}) or Destination ({destination_tag_id}) tag ID.', 'error')
         # Log message translated
         logging.error(f"[books_bp mark_in_transit] Invalid IDs: READY={TAG_ID_LOGISTICS_READY}, DESTINATION={destination_tag_id}")
         # Redirect to shipping management
         return redirect(url_for('books.shipping_management'))

    client = get_odoo_client()
    if not client:
        # Flash message translated
        flash('Odoo connection error.', 'error')
        return redirect(url_for('books.shipping_management'))

    template_id = None
    try:
        # 1. Get Template ID and name (same as before)
        product_info = client.env['product.product'].read(book_id, ['product_tmpl_id', 'name'])
        if not product_info or not product_info[0]['product_tmpl_id']:
             # Flash message translated
            flash(f'Error: Template not found for product ID={book_id}.', 'error')
             # Log message translated
            logging.error(f"[books_bp mark_in_transit] Template not found for Prod ID={book_id}.")
            return redirect(url_for('books.shipping_management'))
        template_id = product_info[0]['product_tmpl_id'][0]
        book_name = product_info[0].get('name', f'ID {book_id}')
        # Log message translated
        logging.info(f"[books_bp mark_in_transit] Prod ID={book_id} ('{book_name}'), Tmpl ID={template_id}")

        # 2. Prepare UPDATE data:
        #    - Remove 'Ready for Shipment' (ID 7)  -> (3, TAG_ID_LOGISTICS_READY)
        #    - Add Destination Tag (ID 10 or 11) -> (4, destination_tag_id)
        update_data = {
            'product_tag_ids': [
                (3, TAG_ID_LOGISTICS_READY),
                (4, destination_tag_id)
            ]
        }
        # Log message translated
        logging.info(f"[books_bp mark_in_transit] Attempting write Tmpl ID={template_id} with data: {update_data}")

        # 3. Execute write
        write_ok = client.env['product.template'].write([template_id], update_data)

        if write_ok:
             # Log message translated
            logging.info(f"[books_bp mark_in_transit] Book '{book_name}' (Tmpl ID:{template_id}) marked IN TRANSIT (Dest ID:{destination_tag_id})!")
             # Flash message translated
            flash(f'Book "{book_name}" marked as In Transit.', 'success')
        else:
            # Log message translated
            logging.warning(f"[books_bp mark_in_transit] Write returned False/None for Tmpl ID:{template_id}.")
             # Flash message translated
            flash(f'Attempted to mark Book "{book_name}" as In Transit, but Odoo did not confirm.', 'warning')

    except odoorpc.error.RPCError as e:
        # Log message translated
        logging.error(f"[books_bp mark_in_transit] RPC Error: (Tmpl ID:{template_id}) {e}", exc_info=True)
        # Flash message translated
        flash(f'RPC Error marking In Transit: {e}', 'error')
    except Exception as e:
        # Log message translated
        logging.error(f"[books_bp mark_in_transit] Unexpected Error: (Tmpl ID:{template_id}) {e}", exc_info=True)
        # Flash message translated
        flash(f'Unexpected error marking In Transit: {e}', 'error')

    # Always redirect back to SHIPPING MANAGEMENT
    # The book will still appear, but with updated status and different buttons (depending on template logic)
    return redirect(url_for('books.shipping_management'))


# --- NEW LOGISTICS ROUTE: Mark as Delivered (POST) ---
# NOTE: Similar to mark_in_transit, this primarily manages tags.
@books_bp.route('/mark_delivered/<int:book_id>', methods=['POST'])
def mark_delivered(book_id):
    """
    Handles the action of marking a book as 'Delivered'.
    Removes ANY 'In Transit' tag and adds 'Logistics: Delivered' (ID 9).
    """
    # Log message translated
    logging.info(f"[books_bp POST /mark_delivered] Request to MARK DELIVERED for product.product ID: {book_id}")

    # IDs to validate: Delivered ID (which we add) and list of transit IDs (which we remove)
    # Variable name fine
    transit_tags_to_remove = [TAG_ID_LOGISTICS_TRANSIT_EC, TAG_ID_LOGISTICS_TRANSIT_VE, 8] # IDs 10, 11, 8
    if TAG_ID_LOGISTICS_DELIVERED <= 0:
        # Flash message translated
         flash(f'Config Error: Invalid Delivered Tag ID ({TAG_ID_LOGISTICS_DELIVERED}).', 'error')
         # Log message translated
         logging.error(f"[books_bp mark_delivered] Invalid ID: DELIVERED={TAG_ID_LOGISTICS_DELIVERED}")
         return redirect(url_for('books.shipping_management'))

    client = get_odoo_client()
    if not client:
        # Flash message translated
        flash('Odoo connection error.', 'error')
        return redirect(url_for('books.shipping_management'))

    template_id = None
    try:
        # 1. Get Template ID and name (same as before)
        product_info = client.env['product.product'].read(book_id, ['product_tmpl_id', 'name'])
        if not product_info or not product_info[0]['product_tmpl_id']:
             # Flash message translated
            flash(f'Error: Template not found for product ID={book_id}.', 'error')
             # Log message translated
            logging.error(f"[books_bp mark_delivered] Template not found for Prod ID={book_id}.")
            return redirect(url_for('books.shipping_management'))
        template_id = product_info[0]['product_tmpl_id'][0]
        book_name = product_info[0].get('name', f'ID {book_id}')
        # Log message translated
        logging.info(f"[books_bp mark_delivered] Prod ID={book_id} ('{book_name}'), Tmpl ID={template_id}")

        # 2. Prepare UPDATE data:
        #    - Remove ALL 'In Transit' tags (IDs 8, 10, 11) -> (3, id) for each one
        #    - Add 'Delivered' (ID 9)             -> (4, TAG_ID_LOGISTICS_DELIVERED)
        # Dynamically build the list of unlink operations
        tags_operations = []
        for tag_id_to_remove in transit_tags_to_remove:
            # Command to unlink
             tags_operations.append((3, tag_id_to_remove)) 

        # Add the operation to link 'Delivered'
        tags_operations.append((4, TAG_ID_LOGISTICS_DELIVERED))

        update_data = {'product_tag_ids': tags_operations}
        # Log message translated
        logging.info(f"[books_bp mark_delivered] Attempting write Tmpl ID={template_id} with data: {update_data}")

        # 3. Execute write
        write_ok = client.env['product.template'].write([template_id], update_data)

        if write_ok:
            # Log message translated
            logging.info(f"[books_bp mark_delivered] Book '{book_name}' (Tmpl ID:{template_id}) marked DELIVERED!")
            # Flash message translated
            flash(f'Book "{book_name}" marked as Delivered.', 'success')
        else:
            # Log message translated
            logging.warning(f"[books_bp mark_delivered] Write returned False/None for Tmpl ID:{template_id}.")
            # Flash message translated
            flash(f'Attempted to mark Book "{book_name}" as Delivered, but Odoo did not confirm.', 'warning')

    except odoorpc.error.RPCError as e:
         # Log message translated
        logging.error(f"[books_bp mark_delivered] RPC Error: (Tmpl ID:{template_id}) {e}", exc_info=True)
         # Flash message translated
        flash(f'RPC Error marking Delivered: {e}', 'error')
    except Exception as e:
         # Log message translated
        logging.error(f"[books_bp mark_delivered] Unexpected Error: (Tmpl ID:{template_id}) {e}", exc_info=True)
         # Flash message translated
        flash(f'Unexpected error marking Delivered: {e}', 'error')

    # Always redirect back to SHIPPING MANAGEMENT
    # The book will NO LONGER appear here if successful, because the view filters by tags IN the pipeline (assumption)
    return redirect(url_for('books.shipping_management'))


# --- NEW ROUTE: Create Batch Shipment (stock.picking) ---
@books_bp.route('/create_batch_shipment', methods=['POST'])
def create_batch_shipment():
    """
    Processes the creation of a batch transfer (stock.picking) in Odoo.
    Receives the IDs of selected books and the destination location ID.
    """
    # Log message translated
    logging.info("[books_bp POST /create_batch_shipment] Received request to create batch shipment.")

    # 1. Get form data
    # getlist gets all values from checkboxes with the same 'name'
    selected_book_ids_str = request.form.getlist('selected_book_ids')
    destination_location_id_str = request.form.get('destination_location_id')

    # Log messages translated
    logging.debug(f"Selected book IDs (str): {selected_book_ids_str}")
    logging.debug(f"Destination location ID (str): {destination_location_id_str}")

    # 2. Basic validations
    if not selected_book_ids_str:
         # Flash message translated
        flash('Error: No books selected for shipment.', 'error')
         # Go back to the selection page
        return redirect(url_for('books.approved_books')) 

    if not destination_location_id_str:
         # Flash message translated
        flash('Error: No destination location selected.', 'error')
        return redirect(url_for('books.approved_books'))

    # Convert IDs to integers
    try:
        # Convert list of strings to list of integers
        selected_book_ids = [int(id_str) for id_str in selected_book_ids_str]
        destination_location_id = int(destination_location_id_str)
        # Log messages translated
        logging.info(f"Books to ship (IDs): {selected_book_ids}")
        logging.info(f"Destination location ID: {destination_location_id}")
    except ValueError:
        # Flash message translated
        flash('Error: Invalid book or destination IDs.', 'error')
        # Log message translated
        logging.error(f"Error converting IDs: books={selected_book_ids_str}, dest={destination_location_id_str}")
        return redirect(url_for('books.approved_books'))

    # --- Odoo Configuration IDs (need to be defined as constants above or passed) ---
   
    SOURCE_LOCATION_ID = 30          # ID of 'Stock Books Approved ONG'
    # Variable name translated
    SHIPMENT_OPERATION_TYPE_ID = 7    # ID of 'Branch Shipments' 
   

    client = get_odoo_client()
    if not client:
        # Flash message translated
        flash('Odoo connection error. Could not create shipment.', 'error')
        return redirect(url_for('books.approved_books'))

    # To store the ID of the created transfer
    new_picking_id = None 
    try:
        # 3. Prepare data to create the stock.picking
        # Log message translated
        logging.info("Preparing data to create 'stock.picking'...")

        # Odoo model for transfers
        PickingModel = client.env['stock.picking']

        # === Building move lines (move_ids_without_package) ===
        # Odoo expects a list of operations, (0, 0, {values}) to create new lines
        move_lines_data = []
        # Log message translated
        logging.info(f"Creating move lines for {len(selected_book_ids)} books...")
        # Get book names for move description (optional but useful)
        try:
             books_data = client.env['product.product'].read(selected_book_ids, ['name'])
             # Create a dictionary id -> name for easy lookup
             book_names = {book['id']: book['name'] for book in books_data}
        except Exception as read_err:
             # Log message translated
             logging.warning(f"Could not read book names: {read_err}. Generic name will be used.", exc_info=True)
             # Empty dictionary
             book_names = {} 

        for book_id in selected_book_ids:
             # Use name if found
            book_name_for_move = book_names.get(book_id, f"Book ID {book_id}") 
            line = (0, 0, {
                # Line description
                'name': book_name_for_move, 
                # Book ID to move
                'product_id': book_id,       
                # Quantity: 1 for now (assume 1 copy per book)
                'product_uom_qty': 1.0, # Use float        
                # Unit of Measure ID (usually 1 for Units)
                'product_uom': 1,            
                 # FIXED Source Location
                'location_id': SOURCE_LOCATION_ID,       
                # Destination Location from form
                'location_dest_id': destination_location_id, 
            })
            move_lines_data.append(line)
            # Log message translated
            logging.debug(f"  Added line for book_id {book_id}: {line}")
        # =============================================================================

        # Main transfer header data (stock.picking)
        picking_data = {
             # Operation Type ID "Branch Shipments"
            'picking_type_id': SHIPMENT_OPERATION_TYPE_ID,   
             # Source Location ID
            'location_id': SOURCE_LOCATION_ID,            
             # Destination Location ID
            'location_dest_id': destination_location_id, 
             # Text to know where it came from translated
            'origin': 'Batch Shipment from ONG Flask App',   
             # Lines of products to move
            'move_ids_without_package': move_lines_data,  
            # Odoo sets to draft by default when created this way
            # 'state': 'draft', 
            # Other fields might be needed depending on strict Odoo configuration
        }
        # Log message translated
        logging.info("Data prepared for creating 'stock.picking'.")
        logging.debug(f"Picking Data: {picking_data}")

        # 4. Execute creation in Odoo
        # Log message translated
        logging.info("Attempting to create 'stock.picking' in Odoo...")
        # Create expects a list
        new_picking_id_list = PickingModel.create([picking_data]) 

        if new_picking_id_list:
             # Get ID from the list
             new_picking_id = new_picking_id_list[0] 
             # Log message translated
             logging.info(f"Success! Transfer (stock.picking) created with ID: {new_picking_id} !")
             
             # READ the name/reference of the created transfer (e.g., BS/00001)
             picking_ref = ""
             try:
                picking_info = PickingModel.read(new_picking_id, ['name'])
                if picking_info: picking_ref = picking_info[0].get('name', '')
             # Not critical if we can't read the name
             except Exception: pass 
             
             # Flash message translated
             flash(f'Batch shipment created successfully in Odoo (Reference: {picking_ref or new_picking_id}).', 'success')

             # ----- IMPORTANT: REMOVE 'Approved' TAG from shipped books -----
             # Now that the shipment is created, remove 'Approved' tag (ID 5)
             # from the included books so they no longer appear in the preparation list.
             try:
                  # Log message translated
                  logging.info(f"Removing 'Approved' tag (ID {TAG_ID_APROBADO}) from shipped books: {selected_book_ids}")
                  templates_to_update = []
                  # Need template IDs associated with the products
                  product_infos = client.env['product.product'].read(selected_book_ids, ['product_tmpl_id'])
                  if product_infos:
                      templates_to_update = [p['product_tmpl_id'][0] for p in product_infos if p.get('product_tmpl_id')]
                       # Remove duplicates if multiple books were from the same template (unlikely here)
                      templates_to_update = list(set(templates_to_update)) 
                      
                      if templates_to_update:
                           # Unlink Approved
                          update_data = {'product_tag_ids': [(3, TAG_ID_APROBADO)]} 
                          write_ok = client.env['product.template'].write(templates_to_update, update_data)
                          if write_ok:
                              # Log message translated
                              logging.info(f"'Approved' tag removed from templates: {templates_to_update}")
                          else:
                              # Log message translated
                              logging.warning(f"Odoo did not confirm removal of Approved tag for templates {templates_to_update}")
                              # Flash message translated
                              flash('Warning: Could not remove the "Approved" tag from shipped books. They might reappear.', 'warning')
                      else:
                           # Log message translated
                           logging.warning("No valid template IDs found to remove tag.")
             except Exception as tag_err:
                   # Log message translated
                  logging.error(f"Error attempting to remove 'Approved' tag from shipped books: {tag_err}", exc_info=True)
                   # Flash message translated
                  flash('Warning: An error occurred while updating the status of shipped books in the preparation list.', 'warning')
             

        else:
             # Rare if no RPC error
             # Log message translated
             logging.error("Odoo 'stock.picking.create' returned no ID but there was no exception.")
             # Flash message translated
             flash('Attempted to create shipment, but Odoo did not return confirmation.', 'error')
             return redirect(url_for('books.approved_books'))


    except odoorpc.error.RPCError as e:
        # Log message translated
        logging.error(f"[books_bp POST /create_batch_shipment] Odoo RPC Error: {e}", exc_info=True)
        error_details = str(getattr(e, 'fault', e))
        # Flash message translated
        flash(f'Odoo error creating shipment ({type(e).__name__}): {error_details}', 'error')
         # Go back to correct
        return redirect(url_for('books.approved_books')) 
    except Exception as e:
        # Log message translated
        logging.error(f"[books_bp POST /create_batch_shipment] Unexpected error: {e}", exc_info=True)
        # Flash message translated
        flash(f'Unexpected server error creating shipment: {e}', 'error')
        return redirect(url_for('books.approved_books'))

    # 5. Redirect to an appropriate page after success
    # Redirect to shipping management page to see the new transfer.
    return redirect(url_for('books.shipping_management'))

# --- NEW ROUTE: Confirm Shipment Transfer (POST) ---
@books_bp.route('/confirm_shipment/<int:picking_id>', methods=['POST'])
def confirm_shipment(picking_id):
    """
    Executes the 'action_confirm' action on a transfer (stock.picking)
    to move it from 'draft' state to 'waiting' or 'confirmed'.
    """
    # Log message translated
    logging.info(f"[books_bp POST /confirm_shipment] Request to CONFIRM transfer ID: {picking_id}")
    client = get_odoo_client()
    if not client:
        # Flash message translated
        flash('Odoo connection error.', 'error')
        return redirect(url_for('books.shipping_management'))

    try:
        PickingModel = client.env['stock.picking']
        # Log message translated
        logging.info(f"Calling 'action_confirm' for picking ID {picking_id}")
        # action_confirm method usually doesn't need extra args here
        # Odoo 16 often needs list of IDs
        PickingModel.action_confirm([picking_id]) 
        # Log message translated
        logging.info(f"Transfer {picking_id} confirmed (or attempt sent)!")
        # Read name/ref for message
        picking_ref = ""
        try:
            picking_info = PickingModel.read(picking_id, ['name'])
            if picking_info: picking_ref = picking_info[0].get('name', '')
        except Exception: pass
        # Flash message translated
        flash(f'Transfer {picking_ref or picking_id} confirmed.', 'success')

    except odoorpc.error.RPCError as e:
        # Log message translated
        logging.error(f"[books_bp POST /confirm_shipment] RPC Error: {e}", exc_info=True)
        # Flash message translated
        flash(f'Odoo RPC Error confirming transfer {picking_id}: {e}', 'error')
    except Exception as e:
        # Log message translated
        logging.error(f"[books_bp POST /confirm_shipment] Unexpected error: {e}", exc_info=True)
        # Flash message translated
        flash(f'Unexpected error confirming transfer {picking_id}: {e}', 'error')

    # Always redirect back to shipping management to see the status change
    return redirect(url_for('books.shipping_management'))


# --- NEW ROUTE: Reserve Stock for Transfer (POST) ---
@books_bp.route('/reserve_shipment/<int:picking_id>', methods=['POST']) # <-- THE MISSING ROUTE! -> Comment translated
def reserve_shipment(picking_id):
    """
    Executes the 'action_assign' action on a transfer (stock.picking)
    to attempt to reserve the necessary stock.
    This should change the state to 'assigned' (ready) or 'confirmed'/'waiting' (if stock is missing).
    """
    # Log message translated
    logging.info(f"[books_bp POST /reserve_shipment] Request to RESERVE STOCK for transfer ID: {picking_id}")
    client = get_odoo_client()
    if not client:
         # Flash message translated
        flash('Odoo connection error. Could not reserve stock.', 'error')
        return redirect(url_for('books.shipping_management'))

    try:
        PickingModel = client.env['stock.picking']
         # Log message translated
        logging.info(f"Calling 'action_assign' (Reserve Stock) for picking ID {picking_id}")

        # action_assign action will attempt reservation. Odoo handles internal logic.
        # In odoorpc, browse(id).action() is common
        PickingModel.browse(picking_id).action_assign() 

        # Log message translated
        logging.info(f"Stock reservation attempt sent for picking ID {picking_id}!")

        # Read name/ref for message
        picking_ref = f"ID {picking_id}"
        try:
            picking_info = PickingModel.read(picking_id, ['name'])
            if picking_info: picking_ref = picking_info[0].get('name', picking_ref)
        except Exception: pass
        # Flash message translated (informational message)
        flash(f'Stock reservation attempt initiated for shipment {picking_ref}. Check the new status.', 'info') 

    except odoorpc.error.RPCError as e:
        # Try to get ref for error message
        picking_ref = f"ID {picking_id}" 
        try:
            p_info = client.env['stock.picking'].read(picking_id, ['name'])
            if p_info: picking_ref = p_info[0].get('name', picking_ref)
        except Exception: pass
            
        # Log message translated
        logging.error(f"[books_bp POST /reserve_shipment] Odoo RPC Error for '{picking_ref}': {e}", exc_info=True)
        # Try to get error message from Odoo
        error_details = str(getattr(e, 'fault', e)) 
        # Flash message translated
        flash(f'Odoo error attempting to reserve stock for {picking_ref}: {error_details}', 'error')
        
    except Exception as e:
        picking_ref = f"ID {picking_id}"
        try:
            p_info = client.env['stock.picking'].read(picking_id, ['name'])
            if p_info: picking_ref = p_info[0].get('name', picking_ref)
        except Exception: pass
            
        # Log message translated
        logging.error(f"[books_bp POST /reserve_shipment] Unexpected error for '{picking_ref}': {e}", exc_info=True)
        # Flash message translated
        flash(f'Unexpected error reserving stock for {picking_ref}: {e}', 'error')

    # Always redirect back to shipping management to see the status change
    return redirect(url_for('books.shipping_management'))


# --- UPDATED ROUTE: REDIRECTS to show details for validation ---
@books_bp.route('/validate_shipment/<int:picking_id>', methods=['POST']) # Keep POST for now due to the form
def validate_shipment(picking_id):
    """
    TEMPORARILY: Redirects to the transfer details page
    to enter done quantities.
    In the future, this could be the function that PROCESSES validation.
    But for now, it just redirects.
    """
    # Log message translated
    logging.info(f"[books_bp POST /validate_shipment] Redirecting to details view for picking ID: {picking_id}")
    # Simply redirect to a NEW GET route that will show the details
    # Use the same picking_id
    return redirect(url_for('books.show_picking_details', picking_id=picking_id))


# --- NEW ROUTE: Show Transfer Details (GET) ---
@books_bp.route('/picking_details/<int:picking_id>') # Accepts GET by default
def show_picking_details(picking_id):
    """
    Shows the details of a specific transfer, including the
    detailed move lines (stock.move.line) to be able to enter done quantities.
    """
     # Log message translated
    logging.info(f"[books_bp GET /picking_details] Showing details for picking ID: {picking_id}")

    picking_data = None
    # List for lines/books (now stock.move.line)
    move_lines = [] 
    error_message = None

    client = get_odoo_client()
    if not client:
         # Flash message translated
        flash('Odoo connection error. Cannot load shipment details.', 'error')
         # Error message translated
        error_message = "Odoo connection error."
        # Try rendering anyway to show the error
        # picking_data and move_lines will remain None/[]
    else:
        # If client exists, try getting data
        try:
            PickingModel = client.env['stock.picking']
            # Read picking header
            picking_fields = ['id', 'name', 'state', 'origin', 'location_id', 'location_dest_id', 'scheduled_date']
            picking_data_list = PickingModel.read(picking_id, fields=picking_fields)

            if not picking_data_list:
                # Flash message translated
                flash(f'Error: Transfer with ID {picking_id} not found.', 'error')
                return redirect(url_for('books.shipping_management'))

            picking_data = picking_data_list[0]
             # Log message translated
            logging.info(f"Header data read for picking {picking_id}: {picking_data}")

            # Read DETAILED MOVE LINES (stock.move.line)
            # Use the 'move_line_ids' field of the picking.
            picking_with_lines = PickingModel.read(picking_id, ['move_line_ids'])
            move_line_ids = []
            if picking_with_lines and picking_with_lines[0].get('move_line_ids'):
                move_line_ids = picking_with_lines[0]['move_line_ids']

             # Log message translated
            logging.info(f"Searching details of DETAILED LINES (stock.move.line) IDs: {move_line_ids}")

            if move_line_ids:
                # If detailed line IDs are found, read them
                MoveLineModel = client.env['stock.move.line']
                line_fields = ['id', 'product_id', 'qty_done', 'product_uom_id', 'move_id']
                move_lines = MoveLineModel.read(move_line_ids, fields=line_fields)
                 # Log message translated
                logging.info(f"Data of {len(move_lines)} detailed lines (stock.move.line) read.")
            else:
                 # If NO move_line_ids, it's an important warning.
                 # Log message translated
                logging.warning(f"Transfer {picking_id} has no DETAILED LINES (stock.move.line). Was stock reserved with 'action_assign'?")
                 # Flash message translated
                flash('Warning: Book details not found to enter quantities. Try "Reserve Stock" first in the shipment list.', 'warning')
                # move_lines is already initialized as [] above, no need to reassign here.

        # Except blocks (correctly indented with try)
        except odoorpc.error.RPCError as e:
             # Log message translated
            logging.error(f"[books_bp GET /picking_details] RPC Error: {e}", exc_info=True)
             # Error message translated
            error_message = f"Odoo RPC Error loading shipment details {picking_id}: {e}"
            flash(error_message, 'error')
            picking_data = None
             # Ensure empty lists if error occurs
            move_lines = [] 
        except Exception as e:
             # Log message translated
            logging.error(f"[books_bp GET /picking_details] Unexpected error: {e}", exc_info=True)
             # Error message translated
            error_message = f"Unexpected error loading shipment details {picking_id}: {e}"
            flash(error_message, 'error')
            picking_data = None
             # Ensure empty lists if error occurs
            move_lines = [] 

    # Render template (correct indentation, outside try but inside main else)
    # Pass 'picking' and 'lines' (which will be None/[] if error or no data found)
    return render_template('picking_details.html',
                            picking=picking_data,
                            lines=move_lines,
                            error_message=error_message)


# --- NEW ROUTE: Process Transfer Validation (with quantities) ---
@books_bp.route('/process_validate_shipment/<int:picking_id>', methods=['POST'])
def process_validate_shipment(picking_id):
    """
    Processes the transfer details form:
    1. Receives 'done' quantities for each move line.
    2. Updates 'done' quantities (qty_done) on Odoo's stock.move.line.
    3. Attempts to call 'button_validate' to mark the picking as 'done'.
    """
    # Log message translated
    logging.info(f"[books_bp POST /process_validate] Processing validation for picking ID: {picking_id}")

    # 1. Extract quantities from the form
    # Form sends pairs: move_id=X, qty_done_X=Y
    # Dictionary to store {move_id: qty_done}
    move_quantities = {} 
     # Get all submitted move IDs
    move_ids_from_form = request.form.getlist('move_id') 

    if not move_ids_from_form:
        # Flash message translated
         flash("Error: No move line data received from form.", "error")
         # Redirecting to details or general list could be options
         return redirect(url_for('books.shipping_management')) 

    # Log message translated
    logging.debug(f"Move IDs received from form: {move_ids_from_form}")

    try:
        for move_id_str in move_ids_from_form:
            move_id = int(move_id_str)
             # Get quantity for THIS move_id
            qty_done_str = request.form.get(f'qty_done_{move_id}') 
            if qty_done_str is not None:
                # Use float just in case, though should be integers for books
                 qty_done = float(qty_done_str) 
                 # Simple validation
                 if qty_done < 0: 
                     # Flash message translated
                     flash(f"Error: Invalid done quantity ({qty_done}) for one of the lines.", "error")
                     # Returning to details page could be confusing without passing data back
                     # Redirect to the general list.
                     return redirect(url_for('books.shipping_management'))
                 move_quantities[move_id] = qty_done
                  # Log message translated
                 logging.debug(f"  Move ID {move_id}: Done Quantity = {qty_done}")
            else:
                 # Shouldn't happen if input is in form, but just in case
                 # Log message translated
                 logging.warning(f"Quantity for move_id {move_id} not found in form.")
                  # Assume 0 if missing
                 move_quantities[move_id] = 0 

    except ValueError:
         # Flash message translated
        flash("Error: Invalid numeric format in quantities.", 'error')
        return redirect(url_for('books.shipping_management'))

    # If dictionary remained empty for some reason
    if not move_quantities: 
         # Flash message translated
         flash("Error: No valid quantities processed from form.", "error")
         return redirect(url_for('books.shipping_management'))

    # --- Odoo Connection ---
    client = get_odoo_client()
    if not client:
        # Flash message translated
        flash('Odoo connection error.', 'error')
        return redirect(url_for('books.shipping_management'))

    # For error/success messages
    picking_ref = f"ID {picking_id}" 
    try:
        PickingModel = client.env['stock.picking']
        MoveLineModel = client.env['stock.move.line']

        # Read picking name for messages
        try:
            p_info = PickingModel.read(picking_id, ['name'])
            if p_info: picking_ref = p_info[0].get('name', picking_ref)
        except Exception: pass

         # Log message translated
        logging.info(f"Validating picking '{picking_ref}'. Quantities to update: {move_quantities}")

        # 2. Find 'stock.move.line' IDs associated with our 'stock.move' IDs and this picking
        # Log message translated
        logging.info(f"Searching 'stock.move.line' for picking {picking_id} and move IDs {list(move_quantities.keys())}")
        # Search for move_line belonging to the picking and whose move_id is in our list
        search_domain_ml = [
             ('picking_id', '=', picking_id),
             ('move_id', 'in', list(move_quantities.keys()))
        ]

        # Read ONLY id and move_id to map the correct line
        move_line_ids_data = MoveLineModel.search_read(search_domain_ml, fields=['id', 'move_id'])

        if not move_line_ids_data:
             # Log message translated
             logging.error(f"No corresponding stock.move.line found for picking {picking_id}.")
             # Usually happens if transfer is not in 'assigned' or 'ready' state yet
             # or if something failed during confirm/reserve.
             # Flash message translated
             flash(f"Error: Detailed lines not found to process shipment '{picking_ref}'. Is stock reserved?", "error")
             # Redirecting to details might show the same empty page. List is better.
             return redirect(url_for('books.shipping_management')) 

         # Log message translated
        logging.info(f"{len(move_line_ids_data)} stock.move.line found.")

        # 3. Prepare 'write' commands to update qty_done on stock.move.line
        # Odoo uses format: [(1, move_line_id, {'field_to_update': new_value}), ...]
        # within a write to the parent record (stock.picking) on the One2many/Many2many field.
        # IMPORTANT!! Odoo expects these commands on the 'move_line_ids' field.

        write_commands = []
        for ml in move_line_ids_data:
            move_line_id = ml['id']
            # Get the parent stock.move ID
            parent_move_id = ml['move_id'][0] 
            # Find the quantity user entered for THAT parent stock.move
             # Use 0 if not found for some reason
            qty_to_set = move_quantities.get(parent_move_id, 0) 

            command = (1, move_line_id, {'qty_done': qty_to_set})
            write_commands.append(command)
             # Log message translated
            logging.debug(f"  Write command prepared for move_line ID {move_line_id}: {command}")

        # 4. Execute WRITE on stock.picking to update lines
        # Log message translated
        logging.info(f"Attempting write on picking ID {picking_id} with commands: {write_commands}")
        write_ok = PickingModel.write([picking_id], {'move_line_ids': write_commands})

        if not write_ok:
             # Very rare if no exception, but can happen.
             # Log message translated
             logging.error(f"Odoo write to update qty_done on picking {picking_id} did not confirm success.")
             # Flash message translated
             flash(f"Error: Odoo did not confirm quantity updates for shipment '{picking_ref}'. Validation aborted.", 'error')
             return redirect(url_for('books.shipping_management'))

        # Log message translated
        logging.info(f"'quantity_done' amounts updated in Odoo for picking {picking_id}.")

        # 5. IF write succeeded, NOW attempt validation
         # Log message translated
        logging.info(f"Attempting to call 'button_validate' for picking '{picking_ref}' (after updating qty_done)")
        validation_result = PickingModel.button_validate([picking_id])
         # Log message translated
        logging.info(f"'button_validate' executed for '{picking_ref}'. Result: {validation_result}")

        # Flash message translated
        flash(f'Shipment {picking_ref} validated and completed successfully!', 'success')


    except odoorpc.error.RPCError as e:
        # RPC error handling (same as before)
        # Log message translated
        logging.error(f"[books_bp POST /process_validate] Odoo RPC Error processing '{picking_ref}': {e}", exc_info=True)
        error_message_from_odoo = str(e.args[0]) if e.args and isinstance(e.args[0], str) else str(e)
        if error_message_from_odoo:
             # Get first line of error message
             error_message_from_odoo = error_message_from_odoo.split('\n')[0] 
             # Flash message translated
             flash(f"Odoo error validating '{picking_ref}': {error_message_from_odoo}", 'error')
        else:
            # Flash message translated
            flash(f"Odoo RPC Error validating transfer '{picking_ref}'.", 'error')
        # Consider redirecting to details to retry? Or list? List is safer.
        # return redirect(url_for('books.show_picking_details', picking_id=picking_id)) # <-- To retry
         # <-- To general list
        return redirect(url_for('books.shipping_management')) 

    except Exception as e:
         # Log message translated
        logging.error(f"[books_bp POST /process_validate] Unexpected error processing '{picking_ref}': {e}", exc_info=True)
         # Flash message translated
        flash(f'Unexpected server error validating shipment.', 'error')
        return redirect(url_for('books.shipping_management'))

    # 6. Final redirection
    # Redirect to general list to see 'done' status
    return redirect(url_for('books.shipping_management'))