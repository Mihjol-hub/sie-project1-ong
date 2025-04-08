# Dockerfile (REESTRUCTURADO)
# 1. Usar una imagen base oficial de Python
FROM python:3.10-slim

# 2. Variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE 1 # Evita crear archivos .pyc
ENV PYTHONUNBUFFERED 1    # Asegura que los prints/logs salgan directo a la consola

# 3. Establecer el directorio de trabajo
WORKDIR /app # Mantenemos /app como workdir

# 4. Instalar dependencias
# Copia solo requirements.txt primero para caché de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar el resto de la aplicación
# Copia la carpeta ong_app y el script run.py
COPY ong_app/ ./ong_app/
COPY run.py .

# 6. Exponer el puerto
EXPOSE 5000

# 7. Comando para ejecutar la aplicación
# Ejecuta el script run.py que a su vez inicia Flask
# Flask ahora se configura dentro de create_app()
# Dockerfile (CMD MODIFICADO)
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]