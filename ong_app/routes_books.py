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
# ------------------------------------------------------------

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
    approved_books_list = [] # Cambiamos el nombre de la variable
    error_message = None
    
    # Usaremos el ID de la etiqueta APROBADO que definimos arriba
    tag_id_a_buscar = TAG_ID_APROBADO 

    client = get_odoo_client()
    if not client:
        flash('Error de conexión con Odoo. No se pueden listar los libros aprobados.', 'error')
        error_message = "Error de conexión con Odoo."
    # Añadimos un else aquí para solo intentar buscar si hay cliente
    else:
        try:
            logging.info(f"[books_bp GET /approved] Buscando libros con etiqueta Aprobado ID={tag_id_a_buscar}...")
            
            # El dominio de búsqueda ahora busca por el TAG_ID_APROBADO
            search_domain = [('product_tag_ids', '=', tag_id_a_buscar)] 

            product_ids = client.env['product.product'].search(search_domain, limit=100)
            logging.info(f"[books_bp GET /approved] IDs de producto aprobados encontrados: {product_ids}")

            if product_ids:
                approved_books_list = client.env['product.product'].read(product_ids, ['id', 'name', 'default_code', 'description']) 
                logging.info(f"[books_bp GET /approved] Datos de libros aprobados leídos.")
            else:
                logging.info(f"[books_bp GET /approved] No se encontraron libros aprobados con ID={tag_id_a_buscar}.")
                if not error_message: # Solo mostrar si no hay otro error
                    flash('No hay libros marcados como aprobados actualmente.', 'info')

        except odoorpc.error.RPCError as e:
            logging.error(f"[books_bp GET /approved] Error RPC: {e}", exc_info=True)
            error_message = f"Error RPC Odoo al buscar aprobados: {e}"
            flash(error_message, 'error')
        except Exception as e:
            logging.error(f"[books_bp GET /approved] Error inesperado: {e}", exc_info=True)
            error_message = f"Error inesperado al buscar aprobados: {e}"
            flash(error_message, 'error')

    # Renderizamos una NUEVA plantilla, pasando la lista con el nuevo nombre
    return render_template('approved_books.html', 
                           books=approved_books_list, # Pasamos la lista correcta
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