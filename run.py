# run.py
from ong_app import create_app 

app = create_app() 

if __name__ == '__main__': 
    import os
    
    debug_mode = app.config.get('DEBUG', False)
    port = int(os.environ.get("PORT", 5000)) 
   
    app.run(host='0.0.0.0', port=port, debug=debug_mode)