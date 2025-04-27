# Dockerfile (RESTRUCTURED & TRANSLATED)

# 1. Use an official Python base image Translated comment
FROM python:3.10-slim

# 2. Environment variables for Python Translated comment
# Avoids creating .pyc files Translated comment
ENV PYTHONDONTWRITEBYTECODE 1 
# Ensures prints/logs output directly to console Translated comment
ENV PYTHONUNBUFFERED 1    

# 3. Set the working directory Translated comment
# Keeping /app as workdir Translated comment
WORKDIR /app 

# 4. Install dependencies Translated comment
# Copy only requirements.txt first for Docker cache Translated comment
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of the application Translated comment
# Copy the ong_app folder and the run.py script Translated comment
COPY ong_app/ ./ong_app/
COPY run.py .

# 6. Expose the port Translated comment
EXPOSE 5000

# 7. Command to run the application Translated comment
# Executes the run.py script which in turn starts Flask Translated comment
# Flask is now configured within create_app() Translated comment
# Dockerfile (CMD KEPT AS IS)
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]