# ong_app/routes_books.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from .odoo_connector import get_odoo_client # Importa la función de conexión
import logging
import odoorpc

# Crear el Blueprint 'books'
# Podríamos añadir un url_prefix='/books' si quisiéramos que todas las rutas aquí
# empezaran con /books (ej: /books/add), pero por ahora lo dejamos sin prefijo.
books_bp = Blueprint('books', __name__)

# --- Ruta para MOSTRAR el formulario de añadir libro ---
@books_bp.route('/add_book', methods=['GET'])
def add_book_form():
    # Usa la plantilla 'add_book.html' que está en la carpeta global 'templates'
    return render_template('add_book.html')

# --- Ruta para PROCESAR el formulario de añadir libro ---
@books_bp.route('/add_book', methods=['POST'])
def add_book_submit():
    title = request.form.get('title')
    author = request.form.get('author')
    isbn = request.form.get('isbn')

    if not title:
        flash('El título del libro es obligatorio.', 'error')
        # ¡OJO! url_for ahora necesita el nombre del blueprint ANTES del nombre de la función: 'books.add_book_form'
        return redirect(url_for('books.add_book_form'))

    logging.info(f"[books_bp] Recibidos datos: Title={title}, Author={author}, ISBN={isbn}")

    client = get_odoo_client()
    if not client:
        flash('Error de conexión con Odoo. No se pudo añadir el libro.', 'error')
        return redirect(url_for('books.add_book_form')) # Usar nombre completo

    try:
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
            return redirect(url_for('books.add_book_form')) # Usar nombre completo

        logging.info("[books_bp] Libro no encontrado, creando...")
        product_data = {
            'name': title,
            'default_code': isbn,
            'description_sale': f"Autor: {author}" if author else "",
            'standard_price': 0,
            'list_price': 1.0, # Mantenemos el 1.0 para la validación
            'type': 'product',
            'categ_id': 1,
            'sale_ok': True
            # Podemos quitar purchase_ok y invoice_policy si no son estrictamente necesarios
        }

        new_book_id = client.env['product.product'].create(product_data)
        logging.info(f"[books_bp] ¡Libro creado con ID: {new_book_id}!")
        flash(f'Libro "{title}" añadido con éxito a Odoo (ID: {new_book_id}).', 'success')

    except odoorpc.error.RPCError as e:
        logging.error(f"[books_bp] Error RPC al crear libro: {e}", exc_info=True)
        flash(f'Error RPC al comunicar con Odoo: {e}', 'error')
    except Exception as e:
        logging.error(f"[books_bp] Error inesperado al crear libro: {e}", exc_info=True)
        flash(f'Error inesperado en el servidor: {e}', 'error')

    # Redirigir siempre usando el nombre completo: blueprint_name.function_name
    return redirect(url_for('books.add_book_form'))


# --- NUEVA RUTA PARA LISTAR LIBROS ---
@books_bp.route('/list_books')
def list_books():
    books = [] # Inicializar lista vacía
    error_message = None

    client = get_odoo_client()
    if not client:
        flash('Error de conexión con Odoo. No se pueden listar los libros.', 'error')
        # Podríamos redirigir a index o mostrar un mensaje aquí mismo
        error_message = "Error de conexión con Odoo."
        # No usamos redirect aquí, vamos a renderizar la plantilla de lista pero indicando el error
        return render_template('list_books.html', books=books, error_message=error_message)

    try:
        logging.info("[books_bp] Intentando buscar y leer libros desde Odoo...")
        # 1. Buscar IDs de los productos: search([]) busca TODOS los productos.
        #    Podríamos añadir un dominio de búsqueda si quisiéramos filtrar,
        #    ej: [('type', '=', 'product')] para asegurar que sean almacenables.
        #    Por ahora, buscamos todos. Limitamos a 50 para no sobrecargar si hay muchos.
        product_ids = client.env['product.product'].search([], limit=80) # Busca hasta 80 productos
        logging.info(f"[books_bp] IDs de productos encontrados: {product_ids}")

        if product_ids:
            # 2. Leer los datos de los productos encontrados:
            #    Especificamos los campos que queremos leer ('name', 'default_code', 'description_sale')
            books_data = client.env['product.product'].read(product_ids, ['name', 'default_code', 'description_sale', 'id'])
            logging.info(f"[books_bp] Datos de libros leídos: {books_data}")
            # books_data será una lista de diccionarios, ej:
            # [{'id': 1, 'name': 'Arturo', 'default_code': 'ISBN123', 'description_sale': 'Autor: Test'}, ...]
            books = books_data # Asignamos los datos leídos a nuestra variable
        else:
            logging.info("[books_bp] No se encontraron productos en Odoo.")
            flash('No se encontraron libros registrados en Odoo.', 'info')


    except odoorpc.error.RPCError as e:
        logging.error(f"[books_bp] Error RPC al listar libros: {e}", exc_info=True)
        error_message = f"Error RPC al comunicar con Odoo: {e}"
        flash(error_message, 'error')
    except Exception as e:
        logging.error(f"[books_bp] Error inesperado al listar libros: {e}", exc_info=True)
        error_message = f"Error inesperado en el servidor: {e}"
        flash(error_message, 'error')

    # Renderizar la plantilla pasando la lista de libros (o vacía si hubo error o no hay)
    # y un posible mensaje de error para mostrar en la plantilla.
    return render_template('list_books.html', books=books, error_message=error_message)