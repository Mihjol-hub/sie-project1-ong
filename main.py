# main.py 

import os
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
import odoorpc
import logging 

app = Flask(__name__)
app.secret_key = 'il_mio_secret_contrase*a_aqui_12345'

# Configura un logger básico para asegurar la salida
logging.basicConfig(level=logging.INFO) # Puedes cambiar a logging.DEBUG para más detalle

# --- Configuración de Odoo desde variables de entorno ---
odoo_url = os.environ.get('ODOO_URL')
odoo_db = os.environ.get('ODOO_DB')
odoo_user = os.environ.get('ODOO_USER')
odoo_password = os.environ.get('ODOO_PASSWORD')

# Variable global para el cliente Odoo
_odoo_client = None # Usaremos un nombre diferente para evitar conflictos

def get_odoo_client():
    """Función MEJORADA para obtener o crear la conexión a Odoo."""
    global _odoo_client
    logging.info("Llamada a get_odoo_client()") # Log inicial de llamada

    # Siempre intenta reconectar si el cliente no está listo
    # O si ya falló antes. Más robusto que el `if _odoo_client is None` solo.
    # if _odoo_client is None: # Vamos a quitar esta condición temporalmente para forzar el intento siempre

    logging.info(f"Variables Odoo: URL={odoo_url}, DB={odoo_db}, User={odoo_user}, Pwd={'Set' if odoo_password else 'None'}")

    if not all([odoo_url, odoo_db, odoo_user, odoo_password]):
        logging.error("Faltan una o más variables de entorno para la conexión a Odoo.")
        _odoo_client = None # Asegura que esté None
        return _odoo_client

    try:
        host = odoo_url.replace('http://', '').split(':')[0]
        port = int(odoo_url.split(':')[-1])
        protocol = 'jsonrpc+ssl' if port == 443 else 'jsonrpc'

        logging.info(f"Paso 1: Intentando crear instancia odoorpc.Odoo(host='{host}', protocol='{protocol}', port={port}, timeout=60)")
        client_instance = odoorpc.ODOO(host, protocol=protocol, port=port, timeout=60) # <-- ¡CORRECTA!
        logging.info("Paso 1.1: Instancia odoorpc.Odoo creada.")

        # Puedes descomentar para probar si la conexión base al host/puerto funciona
        # logging.info("Paso 1.2: Listando bases de datos disponibles...")
        # available_dbs = client_instance.db.list()
        # logging.info(f"Bases de datos: {available_dbs}")

        logging.info(f"Paso 2: Intentando login en DB '{odoo_db}' con usuario '{odoo_user}'")
        client_instance.login(odoo_db, odoo_user, odoo_password)
        logging.info("Paso 3: ¡Login exitoso!")
        _odoo_client = client_instance # Asignamos solo si todo funcionó
        return _odoo_client

    except odoorpc.error.RPCError as e:
        logging.error(f"ERROR RPC al conectar/autenticar con Odoo (odoorpc): {e}", exc_info=True) # Muestra traceback
        _odoo_client = None
        return None
    except Exception as e:
        logging.error(f"ERROR INESPERADO al inicializar/conectar con odoorpc: {e}", exc_info=True) # Muestra traceback
        _odoo_client = None
        return None

    # Nota: Si descomentaste el "if _odoo_client is None" arriba,
    # necesitarías un return aquí para el caso en que ya estuviera conectado
    # return _odoo_client

# --- El resto del código (rutas @app.route...) permanece igual ---
@app.route('/')
def index():
    titulo = "Proyecto ONG - Integración SIE"
    client = get_odoo_client()
    odoo_status = "Conectado (Verificado!)" if client else "Desconectado (Revisa Logs!)" # Cambiado mensaje
    logging.info(f"Renderizando index con estado Odoo: {odoo_status}")
    return render_template('index.html', page_title=titulo, odoo_connection_status=odoo_status)

@app.route('/api/odoo_version')
def odoo_version_test():
    logging.info("Recibida petición para /api/odoo_version")
    client = get_odoo_client() # Intentará conectar
    if client:
        try:
            logging.info("Cliente Odoo disponible, intentando obtener versión...")
            server_version_info = client.version
            logging.info(f"Versión de Odoo obtenida (odoorpc): {server_version_info}")
            return jsonify(server_version_info)
        except odoorpc.error.RPCError as e:
            logging.error(f"Error RPC API Odoo (version): {e}", exc_info=True)
            return jsonify({"error": f"Error RPC API Odoo: {e}"}), 500
        except Exception as e:
            logging.error(f"Error inesperado API call version: {e}", exc_info=True)
            return jsonify({"error": f"Error inesperado: {e}"}), 500
    else:
        logging.warning("Intento de llamada a /api/odoo_version fallido porque no se pudo obtener cliente Odoo.")
        return jsonify({"error": "No se pudo obtener cliente Odoo (revisar logs para detalles de conexión)."}), 503 # Mantenemos 503

# --- Ruta para MOSTRAR el formulario de añadir libro ---

@app.route('/add_book', methods=['GET'])
def add_book_form():
    return render_template('add_book.html')



# --- Ruta para PROCESAR el formulario de añadir libro ---

@app.route('/add_book', methods=['POST'])
def add_book_submit():
    # 1. Obtener datos del formulario
    title = request.form.get('title')
    author = request.form.get('author')
    isbn = request.form.get('isbn')

    # Validaciones básicas (ejemplo: título es obligatorio)
    if not title:
        flash('El título del libro es obligatorio.', 'error')
        return redirect(url_for('add_book_form')) # Redirigir de vuelta al formulario

    logging.info(f"Recibidos datos del formulario: Title={title}, Author={author}, ISBN={isbn}")

    # 2. Obtener conexión Odoo
    client = get_odoo_client()
    if not client:
        flash('Error de conexión con Odoo. No se pudo añadir el libro.', 'error')
        return redirect(url_for('add_book_form'))

    # 3. Intentar crear el libro en Odoo
    try:
        # El modelo en Odoo para productos (libros) es 'product.product'
        # Necesitamos pasar un diccionario con los campos y sus valores
        # 'name' es el campo principal para el título en Odoo.
        # Podemos usar campos existentes o crear campos personalizados en Odoo más adelante.
        # Por ahora, usamos campos básicos. 'default_code' puede usarse para ISBN.
        # 'standard_price' es obligatorio por defecto, lo ponemos a 0.
        # 'type' = 'product' significa que es almacenable (stockable)
        
        # Vamos a buscar primero si existe un producto con ese ISBN o título/autor similar
        # para evitar duplicados (lógica simplificada)
        
        search_criteria = []
        if isbn:
             search_criteria.append(('default_code', '=', isbn))
        elif title: # Si no hay ISBN, buscamos por título (podría mejorarse)
             search_criteria.append(('name', '=', title))
             
        existing_books_ids = []
        if search_criteria:
             existing_books_ids = client.env['product.product'].search(search_criteria)

        if existing_books_ids:
             logging.warning(f"Intento de añadir libro que ya podría existir: {title} / {isbn}. IDs encontrados: {existing_books_ids}")
             flash(f'Ya existe un libro con datos similares (Título/ISBN). ID(s): {existing_books_ids}. No se añadió de nuevo.', 'warning') # 'warning' para un color diferente
             return redirect(url_for('add_book_form'))

        # Si no existe (o no podemos buscarlo bien), creamos uno nuevo
        logging.info("Libro no encontrado, procediendo a crear...")
        product_data = {
            'name': title,            # Campo estándar para el nombre/título
            'default_code': isbn,     # Usamos 'Referencia Interna' para ISBN
            # Añadir autor requiere un campo personalizado o usar uno existente
            # Podríamos ponerlo en la descripción por ahora:
            'description_sale': f"Autor: {author}" if author else "",
            'standard_price': 0,      # Precio de coste (obligatorio, lo ponemos a 0)
            'list_price': 1.0,          # Precio de venta (por si acaso, lo ponemos a 0)
            'type': 'product',        # 'product' = Almacenable, 'service' = Servicio, 'consu' = Consumible
            'categ_id': 1,             # ID de la categoría por defecto ('All') - puede variar, poner 1 es seguro usualmente
            'invoice_policy': 'order', # Política de facturación (no muy relevante para nosotros)
            'purchase_ok': True,      # Indica que se puede comprar (no aplica, pero es común)
            'sale_ok': True           # ¡Importante! Indica que se puede 'vender' (enviar)
        }
        
        new_book_id = client.env['product.product'].create(product_data)
        logging.info(f"¡Libro creado exitosamente en Odoo con ID: {new_book_id}!")
        flash(f'Libro "{title}" añadido con éxito a Odoo (ID: {new_book_id}).', 'success')

    except odoorpc.error.RPCError as e:
        logging.error(f"Error RPC al crear libro en Odoo: {e}", exc_info=True)
        flash(f'Error RPC al comunicar con Odoo: {e}', 'error')
    except Exception as e:
        logging.error(f"Error inesperado al crear libro: {e}", exc_info=True)
        flash(f'Error inesperado en el servidor: {e}', 'error')

    # 4. Redirigir de vuelta al formulario (para que el usuario vea el mensaje flash)
    return redirect(url_for('add_book_form'))

# (...) resto del código