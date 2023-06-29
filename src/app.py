from flask import Flask, request, render_template, redirect, url_for, flash, send_file, Response, session
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

global es_alumno, capturar, frame_capturado, alumno
es_alumno = 0
capturar = 0
frame_capturado = None
alumno = None

@app.route('/')
def Index():
    cursor = mydb.cursor()
    # Realizar la consulta utilizando JOIN para combinar las tablas
    query = '''
        SELECT alumnos.nombre, alumnos.correo, publicaciones.contenido
        FROM alumnos
        JOIN publicaciones ON alumnos.idAlumno = publicaciones.idAlumno
    '''
    cursor.execute(query)

    # Obtener los resultados de la consulta
    resultados = cursor.fetchall()
    # Cerrar el cursor
    cursor.close()
    # Renderizar la plantilla HTML y pasar los resultados
    return render_template('index.html', publicaciones=resultados)

@app.route('/registro-publicacion')
def page_registro_publicacion():
    return render_template('registro-publicacion.html')

@app.route('/agregar-publicacion',methods = ['POST'])
def agregar_publicacion():
    global alumno
    if request.method == 'POST':
        
        idAlumno = alumno[0]
        contenido = request.form['contenido']

        cursor = mydb.cursor()
        query = "INSERT INTO publicaciones (idAlumno,contenido) VALUES (%s, %s)"
        values = (idAlumno,contenido)
        cursor.execute(query,values)
        mydb.commit()
        cursor.close()
        flash ("Se ha registrado de manera correcta!")
    return render_template('registro-publicacion.html')

@app.route('/registro-usuario')
def registro_usuario():
    return render_template('registro-usuario.html')

@app.route('/agregar-usuario', methods = ['POST', 'GET'])
def agregar_usuario():
    global frame_capturado,capturar
    if request.method == 'POST':

        if request.form.get('Capturar') == 'Capturar':
            capturar = 1
            flash('Se esta capturando la foto')
        else:
            #clear 
            capturar = 0
            if request.form.get('Eliminar') == 'Eliminar':
                frame_capturado = None
                flash('Volver a tomar una foto')
            else:

                if frame_capturado is None:
                    flash('No ha capturado una foto para el registro de {}'.format(nombre))
                    return render_template('registro-usuario.html')

                # Encuentra todas las caras en la imagen
                face_locations = face_recognition.face_locations(frame_capturado)

                if len(face_locations) == 1:
                    # Codifica las características faciales de la cara encontrada
                    face_encoding = face_recognition.face_encodings(frame_capturado, face_locations)[0]
                    imagen_encoding_bytes = face_encoding.tostring()

                    ret, imagen_jpeg = cv2.imencode('.jpg', frame_capturado)
                    imagen_bytes = imagen_jpeg.tobytes()
                    
                    nombre = request.form['nombre']
                    apellido = request.form['apellido']
                    correo = request.form['correo']
                    codigo = request.form['codigo']
                    cursor = mydb.cursor()

                    query = "INSERT INTO alumnos (nombre,apellido,correo,codigo,imagen, imagenEncoding) VALUES (%s, %s, %s,%s, %s, %s)"
                    values = (nombre,apellido, correo, codigo, imagen_bytes, imagen_encoding_bytes)
                    cursor.execute(query,values)
                    mydb.commit()
                    cursor.close()
                    flash('Usuario agregado de manera correcta : {}'.format(nombre))

                    #limpiar frame
                    frame_capturado = None
                else:
                    flash ("Error al obtener las caracteristicas del rostro")
                
            
            
        
    return render_template('registro-usuario.html')

@app.route('/login', methods=['POST','GET'])
def login():
    global alumno, es_alumno
    fecha = str(datetime.datetime.now())
    if es_alumno & (alumno != None):

        cursor = mydb.cursor()
        idAlumno = alumno[0]

        query = "INSERT INTO logs (idAlumno, fecha) VALUES (%s,%s)"
        values = (idAlumno,fecha)
        cursor.execute(query,values)
        mydb.commit()
        cursor.close()

        session['logged_in'] = True
        return redirect(url_for('dashboard'))
    else:
        flash("Error de autenticación")
        return render_template('loginFace.html')

@app.route('/logout', methods=['POST','GET'])
def logout():
    global alumno, es_alumno
    es_alumno = 0
    alumno = None
    session.pop('logged_in', None)
    return redirect(url_for('Index'))

@app.route('/dashboard')
def dashboard():
    global alumno
    return render_template('dashboard.html', alumno = alumno)

def getAlumnos():
    cursor = mydb.cursor(buffered=True)
    cursor.execute("SELECT idAlumno,nombre,apellido,correo, codigo,imagen,imagenEncoding FROM alumnos")
    alumnos = cursor.fetchall()
    cursor.close()
    return alumnos

def compararRostros(alumnos, rostros_localizados, frame):
    global es_alumno, alumno
    nombre = "desconocido"
    if len(rostros_localizados) >= 1 :
        face_encoding = face_recognition.face_encodings(frame, rostros_localizados)[0]
        for alumno_data in alumnos:
            stored_encoding = np.frombuffer(alumno_data[6], dtype=np.float64)
                
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

def video_stream_registro():
    global frame_capturado, capturar

    video_capture = cv2.VideoCapture(0)
    video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 250)
    video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 250)

    while True:
        # Captura los cuadros de video #Frame es tipo numpy.ndarray y ret es un Booleano 
        ret, frame = video_capture.read()
        
        # Codifica el cuadro en formato JPEG
        ret, jpeg = cv2.imencode('.jpg', frame)
        # Genera el flujo de video como una respuesta en formato multipart/x-mixed-replace
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')
        
        if capturar :
            frame_capturado = frame
            break
    video_capture.release()

def mostrar_imagen():
    global alumno
    image_bytes =alumno[5]
    if image_bytes:
        yield (b'Content-Type: image/jpeg\r\n\r\n' + image_bytes + b'\r\n\r\n')

@app.route('/login-face')
def login_render():
    return render_template('loginFace.html')


@app.route('/video-feed')
def video_feed():
    return Response(video_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video-feed-registro')
def video_feed_registro():
    return Response(video_stream_registro(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/imagen-feed')
def imagen_feed():
    return Response(mostrar_imagen(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    
    app.run(port = 3000, debug = True)