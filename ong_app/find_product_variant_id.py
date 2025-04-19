# ong_app/find_product_variant_id.py
import odoorpc
import logging

# Intenta importar el conector desde la ubicación esperada
# Si ejecutas esto desde la raíz, la segunda opción funcionará
try:
    from .odoo_connector import get_odoo_client
    logging.info("Importando get_odoo_client desde ruta relativa (.)")
except ImportError:
    try:
        from ong_app.odoo_connector import get_odoo_client
        logging.info("Importando get_odoo_client desde ong_app")
    except ImportError:
        logging.error("¡ERROR FATAL! No se pudo importar get_odoo_client.")
        logging.error("Asegúrate de que ong_app/odoo_connector.py existe y que lo ejecutas desde el directorio raíz del proyecto.")
        exit(1)


# --- ID del Product Template que queremos investigar ---
TEMPLATE_ID_A_BUSCAR = 13
# ---------------------------------------------------

logging.basicConfig(level=logging.INFO)
logging.info(f"--- Buscando el ID del 'product.product' asociado al 'product.template' ID: {TEMPLATE_ID_A_BUSCAR} ---")

# Usa el conector centralizado para obtener el cliente Odoo ya logueado
client = get_odoo_client()

if client:
    logging.info("Conexión Odoo obtenida exitosamente desde el conector.")
    try:
        ProductProductModel = client.env['product.product']

        # El dominio de búsqueda clave: busca variantes cuyo campo 'product_tmpl_id' sea nuestro ID
        search_domain = [('product_tmpl_id', '=', TEMPLATE_ID_A_BUSCAR)]
        logging.info(f"Ejecutando búsqueda en 'product.product' con dominio: {search_domain}")

        # Ejecutar la búsqueda
        product_variant_ids = ProductProductModel.search(search_domain)

        if product_variant_ids:
            logging.info(f"IDs de 'product.product' encontrados para el template {TEMPLATE_ID_A_BUSCAR}: {product_variant_ids}")

            # En el 99% de los casos para un servicio simple, será solo uno.
            if len(product_variant_ids) == 1:
                variant_id = product_variant_ids[0]
                print(f"\n************************************************************")
                print(f"***   ¡ID encontrado! El ID de 'product.product' es: {variant_id}   ***")
                print(f"***   Usa este ID ({variant_id}) en DONATION_PRODUCT_ID         ***")
                print(f"************************************************************\n")

                # (Opcional) Leer y mostrar más detalles de esa variante
                try:
                    variant_data = ProductProductModel.read(variant_id, ['name', 'default_code', 'active', 'product_tmpl_id'])
                    logging.info(f"Detalles de la variante encontrada: {variant_data}")
                except Exception as read_err:
                    logging.warning(f"No se pudieron leer detalles adicionales de la variante ID {variant_id}: {read_err}")

            else:
                # Caso raro: múltiples variantes para la plantilla
                print(f"\n¡ATENCIÓN! Se encontraron MÚLTIPLES ({len(product_variant_ids)}) variantes para el template {TEMPLATE_ID_A_BUSCAR}.")
                print("IDs encontrados:", product_variant_ids)
                print("Necesitas decidir cuál usar. Generalmente será la primera o la que tenga sentido semántico.")
                try:
                    variants_data = ProductProductModel.read(product_variant_ids, ['id', 'name', 'default_code', 'active'])
                    print("Detalles de las variantes:")
                    for v in variants_data:
                         print(f"  - ID: {v['id']}, Nombre: '{v['name']}', Ref: {v.get('default_code')}, Activa: {v.get('active')}")
                except Exception as read_err:
                    logging.warning(f"No se pudieron leer detalles de las múltiples variantes: {read_err}")

        else:
            # No se encontró ninguna variante asociada
            print(f"\nERROR: No se encontró ningún 'product.product' asociado al 'product.template' con ID {TEMPLATE_ID_A_BUSCAR}.")
            print("Verifica lo siguiente:")
            print("  1. ¿Estás 100% seguro de que el ID de la PLANTILLA (Template) es 13? Revisa la URL en Odoo de nuevo.")
            print("  2. ¿Se guardó correctamente el producto como tipo 'Servicio' y está 'Activo'?")
            print("  3. Entra a Odoo > Inventario > Productos > Variantes de producto (Product Variants) y busca si existe.")


    except odoorpc.error.RPCError as e:
        print(f"\nError RPC durante la comunicación con Odoo: {e}")
        logging.error("Error RPC Odoo", exc_info=True)
    except Exception as e:
        print(f"\nError inesperado durante la ejecución del script: {e}")
        logging.error("Error inesperado", exc_info=True)
else:
    print("\nError Crítico: No se pudo obtener la conexión a Odoo desde odoo_connector.")
    logging.error("Fallo al obtener cliente Odoo desde get_odoo_client()")

print("--- Script finalizado ---")