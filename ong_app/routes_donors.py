# ong_app/routes_donors.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from .odoo_connector import get_odoo_client # ¡Necesitamos importar esto ahora!
import logging
import odoorpc # Importar para las excepciones RPC

donors_bp = Blueprint('donors', __name__)

# Ruta para MOSTRAR el formulario de añadir donante
@donors_bp.route('/add_donor', methods=['GET'])
def add_donor_form():
    logging.info("[donors_bp] Mostrando formulario para añadir donante.")
    return render_template('add_donor.html') # Renderiza la plantilla vacía


# --- RUTA PARA PROCESAR el formulario de añadir donante ---

@donors_bp.route('/add_donor', methods=['POST'])
def add_donor_submit():
    # 1. Obtener datos del formulario
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')

    # 2. Validación básica (nombre obligatorio)
    if not name:
        flash('El Nombre Completo es obligatorio.', 'error')
        return redirect(url_for('donors.add_donor_form')) # Redirigir al GET

    logging.info(f"[donors_bp] Datos recibidos para nuevo donante: Name='{name}', Email='{email}', Phone='{phone}'")

    # 3. Obtener conexión Odoo
    client = get_odoo_client()
    if not client:
        flash('Error de conexión con Odoo. No se pudo añadir el donante.', 'error')
        return redirect(url_for('donors.add_donor_form'))

    # 4. Intentar crear el contacto (res.partner) en Odoo
    try:
        # Modelo para contactos en Odoo: res.partner

        # Búsqueda simple para evitar duplicados por email si se proporcionó
        existing_partner_ids = []
        if email:
            search_criteria = [('email', '=', email)]
            logging.info(f"[donors_bp] Buscando partner existente por email: {email}")
            existing_partner_ids = client.env['res.partner'].search(search_criteria)
            logging.info(f"[donors_bp] IDs encontrados: {existing_partner_ids}")

        if existing_partner_ids:
            partner_id = existing_partner_ids[0] # Tomamos el primero encontrado
            logging.warning(f"[donors_bp] Partner ya existe con email {email}. ID: {partner_id}. No se crea nuevo.")
            flash(f'Ya existe un contacto con el email {email} (ID: {partner_id}). No se añadió de nuevo.', 'warning')
            # Podríamos redirigir a una página de "ver donante" en el futuro
            return redirect(url_for('donors.add_donor_form'))

        # Si no existe, crear uno nuevo
        logging.info("[donors_bp] Partner no encontrado por email, creando nuevo...")
        partner_data = {
            'name': name,
            'email': email if email else False, # Odoo espera False si está vacío, no ''
            'phone': phone if phone else False,
            # Cómo marcarlo como Donante/Voluntario:
            # Opción 1 (Simple): Usar notas internas
            'comment': 'Contacto registrado desde App Flask ONG',
            # Opción 2 (Mejor a futuro): Añadir Etiquetas/Categorías.
            # Requeriría buscar o crear las IDs de las categorías 'Donante'/'Voluntario'
            # 'category_id': [(6, 0, [id_categoria_donante])],
            # Opción 3 (Más avanzado): Campos personalizados (ej. x_is_donor = True)

            # Otros campos útiles para contactos:
            'company_type': 'person', # Indicar que es una persona, no una empresa
            # 'is_company': False,   # Otra forma de indicarlo en algunas versiones/vistas
        }

        new_partner_id = client.env['res.partner'].create(partner_data)
        logging.info(f"[donors_bp] ¡Partner creado con éxito en Odoo! ID: {new_partner_id}")
        flash(f'Donante/Voluntario "{name}" añadido con éxito a Odoo (ID: {new_partner_id}).', 'success')

    except odoorpc.error.RPCError as e:
        logging.error(f"[donors_bp] Error RPC al crear partner: {e}", exc_info=True)
        flash(f'Error RPC al comunicar con Odoo: {e}', 'error')
    except Exception as e:
        logging.error(f"[donors_bp] Error inesperado al crear partner: {e}", exc_info=True)
        flash(f'Error inesperado en el servidor: {e}', 'error')

    # Redirigir de vuelta al formulario para ver el mensaje flash
    return redirect(url_for('donors.add_donor_form'))


# --- NUEVA RUTA PARA LISTAR DONANTES ---

@donors_bp.route('/list_donors')
def list_donors():
    donors = []
    error_message = None

    client = get_odoo_client()
    if not client:
        flash('Error de conexión con Odoo. No se pueden listar los donantes.', 'error')
        error_message = "Error de conexión con Odoo."
        # Renderizamos igual para mostrar el error en la plantilla de lista
        return render_template('list_donors.html', donors=donors, error_message=error_message)

    try:
        logging.info("[donors_bp] Intentando buscar y leer donantes (partners) desde Odoo...")
        # Buscamos partners que sean personas
        # Leemos los campos id, name, email, phone. Limitamos por si acaso.
        # Nota: Podríamos ordenar desde la búsqueda con 'order="name asc"'
        partner_ids = client.env['res.partner'].search([('company_type', '=', 'person')], limit=100, order="name asc")
        logging.info(f"[donors_bp] IDs de partners encontrados: {partner_ids}")

        if partner_ids:
            donors = client.env['res.partner'].read(partner_ids, ['id', 'name', 'email', 'phone'])
            logging.info(f"[donors_bp] Datos de partners leídos: {donors}")
            # La búsqueda ya los ordenó por nombre si se especificó 'order'
        else:
            logging.info("[donors_bp] No se encontraron partners tipo 'persona'.")
            flash('No se encontraron donantes/contactos registrados.', 'info')

    except odoorpc.error.RPCError as e:
        logging.error(f"[donors_bp] Error RPC al listar partners: {e}", exc_info=True)
        error_message = f"Error RPC al comunicar con Odoo: {e}"
        flash(error_message, 'error')
    except Exception as e:
        logging.error(f"[donors_bp] Error inesperado al listar partners: {e}", exc_info=True)
        error_message = f"Error inesperado en el servidor: {e}"
        flash(error_message, 'error')

    # Renderizar plantilla pasando la lista de donantes y posible error
    return render_template('list_donors.html', donors=donors, error_message=error_message)