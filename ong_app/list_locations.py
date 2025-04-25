# ong_app/list_locations.py
# Script para listar ubicaciones de stock (stock.location) y sus IDs
import odoorpc
import logging

# Importar el conector centralizado
try:
    from .odoo_connector import get_odoo_client
except ImportError:
    try:
        from ong_app.odoo_connector import get_odoo_client
    except ImportError:
        logging.basicConfig(level=logging.ERROR) # Configura logging básico para ver el error
        logging.error("¡ERROR FATAL! No se pudo importar get_odoo_client.")
        logging.error("Asegúrate de que ong_app/odoo_connector.py existe y que lo ejecutas desde el directorio raíz.")
        exit(1)

logging.basicConfig(level=logging.INFO)
logging.info("--- Buscando ubicaciones de stock ('stock.location') ---")

client = get_odoo_client()

if client:
    logging.info("Conexión Odoo obtenida.")
    try:
        LocationModel = client.env['stock.location']

        # Buscar todas las ubicaciones activas para no listar las archivadas
        # Podríamos añadir más filtros si quisiéramos (ej: solo tipo 'Internal')
        search_domain = [('active', '=', True)]
        # Ordenar por nombre completo para encontrarlas fácil
        order = 'complete_name asc'
        logging.info("Ejecutando búsqueda en 'stock.location'...")

        # Leer campos importantes: id, nombre completo, tipo, si es de desguace/devolución
        fields_to_read = ['id', 'complete_name', 'usage', 'scrap_location', 'return_location']
        location_data = LocationModel.search_read(search_domain, fields=fields_to_read, order=order)

        if location_data:
            print("\n===============================================")
            print("         Ubicaciones Encontradas:")
            print("===============================================")
            for loc in location_data:
                # Formatear un poco la salida
                loc_id = loc.get('id')
                loc_name = loc.get('complete_name', 'N/A')
                loc_usage = loc.get('usage', 'N/A')
                print(f"  ID: {loc_id:<5} | Nombre: '{loc_name}'  (Tipo: {loc_usage})")
            print("===============================================\n")
            print("Busca los IDs de:")
            print("  - 'WH/Stock/Stock Books Approved ONG'")
            print("  - 'WH/Stock/Sucursal Ecuador'")
            print("  - 'WH/Stock/Sucursal Venezuela'")

        else:
            print("\nERROR: No se encontraron ubicaciones activas.")

    except odoorpc.error.RPCError as e:
        print(f"\nError RPC Odoo: {e}")
        logging.error("Error RPC", exc_info=True)
    except Exception as e:
        print(f"\nError inesperado: {e}")
        logging.error("Error inesperado", exc_info=True)
else:
    print("\nError Crítico: No se pudo obtener cliente Odoo.")

print("--- Script finalizado ---")