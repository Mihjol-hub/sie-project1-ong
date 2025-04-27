# ong_app/scripts/find_product_variant_id.py
# run with this with: python -m ong_app.scripts.find_product_variant_id

import odoorpc
import logging


try:
    # Use relative import for execution as module within the package
    from ..odoo_connector import get_odoo_client
    # Log message translated
    logging.info("Importing get_odoo_client using relative path (.)")
except ImportError:
    try:
         # Fallback if run directly from ong_app directory (less common now)
        from ong_app.odoo_connector import get_odoo_client
        # Log message translated
        logging.info("Importing get_odoo_client from ong_app")
    except ImportError:
        # Log messages translated
        logging.error("FATAL ERROR! Could not import get_odoo_client.")
        logging.error("Ensure ong_app/odoo_connector.py exists and you are running from the project's root directory (e.g., using python -m).")
        exit(1)


# --- ID of the Product Template we want to investigate --- Translated comment
TEMPLATE_ID_TO_SEARCH = 13 # Set to the ID of the "Monetary Donation" TEMPLATE

logging.basicConfig(level=logging.INFO)
# Log message translated
logging.info(f"--- Searching for the 'product.product' ID associated with 'product.template' ID: {TEMPLATE_ID_TO_SEARCH} ---")

# Use the centralized connector to get the already logged-in Odoo client Translated comment
client = get_odoo_client()

if client:
    # Log message translated
    logging.info("Odoo connection obtained successfully from connector.")
    try:
        ProductProductModel = client.env['product.product']

        # The key search domain: find variants whose 'product_tmpl_id' field matches our ID Translated comment
        search_domain = [('product_tmpl_id', '=', TEMPLATE_ID_TO_SEARCH)]
        # Log message translated
        logging.info(f"Executing search on 'product.product' with domain: {search_domain}")

        # Execute the search Comment translated
        product_variant_ids = ProductProductModel.search(search_domain)

        if product_variant_ids:
            # Log message translated
            logging.info(f"'product.product' IDs found for template {TEMPLATE_ID_TO_SEARCH}: {product_variant_ids}")

            # In 99% of cases for a simple service, there will be only one. Translated comment
            if len(product_variant_ids) == 1:
                variant_id = product_variant_ids[0]
                # Print messages translated
                print(f"\n************************************************************")
                print(f"***   ID Found! The 'product.product' ID is: {variant_id}   ***")
                print(f"***   Use this ID ({variant_id}) in DONATION_PRODUCT_ID         ***")
                print(f"************************************************************\n")

                # (Optional) Read and display more details of that variant Translated comment
                try:
                    variant_data = ProductProductModel.read(variant_id, ['name', 'default_code', 'active', 'product_tmpl_id'])
                    # Log message translated
                    logging.info(f"Details of the found variant: {variant_data}")
                except Exception as read_err:
                    # Log message translated
                    logging.warning(f"Could not read additional details for variant ID {variant_id}: {read_err}")

            else:
                # Rare case: multiple variants for the template Translated comment
                # Print messages translated
                print(f"\nATTENTION! MULTIPLE ({len(product_variant_ids)}) variants found for template {TEMPLATE_ID_TO_SEARCH}.")
                print("Found IDs:", product_variant_ids)
                print("You need to decide which one to use. Usually, it will be the first or the one that makes semantic sense.")
                try:
                    variants_data = ProductProductModel.read(product_variant_ids, ['id', 'name', 'default_code', 'active'])
                     # Print message translated
                    print("Variant details:")
                    for v in variants_data:
                         # Print messages translated
                         print(f"  - ID: {v['id']}, Name: '{v['name']}', Ref: {v.get('default_code')}, Active: {v.get('active')}")
                except Exception as read_err:
                    # Log message translated
                    logging.warning(f"Could not read details for multiple variants: {read_err}")

        else:
            # No associated variant found Translated comment
            # Print messages translated
            print(f"\nERROR: No 'product.product' found associated with 'product.template' ID {TEMPLATE_ID_TO_SEARCH}.")
            print("Check the following:")
            print("  1. Are you 100% sure the TEMPLATE ID is {TEMPLATE_ID_TO_SEARCH}? Check the URL in Odoo again.")
            print("  2. Was the product correctly saved as type 'Service' and is it 'Active'?")
            print("  3. Go to Odoo > Inventory > Products > Product Variants and check if it exists.")


    except odoorpc.error.RPCError as e:
         # Print/Log messages translated
        print(f"\nRPC Error during communication with Odoo: {e}")
        logging.error("Odoo RPC Error", exc_info=True)
    except Exception as e:
         # Print/Log messages translated
        print(f"\nUnexpected error during script execution: {e}")
        logging.error("Unexpected error", exc_info=True)
else:
    # Print/Log messages translated
    print("\nCritical Error: Could not obtain Odoo connection from odoo_connector.")
    logging.error("Failed to get Odoo client from get_odoo_client()")

# Print message translated

print("--- Script finished ---")