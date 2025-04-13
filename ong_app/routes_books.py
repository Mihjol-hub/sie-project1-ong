# ong_app/routes_books.py (COMPLETO CON VINCULACIÓN DONANTE A DESCRIPCIÓN)

from flask import Blueprint, render_template, request, redirect, url_for, flash
from .odoo_connector import get_odoo_client
import logging
import odoorpc

books_bp = Blueprint('books', __name__)

# --- Ruta para MOSTRAR el formulario de añadir libro (CON CARGA DE DONANTES) ---
@books_bp.route('/add_book', methods=['GET'])
def add_book_form():
    donors = [] # Lista para guardar los donantes
    error_message = None

    client = get_odoo_client()
    if not client:
        flash('Error de conexión con Odoo. No se pueden cargar los donantes.', 'error')
        error_message = "Error de conexión con Odoo."
    else:
        try:
            donor_ids = client.env['res.partner'].search([('company_type', '=', 'person')], limit=100, order="name asc")
            logging.info(f"[books_bp/GET /add_book] IDs de donantes encontrados: {donor_ids}")
            if donor_ids:
                donors = client.env['res.partner'].read(donor_ids, ['id', 'name'])
                logging.info(f"[books_bp/GET /add_book] Datos de donantes leídos: {donors}")
                # Nota: La ordenación por nombre ya se hizo en el search
            else:
                logging.info("[books_bp/GET /add_book] No se encontraron partners tipo 'persona'.")

        except odoorpc.error.RPCError as e:
            logging.error(f"[books_bp/GET /add_book] Error RPC al cargar donantes: {e}", exc_info=True)
            error_message = f"Error RPC al cargar lista de donantes: {e}"
            flash(error_message, 'error')
        except Exception as e:
            logging.error(f"[books_bp/GET /add_book] Error inesperado al cargar donantes: {e}", exc_info=True)
            error_message = f"Error inesperado al cargar donantes: {e}"
            flash(error_message, 'error')

    return render_template('add_book.html', donors=donors, error_message=error_message)


# --- Ruta para PROCESAR el formulario de añadir libro (CON LÓGICA DE DONANTE) ---
@books_bp.route('/add_book', methods=['POST'])
def add_book_submit():
    # 1. Obtener datos del formulario
    title = request.form.get('title')
    author = request.form.get('author')
    isbn = request.form.get('isbn')
    donor_id_str = request.form.get('donor_id') # Obtener el ID del donante seleccionado (como string)

    # --- Validación ---
    if not title:
        flash('El título del libro es obligatorio.', 'error')
        return redirect(url_for('books.add_book_form'))

    logging.info(f"[books_bp] Datos recibidos: Title='{title}', Author='{author}', ISBN='{isbn}', DonorID='{donor_id_str}'")

    # --- Conexión Odoo ---
    client = get_odoo_client()
    if not client:
        flash('Error de conexión con Odoo. No se pudo añadir el libro.', 'error')
        return redirect(url_for('books.add_book_form'))

    # --- Preparar información del donante (si se seleccionó) ---
    donor_name = None
    donor_info_text = ""
    if donor_id_str: # Si se seleccionó un valor (no es la opción vacía '-- Seleccionar...')
        try:
            donor_id = int(donor_id_str) # Convertir a entero
            logging.info(f"[books_bp] Buscando nombre para Donante ID: {donor_id}")
            # Leemos solo el nombre del donante seleccionado
            donor_data = client.env['res.partner'].read(donor_id, ['name'])
            if donor_data:
                donor_name = donor_data[0]['name']
                donor_info_text = f"Donante: {donor_name} (ID: {donor_id})"
                logging.info(f"[books_bp] Donante encontrado: {donor_name}")
            else:
                 logging.warning(f"[books_bp] Donante con ID {donor_id} no encontrado en Odoo.")
        except ValueError:
             logging.error(f"[books_bp] ID de donante '{donor_id_str}' no es un número válido.")
        except Exception as e:
            logging.error(f"[books_bp] Error al leer datos del donante {donor_id_str}: {e}", exc_info=True)
            # Continuamos sin la información del donante si hay error al leerlo


    # --- Crear libro en Odoo ---
    try:
        # Buscar duplicados (lógica simple)
        search_criteria = []
        if isbn:
             search_criteria.append(('default_code', '=', isbn))
        elif title:
             search_criteria.append(('name', '=', title))

        existing_books_ids = []
        if search_criteria:
             logging.info(f"[books_bp] Buscando producto existente: {search_criteria}")
             existing_books_ids = client.env['product.product'].search(search_criteria)
             logging.info(f"[books_bp] IDs encontrados: {existing_books_ids}")


        if existing_books_ids:
             logging.warning(f"[books_bp] Libro ya podría existir: {title} / {isbn}. IDs: {existing_books_ids}")
             flash(f'Ya existe un libro con datos similares (Título/ISBN). ID(s): {existing_books_ids}. No se añadió.', 'warning')
             return redirect(url_for('books.add_book_form'))

        # Preparar datos del libro, incluyendo la info del donante
        logging.info("[books_bp] Libro no encontrado, creando...")
        description_parts = []
        if author:
            description_parts.append(f"Autor: {author}")
        if donor_info_text:
            description_parts.append(donor_info_text)
        
        full_description = ". ".join(description_parts) # Unir con ". " si hay ambos

        product_data = {
            'name': title,
            'default_code': isbn,
            'description_sale': full_description, # Ponemos la info combinada aquí
            'standard_price': 0,
            'list_price': 1.0,
            'type': 'product',
            'categ_id': 1,
            'sale_ok': True
        }

        # Crear el producto
        new_book_id = client.env['product.product'].create(product_data)
        logging.info(f"[books_bp] ¡Libro creado con ID: {new_book_id}!")
        flash(f'Libro "{title}" añadido con éxito a Odoo (ID: {new_book_id}).', 'success')

    except odoorpc.error.RPCError as e:
        logging.error(f"[books_bp] Error RPC al crear libro: {e}", exc_info=True)
        flash(f'Error RPC al comunicar con Odoo: {e}', 'error')
    except Exception as e:
        logging.error(f"[books_bp] Error inesperado al crear libro: {e}", exc_info=True)
        flash(f'Error inesperado en el servidor: {e}', 'error')

    # Redirigir de vuelta al formulario
    return redirect(url_for('books.add_book_form'))

# --- Ruta para listar libros (SIN CAMBIOS) ---
@books_bp.route('/list_books')
def list_books():
    books = []
    error_message = None
    client = get_odoo_client()
    if not client:
        flash('Error de conexión con Odoo. No se pueden listar los libros.', 'error')
        error_message = "Error de conexión con Odoo."
        return render_template('list_books.html', books=books, error_message=error_message)
    try:
        product_ids = client.env['product.product'].search([], limit=80)
        if product_ids:
            books = client.env['product.product'].read(product_ids, ['name', 'default_code', 'description_sale', 'id'])
        else:
            flash('No se encontraron libros registrados en Odoo.', 'info')
    except odoorpc.error.RPCError as e:
        logging.error(f"[books_bp] Error RPC al listar libros: {e}", exc_info=True)
        error_message = f"Error RPC al comunicar con Odoo: {e}"
        flash(error_message, 'error')
    except Exception as e:
        logging.error(f"[books_bp] Error inesperado al listar libros: {e}", exc_info=True)
        error_message = f"Error inesperado en el servidor: {e}"
        flash(error_message, 'error')
    return render_template('list_books.html', books=books, error_message=error_message)



