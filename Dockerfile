# Define la imagen base de Python que utilizarás
FROM python:3.8

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia los archivos de requerimientos al contenedor
COPY requirements.txt .

RUN apt-get update && apt-get install -y libgl1-mesa-glx libglib2.0-0
# Instala las dependencias del proyecto
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código fuente del proyecto al contenedor
COPY . .

# Expone el puerto en el que se ejecutará la aplicación Flask
EXPOSE 5000

# Define el comando de inicio para ejecutar la aplicación Flask
CMD ["python", "app.py"]