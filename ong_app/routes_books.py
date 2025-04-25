# ong_app/routes_books.py 
# (Asegúrate que Flask y otras dependencias estén importadas arriba)
from flask import Blueprint, render_template, request, redirect, url_for, flash
from .odoo_connector import get_odoo_client
import logging
import odoorpc

# --- DEFINIR LOS IDs REALES DE LAS ETIQUETAS (¡Actualizados!) ---
TAG_ID_PENDIENTE = 4 
TAG_ID_APROBADO  = 5 
TAG_ID_RECHAZADO = 6 
# --- CONSTANTES IDs DE TAGS LOGÍSTICAS ---
TAG_ID_LOGISTICS_READY = 7
TAG_ID_LOGISTICS_TRANSIT_EC = 10
TAG_ID_LOGISTICS_TRANSIT_VE = 11
TAG_ID_LOGISTICS_DELIVERED = 9

# (Podríamos usar el ID 8 'In Transit' genérico si quisiéramos simplificar más adelante)
LIST_ALL_LOGISTICS_TAGS = [TAG_ID_LOGISTICS_READY, TAG_ID_LOGISTICS_TRANSIT_EC, 
                           TAG_ID_LOGISTICS_TRANSIT_VE, TAG_ID_LOGISTICS_DELIVERED, 8]


books_bp = Blueprint('books', __name__)

# --- Ruta para MOSTRAR el formulario de añadir libro (CON CARGA DE DONANTES) ---

@books_bp.route('/add_book', methods=['GET'])
def add_book_form():
    donors = [] # Inicializar como lista vacía
    error_message = None

    client = get_odoo_client()
    if not client:
        flash('Error de conexión con Odoo. No se pueden cargar los donantes.', 'error')
        error_message = "Error de conexión con Odoo al cargar donantes." # Mensaje más específico
        # No hacemos return aquí todavía, para renderizar el form aunque sea sin donantes
    else:
        # Intentar obtener la lista de donantes SOLO si la conexión fue exitosa
        try:
            # Buscar partners de tipo 'persona' (asumiendo que son los donantes/voluntarios)
            # Ordenamos por nombre ascendente para el desplegable
            donor_ids = client.env['res.partner'].search(
                [('company_type', '=', 'person')], 
                limit=150,  # Aumentamos límite por si acaso
                order="name asc" 
            )
            logging.info(f"[books_bp GET /add_book] IDs de donantes encontrados: {donor_ids}")
            
            if donor_ids:
                # Leer solo el ID y el nombre para el desplegable
                donors = client.env['res.partner'].read(donor_ids, ['id', 'name'])
                logging.info(f"[books_bp GET /add_book] Datos de donantes (id, name) leídos: {len(donors)} encontrados.")
            else:
                logging.info("[books_bp GET /add_book] No se encontraron partners tipo 'persona'.")
                # Podríamos poner un flash info aquí si queremos, pero no es crítico
                # flash('No hay donantes registrados para seleccionar.', 'info')

        except odoorpc.error.RPCError as e:
            logging.error(f"[books_bp GET /add_book] Error RPC al cargar donantes: {e}", exc_info=True)
            error_message = f"Error RPC al cargar lista de donantes: {e}"
            flash(error_message, 'error')
        except Exception as e:
            logging.error(f"[books_bp GET /add_book] Error inesperado al cargar donantes: {e}", exc_info=True)
            error_message = f"Error inesperado al cargar donantes: {e}"
            flash(error_message, 'error')
            
    # Renderizar SIEMPRE la plantilla, pasando la lista 'donors' (que estará llena o vacía)
    return render_template('add_book.html', donors=donors, error_message=error_message)


# --- Ruta para PROCESAR el formulario de añadir libro ---
# (INTENTA añadir etiqueta Pendiente (ID 4) al crear, via template write)
@books_bp.route('/add_book', methods=['POST'])
def add_book_submit():
    title = request.form.get('title')
    author = request.form.get('author')
    isbn = request.form.get('isbn')
    donor_id_str = request.form.get('donor_id') 

    if not title:
        flash('El título del libro es obligatorio.', 'error')
        return redirect(url_for('books.add_book_form'))

    logging.info(f"[books_bp POST /add_book] Datos: T={title}, A={author}, I={isbn}, D={donor_id_str}")
    client = get_odoo_client()
    if not client:
        flash('Error de conexión con Odoo. No se pudo añadir el libro.', 'error')
        return redirect(url_for('books.add_book_form'))

    # --- Preparar info donante (SIN CAMBIOS) ---
    donor_name = None
    donor_info_text = ""
    if donor_id_str:
        try:
            donor_id = int(donor_id_str)
            logging.info(f"[books_bp] Buscando nombre para Donante ID: {donor_id}")
            donor_data = client.env['res.partner'].read(donor_id, ['name'])
            if donor_data:
                donor_name = donor_data[0]['name']
                donor_info_text = f"Donante: {donor_name} (ID: {donor_id})"
                logging.info(f"[books_bp] Donante encontrado: {donor_name}")
            else:
                logging.warning(f"[books_bp] Donante ID {donor_id} no encontrado.")
        except ValueError:
            logging.error(f"[books_bp] ID Donante '{donor_id_str}' inválido.")
        except Exception as e:
            logging.error(f"[books_bp] Error al leer donante {donor_id_str}: {e}", exc_info=True)

    # --- Crear libro en Odoo ---
    new_book_id = None # Inicializar
    try:
        # Buscar duplicados (SIN CAMBIOS)
        search_criteria = []
        if isbn: search_criteria.append(('default_code', '=', isbn))
        elif title: search_criteria.append(('name', '=', title))
        existing_books_ids = client.env['product.product'].search(search_criteria) if search_criteria else []
        if existing_books_ids:
             logging.warning(f"[books_bp] Libro ya podría existir: {title}/{isbn}. IDs: {existing_books_ids}")
             flash(f'Libro ya existe (Título/ISBN). IDs: {existing_books_ids}. No se añadió.', 'warning')
             return redirect(url_for('books.add_book_form'))

        # Preparar datos libro (SIN la etiqueta inicialmente)
        logging.info("[books_bp] Libro no encontrado, creando...")
        description_parts = [f"Autor: {author}"] if author else []
        if donor_info_text: description_parts.append(donor_info_text)
        full_description = ". ".join(description_parts)

        product_data = {
            'name': title, 'default_code': isbn, 'description': full_description,
            'standard_price': 0, 'list_price': 1.0, 'type': 'product',
            'categ_id': 1, 'sale_ok': True 
        }
        
        # Crear el producto
        new_book_id = client.env['product.product'].create(product_data)
        logging.info(f"[books_bp] Libro creado con ID: {new_book_id}!")
        
        # INTENTAR añadir etiqueta Pendiente (ID 4) vía TEMPLATE WRITE
        if new_book_id:
            try:
                product_info = client.env['product.product'].read(new_book_id, ['product_tmpl_id'])
                if product_info and product_info[0]['product_tmpl_id']:
                    template_id = product_info[0]['product_tmpl_id'][0]
                    logging.info(f"[books_bp] Producto ID={new_book_id} tiene Template ID={template_id}")
                    
                    # Usamos TAG_ID_PENDIENTE = 4
                    update_data_template = {'product_tag_ids': [(4, TAG_ID_PENDIENTE)]} 
                    
                    client.env['product.template'].write([template_id], update_data_template)
                    logging.info(f"[books_bp] Etiqueta Pendiente (ID={TAG_ID_PENDIENTE}) añadida al Template ID={template_id} mediante write.")
                    # Mensaje combinado si todo va bien
                    flash(f'Libro "{title}" (ID: {new_book_id}) añadido y marcado como Pendiente Revisión.', 'success')
                else:
                    logging.warning(f"[books_bp] No se pudo encontrar template ID para Prod ID={new_book_id}. No se añadió etiqueta pendiente.")
                    # Mensaje si se crea pero no se encuentra template (raro)
                    flash(f'Libro "{title}" (ID: {new_book_id}) creado, pero NO se pudo marcar como Pendiente (template no encontrado).', 'warning')
            
            except Exception as e_tag:
                logging.error(f"[books_bp] Error al intentar añadir etiqueta Pendiente (ID={TAG_ID_PENDIENTE}) al template de Prod ID={new_book_id}: {e_tag}", exc_info=True)
                # Mensaje si la etiqueta falla
                flash(f'Libro "{title}" (ID: {new_book_id}) creado, pero falló al marcar como Pendiente Revisión.', 'warning')
        
        else: # Si new_book_id es None o 0
            flash(f'Se intentó crear libro "{title}", pero no se obtuvo ID de Odoo.', 'error')

    except odoorpc.error.RPCError as e:
        logging.error(f"[books_bp] Error RPC durante creación/etiquetado: {e}", exc_info=True)
        flash(f'Error RPC al comunicar con Odoo: {e}', 'error')
    except Exception as e:
        logging.error(f"[books_bp] Error inesperado durante creación/etiquetado: {e}", exc_info=True)
        flash(f'Error inesperado: {e}', 'error')

    # Redirigir de vuelta al formulario SIEMPRE (incluso si hubo warnings al etiquetar)
    return redirect(url_for('books.add_book_form'))


# --- Ruta para listar libros (list_books) ---

# Dentro de routes_books.py

@books_bp.route('/list_books')
def list_books():
    books = [] # <---- ¡¡AÑADIR ESTA LÍNEA AQUÍ!!
    error_message = None
    client = get_odoo_client()
    if not client:
        flash('Error de conexión con Odoo. No se pueden listar los libros.', 'error')
        error_message = "Error de conexión con Odoo."
        # Ahora, aunque falle la conexión, books ya existe (como lista vacía)
        # Así que el return final funcionará.
    
    # El resto del try/except puede quedar igual...
    # PERO también es buena idea mover el return DENTRO del else y except
    # para ser más explícito. 
    # Mejor aún, dejemos el return al final, pero asegurándonos que 
    # books está definida. El `books = []` al inicio es suficiente.

    try:
        if client: # Solo intenta si hay cliente
            product_ids = client.env['product.product'].search([], limit=80)
            if product_ids:
                # Aquí books se sobreescribe si se encuentran productos
                books = client.env['product.product'].read(product_ids, ['name', 'default_code', 'description_sale', 'id']) 
            else:
                # Si no hay productos, books sigue siendo [] (definido al inicio)
                flash('No se encontraron libros registrados en Odoo.', 'info')
    except odoorpc.error.RPCError as e:
        logging.error(f"[books_bp] Error RPC al listar libros: {e}", exc_info=True)
        error_message = f"Error RPC al comunicar con Odoo: {e}"
        flash(error_message, 'error')
        # books sigue siendo [] si hay error aquí
    except Exception as e:
        logging.error(f"[books_bp] Error inesperado al listar libros: {e}", exc_info=True)
        error_message = f"Error inesperado en el servidor: {e}"
        flash(error_message, 'error')
        # books sigue siendo [] si hay error aquí

    # Este return ahora siempre tendrá 'books' definida (como lista vacía o con datos)
    return render_template('list_books.html', books=books, error_message=error_message)

# --- Ruta para VER LIBROS PENDIENTES DE REVISIÓN ---
# (ACTUALIZADO para buscar por TAG_ID_PENDIENTE = 4)
@books_bp.route('/review_books')
def review_books():
    pending_books = []
    error_message = None
    
    # Usa la constante definida arriba (TAG_ID_PENDIENTE = 4)
    tag_id_a_buscar = TAG_ID_PENDIENTE 

    client = get_odoo_client()
    if not client:
        flash('Error de conexión con Odoo. No se pueden listar los libros pendientes.', 'error')
        error_message = "Error de conexión con Odoo."
    else:
        try:
            logging.info(f"[books_bp GET /review] Buscando libros con etiqueta ID={tag_id_a_buscar}...")
            
            # Dominio de búsqueda: busca productos (variants) que TENGAN la etiqueta ID 4
            # Probamos buscar directamente en product.product usando su campo Many2many 'product_tag_ids'
            # Este campo SÍ existe en product.product y hereda/refleja las etiquetas del template
            search_domain = [('product_tag_ids', '=', tag_id_a_buscar)] 

            product_ids = client.env['product.product'].search(search_domain, limit=100)
            logging.info(f"[books_bp GET /review] IDs de producto (variant) pendientes encontrados: {product_ids}")

            if product_ids:
                pending_books = client.env['product.product'].read(product_ids, ['id', 'name', 'default_code', 'description']) 
                logging.info(f"[books_bp GET /review] Datos de libros pendientes leídos: {pending_books}")
            else:
                logging.info(f"[books_bp GET /review] No se encontraron libros pendientes de revisión con ID={tag_id_a_buscar}.")
                # El flash ahora es más dinámico (si no hay libros y no hay error de conexión)
                if not error_message:
                    flash('No hay libros pendientes de revisión actualmente.', 'info')

        except odoorpc.error.RPCError as e:
            logging.error(f"[books_bp GET /review] Error RPC: {e}", exc_info=True)
            error_message = f"Error RPC Odoo: {e}"
            flash(error_message, 'error')
        except Exception as e:
            logging.error(f"[books_bp GET /review] Error inesperado: {e}", exc_info=True)
            error_message = f"Error inesperado: {e}"
            flash(error_message, 'error')

    # Renderizamos la plantilla
    return render_template('review_books.html', books=pending_books, error_message=error_message)

# --- NUEVA RUTA PARA APROBAR UN LIBRO (POST) ---
@books_bp.route('/approve_book/<int:book_id>', methods=['POST'])
def approve_book(book_id):
    logging.info(f"[books_bp POST /approve] Solicitud para APROBAR product.product ID: {book_id}")

    # Validar IDs configurados (ya no necesitamos pendiente aquí si usamos 3 y 4)
    if TAG_ID_APROBADO <= 0: # Solo revisamos Aprobado
         flash('Error config: ID etiqueta Aprobado no configurado.', 'error')
         logging.error("[books_bp approve] Error: ID TAG_ID_APROBADO no configurado.")
         return redirect(url_for('books.review_books'))

    client = get_odoo_client()
    if not client:
        flash('Error conexión Odoo.', 'error')
        return redirect(url_for('books.review_books'))

    template_id = None # Inicializar para logs
    try:
        # 1. Obtener Template ID y nombre desde el Product ID
        product_info = client.env['product.product'].read(book_id, ['product_tmpl_id', 'name'])
        if not product_info or not product_info[0]['product_tmpl_id']:
            flash(f'Error: No se encontró template para producto ID={book_id}.', 'error')
            logging.error(f"[books_bp approve] Template no encontrado para product.product ID={book_id}.")
            return redirect(url_for('books.review_books'))
        template_id = product_info[0]['product_tmpl_id'][0]
        book_name = product_info[0].get('name', f'ID {book_id}') 
        logging.info(f"[books_bp approve] Producto ID={book_id} (Nombre:'{book_name}') tiene Template ID={template_id}.")

        # 2. Preparar datos para ACTUALIZAR etiquetas en el TEMPLATE:
        #    - Quitar Pendiente (ID 4) -> (3, id)
        #    - Añadir Aprobado (ID 5)   -> (4, id)
        update_data = {
            'product_tag_ids': [
                (3, TAG_ID_PENDIENTE),  # Desvincular ID 4
                (4, TAG_ID_APROBADO)   # Vincular ID 5
            ]
        }
        logging.info(f"[books_bp approve] Intentando write en template ID={template_id} con datos: {update_data}")

        # 3. Ejecutar write en product.template
        write_ok = client.env['product.template'].write([template_id], update_data)
        
        # Odoo 16 write devuelve True si tiene éxito
        if write_ok:
            logging.info(f"[books_bp approve] ¡Libro '{book_name}' (Template ID: {template_id}) aprobado exitosamente!")
            flash(f'Libro "{book_name}" aprobado.', 'success')
        else:
            # Esto sería raro si no hay excepción, pero por si acaso
            logging.warning(f"[books_bp approve] Odoo write en template ID={template_id} devolvió False/None.")
            flash(f'Se intentó aprobar Libro "{book_name}", pero Odoo no confirmó el cambio.', 'warning')

    except odoorpc.error.RPCError as e:
        logging.error(f"[books_bp approve] Error RPC: {e}", exc_info=True)
        flash(f'Error RPC al aprobar: {e}', 'error')
    except Exception as e:
        logging.error(f"[books_bp approve] Error inesperado: {e}", exc_info=True)
        flash(f'Error inesperado al aprobar: {e}', 'error')

    return redirect(url_for('books.review_books'))

# --- NUEVA RUTA PARA RECHAZAR UN LIBRO (POST) ---
@books_bp.route('/reject_book/<int:book_id>', methods=['POST'])
def reject_book(book_id):
    logging.info(f"[books_bp POST /reject] Solicitud para RECHAZAR product.product ID: {book_id}")

    if TAG_ID_RECHAZADO <= 0: # Solo revisamos Rechazado
         flash('Error config: ID etiqueta Rechazado no configurado.', 'error')
         logging.error("[books_bp reject] Error: ID TAG_ID_RECHAZADO no configurado.")
         return redirect(url_for('books.review_books'))

    client = get_odoo_client()
    if not client:
        flash('Error conexión Odoo.', 'error')
        return redirect(url_for('books.review_books'))

    template_id = None # Inicializar
    try:
        # 1. Obtener Template ID y nombre desde el Product ID
        product_info = client.env['product.product'].read(book_id, ['product_tmpl_id', 'name'])
        if not product_info or not product_info[0]['product_tmpl_id']:
            flash(f'Error: No se encontró template para producto ID={book_id}.', 'error')
            logging.error(f"[books_bp reject] Template no encontrado para product.product ID={book_id}.")
            return redirect(url_for('books.review_books'))
        template_id = product_info[0]['product_tmpl_id'][0]
        book_name = product_info[0].get('name', f'ID {book_id}')
        logging.info(f"[books_bp reject] Producto ID={book_id} (Nombre:'{book_name}') tiene Template ID={template_id}.")

        # 2. Preparar datos para ACTUALIZAR etiquetas en el TEMPLATE:
        #    - Quitar Pendiente (ID 4) -> (3, id)
        #    - Añadir Rechazado (ID 6)  -> (4, id)
        update_data = {
            'product_tag_ids': [
                (3, TAG_ID_PENDIENTE),  # Desvincular ID 4
                (4, TAG_ID_RECHAZADO)   # Vincular ID 6
            ]
        }
        logging.info(f"[books_bp reject] Intentando write en template ID={template_id} con datos: {update_data}")

        # 3. Ejecutar write en product.template
        write_ok = client.env['product.template'].write([template_id], update_data)

        if write_ok:
            logging.info(f"[books_bp reject] ¡Libro '{book_name}' (Template ID: {template_id}) rechazado exitosamente!")
            flash(f'Libro "{book_name}" rechazado.', 'success')
        else:
            logging.warning(f"[books_bp reject] Odoo write en template ID={template_id} devolvió False/None.")
            flash(f'Se intentó rechazar Libro "{book_name}", pero Odoo no confirmó el cambio.', 'warning')

    except odoorpc.error.RPCError as e:
        logging.error(f"[books_bp reject] Error RPC: {e}", exc_info=True)
        flash(f'Error RPC al rechazar: {e}', 'error')
    except Exception as e:
        logging.error(f"[books_bp reject] Error inesperado: {e}", exc_info=True)
        flash(f'Error inesperado al rechazar: {e}', 'error')

    return redirect(url_for('books.review_books'))


# --- NUEVA RUTA PARA VER LIBROS APROBADOS ---

@books_bp.route('/approved_books')
def approved_books():
    # Esta vista ahora mostrará libros que están aprobados PERO AÚN NO en el flujo logístico.
    
    eligible_for_shipping_list = [] # Usaremos un nombre de variable más descriptivo
    error_message = None
    
    # ID de la etiqueta APROBADO (ya definido como constante)
    tag_id_aprobado = TAG_ID_APROBADO # Es 5
    # Lista de IDs de logística a excluir (ya definida como constante)
    tags_logistica_a_excluir = LIST_ALL_LOGISTICS_TAGS 

    client = get_odoo_client()
    if not client:
        flash('Error de conexión con Odoo. No se pueden listar los libros aprobados.', 'error')
        error_message = "Error de conexión con Odoo."
    else:
        try:
            # Actualizamos el log para reflejar la nueva lógica
            logging.info(f"[books_bp GET /approved] Buscando libros APROBADOS (ID={tag_id_aprobado}) y que NO TENGAN tags de logística {tags_logistica_a_excluir}...")

            # === INICIO DE LA MODIFICACIÓN CLAVE ===
            # Construir el dominio de búsqueda compuesto:
            # 1. DEBE tener la etiqueta 'Approved' (ID 5)
            # 2. NO DEBE tener NINGUNA de las etiquetas de logística (IDs 7, 10, 11, 9, 8)
            search_domain = [
                ('product_tag_ids', '=', tag_id_aprobado),
                ('product_tag_ids', 'not in', tags_logistica_a_excluir)
            ]
            logging.debug(f"[books_bp GET /approved] Dominio de búsqueda final: {search_domain}")

            # Ejecutar la búsqueda con el nuevo dominio
            product_ids = client.env['product.product'].search(search_domain, limit=100, order="name asc") # Ordenamos por nombre
            # === FIN DE LA MODIFICACIÓN CLAVE ===

            logging.info(f"[books_bp GET /approved] IDs de producto (aprobados, no en logística) encontrados: {product_ids}")

            if product_ids:
                # Leemos los campos necesarios. Puedes añadir 'author', 'isbn' si los quieres mostrar aquí
                eligible_for_shipping_list = client.env['product.product'].read(product_ids, ['id', 'name', 'default_code', 'description'])
                logging.info(f"[books_bp GET /approved] Datos de libros listos para preparar envío leídos.")
            else:
                logging.info(f"[books_bp GET /approved] No se encontraron libros aprobados que no estén ya en logística.")
                if not error_message: # Solo mostrar si no hay otro error
                    flash('No hay libros aprobados pendientes de iniciar el proceso de envío.', 'info')

        except odoorpc.error.RPCError as e:
            logging.error(f"[books_bp GET /approved] Error RPC: {e}", exc_info=True)
            error_message = f"Error RPC Odoo al buscar aprobados/pendientes de envío: {e}"
            flash(error_message, 'error')
        except Exception as e:
            logging.error(f"[books_bp GET /approved] Error inesperado: {e}", exc_info=True)
            error_message = f"Error inesperado al buscar aprobados/pendientes de envío: {e}"
            flash(error_message, 'error')

    # Renderizamos la plantilla, pasando la lista con el nombre 'books' como espera la plantilla
    return render_template('approved_books.html',
                           books=eligible_for_shipping_list, # La plantilla espera 'books'
                           error_message=error_message)


# --- NUEVA RUTA PARA VER LIBROS RECHAZADOS ---

@books_bp.route('/rejected_books')
def rejected_books():
    rejected_books_list = [] # Nombre de variable diferente
    error_message = None
    
    # Usaremos el ID de la etiqueta RECHAZADO
    tag_id_a_buscar = TAG_ID_RECHAZADO 

    client = get_odoo_client()
    if not client:
        flash('Error de conexión con Odoo. No se pueden listar los libros rechazados.', 'error')
        error_message = "Error de conexión con Odoo."
    else:
        try:
            logging.info(f"[books_bp GET /rejected] Buscando libros con etiqueta Rechazado ID={tag_id_a_buscar}...")
            
            # El dominio de búsqueda ahora busca por el TAG_ID_RECHAZADO
            search_domain = [('product_tag_ids', '=', tag_id_a_buscar)] 

            product_ids = client.env['product.product'].search(search_domain, limit=100)
            logging.info(f"[books_bp GET /rejected] IDs de producto rechazados encontrados: {product_ids}")

            if product_ids:
                rejected_books_list = client.env['product.product'].read(product_ids, ['id', 'name', 'default_code', 'description']) 
                logging.info(f"[books_bp GET /rejected] Datos de libros rechazados leídos.")
            else:
                logging.info(f"[books_bp GET /rejected] No se encontraron libros rechazados con ID={tag_id_a_buscar}.")
                if not error_message:
                    flash('No hay libros marcados como rechazados actualmente.', 'info')

        except odoorpc.error.RPCError as e:
            logging.error(f"[books_bp GET /rejected] Error RPC: {e}", exc_info=True)
            error_message = f"Error RPC Odoo al buscar rechazados: {e}"
            flash(error_message, 'error')
        except Exception as e:
            logging.error(f"[books_bp GET /rejected] Error inesperado: {e}", exc_info=True)
            error_message = f"Error inesperado al buscar rechazados: {e}"
            flash(error_message, 'error')

    # Renderizamos otra NUEVA plantilla
    return render_template('rejected_books.html', 
                           books=rejected_books_list, # Pasamos la lista correcta
                           error_message=error_message)
    

# --- NUEVA RUTA LOGÍSTICA: Marcar como Listo para Envío (POST) ---

@books_bp.route('/mark_ready_for_shipment/<int:book_id>', methods=['POST'])
def mark_ready_for_shipment(book_id):
    """
    Maneja la acción de marcar un libro aprobado como 'Listo para Envío'.
    Quita la etiqueta 'Approved' (ID 5) y añade 'Logistics: Ready for Shipment' (ID 7).
    """
    logging.info(f"[books_bp POST /mark_ready] Solicitud para MARCAR LISTO ENVÍO para product.product ID: {book_id}")

    # Validar IDs de configuración requeridos (Aprobado y Listo para Envío)
    if TAG_ID_APROBADO <= 0 or TAG_ID_LOGISTICS_READY <= 0:
         flash('Error de Configuración: IDs de etiquetas Aprobado/ListoEnvío no válidos.', 'error')
         logging.error(f"[books_bp mark_ready] Error: IDs TAG_ID_APROBADO ({TAG_ID_APROBADO}) o TAG_ID_LOGISTICS_READY ({TAG_ID_LOGISTICS_READY}) no válidos.")
         # Redirigir a la vista de aprobados donde estaba el botón
         return redirect(url_for('books.approved_books'))

    client = get_odoo_client()
    if not client:
        flash('Error conexión Odoo. No se pudo actualizar el estado logístico.', 'error')
        return redirect(url_for('books.approved_books'))

    template_id = None # Para logging en caso de error
    try:
        # 1. Obtener Template ID y nombre desde el Product ID (como en approve/reject)
        product_info = client.env['product.product'].read(book_id, ['product_tmpl_id', 'name'])
        if not product_info or not product_info[0]['product_tmpl_id']:
            flash(f'Error: No se encontró template para producto ID={book_id}.', 'error')
            logging.error(f"[books_bp mark_ready] Template no encontrado para product.product ID={book_id}.")
            return redirect(url_for('books.approved_books'))
        template_id = product_info[0]['product_tmpl_id'][0]
        book_name = product_info[0].get('name', f'ID {book_id}')
        logging.info(f"[books_bp mark_ready] Producto ID={book_id} ('{book_name}') tiene Template ID={template_id}.")

        # 2. Preparar datos para ACTUALIZAR etiquetas en el TEMPLATE:
        #    - Quitar 'Approved' (ID 5)       -> (3, ID_APROBADO)
        #    - Añadir 'Ready for Shipment' (ID 7) -> (4, ID_LOGISTICS_READY)
        update_data = {
            'product_tag_ids': [
                (3, TAG_ID_APROBADO),           # Desvincular ID 5
                (4, TAG_ID_LOGISTICS_READY)    # Vincular ID 7
            ]
        }
        logging.info(f"[books_bp mark_ready] Intentando write en template ID={template_id} con datos: {update_data}")

        # 3. Ejecutar write en product.template
        write_ok = client.env['product.template'].write([template_id], update_data)

        if write_ok:
            logging.info(f"[books_bp mark_ready] ¡Libro '{book_name}' (Template ID: {template_id}) marcado como Listo para Envío exitosamente!")
            flash(f'Libro "{book_name}" marcado como Listo para Envío.', 'success')
        else:
            logging.warning(f"[books_bp mark_ready] Odoo write en template ID={template_id} devolvió False/None.")
            flash(f'Se intentó marcar Libro "{book_name}" como Listo, pero Odoo no confirmó.', 'warning')

    except odoorpc.error.RPCError as e:
        logging.error(f"[books_bp mark_ready] Error RPC al marcar listo: (Tmpl ID: {template_id}) {e}", exc_info=True)
        flash(f'Error RPC al actualizar estado: {e}', 'error')
    except Exception as e:
        logging.error(f"[books_bp mark_ready] Error inesperado al marcar listo: (Tmpl ID: {template_id}) {e}", exc_info=True)
        flash(f'Error inesperado al actualizar estado: {e}', 'error')

    # Redirigir siempre de vuelta a la lista de aprobados
    # El libro ya NO aparecerá ahí si la operación tuvo éxito (por el filtro que añadimos)
    return redirect(url_for('books.approved_books'))


# --- NUEVA RUTA: Vista del Pipeline Logístico ---

@books_bp.route('/shipping_management')
def shipping_management():
    """
    Muestra los libros que están actualmente en el flujo logístico
    (Listos para Envío, En Tránsito).
    """
    shipping_books_list = []
    error_message = None

    # IDs de las etiquetas que indican que un libro está EN el pipeline
    # Incluimos Ready (7), In Transit EC(10), In Transit VE(11), y In Transit General (8)
    # NO incluimos Delivered (9) porque esos ya salieron del pipeline activo.
    PIPELINE_TAG_IDS = [
        TAG_ID_LOGISTICS_READY,
        TAG_ID_LOGISTICS_TRANSIT_EC,
        TAG_ID_LOGISTICS_TRANSIT_VE,
        8 # ID de 'Logistics: In Transit' General
    ]
    logging.info(f"[books_bp GET /shipping_management] Buscando libros con etiquetas de pipeline: {PIPELINE_TAG_IDS}")

    client = get_odoo_client()
    if not client:
        flash('Error conexión Odoo. No se puede mostrar el pipeline de envío.', 'error')
        error_message = "Error de conexión con Odoo."
    else:
        try:
            # Buscamos productos que tengan CUALQUIERA de las etiquetas del pipeline
            search_domain = [('product_tag_ids', 'in', PIPELINE_TAG_IDS)]
            logging.debug(f"Dominio de búsqueda: {search_domain}")

            product_ids = client.env['product.product'].search(search_domain, limit=100, order="name asc")
            logging.info(f"IDs de productos en pipeline encontrados: {product_ids}")

            if product_ids:
                # Leemos campos, incluyendo 'product_tag_ids' para saber el estado actual
                fields_to_read = ['id', 'name', 'default_code', 'description', 'product_tag_ids']
                shipping_books_list = client.env['product.product'].read(product_ids, fields_to_read)
                logging.info(f"Datos de {len(shipping_books_list)} libros en pipeline leídos.")
                
                # (Opcional) Podríamos añadir lógica aquí para determinar el estado exacto
                # (Ready, Transit EC, Transit VE) basado en los IDs de tags leídos,
                # pero lo haremos más fácil en la plantilla Jinja por ahora.

            else:
                logging.info("No se encontraron libros en el pipeline de envío.")
                if not error_message:
                    flash('No hay libros actualmente en proceso de envío.', 'info')

        except odoorpc.error.RPCError as e:
            logging.error(f"[books_bp GET /shipping_pipeline] Error RPC: {e}", exc_info=True)
            error_message = f"Error RPC Odoo al buscar libros en pipeline: {e}"
            flash(error_message, 'error')
        except Exception as e:
            logging.error(f"[books_bp GET /shipping_pipeline] Error inesperado: {e}", exc_info=True)
            error_message = f"Error inesperado al buscar libros en pipeline: {e}"
            flash(error_message, 'error')

    # Renderizar la nueva plantilla
    return render_template('shipping_management.html',
                           books=shipping_books_list, # La plantilla esperará 'books'
                           # Pasamos los IDs de los tags a la plantilla para lógica condicional
                           TAG_ID_READY = TAG_ID_LOGISTICS_READY,
                           TAG_ID_TRANSIT_EC = TAG_ID_LOGISTICS_TRANSIT_EC,
                           TAG_ID_TRANSIT_VE = TAG_ID_LOGISTICS_TRANSIT_VE,
                           TAG_ID_TRANSIT_GENERAL = 8,
                           error_message=error_message)
    
# --- NUEVA RUTA LOGÍSTICA: Marcar como En Tránsito (POST) ---

@books_bp.route('/mark_in_transit/<int:destination_tag_id>/<int:book_id>', methods=['POST'])
def mark_in_transit(destination_tag_id, book_id):
    """
    Maneja la acción de marcar un libro como 'En Tránsito' hacia un destino específico.
    Quita la etiqueta 'Ready for Shipment' (ID 7) y añade la etiqueta de destino (ID 10 o 11).
    """
    logging.info(f"[books_bp POST /mark_in_transit] Solicitud para MARCAR EN TRÁNSITO (Dest ID: {destination_tag_id}) para product.product ID: {book_id}")

    # Validar IDs necesarios: Ready (que quitamos) y el Destino (que añadimos)
    tags_validas_destino = [TAG_ID_LOGISTICS_TRANSIT_EC, TAG_ID_LOGISTICS_TRANSIT_VE, 8] # Incluir el ID 8 general por si lo usamos después
    if TAG_ID_LOGISTICS_READY <= 0 or destination_tag_id not in tags_validas_destino:
         flash(f'Error Config: ID Etiqueta Ready ({TAG_ID_LOGISTICS_READY}) o Destino ({destination_tag_id}) inválido.', 'error')
         logging.error(f"[books_bp mark_in_transit] IDs inválidos: READY={TAG_ID_LOGISTICS_READY}, DESTINATION={destination_tag_id}")
         # Redirigir a la gestión de envíos
         return redirect(url_for('books.shipping_management'))

    client = get_odoo_client()
    if not client:
        flash('Error conexión Odoo.', 'error')
        return redirect(url_for('books.shipping_management'))

    template_id = None
    try:
        # 1. Obtener Template ID y nombre (igual que antes)
        product_info = client.env['product.product'].read(book_id, ['product_tmpl_id', 'name'])
        if not product_info or not product_info[0]['product_tmpl_id']:
            flash(f'Error: Template no encontrado para producto ID={book_id}.', 'error')
            logging.error(f"[books_bp mark_in_transit] Template no encontrado para Prod ID={book_id}.")
            return redirect(url_for('books.shipping_management'))
        template_id = product_info[0]['product_tmpl_id'][0]
        book_name = product_info[0].get('name', f'ID {book_id}')
        logging.info(f"[books_bp mark_in_transit] Prod ID={book_id} ('{book_name}'), Tmpl ID={template_id}")

        # 2. Preparar datos ACTUALIZACIÓN:
        #    - Quitar 'Ready for Shipment' (ID 7)  -> (3, TAG_ID_LOGISTICS_READY)
        #    - Añadir Etiqueta Destino (ID 10 o 11) -> (4, destination_tag_id)
        update_data = {
            'product_tag_ids': [
                (3, TAG_ID_LOGISTICS_READY),
                (4, destination_tag_id)
            ]
        }
        logging.info(f"[books_bp mark_in_transit] Intentando write Tmpl ID={template_id} con datos: {update_data}")

        # 3. Ejecutar write
        write_ok = client.env['product.template'].write([template_id], update_data)

        if write_ok:
            logging.info(f"[books_bp mark_in_transit] ¡Libro '{book_name}' (Tmpl ID:{template_id}) marcado EN TRÁNSITO (Dest ID:{destination_tag_id})!")
            flash(f'Libro "{book_name}" marcado como En Tránsito.', 'success')
        else:
            logging.warning(f"[books_bp mark_in_transit] Write devolvió False/None para Tmpl ID:{template_id}.")
            flash(f'Se intentó marcar Libro "{book_name}" como En Tránsito, pero Odoo no confirmó.', 'warning')

    except odoorpc.error.RPCError as e:
        logging.error(f"[books_bp mark_in_transit] Error RPC: (Tmpl ID:{template_id}) {e}", exc_info=True)
        flash(f'Error RPC al marcar En Tránsito: {e}', 'error')
    except Exception as e:
        logging.error(f"[books_bp mark_in_transit] Error Inesperado: (Tmpl ID:{template_id}) {e}", exc_info=True)
        flash(f'Error inesperado al marcar En Tránsito: {e}', 'error')

    # Redirigir siempre de vuelta a la GESTIÓN DE ENVÍOS
    # El libro seguirá apareciendo, pero con el estado actualizado y diferentes botones
    return redirect(url_for('books.shipping_management'))


# --- NUEVA RUTA LOGÍSTICA: Marcar como Entregado (POST) ---

@books_bp.route('/mark_delivered/<int:book_id>', methods=['POST'])
def mark_delivered(book_id):
    """
    Maneja la acción de marcar un libro como 'Entregado'.
    Quita CUALQUIER etiqueta 'In Transit' y añade 'Logistics: Delivered' (ID 9).
    """
    logging.info(f"[books_bp POST /mark_delivered] Solicitud para MARCAR ENTREGADO para product.product ID: {book_id}")

    # IDs a validar: El ID de Delivered (que añadimos) y la lista de los de tránsito (que quitamos)
    transit_tags_to_remove = [TAG_ID_LOGISTICS_TRANSIT_EC, TAG_ID_LOGISTICS_TRANSIT_VE, 8] # IDs 10, 11, 8
    if TAG_ID_LOGISTICS_DELIVERED <= 0:
         flash(f'Error Config: ID Etiqueta Delivered ({TAG_ID_LOGISTICS_DELIVERED}) inválido.', 'error')
         logging.error(f"[books_bp mark_delivered] ID inválido: DELIVERED={TAG_ID_LOGISTICS_DELIVERED}")
         return redirect(url_for('books.shipping_management'))

    client = get_odoo_client()
    if not client:
        flash('Error conexión Odoo.', 'error')
        return redirect(url_for('books.shipping_management'))

    template_id = None
    try:
        # 1. Obtener Template ID y nombre (igual que antes)
        product_info = client.env['product.product'].read(book_id, ['product_tmpl_id', 'name'])
        if not product_info or not product_info[0]['product_tmpl_id']:
            flash(f'Error: Template no encontrado para producto ID={book_id}.', 'error')
            logging.error(f"[books_bp mark_delivered] Template no encontrado para Prod ID={book_id}.")
            return redirect(url_for('books.shipping_management'))
        template_id = product_info[0]['product_tmpl_id'][0]
        book_name = product_info[0].get('name', f'ID {book_id}')
        logging.info(f"[books_bp mark_delivered] Prod ID={book_id} ('{book_name}'), Tmpl ID={template_id}")

        # 2. Preparar datos ACTUALIZACIÓN:
        #    - Quitar TODAS las etiquetas 'In Transit' (IDs 8, 10, 11) -> (3, id) para cada una
        #    - Añadir 'Delivered' (ID 9)             -> (4, TAG_ID_LOGISTICS_DELIVERED)
        # Construimos la lista de operaciones de desvinculación dinámicamente
        tags_operations = []
        for tag_id_to_remove in transit_tags_to_remove:
             tags_operations.append((3, tag_id_to_remove)) # Comando para desvincular

        # Añadimos la operación para vincular 'Delivered'
        tags_operations.append((4, TAG_ID_LOGISTICS_DELIVERED))

        update_data = {'product_tag_ids': tags_operations}
        logging.info(f"[books_bp mark_delivered] Intentando write Tmpl ID={template_id} con datos: {update_data}")

        # 3. Ejecutar write
        write_ok = client.env['product.template'].write([template_id], update_data)

        if write_ok:
            logging.info(f"[books_bp mark_delivered] ¡Libro '{book_name}' (Tmpl ID:{template_id}) marcado ENTREGADO!")
            flash(f'Libro "{book_name}" marcado como Entregado.', 'success')
        else:
            logging.warning(f"[books_bp mark_delivered] Write devolvió False/None para Tmpl ID:{template_id}.")
            flash(f'Se intentó marcar Libro "{book_name}" como Entregado, pero Odoo no confirmó.', 'warning')

    except odoorpc.error.RPCError as e:
        logging.error(f"[books_bp mark_delivered] Error RPC: (Tmpl ID:{template_id}) {e}", exc_info=True)
        flash(f'Error RPC al marcar Entregado: {e}', 'error')
    except Exception as e:
        logging.error(f"[books_bp mark_delivered] Error Inesperado: (Tmpl ID:{template_id}) {e}", exc_info=True)
        flash(f'Error inesperado al marcar Entregado: {e}', 'error')

    # Redirigir siempre de vuelta a la GESTIÓN DE ENVÍOS
    # El libro YA NO aparecerá aquí si tuvo éxito, porque la vista filtra por tags EN pipeline
    return redirect(url_for('books.shipping_management'))


# --- NUEVA RUTA: Crear Envío de Lote (stock.picking) ---

@books_bp.route('/create_batch_shipment', methods=['POST'])
def create_batch_shipment():
    """
    Procesa la creación de una transferencia de lote (stock.picking) en Odoo.
    Recibe los IDs de los libros seleccionados y el ID de la ubicación destino.
    """
    logging.info("[books_bp POST /create_batch_shipment] Solicitud recibida para crear envío de lote.")

    # 1. Obtener datos del formulario
    # getlist obtiene todos los valores de checkboxes con el mismo 'name'
    selected_book_ids_str = request.form.getlist('selected_book_ids')
    destination_location_id_str = request.form.get('destination_location_id')

    logging.debug(f"IDs de libros seleccionados (str): {selected_book_ids_str}")
    logging.debug(f"ID de ubicación destino (str): {destination_location_id_str}")

    # 2. Validaciones básicas
    if not selected_book_ids_str:
        flash('Error: No se seleccionó ningún libro para el envío.', 'error')
        return redirect(url_for('books.approved_books')) # Volver a la página de selección

    if not destination_location_id_str:
        flash('Error: No se seleccionó ninguna ubicación de destino.', 'error')
        return redirect(url_for('books.approved_books'))

    # Convertir IDs a enteros
    try:
        # Convertimos la lista de strings a lista de integers
        selected_book_ids = [int(id_str) for id_str in selected_book_ids_str]
        destination_location_id = int(destination_location_id_str)
        logging.info(f"Libros a enviar (IDs): {selected_book_ids}")
        logging.info(f"Ubicación destino ID: {destination_location_id}")
    except ValueError:
        flash('Error: IDs de libro o destino inválidos.', 'error')
        logging.error(f"Error al convertir IDs: books={selected_book_ids_str}, dest={destination_location_id_str}")
        return redirect(url_for('books.approved_books'))

    # --- IDs de Configuración Odoo (necesitamos definirlos como constantes arriba o pasarlos) ---
    # ¡¡¡ASEGÚRATE DE TENER ESTOS IDS CORRECTOS!!!
    SOURCE_LOCATION_ID = 30          # ID de 'Stock Libros Aprobados ONG'
    OPERATION_TYPE_ID_ENVIO = 7    # ID de 'Envíos a Sucursales' / 'Branch Shipments'
    # ---------------------------------------------------------------------------------------

    client = get_odoo_client()
    if not client:
        flash('Error conexión Odoo. No se pudo crear el envío.', 'error')
        return redirect(url_for('books.approved_books'))

    new_picking_id = None # Para guardar el ID de la transferencia creada
    try:
        # 3. Preparar datos para crear el stock.picking
        logging.info("Preparando datos para crear 'stock.picking'...")

        # Modelo de Odoo para transferencias
        PickingModel = client.env['stock.picking']

        # === Construcción de las líneas de movimiento (move_ids_without_package) ===
        # Odoo espera una lista de operaciones, (0, 0, {valores}) para crear nuevas líneas
        move_lines_data = []
        logging.info(f"Creando líneas de movimiento para {len(selected_book_ids)} libros...")
        # Necesitamos obtener el nombre de cada libro para la descripción del movimiento (opcional pero útil)
        try:
             books_data = client.env['product.product'].read(selected_book_ids, ['name'])
             # Crear un diccionario id -> nombre para buscar fácil
             book_names = {book['id']: book['name'] for book in books_data}
        except Exception as read_err:
             logging.warning(f"No se pudieron leer los nombres de los libros: {read_err}. Se usará nombre genérico.", exc_info=True)
             book_names = {} # Diccionario vacío

        for book_id in selected_book_ids:
            book_name_for_move = book_names.get(book_id, f"Libro ID {book_id}") # Usa el nombre si lo encontró
            line = (0, 0, {
                'name': book_name_for_move, # Descripción de la línea
                'product_id': book_id,       # El ID del libro a mover
                'product_uom_qty': 1,        # Cantidad: 1 por ahora (asumimos 1 copia por libro)
                'product_uom': 1,            # ID de Unidad de Medida (normalmente 1 para Unidades)
                'location_id': SOURCE_LOCATION_ID,       # Ubicación Origen FIJA
                'location_dest_id': destination_location_id, # Ubicación Destino del formulario
            })
            move_lines_data.append(line)
            logging.debug(f"  Añadida línea para book_id {book_id}: {line}")
        # =============================================================================

        # Datos principales (cabecera) de la transferencia (stock.picking)
        picking_data = {
            'picking_type_id': OPERATION_TYPE_ID_ENVIO,   # ID del Tipo de Operación "Envíos a Sucursales"
            'location_id': SOURCE_LOCATION_ID,            # ID Ubicación Origen
            'location_dest_id': destination_location_id, # ID Ubicación Destino
            'origin': 'Envío Lote desde App Flask ONG',   # Un texto para saber de dónde vino
            'move_ids_without_package': move_lines_data,  # Las líneas de los productos a mover
            # 'state': 'draft', # Odoo lo pone en draft por defecto al crear así
            # Podrían necesitarse otros campos según configuración estricta de Odoo
        }
        logging.info("Datos para crear 'stock.picking' preparados.")
        logging.debug(f"Picking Data: {picking_data}")

        # 4. Ejecutar la creación en Odoo
        logging.info("Intentando crear 'stock.picking' en Odoo...")
        new_picking_id_list = PickingModel.create([picking_data]) # Create espera una lista

        if new_picking_id_list:
             new_picking_id = new_picking_id_list[0] # Obtenemos el ID de la lista
             logging.info(f"¡Éxito! Transferencia (stock.picking) creada con ID: {new_picking_id} !")
             
             # LEER el nombre/referencia de la transferencia creada (ej: WH/OUT/00005)
             picking_ref = ""
             try:
                picking_info = PickingModel.read(new_picking_id, ['name'])
                if picking_info: picking_ref = picking_info[0].get('name', '')
             except Exception: pass # No crítico si no podemos leer el nombre
             
             flash(f'Envío de lote creado con éxito en Odoo (Referencia: {picking_ref or new_picking_id}).', 'success')

             # ----- IMPORTANTE: QUITAR TAG 'Approved' de los libros enviados -----
             # Ahora que se creó el envío, debemos quitar la etiqueta 'Approved' (ID 5)
             # de los libros incluidos para que no aparezcan más en la lista de preparación.
             try:
                  logging.info(f"Quitando tag 'Approved' (ID {TAG_ID_APROBADO}) de los libros enviados: {selected_book_ids}")
                  templates_to_update = []
                  # Necesitamos los IDs de los templates asociados a los products
                  product_infos = client.env['product.product'].read(selected_book_ids, ['product_tmpl_id'])
                  if product_infos:
                      templates_to_update = [p['product_tmpl_id'][0] for p in product_infos if p.get('product_tmpl_id')]
                      # Quitar duplicados si varios libros eran del mismo template (poco probable aquí)
                      templates_to_update = list(set(templates_to_update)) 
                      
                      if templates_to_update:
                          update_data = {'product_tag_ids': [(3, TAG_ID_APROBADO)]} # Desvincular Aprobado
                          write_ok = client.env['product.template'].write(templates_to_update, update_data)
                          if write_ok:
                              logging.info(f"Tag 'Approved' quitado de los templates: {templates_to_update}")
                          else:
                              logging.warning(f"Odoo no confirmó el quitado del tag Approved para templates {templates_to_update}")
                              flash('Advertencia: No se pudo quitar la etiqueta "Aprobado" de los libros enviados. Podrían reaparecer.', 'warning')
                      else:
                           logging.warning("No se encontraron IDs de template válidos para quitar etiqueta.")
             except Exception as tag_err:
                  logging.error(f"Error al intentar quitar tag 'Approved' de libros enviados: {tag_err}", exc_info=True)
                  flash('Advertencia: Hubo un error al actualizar el estado de los libros enviados en la lista de preparación.', 'warning')
             # ---------------------------------------------------------------------

        else:
             # Raro si no hay error RPC
             logging.error("Odoo 'stock.picking.create' no devolvió ID pero no hubo excepción.")
             flash('Se intentó crear el envío, pero Odoo no devolvió confirmación.', 'error')
             return redirect(url_for('books.approved_books'))


    except odoorpc.error.RPCError as e:
        logging.error(f"[books_bp POST /create_batch_shipment] Error RPC Odoo: {e}", exc_info=True)
        error_details = str(getattr(e, 'fault', e))
        flash(f'Error de Odoo al crear envío ({type(e).__name__}): {error_details}', 'error')
        return redirect(url_for('books.approved_books')) # Volver para corregir
    except Exception as e:
        logging.error(f"[books_bp POST /create_batch_shipment] Error inesperado: {e}", exc_info=True)
        flash(f'Error inesperado del servidor al crear envío: {e}', 'error')
        return redirect(url_for('books.approved_books'))

    # 5. Redirigir a una página apropiada tras el éxito
    # Podríamos redirigir a la lista de aprobados (donde ahora faltarán esos libros)
    # o MEJOR AÚN, a la página de gestión de envíos/pipeline para ver la nueva transferencia.
    # Asumimos que 'shipping_management' es la vista para ver transferencias (¡Aún no la hemos adaptado para eso!)
    return redirect(url_for('books.shipping_management'))