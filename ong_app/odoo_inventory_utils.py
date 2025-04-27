import logging
from odoorpc.error import RPCError

def find_virtual_location_id(odoo_client, usage_type='inventory'):
    # ... (Esta función auxiliar no cambia, la dejamos como estaba) ...
    StockLocation = odoo_client.env['stock.location']
    domain = [('usage', '=', usage_type)]
    location_ids = StockLocation.search(domain, limit=1)
    if location_ids:
        logging.info(f"Ubicación virtual encontrada con uso '{usage_type}': ID {location_ids[0]}")
        return location_ids[0]
    else:
        logging.warning(f"No se encontró una ubicación virtual con uso '{usage_type}'.")
        if usage_type == 'inventory':
            logging.info("Intentando buscar ubicación con uso 'production'...")
            return find_virtual_location_id(odoo_client, 'production')
        return None

def add_initial_stock_via_receipt(odoo_client, product_id, quantity, target_location_id):
    """
    Añade stock inicial simulando una Recepción (stock.picking).
    Usa métodos públicos API para confirmar y validar.

    :param odoo_client: Instancia del cliente odoorpc conectado.
    :param product_id: ID del product.product.
    :param quantity: Cantidad a añadir (float).
    :param target_location_id: ID de la stock.location destino (interna).
    :return: True si tuvo éxito, False en caso contrario.
    """
    logging.info(f"Intentando añadir stock inicial (via Picking Recepción) para producto ID {product_id} en ubicación ID {target_location_id}")

    # --- !!! NECESITAS PONER EL ID REAL DE TU TIPO DE OPERACIÓN "RECEPCIONES" AQUÍ !!! ---
    # --- Búscalo en Odoo: Inventario -> Configuración -> Tipos de Operación ---
    RECEIPT_PICKING_TYPE_ID = 1 
    
    picking_id = None  # Inicializar para logs de error
    source_location_id = None # Inicializar para logs de error

    try:
        ProductProduct = odoo_client.env['product.product']
        
        # 1. Obtener info del producto (UoM y Nombre)
        product_info = ProductProduct.read(product_id, ['uom_id', 'display_name'])
        if not product_info or not product_info[0].get('uom_id') or not product_info[0].get('display_name'):
            logging.error(f"No se pudo obtener información completa (UoM/Nombre) para el producto ID {product_id}")
            return False
        product_uom_id = product_info[0]['uom_id'][0]
        product_display_name = product_info[0]['display_name']
        logging.info(f"Producto ID {product_id} - Nombre: '{product_display_name}', UoM ID: {product_uom_id}")

        # 2. Encontrar ubicación virtual de origen (como antes)
        source_location_id = find_virtual_location_id(odoo_client)
        if not source_location_id:
            logging.error("¡Error Crítico! No se pudo encontrar una ubicación virtual de origen ('inventory' o 'production').")
            return False
        logging.info(f"Usando ubicación origen virtual ID: {source_location_id}")
            
        # 3. Preparar datos para crear el stock.picking (RECEPCIÓN)
        # Nota: Las ubicaciones en el picking definen el flujo general,
        #       y las líneas de move heredan esto si no se especifican diferente.
        picking_vals = {
            'picking_type_id': RECEIPT_PICKING_TYPE_ID,   # <-- ¡Usa el ID correcto!
            'location_id': source_location_id,            # Origen (Virtual)
            'location_dest_id': target_location_id,       # Destino (Donde quieres el stock final)
            'origin': f'Entrada Stock Inicial Auto (Flask): {product_display_name}', # Texto descriptivo
            'move_ids_without_package': [
                (0, 0, { # Comando para crear una nueva línea de move
                    'name': product_display_name,         # Descripción de la línea
                    'product_id': product_id,           # El producto
                    'product_uom_qty': quantity,        # La cantidad esperada
                    'product_uom': product_uom_id,      # La unidad de medida
                    'location_id': source_location_id,    # Origen de la línea (puede heredar)
                    'location_dest_id': target_location_id # Destino de la línea (puede heredar)
                })
            ]
        }
        logging.info(f"Valores para crear stock.picking (Recepción): {picking_vals}")

        # 4. Crear el stock.picking
        picking_id = odoo_client.execute_kw('stock.picking', 'create', [picking_vals])
        if not picking_id:
             logging.error("La creación del stock.picking (Recepción) no devolvió ID.")
             return False
        if isinstance(picking_id, list): # Manejar si devuelve lista
             if not picking_id:
                 logging.error("La creación del stock.picking (Recepción) devolvió lista vacía.")
                 return False
             picking_id = picking_id[0]
        logging.info(f"Stock Picking (Recepción) creado con ID: {picking_id}")

        # 5. Confirmar el Picking (acción pública)
        logging.info(f"Llamando a action_confirm para picking ID {picking_id}...")
        odoo_client.execute_kw('stock.picking', 'action_confirm', [[picking_id]])
        logging.info(f"Picking ID {picking_id} confirmado.")

        # 6. Reservar/Asignar el Picking (acción pública)
        logging.info(f"Llamando a action_assign para picking ID {picking_id}...")
        odoo_client.execute_kw('stock.picking', 'action_assign', [[picking_id]])
        logging.info(f"Intento de asignación para picking ID {picking_id} enviado.")
        
        # --- PASO EXTRA CRUCIAL PARA RECEPCIONES ---
        # 7. Establecer la cantidad "Hecha" (qty_done) en las líneas de movimiento detalladas
        logging.info(f"Estableciendo 'qty_done' = {quantity} para las líneas del picking ID {picking_id}")
        
        # Leer las líneas de movimiento detalladas (stock.move.line) asociadas al picking
        move_lines_data = odoo_client.execute_kw(
            'stock.move.line', 'search_read',
            [[('picking_id', '=', picking_id), ('product_id', '=', product_id)]],
            {'fields': ['id'], 'limit': 1} # Buscamos la línea de nuestro producto
        )
        
        if not move_lines_data:
            logging.error(f"No se encontraron stock.move.line para el producto {product_id} en el picking {picking_id} después de asignar. ¡No se puede validar!")
            # Podríamos intentar cancelar el picking aquí si quisiéramos...
            return False
            
        move_line_id = move_lines_data[0]['id']
        logging.info(f"Línea de movimiento detallada encontrada (stock.move.line) ID: {move_line_id}. Actualizando qty_done...")
        
        # Escribir la cantidad hecha en la línea encontrada
        write_ok = odoo_client.execute_kw(
            'stock.move.line', 'write',
            [[move_line_id], {'qty_done': quantity}]
        )
        if not write_ok:
             logging.error(f"Falló la escritura de qty_done en stock.move.line ID {move_line_id}.")
             return False
        logging.info(f"qty_done actualizado en stock.move.line ID {move_line_id}.")
        # --- FIN PASO EXTRA ---

        # 8. Validar/Procesar el Picking (acción pública del botón "Validar")
        logging.info(f"Intentando validar el picking ID {picking_id} llamando a button_validate...")
        # button_validate puede devolver True o un diccionario de acción si requiere pasos extra (ej. backorder)
        validation_result = odoo_client.execute_kw('stock.picking', 'button_validate', [[picking_id]])
        logging.info(f"Resultado de button_validate para picking ID {picking_id}: {validation_result}")

        # Consideramos éxito si no hubo errores RPC y button_validate no devolvió explícitamente False
        # (Un diccionario de acción como resultado a menudo significa éxito parcial o backorder, que está OK para nuestro propósito inicial de stock)
        if validation_result is False: # Chequeo explícito por si devuelve False
             logging.error(f"button_validate para picking ID {picking_id} devolvió False.")
             return False

        # Verificar estado final del picking (opcional, pero bueno)
        final_picking_state_data = odoo_client.execute_kw('stock.picking', 'read', [[picking_id]], {'fields': ['state']})
        final_picking_state = final_picking_state_data[0]['state'] if final_picking_state_data else 'desconocido'
        logging.info(f"Stock Picking ID {picking_id}: Estado final verificado como '{final_picking_state}'.")
        
        if final_picking_state == 'done':
            logging.info(f"¡Éxito! Stock añadido correctamente via Picking Recepción para producto {product_id}.")
            return True
        else:
            # Si no está 'done' pero la validación no dio error directo, puede que esté esperando un backorder.
            # Para el propósito de añadir stock inicial, esto podría ser suficiente, pero es bueno registrarlo.
            logging.warning(f"El estado final del picking {picking_id} es '{final_picking_state}' (no 'done'). Stock podría estar disponible, pero revisar el picking en Odoo.")
            # Decidimos si devolver True o False aquí. Si el objetivo es SOLO tener stock disponible, True podría estar bien.
            # Si queremos que TODO el flujo se complete perfectamente, sería False. Seamos optimistas por ahora:
            return True # Asumir éxito si la validación no falló explícitamente


    except RPCError as e:
        error_msg = f"Error RPC de Odoo"
        if picking_id: error_msg += f" (Picking ID {picking_id})"
        error_msg += f" al intentar añadir stock via Recepción para producto {product_id}: {e}"
        logging.error(error_msg, exc_info=True)
        # Podríamos intentar cancelar el picking aquí también
        # if picking_id:
        #    try: odoo_client.execute_kw('stock.picking', 'action_cancel', [[picking_id]])
        #    except: pass
        return False
    except Exception as e:
        error_msg = f"Error inesperado"
        if picking_id: error_msg += f" (Picking ID {picking_id})"
        error_msg += f" al añadir stock via Recepción para producto {product_id}: {e}"
        logging.error(error_msg, exc_info=True)
        return False