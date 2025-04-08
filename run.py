# run.py
from ong_app import create_app # Importa la factory

app = create_app() # Crea la instancia de la app

if __name__ == '__main__': # Este bloque es clave
    import os
    # ¿Está FLASK_DEBUG=1 en el entorno? Si no, lo toma de la config o default (off)
    # El app.run() respeta el modo debug de la config de la app
    debug_mode = app.config.get('DEBUG', False)
    port = int(os.environ.get("PORT", 5000)) # Obtenemos el PUERTO INTERNO
    # ¡Asegurar host='0.0.0.0'!
    app.run(host='0.0.0.0', port=port, debug=debug_mode)