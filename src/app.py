from flask import Flask, request, render_template, redirect, url_for, flash, send_file, Response
import cv2
import numpy as np
import io
import face_recognition
import datetime, time
import mysql.connector

app = Flask(__name__)

#SETTING
app.secret_key = "mysecretkey"

mydb = mysql.connector.connect(
    host="server-mysql-remote.mysql.database.azure.com",
    user="ginorubio",
    password="FISIbi123",
    database="fisidb"
)

global es_alumno, capturar, activar_camara, imagen_jpg, alumno
es_alumno = 0
capturar = 0
activar_camara = 0
imagen_jpg = None
alumno = None


@app.route('/')
def Index():
    return render_template('index.html')

@app.route('/registro-usuario')
def registro_usuario():
    return render_template('registro-usuario.html')

@app.route('/agregar-usuario', methods = ['POST', 'GET'])
def agregar_usuario():
    global imagen_jpg
    if request.method == 'POST':

        if request.form.get('Capturar') == 'Capturar':
            global capturar
            capturar = 1
        else:
            nombre = request.form['nombre']
            apellido = request.form['apellido']
            correo = request.form['correo']
            codigo = request.form['codigo']
            #imagen = request.files['imagen']

            datos_imagen = imagen.read()
            #agregar rostro encoding
            image_load= face_recognition.load_image_file(imagen)

            # Encuentra todas las caras en la imagen
            face_locations = face_recognition.face_locations(image_load)
            
            if len(face_locations) == 1:
                # Codifica las características faciales de la cara encontrada
                face_encoding = face_recognition.face_encodings(image_load, face_locations)[0]
                imagen_bytes = face_encoding.tostring()
                cursor = mydb.cursor()
                query = "INSERT INTO alumnos (nombre,apellido,correo,codigo,imagen, imagenEncoding) VALUES (%s, %s, %s,%s, %s, %s)"
                values = (nombre,apellido, correo, codigo, datos_imagen, imagen_bytes)
                cursor.execute(query,values)
                mydb.commit()
                cursor.close()
                flash('Usuario agregado de manera correcta '.format(nombre))
            else:
                flash ("Error al obtener las caracteristicas del rostro")
            
        
    return render_template('registro-usuario.html')

@app.route('/login', methods=['POST','GET'])
def login():
    global alumno, es_alumno
    fecha = str(datetime.datetime.now())
    if es_alumno & (alumno != None):
        cursor = mydb.cursor()
        query = "INSERT INTO logs (idAlumno, fecha) VALUES (%s,%s)"
        values = (alumno[0],fecha)
        cursor.execute(query,values)
        mydb.commit()
        cursor.close()

        #Clear datos
        es_alumno = 0
        alumno = None
        
        return redirect(url_for('dashboard'))
    else:
        flash("Error de autenticación")
        return render_template('validacion.html')



@app.route('/mostrar-imagen', methods = ['POST'] )
def mostrarImagen():
    if request.method == 'POST':
        imagen = request.files['imagen']
        datos_imagen = imagen.read()

    return send_file(io.BytesIO(datos_imagen), mimetype='image/jpeg')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

def convertToBinary(filename):
    with open(filename, 'rb') as file:
        binarydata = file.read()
        return binarydata

def convertBinaryToFile(binarydata,filename):
    with open(filename, 'wb') as file:
        file.write(binarydata)

def getAlumnos():
    cursor = mydb.cursor(buffered=True)
    cursor.execute("SELECT idAlumno,nombre,apellido,correo, codigo,imagenEncoding FROM alumnos")
    alumnos = cursor.fetchall()
    cursor.close()
    return alumnos

def compararRostros(alumnos, rostros_localizados, frame):
    global es_alumno, alumno
    nombre = "desconocido"
    if len(rostros_localizados) >= 1 :
        face_encoding = face_recognition.face_encodings(frame, rostros_localizados)[0]
        for alumno_data in alumnos:
            stored_encoding = np.frombuffer(alumno_data[5], dtype=np.float64)
                
            # Calcula la distancia entre las características faciales
            face_distance = face_recognition.face_distance([stored_encoding], face_encoding)
            if face_distance < 0.6:  # Ajusta el umbral según tus necesidades
                # Inicio de sesión exitoso
                nombre = alumno_data[1]
                es_alumno = 1
                alumno = alumno_data
            else:
                nombre = "Desconocido"
                alumno = None
                es_alumno = 0
    else:
        nombre = "Desconocido"
        alumno = None
        es_alumno = 0

    return nombre

def video_stream():
    global es_alumno, imagen_bytes
    
    alumnos = getAlumnos()

    video_capture = cv2.VideoCapture(0)

    contador = 20
    while True:
        # Captura los cuadros de video #Frame es tipo numpy.ndarray y ret es un Booleano 
        ret, frame = video_capture.read()

        #AGREGA UN CONTADOR 
        contador = contador - 1
        cv2.putText(frame, str(contador), (20, 20), cv2.FONT_ITALIC, 0.5, (255, 255, 255), 1)
        # Realiza el reconocimiento facial en el cuadro actual
        face_locations = face_recognition.face_locations(frame)
        nombreResultado = compararRostros(alumnos=alumnos, rostros_localizados=face_locations,frame=frame)

        for (top, right, bottom, left) in face_locations:
            # Dibuja un cuadro alrededor de cada rostro detectado
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
            cv2.putText(frame, nombreResultado, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)
        
        if contador <= 0 :
            break
        # Codifica el cuadro en formato JPEG
        ret, jpeg = cv2.imencode('.jpg', frame)
        # Genera el flujo de video como una respuesta en formato multipart/x-mixed-replace
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')
    video_capture.release()

@app.route('/validacion')
def validacion():
    return render_template('validacion.html')

@app.route('/capture', methods=['POST'])
def capture():
    # Capturar la foto utilizando OpenCV
    camera = cv2.VideoCapture(0)
    ret, frame = camera.read()

    # Guardar la foto en el directorio estático de Flask
    photo_path = 'static/photo.jpg'
    cv2.imwrite(photo_path, frame)

    camera.release()
    return render_template('validacion.html', photo_path=photo_path , stop = True)

@app.route('/video-feed')
def video_feed():
    return Response(video_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    
    app.run(port = 3000, debug = True)