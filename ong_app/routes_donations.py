# ong_app/routes_donations.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from .odoo_connector import get_odoo_client # Necesario para hablar con Odoo
from datetime import datetime # Para manejar fechas
import logging
import odoorpc # Para manejar excepciones específicas de Odoo

# Crear el Blueprint específico para donaciones monetarias
# 'donations' es el nombre interno del blueprint
# __name__ ayuda a Flask a encontrar recursos asociados
donations_bp = Blueprint('donations', __name__)

# --- CONSTANTE CLAVE: ID DEL PRODUCTO ODOO ---
# Este es el ID del producto "Donación Monetaria" tipo Servicio que creamos en Odoo.
DONATION_PRODUCT_ID = 11 # ¡ID confirmado!

# --- Ruta para MOSTRAR el formulario de añadir donación monetaria (GET) ---
@donations_bp.route('/add_monetary', methods=['GET'])
def add_monetary_donation_form():
    """
    Muestra el formulario para registrar una nueva donación monetaria.
    Carga la lista de donantes existentes desde Odoo para el desplegable.
    """
    logging.info("[donations_bp GET /add_monetary] Accediendo al formulario de donación monetaria.")

    # Comprobación crítica inicial
    if DONATION_PRODUCT_ID <= 0: # Si el ID no es válido (<=0 en lugar de -1)
         flash("Error Crítico: El ID del producto de donación monetaria (DONATION_PRODUCT_ID) no es válido en routes_donations.py.", "error")
         logging.error("[donations_bp GET /add_monetary] DONATION_PRODUCT_ID no es válido.")
         # Es mejor redirigir a inicio si la configuración básica falla
         return redirect(url_for('main.index'))

    donors = [] # Lista para guardar los donantes para el <select>
    error_message = None # Variable para mensajes de error específicos de esta carga
    client = get_odoo_client() # Obtiene la conexión a Odoo

    if not client:
        flash('Error de conexión con Odoo. No se pueden cargar los donantes para el formulario.', 'error')
        logging.warning("[donations_bp GET /add_monetary] No se pudo obtener cliente Odoo.")
        error_message = "Error de conexión con Odoo al cargar donantes."
        # Se renderizará el formulario, pero el desplegable estará vacío y se mostrará el error
    else:
        # Si hay conexión, intentar obtener los donantes
        try:
            logging.info("[donations_bp GET /add_monetary] Conexión Odoo OK. Buscando donantes (res.partner tipo persona)...")
            # Buscamos partners (contactos) que sean 'persona' (company_type='person')
            # Los ordenamos por nombre para el desplegable
            partner_ids = client.env['res.partner'].search([('company_type', '=', 'person')], order="name asc")
            if partner_ids:
                # Leemos solo el ID y el Nombre, que es lo necesario para el <select>
                donors = client.env['res.partner'].read(partner_ids, ['id', 'name'])
                logging.info(f"[donations_bp GET /add_monetary] {len(donors)} donantes encontrados y leídos.")
            else:
                 # Si no se encuentran donantes registrados
                 logging.info("[donations_bp GET /add_monetary] No se encontraron partners tipo 'persona'.")
                 # Informar al usuario, pero no es un error crítico del sistema
                 flash('No hay donantes registrados en el sistema para seleccionar. Puede añadirlos primero.', 'info')

        except odoorpc.error.RPCError as e:
            logging.error(f"[donations_bp GET /add_monetary] Error RPC Odoo al buscar donantes: {e}", exc_info=True)
            error_message = f"Error de Odoo al obtener la lista de donantes: {e}"
            flash(error_message, 'error')
        except Exception as e:
            logging.error(f"[donations_bp GET /add_monetary] Error inesperado al buscar donantes: {e}", exc_info=True)
            error_message = f"Error inesperado del servidor al obtener donantes: {e}"
            flash(error_message, 'error')

    # Renderizar la plantilla HTML del formulario
    # Pasamos la lista de 'donors' (puede estar vacía) y 'error_message' (puede ser None)
    logging.info("[donations_bp GET /add_monetary] Renderizando plantilla add_monetary_donation.html.")
    return render_template('add_monetary_donation.html',
                           donors=donors,
                           error_message=error_message)


# --- RUTA PARA PROCESAR el formulario de añadir donación monetaria (POST) ---
@donations_bp.route('/add_monetary', methods=['POST'])
def add_monetary_donation_submit():
    """
    Procesa los datos enviados desde el formulario de donación monetaria.
    Valida los datos y crea un registro 'sale.order' en Odoo.
    """
    logging.info("[donations_bp POST /add_monetary] Recibida solicitud para registrar donación monetaria.")

    # Comprobación crítica inicial (de nuevo, por si acaso)
    if DONATION_PRODUCT_ID <= 0:
        flash("Error Crítico: El ID del producto de donación monetaria no está configurado o no es válido.", "error")
        logging.error("[donations_bp POST /add_monetary] DONATION_PRODUCT_ID no es válido.")
        # Volver al formulario para mostrar el error
        return redirect(url_for('donations.add_monetary_donation_form'))

    # 1. Obtener datos del formulario HTML
    donor_id_str = request.form.get('donor_id')
    amount_str = request.form.get('amount')
    donation_date_str = request.form.get('donation_date') # Input tipo 'date', puede venir vacío
    description = request.form.get('description', '') # Textarea opcional, default a string vacío si no viene

    logging.debug(f"[donations_bp POST /add_monetary] Datos brutos recibidos: donor_id='{donor_id_str}', amount='{amount_str}', date='{donation_date_str}', desc='{description}'")

    # 2. Validación y conversión de datos
    if not donor_id_str or not amount_str:
        flash('El Donante y el Monto son campos obligatorios.', 'error')
        return redirect(url_for('donations.add_monetary_donation_form')) # Volver al formulario

    try:
        donor_id = int(donor_id_str) # Convertir ID del donante a entero
        amount = float(amount_str.replace(',', '.')) # Convertir monto a flotante (reemplaza coma por punto por si acaso)
        if amount <= 0:
            flash('El Monto debe ser un número positivo.', 'error')
            return redirect(url_for('donations.add_monetary_donation_form'))
    except ValueError:
        flash('El ID del donante o el Monto no tienen un formato numérico válido.', 'error')
        return redirect(url_for('donations.add_monetary_donation_form'))

    # Procesamiento de la Fecha
    donation_date_odoo_format = None # Formato que espera Odoo (string 'YYYY-MM-DD HH:MM:SS' o False)
    if donation_date_str:
        try:
            # Intenta convertir 'YYYY-MM-DD' a 'YYYY-MM-DD HH:MM:SS' (Odoo lo prefiere así para campos Datetime)
            dt_obj = datetime.strptime(donation_date_str, '%Y-%m-%d')
            donation_date_odoo_format = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
            logging.debug(f"Fecha proporcionada '{donation_date_str}' convertida a '{donation_date_odoo_format}' para Odoo.")
        except ValueError:
             # Si el formato es inválido, informamos y usamos la fecha/hora actual
             flash('Formato de fecha inválido. Se usará la fecha y hora actuales.', 'warning')
             donation_date_odoo_format = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
             logging.warning(f"Formato de fecha inválido recibido: '{donation_date_str}'. Usando ahora: '{donation_date_odoo_format}'.")
    else:
         # Si no se proporcionó fecha, usar la actual
         donation_date_odoo_format = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
         logging.debug(f"No se proporcionó fecha. Usando ahora: '{donation_date_odoo_format}'.")

    logging.info(f"[donations_bp POST /add_monetary] Datos validados: Donante ID={donor_id}, Monto={amount}, Fecha='{donation_date_odoo_format}', Desc='{description}'")

    # 3. Obtener conexión a Odoo
    client = get_odoo_client()
    if not client:
        flash('Error de conexión con Odoo. No se pudo registrar la donación en este momento.', 'error')
        logging.error("[donations_bp POST /add_monetary] No se pudo obtener cliente Odoo.")
        return redirect(url_for('donations.add_monetary_donation_form'))

    # 4. Intentar crear el Pedido de Venta ('sale.order') en Odoo
    try:
        logging.info("[donations_bp POST /add_monetary] Conexión Odoo OK. Preparando datos para crear sale.order...")

        # (Opcional pero útil) Obtener el nombre del donante para incluirlo en la descripción
        donor_name = ""
        try:
            donor_info = client.env['res.partner'].read(donor_id, ['name'])
            if donor_info and 'name' in donor_info[0]:
                 donor_name = donor_info[0]['name']
                 logging.debug(f"Nombre del donante obtenido: '{donor_name}'")
        except Exception as e:
             logging.warning(f"[donations_bp POST /add_monetary] No se pudo obtener nombre del donante ID {donor_id}. Error: {e}", exc_info=True)


        # Construir el diccionario de datos para la llamada 'create' a 'sale.order'
        order_data = {
            'partner_id': donor_id,            # ID del Contacto (Donante)
            'date_order': donation_date_odoo_format, # Fecha del pedido (donación)
            'state': 'draft',                 # Estado inicial: Borrador (podría ser 'sale' para confirmar automáticamente)
            # Campo 'note': útil para descripción general visible en Odoo
            'note': description or f"Donación monetaria registrada desde la aplicación Flask el {datetime.now().strftime('%Y-%m-%d')}.",

            # --- LÍNEAS DE PEDIDO ('order_line') ---
            # Se usa una lista de tuplas. Cada tupla representa una operación sobre las líneas.
            # (0, 0, {valores}) significa "crear una nueva línea con estos valores"
            'order_line': [
                (0, 0, {
                    'product_id': DONATION_PRODUCT_ID, # ID del producto "Donación Monetaria" (tipo Servicio)
                    # 'name': Campo de texto libre para la descripción de la línea.
                    # Lo hacemos descriptivo, incluyendo el nombre del donante si lo tenemos.
                    'name': f"Donación Monetaria - {donor_name}" if donor_name else f"Donación Monetaria (Producto ID: {DONATION_PRODUCT_ID})",
                    'product_uom_qty': 1,       # Cantidad: Siempre 1 para una donación simple
                    'price_unit': amount,       # Precio Unitario: El monto donado
                    # 'product_uom': ID de la Unidad de Medida. Suele ser 1 para "Unidades".
                    # Si Odoo se queja de este campo, podríamos omitirlo o buscar el ID correcto.
                    'product_uom': 1,
                    # Podrían requerirse otros campos dependiendo de la configuración de Odoo
                    # (impuestos, cuentas analíticas, etc.), pero intentamos lo mínimo.
                })
            ]
            # Campos opcionales que podrían ser útiles si tuviéramos usuarios/equipos configurados:
            # 'user_id': ID del usuario de Odoo responsable (si tu app tuviera login de Odoo)
            # 'team_id': ID del equipo de ventas (si estuviera configurado y fuera relevante)
        }
        logging.debug(f"[donations_bp POST /add_monetary] Datos que se enviarán a Odoo 'sale.order.create': {order_data}")

        # ¡LA LLAMADA CLAVE PARA CREAR EL REGISTRO EN ODOO!
        new_order_id = client.env['sale.order'].create([order_data]) # Se pasa una lista con un diccionario

        if new_order_id:
            logging.info(f"[donations_bp POST /add_monetary] ¡Pedido de venta (Donación) creado con éxito en Odoo! Nuevo ID: {new_order_id}")
            flash(f'Donación monetaria de {amount:.2f}€ registrada con éxito (Referencia Odoo: {new_order_id}).', 'success')

            # --- Opcional: Confirmar el Pedido Automáticamente ---
            # Si queremos que el pedido pase de 'Borrador' a 'Pedido de venta' directamente.
            # A veces es útil, a veces se prefiere revisar en Odoo primero.
            # Descomentar las siguientes líneas para activar la confirmación automática:
            try:
                client.env['sale.order'].action_confirm(new_order_id)
                logging.info(f"[donations_bp POST /add_monetary] Pedido {new_order_id} confirmado automáticamente en Odoo.")
                flash(f'Pedido Odoo ID:{new_order_id} confirmado automáticamente.', 'info') # Mensaje adicional
            except Exception as confirm_err:
                logging.error(f"[donations_bp POST /add_monetary] Error al auto-confirmar el pedido Odoo ID {new_order_id}: {confirm_err}", exc_info=True)
                # La donación se creó, pero la confirmación falló. Informar como warning.
                flash(f'Donación registrada (ID:{new_order_id}), pero hubo un problema al confirmarla automáticamente en Odoo.', 'warning')

        else:
             # Esto no debería ocurrir si no hay excepción, pero por si acaso
             logging.error("[donations_bp POST /add_monetary] La llamada a Odoo 'sale.order.create' no devolvió un ID, pero no lanzó excepción.")
             flash('La donación parece haberse registrado en Odoo, pero no se recibió confirmación del ID.', 'warning')


    except odoorpc.error.RPCError as e:
        # Error específico de la comunicación con Odoo (ej: campo obligatorio faltante, permiso, etc.)
        logging.error(f"[donations_bp POST /add_monetary] Error RPC Odoo al crear sale.order: {e}", exc_info=True)
        # Intentar obtener un mensaje de error más detallado del objeto excepción
        error_details = str(getattr(e, 'fault', e)) # Intenta obtener 'fault' si existe, sino el error genérico
        flash(f'Error de Odoo al intentar registrar la donación ({type(e).__name__}): {error_details}. Revise los datos e intente de nuevo.', 'error')
        # Volver al formulario para que el usuario pueda corregir y reintentar
        return redirect(url_for('donations.add_monetary_donation_form'))

    except Exception as e:
        # Otro tipo de error inesperado (ej: problema de red, error en nuestro código Python)
        logging.error(f"[donations_bp POST /add_monetary] Error inesperado al procesar la donación: {e}", exc_info=True)
        flash(f'Error inesperado en el servidor al procesar la donación: {e}', 'error')
        # Volver al formulario
        return redirect(url_for('donations.add_monetary_donation_form'))

    # Si todo fue bien (creación exitosa), redirigir a la página que lista las donaciones
    logging.info("[donations_bp POST /add_monetary] Redirigiendo a la lista de donaciones.")
    return redirect(url_for('donations.list_monetary_donations'))


# --- RUTA PARA LISTAR LAS DONACIONES MONETARIAS REGISTRADAS (GET) ---
@donations_bp.route('/list_monetary')
def list_monetary_donations():
    """
    Muestra una lista de las donaciones monetarias registradas (pedidos de venta en Odoo).
    """
    logging.info("[donations_bp GET /list_monetary] Accediendo a la lista de donaciones monetarias.")
    donations_list = [] # Lista para guardar las donaciones leídas de Odoo
    error_message = None
    client = get_odoo_client()

    if not client:
        flash('Error de conexión con Odoo. No se pueden listar las donaciones.', 'error')
        logging.warning("[donations_bp GET /list_monetary] No se pudo obtener cliente Odoo.")
        error_message = "Error de conexión con Odoo."
    else:
        try:
            logging.info("[donations_bp GET /list_monetary] Conexión Odoo OK. Buscando pedidos de venta (sale.order)...")
            # Definir qué campos queremos leer de cada 'sale.order'
            fields_to_read = ['id', 'name', 'partner_id', 'amount_total', 'date_order', 'state']
            # Buscar TODOS los sale.order.
            # NOTA: Si la app gestionara ventas normales además de donaciones, necesitaríamos filtrar
            #       (ej: buscar solo los que usan DONATION_PRODUCT_ID en sus líneas, más complejo).
            #       Por ahora, asumimos que todos los 'sale.order' son donaciones.
            # Ordenamos por fecha descendente para ver las más recientes primero. Limitamos a 100 por si acaso.
            order_ids = client.env['sale.order'].search([], order="date_order desc", limit=100)
            logging.info(f"[donations_bp GET /list_monetary] IDs de sale.order encontrados: {order_ids}")

            if order_ids:
                # Si se encontraron IDs, leer los datos de esos registros
                donations_list = client.env['sale.order'].read(order_ids, fields_to_read)
                logging.info(f"[donations_bp GET /list_monetary] {len(donations_list)} donaciones (pedidos) leídas de Odoo.")
                # 'partner_id' viene como una tupla [ID, Nombre], así que en la plantilla accederemos a partner_id[1]
            else:
                logging.info("[donations_bp GET /list_monetary] No se encontraron pedidos de venta (donaciones) en Odoo.")
                flash('Aún no hay donaciones monetarias registradas en el sistema.', 'info')

        except odoorpc.error.RPCError as e:
            logging.error(f"[donations_bp GET /list_monetary] Error RPC Odoo al listar sale.order: {e}", exc_info=True)
            error_message = f"Error de Odoo al obtener la lista de donaciones: {e}"
            flash(error_message, 'error')
        except Exception as e:
            logging.error(f"[donations_bp GET /list_monetary] Error inesperado al listar sale.order: {e}", exc_info=True)
            error_message = f"Error inesperado del servidor al obtener donaciones: {e}"
            flash(error_message, 'error')

    # Renderizar la plantilla HTML que muestra la lista
    # Pasamos la 'donations_list' (puede estar vacía) y 'error_message' (puede ser None)
    logging.info("[donations_bp GET /list_monetary] Renderizando plantilla list_monetary_donations.html.")
    return render_template('list_monetary_donations.html',
                           donations=donations_list, # Nombre de variable consistente con la plantilla
                           error_message=error_message)