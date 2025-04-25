# ong_app/list_operation_types.py
import odoorpc
import logging
try:
    from .odoo_connector import get_odoo_client
except ImportError:
    from ong_app.odoo_connector import get_odoo_client

logging.basicConfig(level=logging.INFO)
logging.info("--- Buscando Tipos de Operación ('stock.picking.type') ---")
client = get_odoo_client()
if client:
    try:
        OpTypeModel = client.env['stock.picking.type']
        op_types = OpTypeModel.search_read([], fields=['id', 'name', 'code', 'warehouse_id', 'default_location_src_id', 'default_location_dest_id'])
        print("\n================ Tipos de Operación Encontrados ================")
        for ot in op_types:
            print(f" ID: {ot.get('id'):<4} | Nombre: '{ot.get('name')}' | Código: {ot.get('code')}")
            print(f"     └─ Origen Def: {ot.get('default_location_src_id')} | Destino Def: {ot.get('default_location_dest_id')} | Almacén: {ot.get('warehouse_id')}")
        print("============================================================\n")
        print("Busca el ID del tipo de operación que creaste ('Envíos a Sucursales' o 'Branch Shipments').")
    except Exception as e:
        print(f"Error: {e}")
else:
    print("Error: No se pudo conectar a Odoo.")
print("--- Script finalizado ---")