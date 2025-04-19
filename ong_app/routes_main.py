# ong_app/routes_main.py
from flask import Blueprint, render_template, jsonify, redirect, url_for
from .odoo_connector import get_odoo_client # Importa la función de conexión
import logging
import odoorpc # Importamos para manejar sus excepciones específicas
#from .routes_books import TAG_ID_PENDIENTE, TAG_ID_APROBADO, TAG_ID_RECHAZADO 

# Crear el Blueprint 'main'
# El primer argumento 'main' es el nombre del blueprint (interno)
# __name__ ayuda a Flask a localizar el blueprint
# template_folder='templates' (opcional) si las plantillas de este BP estuvieran en una subcarpeta.
# Por ahora, Flask buscará en la carpeta 'templates' principal definida en create_app.
main_bp = Blueprint('main', __name__)

# --- IMPORTANTE: Asegúrate de que los IDs de las etiquetas están definidos aquí o en otro lugar accesible ---
TAG_ID_PENDIENTE_MAIN = 4 # Reemplazar con el ID REAL de 'Donado: Aprobado'
TAG_ID_APROBADO_MAIN = 5
TAG_ID_RECHAZADO_MAIN = 6


# --- RUTAS DEL BLUEPRINT PRINCIPAL ---

@main_bp.route('/')
def index():
    titulo = "Proyecto ONG - Integración SIE"
    client = get_odoo_client() 
    odoo_status = "Conectado (Verificado!)" if client else "Desconectado (Revisa Logs!)"
    
    # Inicializar contadores
    counts = {
        'pending': 0,
        'approved': 0,
        'rejected': 0
    }
    count_error = None # Para errores específicos del conteo

    if client:
        logging.info("[main_bp index] **VERIFICANDO IDs LOCALES A USAR:**") # Log actualizado
        logging.info(f"  - PENDIENTE_MAIN = {TAG_ID_PENDIENTE_MAIN}")
        logging.info(f"  - APROBADO_MAIN  = {TAG_ID_APROBADO_MAIN}")
        logging.info(f"  - RECHAZADO_MAIN = {TAG_ID_RECHAZADO_MAIN}")
        
        logging.info("[main_bp index] Cliente Odoo conectado, obteniendo contadores...")
        try:
            ProductModel = client.env['product.template'] 
            
            # Usar las constantes LOCALES '_MAIN'
            counts['pending'] = ProductModel.search_count([('product_tag_ids', '=', TAG_ID_PENDIENTE_MAIN)])
            logging.info(f"[main_bp index] >> RESULTADO search_count Pendiente (ID={TAG_ID_PENDIENTE_MAIN}): {counts['pending']}")

            counts['approved'] = ProductModel.search_count([('product_tag_ids', '=', TAG_ID_APROBADO_MAIN)])
            logging.info(f"[main_bp index] >> RESULTADO search_count Aprobado (ID={TAG_ID_APROBADO_MAIN}): {counts['approved']}")
            
            counts['rejected'] = ProductModel.search_count([('product_tag_ids', '=', TAG_ID_RECHAZADO_MAIN)])
            logging.info(f"[main_bp index] >> RESULTADO search_count Rechazado (ID={TAG_ID_RECHAZADO_MAIN}): {counts['rejected']}")

        except odoorpc.error.RPCError as e:
            
            logging.error(f"[main_bp index] Error RPC al obtener contadores: {e}", exc_info=True)
            count_error = f"Error RPC Odoo al obtener contadores: {e}"
            # Los counts seguirán en 0, mostramos el error
        
        except Exception as e:
             logging.error(f"[main_bp index] Error inesperado al obtener contadores: {e}", exc_info=True)
             count_error = f"Error inesperado al obtener contadores: {e}"
             # Los counts seguirán en 0, mostramos el error
    
    else:
        logging.warning("[main_bp index] No hay cliente Odoo, no se pueden obtener contadores.")
        # Ya tenemos el odoo_status, no necesitamos otro error aquí
        pass # Los counts quedarán en 0

    logging.info(f"Renderizando index desde main_bp con estado Odoo: {odoo_status}, Counts: {counts}")
    
    # Pasamos los contadores y el posible error de conteo a la plantilla
    return render_template('index.html', 
                           page_title=titulo, 
                           odoo_connection_status=odoo_status,
                           book_counts=counts,          # <-- Diccionario con cuentas
                           count_fetch_error=count_error # <-- Error específico del conteo
                           )

# --- RUTA DE PRUEBA PARA ODOO ---
@main_bp.route('/api/odoo_version')
def odoo_version_test():
    logging.info("Recibida petición para /api/odoo_version en main_bp")
    client = get_odoo_client() # Usa la función importada
    if client:
        try:
            logging.info("Cliente Odoo disponible, intentando obtener versión...")
            server_version_info = client.version
            logging.info(f"Versión de Odoo obtenida (odoorpc): {server_version_info}")
            return jsonify(server_version_info)
        except odoorpc.error.RPCError as e:
            logging.error(f"Error RPC API Odoo (version) en main_bp: {e}", exc_info=True)
            return jsonify({"error": f"Error RPC API Odoo: {e}"}), 500
        except Exception as e:
            logging.error(f"Error inesperado API call version en main_bp: {e}", exc_info=True)
            return jsonify({"error": f"Error inesperado: {e}"}), 500
    else:
        logging.warning("Intento de llamada a /api/odoo_version en main_bp fallido, no hay cliente Odoo.")
        return jsonify({"error": "No se pudo obtener cliente Odoo (revisar logs para detalles de conexión)."}), 503

# Podemos añadir aquí la ruta '/api/hello' si la queremos de vuelta
@main_bp.route('/api/hello')
def api_hello():
    return jsonify({"message": "Hola desde el Blueprint Principal!"})

# Añadir una ruta para buscar el ID de la etiqueta

# BORRA la función find_tag_id y PEGA ESTA en su lugar:
@main_bp.route('/list_all_tags') 
def list_all_tags():
    # BORRA TODO el código que estaba aquí dentro (conexión a odoo, búsqueda, etc.)
    # Y pon SOLO esta línea:
    return "Ruta de prueba /list_all_tags funciona!" 


# --- DEFINIR LOS IDs REALES DE LAS ETIQUETAS ---
# !!! MUY IMPORTANTE: REEMPLAZA ESTOS VALORES CON LOS IDs REALES DE TUS ETIQUETAS EN ODOO !!!
# Puedes usar el script find_tag_ids.py que creamos para obtenerlos ejecutando:
# docker compose exec flask_app python find_tag_ids.py
TAG_ID_PENDIENTE = 5 # El ID que CREEMOS que es 'Donado: Pendiente Revisión' (¡VERIFICAR!)
TAG_ID_APROBADO  = 1 # Reemplazar con el ID REAL de 'Donado: Aprobado'
TAG_ID_RECHAZADO = 2 # Reemplazar con el ID REAL de 'Donado: Rechazado'
# -------------------------------------------------

books_bp = Blueprint('books', __name__) # Si no estaba definido ya

# ... (tus rutas existentes: add_book_form, add_book_submit, list_books, review_books) ...


# --- NUEVA RUTA PARA APROBAR UN LIBRO (POST) ---
@books_bp.route('/approve_book/<int:book_id>', methods=['POST'])
def approve_book(book_id):
    logging.info(f"[books_bp] Solicitud POST para APROBAR libro con ID de Producto: {book_id}")

    # Validar que los IDs de etiquetas están configurados (son diferentes de -1)
    if TAG_ID_PENDIENTE <= 0 or TAG_ID_APROBADO <= 0:
         flash('Error de configuración: IDs de etiquetas Pendiente/Aprobado no configurados correctamente en el código.', 'error')
         logging.error("[books_bp approve] Error: IDs de etiquetas Pendiente/Aprobado no configurados.")
         return redirect(url_for('books.review_books'))

    client = get_odoo_client()
    if not client:
        flash('Error de conexión con Odoo. No se pudo aprobar el libro.', 'error')
        return redirect(url_for('books.review_books'))

    try:
        # 1. Obtener el ID del Template asociado al Product ID
        product_info = client.env['product.product'].read(book_id, ['product_tmpl_id', 'name'])
        if not product_info or not product_info[0]['product_tmpl_id']:
            flash(f'Error: No se pudo encontrar el template para el producto ID={book_id}.', 'error')
            logging.error(f"[books_bp approve] No se pudo encontrar el template para product.product ID={book_id}.")
            return redirect(url_for('books.review_books'))

        template_id = product_info[0]['product_tmpl_id'][0]
        book_name = product_info[0].get('name', f'ID {book_id}') # Obtener nombre para el mensaje
        logging.info(f"[books_bp approve] Producto ID={book_id} (Nombre: '{book_name}') tiene Template ID={template_id}.")

        # 2. Preparar datos para actualizar etiquetas en el TEMPLATE:
        #    - Quitar etiqueta "Pendiente" (3)
        #    - Añadir etiqueta "Aprobado"   (4)
        update_data = {
            'product_tag_ids': [
                (3, TAG_ID_PENDIENTE),
                (4, TAG_ID_APROBADO)
            ]
        }
        logging.info(f"[books_bp approve] Intentando write en product.template ID={template_id} con datos: {update_data}")

        # 3. Ejecutar el write en el product.template
        client.env['product.template'].write([template_id], update_data)

        logging.info(f"[books_bp approve] ¡Libro '{book_name}' (Template ID: {template_id}) aprobado exitosamente!")
        flash(f'Libro "{book_name}" aprobado con éxito.', 'success')

    except odoorpc.error.RPCError as e:
        logging.error(f"[books_bp approve] Error RPC al aprobar libro (Prod ID: {book_id}, Tmpl ID: {template_id if 'template_id' in locals() else 'N/A'}): {e}", exc_info=True)
        flash(f'Error RPC al comunicar con Odoo al aprobar: {e}', 'error')
    except Exception as e:
        logging.error(f"[books_bp approve] Error inesperado al aprobar libro (Prod ID: {book_id}): {e}", exc_info=True)
        flash(f'Error inesperado en el servidor al aprobar: {e}', 'error')

    # Redirigir siempre de vuelta a la lista de revisión
    return redirect(url_for('books.review_books'))


# --- NUEVA RUTA PARA RECHAZAR UN LIBRO (POST) ---
@books_bp.route('/reject_book/<int:book_id>', methods=['POST'])
def reject_book(book_id):
    logging.info(f"[books_bp] Solicitud POST para RECHAZAR libro con ID de Producto: {book_id}")

    # Validar que los IDs de etiquetas están configurados
    if TAG_ID_PENDIENTE <= 0 or TAG_ID_RECHAZADO <= 0:
         flash('Error de configuración: IDs de etiquetas Pendiente/Rechazado no configurados correctamente en el código.', 'error')
         logging.error("[books_bp reject] Error: IDs de etiquetas Pendiente/Rechazado no configurados.")
         return redirect(url_for('books.review_books'))

    client = get_odoo_client()
    if not client:
        flash('Error de conexión con Odoo. No se pudo rechazar el libro.', 'error')
        return redirect(url_for('books.review_books'))

    try:
        # 1. Obtener el ID del Template asociado al Product ID
        product_info = client.env['product.product'].read(book_id, ['product_tmpl_id', 'name'])
        if not product_info or not product_info[0]['product_tmpl_id']:
            flash(f'Error: No se pudo encontrar el template para el producto ID={book_id}.', 'error')
            logging.error(f"[books_bp reject] No se pudo encontrar el template para product.product ID={book_id}.")
            return redirect(url_for('books.review_books'))

        template_id = product_info[0]['product_tmpl_id'][0]
        book_name = product_info[0].get('name', f'ID {book_id}') # Obtener nombre para el mensaje
        logging.info(f"[books_bp reject] Producto ID={book_id} (Nombre: '{book_name}') tiene Template ID={template_id}.")

        # 2. Preparar datos para actualizar etiquetas en el TEMPLATE:
        #    - Quitar etiqueta "Pendiente" (3)
        #    - Añadir etiqueta "Rechazado"   (4)
        update_data = {
            'product_tag_ids': [
                (3, TAG_ID_PENDIENTE),
                (4, TAG_ID_RECHAZADO)
            ]
        }
        logging.info(f"[books_bp reject] Intentando write en product.template ID={template_id} con datos: {update_data}")

        # 3. Ejecutar el write en el product.template
        client.env['product.template'].write([template_id], update_data)

        logging.info(f"[books_bp reject] ¡Libro '{book_name}' (Template ID: {template_id}) rechazado exitosamente!")
        flash(f'Libro "{book_name}" rechazado con éxito.', 'success')

    except odoorpc.error.RPCError as e:
        logging.error(f"[books_bp reject] Error RPC al rechazar libro (Prod ID: {book_id}, Tmpl ID: {template_id if 'template_id' in locals() else 'N/A'}): {e}", exc_info=True)
        flash(f'Error RPC al comunicar con Odoo al rechazar: {e}', 'error')
    except Exception as e:
        logging.error(f"[books_bp reject] Error inesperado al rechazar libro (Prod ID: {book_id}): {e}", exc_info=True)
        flash(f'Error inesperado en el servidor al rechazar: {e}', 'error')

    # Redirigir siempre de vuelta a la lista de revisión
    return redirect(url_for('books.review_books'))