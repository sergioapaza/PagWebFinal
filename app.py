import os
from flask import Flask, render_template, redirect, request, flash
from flask import Response, session, url_for, jsonify
from flask_mysqldb import MySQL
import bcrypt #para el hashing del password
import hashlib

app = Flask(__name__)

MONEDA = 'S/. '
KEY_TOKEN = 'APR.wqc-354*'
app.secret_key = 'user54321'
app.config['MYSQL_HOST'] = "localhost"
app.config['MYSQL_USER'] = "root"
app.config['MYSQL_PASSWORD'] = ""
app.config['MYSQL_DB'] = "alpamayo"

mysql = MySQL(app)

def generate_token(id):
    token = f"{id}{KEY_TOKEN}"
    return hashlib.sha1(token.encode()).hexdigest()

def verify_token(id, token):
    return generate_token(id) == token

# ------------------ Rutas para el usuario ------------------

@app.route('/')
def index():
    return render_template ('index.html')

@app.route('/catalogo')
def catalogo():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, nombre, precio FROM productos WHERE activo = 1")
    resultados = cur.fetchall()
    MONEDA = 'S/.'
    productos = []

    for row in resultados:
        id = row[0]
        nombre = row[1]
        precio = row[2]

        imagen = f"img/productos/{id}/item.png"
        imagen_path = os.path.join('static', imagen)
        if not os.path.exists(imagen_path):
            imagen = "img/no-imagen.jpg"

        token = generate_token(id)
        productos.append({'id': id, 'nombre': nombre, 'precio': precio, 'imagen': imagen, 'token': token })
    cur.close()

    return render_template('catalogo.html', productos=productos, MONEDA=MONEDA)

@app.route('/producto/<int:id>/<token>')
def detalles_producto(id, token):
    if not verify_token(id, token):
        flash("Error al procesar la petición", "danger")
        return redirect(url_for('index'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, nombre, descripcion, precio, descuento FROM productos WHERE id = %s AND activo = 1 LIMIT 1", (id,))
    row = cur.fetchone()

    if row:
        nombre = row[1]
        descripcion = row[2]
        precio = row[3]
        descuento = row[4]
        precio_desc = precio - ((precio * descuento) / 100)
        imagen = f"img/productos/{id}/item.png"
        imagen_path = os.path.join('static', imagen)
        if not os.path.exists(imagen_path):
            imagen = "img/no-imagen.jpg"
    else:
        flash("Producto no encontrado", "warning")
        return redirect(url_for('catalogo'))

    cur.close()
    
    return render_template('detalles_producto.html', MONEDA=MONEDA, nombre=nombre, precio=precio, descuento=descuento, descripcion=descripcion, precio_desc=precio_desc, imagen=imagen, id=id)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, usuario, password, id_rol FROM clientes WHERE usuario = %s", (usuario,))
        cuenta = cur.fetchone()
        if cuenta:
            hashed_password = cuenta[2]
            if bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8')):
                session['logueado'] = True
                session['id_cliente'] = cuenta[0]
                session['id_rol'] = cuenta[3]

                if session['id_rol'] == 1:
                    return render_template('admin.html')
                else:
                    flash("Ingreso exitoso.", "success")
                    session['nombre_completo'] = f"{cuenta[1]}"
                    cur.execute("SELECT id_producto, cantidad FROM carrito WHERE id_cliente = %s", (cuenta[0],))
                    carrito = cur.fetchall()
                    session['carrito'] = [{'producto_id': item[0], 'cantidad': item[1]} for item in carrito]
            else:
                flash("Usuario o contraseña incorrectos.", "danger")
        else:
            flash("Usuario o contraseña incorrectos.", "danger")
        cur.close()
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombres = request.form['nombres']
        apellidos = request.form['apellidos']
        email = request.form['email']
        telefono = request.form['telefono']
        dni = request.form['dni']
        usuario = request.form['usuario']
        password = request.form['password']
        repassword = request.form['repassword']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM clientes WHERE usuario = %s", [usuario])
        user_exists = cur.fetchone()
        if user_exists:
            flash("El nombre de usuario ya está en uso.", "danger")
            return render_template('registro.html')
        cur.execute("SELECT * FROM clientes WHERE email = %s", [email])
        email_exists = cur.fetchone()
        if email_exists:
            flash("El email ya está en uso.", "danger")
            return render_template('registro.html')
        if password != repassword:
            flash("Las contraseñas no coinciden.", "danger")
            return render_template('registro.html')
        new_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        cur.execute("INSERT INTO clientes (nombres, apellidos, email, telefono, dni, estatus, fecha_atta, usuario, password) VALUES (%s, %s, %s, %s, %s, 1, CURRENT_TIMESTAMP, %s, %s)", (nombres, apellidos, email, telefono, dni, usuario, new_password))
        mysql.connection.commit()
        flash("Registro exitoso. Puedes iniciar sesión ahora.", "success")
        cur.close()
    return render_template('registro.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Has cerrado sesión exitosamente.", "success")
    return redirect(url_for('index'))

# ------------------ Rutas para el carrito ------------------

@app.route('/carrito')
def mostrar_carrito():
    if 'logueado' not in session:
        flash('Debes iniciar sesión para ver tu carrito.', 'warning')
        return redirect(url_for('login'))
    id_cliente = session['id_cliente']
    cur = mysql.connection.cursor()
    cur.execute("SELECT id_producto, cantidad FROM carrito WHERE id_cliente = %s", (id_cliente,))
    productos_carrito = cur.fetchall()
    carrito = []
    total_carrito = 0
    for producto_carrito in productos_carrito:
        id_producto = producto_carrito[0]
        cantidad = producto_carrito[1]
        cur.execute("SELECT id, nombre, precio FROM productos WHERE id = %s", (id_producto,))
        producto = cur.fetchone()
        if producto:
            total = producto[2] * cantidad
            carrito.append({
                'id': producto[0],
                'nombre': producto[1],
                'precio': producto[2],
                'cantidad': cantidad,
                'total': total
            })
            total_carrito += total
    cur.close()
    return render_template('carrito.html', carrito=carrito, total_carrito=total_carrito, MONEDA=MONEDA)

@app.route('/carrito/agregar', methods=['POST'])
def agregar_producto_carrito():
    if 'logueado' not in session:
        flash('Debes iniciar sesión para ver tu carrito.', 'warning')
        return redirect(url_for('login'))
    id_cliente = session['id_cliente']
    id_producto = request.form.get('id_producto')
    cantidad = request.form.get('cantidad', 1)
    cur = mysql.connection.cursor()
    cur.execute("SELECT cantidad FROM carrito WHERE id_cliente = %s AND id_producto = %s", (id_cliente, id_producto))
    producto_en_carrito = cur.fetchone()
    if producto_en_carrito:
        nueva_cantidad = producto_en_carrito[0] + int(cantidad)
        cur.execute("UPDATE carrito SET cantidad = %s WHERE id_cliente = %s AND id_producto = %s", (nueva_cantidad, id_cliente, id_producto))
    else:
        cur.execute("INSERT INTO carrito (id_cliente, id_producto, cantidad) VALUES (%s, %s, %s)", (id_cliente, id_producto, cantidad))
    mysql.connection.commit()
    cur.close()
    flash('Producto agregado al carrito.', 'success')
    return redirect(url_for('catalogo'))

@app.route('/carrito/eliminar/<int:id_producto>', methods=['POST'])
def eliminar_producto_carrito(id_producto):
    if 'logueado' not in session:
        flash('Debes iniciar sesión para modificar tu carrito.', 'warning')
        return redirect(url_for('login'))
    id_cliente = session['id_cliente']
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM carrito WHERE id_cliente = %s AND id_producto = %s", (id_cliente, id_producto))
    mysql.connection.commit()
    cur.close()
    flash('Producto eliminado del carrito.', 'success')
    return redirect(url_for('mostrar_carrito'))


@app.route('/carrito/actualizar/<int:id_producto>', methods=['POST'])
def actualizar_cantidad_producto_carrito(id_producto):
    if 'logueado' not in session:
        flash('Debes iniciar sesión para modificar tu carrito.', 'warning')
        return redirect(url_for('login'))
    
    nueva_cantidad = request.form.get('nueva_cantidad', type=int)
    
    if nueva_cantidad <= 0:
        flash('La cantidad debe ser mayor que 0.', 'danger')
        return redirect(url_for('mostrar_carrito'))

    id_cliente = session['id_cliente']
    cur = mysql.connection.cursor()

    # Actualizar la cantidad del producto en el carrito
    cur.execute("UPDATE carrito SET cantidad = %s WHERE id_cliente = %s AND id_producto = %s", (nueva_cantidad, id_cliente, id_producto))
    mysql.connection.commit()
    cur.close()

    flash('Cantidad actualizada con éxito.', 'success')
    return redirect(url_for('mostrar_carrito'))

#------------ ruta para verificaion final--------------------------
@app.route('/verif_final')
def verif_final():
    if 'logueado' not in session:
        flash('Debes iniciar sesión para proceder con el pago.', 'warning')
        return redirect(url_for('login'))
    
    id_cliente = session['id_cliente']

    # Obtener los datos del cliente
    cur = mysql.connection.cursor()
    cur.execute("SELECT nombres, apellidos, email, telefono FROM clientes WHERE id = %s", (id_cliente,))
    cliente = cur.fetchone()

    # Obtener los productos en el carrito
    cur.execute("SELECT id_producto, cantidad FROM carrito WHERE id_cliente = %s", (id_cliente,))
    productos_carrito = cur.fetchall()
    carrito = []
    total_carrito = 0
    for producto_carrito in productos_carrito:
        id_producto = producto_carrito[0]
        cantidad = producto_carrito[1]
        cur.execute("SELECT nombre, precio FROM productos WHERE id = %s", (id_producto,))
        producto = cur.fetchone()
        if producto:
            total = producto[1] * cantidad
            carrito.append({
                'nombre': producto[0],
                'precio': producto[1],
                'cantidad': cantidad,
                'total': total
            })
            total_carrito += total
    cur.close()

    return render_template('verif_final.html', carrito=carrito, total_carrito=total_carrito, MONEDA=MONEDA, cliente={
        'nombres': cliente[0],
        'apellidos': cliente[1],
        'email': cliente[2],
        'telefono': cliente[3]
    })


@app.route('/realizar_pedido', methods=['POST'])
def realizar_pedido():
    if 'logueado' not in session:
        flash('Debes iniciar sesión para realizar el pedido.', 'warning')
        return redirect(url_for('login'))

    id_cliente = session['id_cliente']
    
    # Obtener el carrito del cliente
    cur = mysql.connection.cursor()
    cur.execute("SELECT id_producto, cantidad FROM carrito WHERE id_cliente = %s", (id_cliente,))
    productos_carrito = cur.fetchall()

    # Insertar el pedido en la tabla de pedidos
    for producto_carrito in productos_carrito:
        id_producto = producto_carrito[0]
        cantidad = producto_carrito[1]
        cur.execute("SELECT precio FROM productos WHERE id = %s", (id_producto,))
        producto = cur.fetchone()
        if producto:
            total = producto[0] * cantidad
            cur.execute("INSERT INTO pedidos (id_cliente, id_producto, fecha_pedido, total) VALUES (%s, %s, NOW(), %s)", 
                        (id_cliente, id_producto, total))
    mysql.connection.commit()

    # Vaciar el carrito
    cur.execute("DELETE FROM carrito WHERE id_cliente = %s", (id_cliente,))
    mysql.connection.commit()
    cur.close()

    flash('Pedido realizado con éxito.', 'success')
    return redirect(url_for('index'))



#--------------------------------------------------------------------

# ------------------ Rutas para la Gestión de Productos ------------------


import os
from werkzeug.utils import secure_filename

@app.route('/admin/agregar-producto', methods=['GET', 'POST'])
def agregar_producto():
    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = request.form['precio']
        id_categoria = request.form['id_categoria']
        activo = 1 if 'activo' in request.form else 0
        descuento = request.form['descuento']
        
        # Guardar el producto sin imagen primero para obtener el ID
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO productos (nombre, descripcion, precio, id_categoria, activo, descuento) VALUES (%s, %s, %s, %s, %s, %s)", 
                    (nombre, descripcion, precio, id_categoria, activo, descuento))
        mysql.connection.commit()
        producto_id = cur.lastrowid  # Obtener el ID del producto recién insertado

        # Verificar si se subió una imagen
        imagen = request.files.get('imagen')
        if imagen and imagen.filename != '':
            # Crear la carpeta para el producto si no existe
            carpeta_producto = os.path.join('static', 'img', 'productos', str(producto_id))
            if not os.path.exists(carpeta_producto):
                os.makedirs(carpeta_producto)
            
            # Guardar la imagen como item.png dentro de la carpeta del producto
            imagen_path = os.path.join(carpeta_producto, 'item.png')
            imagen.save(imagen_path)

        # Actualizar el producto con la ruta de la imagen si se subió
        if imagen:
            cur.execute("UPDATE productos SET imagen = 'item.png' WHERE id = %s", (producto_id,))
            mysql.connection.commit()

        cur.close()
        
        flash("Producto agregado con éxito.", "success")
        return redirect(url_for('agregar_producto'))
    return render_template('agregar_producto.html')




@app.route('/admin/modificar-eliminar-producto', methods=['GET', 'POST'])
def modificar_eliminar_producto():
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        if 'modificar' in request.form:
            id_producto = request.form['id_producto']
            nombre = request.form['nombre']
            descripcion = request.form['descripcion']
            precio = request.form['precio']
            id_categoria = request.form['id_categoria']
            activo = 1 if 'activo' in request.form else 0
            descuento = request.form['descuento']

            # Verificar si se subió una nueva imagen
            nueva_imagen = request.files.get('nueva_imagen')
            if nueva_imagen and nueva_imagen.filename != '':
                # Crear la carpeta para el producto si no existe
                carpeta_producto = os.path.join('static', 'img', 'productos', str(id_producto))
                if not os.path.exists(carpeta_producto):
                    os.makedirs(carpeta_producto)
                
                # Guardar la imagen como item.png dentro de la carpeta del producto
                imagen_path = os.path.join(carpeta_producto, 'item.png')
                nueva_imagen.save(imagen_path)

            # Actualizar los datos del producto
            cur.execute("""
                UPDATE productos 
                SET nombre = %s, descripcion = %s, precio = %s, id_categoria = %s, activo = %s, descuento = %s
                WHERE id = %s
            """, (nombre, descripcion, precio, id_categoria, activo, descuento, id_producto))

            mysql.connection.commit()
            flash("Producto modificado con éxito.", "success")
        elif 'eliminar' in request.form:
            id_producto = request.form['id_producto']
            cur.execute("DELETE FROM productos WHERE id = %s", (id_producto,))
            mysql.connection.commit()
            flash("Producto eliminado con éxito.", "success")

    cur.execute("SELECT * FROM productos")
    productos = cur.fetchall()
    cur.close()
    return render_template('modificar_eliminar_producto.html', productos=productos)



# ------------------ Rutas para la Gestión de Usuarios ------------------

@app.route('/admin/modificar-eliminar-usuario', methods=['GET', 'POST'])
def modificar_eliminar_usuario():
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        if 'modificar' in request.form:
            id_usuario = request.form['id_usuario']
            nuevo_email = request.form['nuevo_email']
            nuevo_telefono = request.form['nuevo_telefono']
            cur.execute("UPDATE clientes SET email = %s, telefono = %s WHERE id = %s", (nuevo_email, nuevo_telefono, id_usuario))
            mysql.connection.commit()
            flash("Usuario modificado con éxito.", "success")
        elif 'eliminar' in request.form:
            id_usuario = request.form['id_usuario']
            cur.execute("DELETE FROM carrito WHERE id_cliente = %s", (id_usuario,))
            cur.execute("DELETE FROM clientes WHERE id = %s", (id_usuario,))
            mysql.connection.commit()
            flash("Usuario eliminado con éxito.", "success")
    cur.execute("SELECT id, usuario, email, telefono FROM clientes")
    usuarios = cur.fetchall()
    cur.close()
    return render_template('modificar_eliminar_usuario.html', usuarios=usuarios)

# ------------------ Ruta para Ver Pedidos ------------------

@app.route('/admin/ver-pedidos')
def ver_pedidos():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT pedidos.id, productos.nombre, clientes.usuario, pedidos.fecha_pedido, pedidos.total 
        FROM pedidos 
        JOIN productos ON pedidos.id_producto = productos.id 
        JOIN clientes ON pedidos.id_cliente = clientes.id
    """)
    pedidos = cur.fetchall()
    cur.close()
    return render_template('ver_pedidos.html', pedidos=pedidos)

if __name__ == '__main__':
    app.run(debug=True)
