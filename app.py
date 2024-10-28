from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
from fpdf import FPDF
import os
from flask import send_from_directory




app = Flask(__name__)
app.secret_key = 'mysecretkey'

# Conexión a la base de datos
def get_db():
    conn = sqlite3.connect('pos.db')
    conn.row_factory = sqlite3.Row
    return conn

# Ruta para la página de inicio
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

# Ruta para iniciar sesión
@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cur.fetchone()
    
    if user and check_password_hash(user['password'], password):
        session['user'] = user['username']
        session['role'] = user['role']
        return redirect(url_for('dashboard'))
    
    return "Usuario o contraseña incorrectos"

# Ruta para el panel principal
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('index'))
    
    role = session['role']
    if role == 'admin':
        return redirect(url_for('admin'))
    elif role == 'worker':
        return redirect(url_for('worker'))
    elif role == 'kitchen':
        return redirect(url_for('kitchen'))

@app.route('/admin')
def admin():
    if session['role'] != 'admin':
        return redirect(url_for('index'))

    conn = get_db()
    cur = conn.cursor()
    # Obtener todos los productos
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()

    # Obtener todas las cuentas generadas (bills)
    cur.execute("SELECT * FROM bills")
    bills = cur.fetchall()

    # Calcular el total de ingresos
    cur.execute("SELECT SUM(total) AS total_revenue FROM bills")
    total_revenue = cur.fetchone()['total_revenue']

    return render_template('admin.html', products=products, bills=bills, total_revenue=total_revenue)






from flask import send_file, redirect, url_for, session
from datetime import datetime
import os
from fpdf import FPDF


@app.route('/generate_report', methods=['POST'])
def generate_report():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))

    conn = get_db()
    cur = conn.cursor()

    # Obtener ventas del día
    today = datetime.now().strftime('%Y-%m-%d')
    cur.execute("SELECT * FROM bills WHERE DATE(time_created) = ?", (today,))
    bills = cur.fetchall()

    # Obtener el total de ganancias del día
    cur.execute("SELECT SUM(total) FROM bills WHERE DATE(time_created) = ?", (today,))
    total_revenue = cur.fetchone()[0] or 0.0

    # Obtener productos vendidos
    cur.execute("""
        SELECT p.name, SUM(s.quantity) AS quantity_sold
        FROM sales s
        JOIN products p ON s.product_id = p.id
        JOIN bills b ON s.bill_id = b.id
        WHERE DATE(b.time_created) = ?
        GROUP BY p.name
    """, (today,))
    products_sold = cur.fetchall()

    # Imprimir datos para depuración
    print("Productos Vendidos:", products_sold)  # Depuración

    # Crear un PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Título del reporte
    pdf.cell(200, 10, txt=f"Reporte de Ventas del {today}", ln=True, align='C')

    # Total de ganancias
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Total de Ganancias: ${total_revenue:.2f}", ln=True, align='L')

    # Tabla de ventas
    pdf.ln(10)
    pdf.set_font("Arial", size=10)
    pdf.cell(40, 10, "ID", 1)
    pdf.cell(80, 10, "Número de Mesa", 1)
    pdf.cell(40, 10, "Lugar", 1)
    pdf.cell(30, 10, "Total", 1)
    pdf.ln()

    for bill in bills:
        pdf.cell(40, 10, str(bill[0]), 1)  # ID
        pdf.cell(80, 10, str(bill[1]), 1)  # Número de Mesa
        pdf.cell(40, 10, str(bill[2]), 1)  # Lugar
        pdf.cell(30, 10, f"${bill[3]:.2f}", 1)  # Total
        pdf.ln()

    # Tabla de productos vendidos
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt="Productos Vendidos", ln=True, align='L')
    
    pdf.set_font("Arial", size=10)
    pdf.cell(120, 10, "Producto", 1)
    pdf.cell(30, 10, "Cantidad", 1)
    pdf.ln()

    for product in products_sold:
        pdf.cell(120, 10, str(product[0]), 1)  # Producto
        pdf.cell(30, 10, str(product[1]), 1)  # Cantidad
        pdf.ln()

    # Guardar el PDF
    report_path = os.path.join('static', 'reports', f'reporte_ventas_{today}.pdf')
    pdf.output(report_path)

    return send_file(report_path, as_attachment=True)



# Ruta para eliminar una cuenta
@app.route('/delete_bill', methods=['POST'])
def delete_bill():
    if session['role'] != 'admin':
        return redirect(url_for('index'))

    bill_id = request.form['bill_id']

    conn = get_db()
    cur = conn.cursor()

    # Eliminar la cuenta con el bill_id proporcionado
    cur.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
    conn.commit()

    return redirect(url_for('admin'))


# Ruta para ver una cuenta en específico (abre el PDF en una nueva pestaña)
@app.route('/view_bill', methods=['POST'])
def view_bill():
    if session['role'] != 'admin':
        return redirect(url_for('index'))

    bill_id = request.form['bill_id']

    # Generar la ruta al PDF
    pdf_filename = f"bill_{bill_id}.pdf"
    pdf_path = url_for('static', filename=f'bills/{pdf_filename}')

    # Abrir en una nueva pestaña
    return redirect(pdf_path)




# Ruta para trabajador (caja)
@app.route('/worker')
def worker():
    if session.get('role') not in ['worker', 'admin']:
        return redirect(url_for('index'))
     
    conn = get_db()
    cur = conn.cursor()

    # Obtener productos
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()

    # Obtener pedidos pendientes con nombres de productos
    cur.execute("""
        SELECT t.id, t.table_number, t.lugar, t.product_id, t.quantity, t.time_ordered, t.note, p.name AS product_name
        FROM tickets t
        JOIN products p ON t.product_id = p.id
        WHERE t.status = 'pending'
    """)
    pending_orders = cur.fetchall()

    # Obtener pedidos completados con nombres de productos
    cur.execute("""
        SELECT t.id, t.table_number, t.lugar, t.product_id, t.quantity, t.time_ordered, t.note, p.name AS product_name
        FROM tickets t
        JOIN products p ON t.product_id = p.id
        WHERE t.status = 'completed'
    """)
    completed_orders = cur.fetchall()

    # Agrupar pedidos completados por mesa y lugar
    completed_by_table = {}
    for order in completed_orders:
        key = (order['table_number'], order['lugar'])
        if key not in completed_by_table:
            completed_by_table[key] = []
        completed_by_table[key].append(order)

    # También se pueden incluir los pedidos pendientes en la vista si es necesario
    pending_by_table = {}
    for order in pending_orders:
        key = (order['table_number'], order['lugar'])
        if key not in pending_by_table:
            pending_by_table[key] = []
        pending_by_table[key].append(order)

    return render_template('worker.html', products=products, completed_by_table=completed_by_table, pending_by_table=pending_by_table)



@app.route('/add_note', methods=['POST'])
def add_note():
    try:
        data = request.get_json()
        table_number = data.get('table_number')
        lugar = data.get('lugar')
        note = data.get('note')

        conn = get_db()
        cur = conn.cursor()
        
        # Actualiza la columna 'notes' en la tabla 'ticket'
        cur.execute("""
            UPDATE tickets
            SET note = ?
            WHERE table_number = ? AND lugar = ?
        """, (note, table_number, lugar))
        
        conn.commit()

        return jsonify({'message': 'Nota añadida correctamente.'}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Error al añadir la nota.'}), 500




# Ruta para cocina
@app.route('/kitchen')
def kitchen():
    if session.get('role') not in ['kitchen', 'admin']:
        return redirect(url_for('index'))
    
    conn = get_db()
    cur = conn.cursor()

    # Obtener pedidos pendientes con nombres de productos y notas
    cur.execute("""
        SELECT t.id, t.table_number, t.lugar, t.product_id, t.quantity, t.time_ordered, p.name AS product_name, t.note
        FROM tickets t
        JOIN products p ON t.product_id = p.id
        WHERE t.status = 'pending'
    """)
    pending_orders = cur.fetchall()

    # Obtener pedidos completados con nombres de productos y notas
    cur.execute("""
        SELECT t.id, t.table_number, t.lugar, t.product_id, t.quantity, t.time_ordered, p.name AS product_name, t.note
        FROM tickets t
        JOIN products p ON t.product_id = p.id
        WHERE t.status = 'completed'
    """)
    completed_orders = cur.fetchall()

    # Agrupar pedidos pendientes por mesa y lugar
    pending_by_table = {}
    for order in pending_orders:
        key = (order['table_number'], order['lugar'])
        if key not in pending_by_table:
            pending_by_table[key] = []
        pending_by_table[key].append(order)

    # Agrupar pedidos completados por mesa y lugar
    completed_by_table = {}
    for order in completed_orders:
        key = (order['table_number'], order['lugar'])
        if key not in completed_by_table:
            completed_by_table[key] = []
        completed_by_table[key].append(order)

    # Agrupar notas por mesa y lugar
    notes_by_table = {}
    for order in pending_orders:
        key = (order['table_number'], order['lugar'])
        if key not in notes_by_table:
            notes_by_table[key] = set()  # Usar set para evitar duplicados
        if order['note']:
            notes_by_table[key].add(order['note'])

    return render_template('kitchen.html', pending_by_table=pending_by_table, completed_by_table=completed_by_table, notes_by_table=notes_by_table)







# Ruta para cerrar sesión
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))




# Agregar producto
@app.route('/add_product', methods=['POST'])
def add_product():
    name = request.form['name']
    price = float(request.form['price'])
    stock = int(request.form['stock'])

    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", (name, price, stock))
    conn.commit()
    return redirect(url_for('admin'))

# Editar producto
@app.route('/edit_product', methods=['POST'])
def edit_product():
    product_id = request.form['id']
    name = request.form['name']
    price = float(request.form['price'])
    stock = int(request.form['stock'])

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE products SET name = ?, price = ?, stock = ? WHERE id = ?", (name, price, stock, product_id))
    conn.commit()
    return redirect(url_for('admin'))

# Eliminar producto
@app.route('/delete_product', methods=['POST'])
def delete_product():
    product_id = request.form['id']

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    return redirect(url_for('admin'))




# Crear ticket con separación por mesa, lugar y hora del pedido
@app.route('/create_ticket', methods=['POST'])
def create_ticket():
    table_number = request.form.get('table_number')
    lugar = request.form.get('lugar')
    note = request.form.get('note', '')  # Obtener la nota del formulario (opcional)
    
    if not table_number or not lugar:
        abort(400, description="Número de mesa y lugar son necesarios.")
    
    conn = get_db()
    cur = conn.cursor()

    # Capturar la hora actual del pedido
    time_ordered = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Procesar cada producto en el formulario
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()

    ticket_created = False
    for product in products:
        quantity_str = request.form.get(f'quantity_{product["id"]}', '0')
        try:
            quantity = int(quantity_str) if quantity_str.isdigit() else 0
        except ValueError:
            quantity = 0

        if quantity > 0:
            # Insertar el ticket con la nota en la columna 'notes'
            cur.execute("""
                INSERT INTO tickets (product_id, quantity, table_number, lugar, time_ordered, status, note)
                VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """, (product['id'], quantity, table_number, lugar, time_ordered, note))
            ticket_created = True

    conn.commit()
    
    if not ticket_created:
        abort(400, description="No se ha creado ningún ticket.")
    
    return redirect(url_for('worker'))









@app.route('/create_bill', methods=['POST'])
def create_bill():
    table_number = request.form['table_number']
    lugar = request.form['lugar']
    conn = get_db()
    cur = conn.cursor()

    # Obtener todos los pedidos completados de la mesa y lugar
    cur.execute("SELECT * FROM tickets WHERE table_number = ? AND lugar = ? AND status = 'completed'", (table_number, lugar))
    completed_orders = cur.fetchall()

    # Obtener detalles de productos y precios
    orders = []
    total = 0
    for order in completed_orders:
        cur.execute("SELECT name, price FROM products WHERE id = ?", (order['product_id'],))
        product = cur.fetchone()
        product_name = product['name']
        price = product['price']
        quantity = order['quantity']
        total_price = quantity * price
        total += total_price
        
        orders.append({
            'product_name': product_name,
            'quantity': quantity,
            'price': price
        })

    # Registrar la cuenta en la tabla de cuentas
    cur.execute("INSERT INTO bills (table_number, lugar, total, time_created) VALUES (?, ?, ?, ?)",
                (table_number, lugar, total, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    bill_id = cur.lastrowid  # Obtener el ID de la nueva cuenta

    # Insertar en la tabla de ventas
    for order in completed_orders:
        cur.execute("INSERT INTO sales (bill_id, product_id, quantity) VALUES (?, ?, ?)",
                    (bill_id, order['product_id'], order['quantity']))

    # Eliminar los pedidos de la mesa y lugar
    cur.execute("DELETE FROM tickets WHERE table_number = ? AND lugar = ?", (table_number, lugar))

    conn.commit()
    
    # Generar el PDF
    generate_pdf_bill(table_number, lugar, bill_id, orders)
    
    return redirect(url_for('kitchen'))






@app.route('/filter_by_date', methods=['POST'])
def filter_by_date():
    selected_date = request.form['filter_date']
    # Convertir la fecha seleccionada en un objeto de datetime
    date_obj = datetime.strptime(selected_date, '%Y-%m-%d')

    # Obtener la conexión a la base de datos
    conn = get_db()
    cur = conn.cursor()

    # Consultar las cuentas de la base de datos para la fecha seleccionada
    cur.execute("SELECT * FROM bills WHERE DATE(time_created) = ?", (date_obj.date(),))
    bills = cur.fetchall()  # Aquí obtienes todas las cuentas que coinciden con la fecha

    # Filtrar las cuentas basadas en la fecha seleccionada
    filtered_bills = []
    for bill in bills:
        # bill[4] contiene la cadena de tiempo en formato 'YYYY-MM-DD HH:MM:SS'
        time_created_str = bill[4]
        # Convertir la cadena a un objeto datetime
        time_created_obj = datetime.strptime(time_created_str, '%Y-%m-%d %H:%M:%S')
        
        # Comparar solo la parte de la fecha
        if time_created_obj.date() == date_obj.date():
            filtered_bills.append(bill)

    # Calcular los ingresos totales
    total_revenue = sum(bill[3] for bill in filtered_bills)  # Suponiendo que la columna 3 es `total`

    return render_template('admin.html', bills=filtered_bills, total_revenue=total_revenue)







from reportlab.lib.pagesizes import inch
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
from textwrap import wrap  # Importar textwrap para dividir texto en líneas

def generate_pdf_bill(table_number, lugar, bill_id, orders):
    # Convertir milímetros a puntos
    width_mm = 80
    # Asumir una altura base y agregar altura dinámica según el contenido
    base_height_mm = 60
    height_mm = base_height_mm + len(orders) * 15  # Ajustar la altura en función del número de productos y líneas adicionales
    width = width_mm / 25.4 * 72
    height = height_mm / 25.4 * 72

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))

    # Configura el estilo del PDF
    c.setFont("Helvetica-Bold", 8)
    c.drawString(2, height - 15, "Ticket de Cuenta")

    # Subtítulos y datos
    c.setFont("Helvetica", 7)
    y_position = height - 25
    c.drawString(2, y_position, f"Mesa: {table_number}")
    y_position -= 10
    c.drawString(2, y_position, f"Lugar: {lugar}")
    y_position -= 10
    c.drawString(2, y_position, f"ID de Cuenta: {bill_id}")
    y_position -= 10
    c.drawString(2, y_position, f"Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    y_position -= 10
    c.drawString(2, y_position, "----------------------------------------")
    y_position -= 10

    # Encabezado de la tabla de productos
    c.setFont("Helvetica-Bold", 7)
    c.drawString(2, y_position, "Producto")
    c.drawString(75, y_position, "Precio Unidad")
    c.drawString(135, y_position, "Cantidad")
    c.drawString(190, y_position, "Total")
    y_position -= 10
    c.setFont("Helvetica", 7)
    c.drawString(2, y_position, "----------------------------------------")
    y_position -= 10

    # Listar productos y precios
    total = 0
    max_line_length = 21  # Número máximo de caracteres por línea
    line_spacing = 5  # Espacio entre líneas de texto del producto
    for order in orders:
        product_name = order['product_name']
        quantity = order['quantity']
        price = order['price']
        total_price = quantity * price
        total += total_price

        # Dividir el nombre del producto en líneas si es necesario
        wrapped_product_name = wrap(product_name, max_line_length)
        
        # Imprimir cada línea del nombre del producto
        for line in wrapped_product_name:
            c.drawString(2, y_position, line)
            y_position -= line_spacing
        
        # Ajustar la posición para los detalles de precio, cantidad y total
        c.drawString(75, y_position + line_spacing, f"${price:.2f}")  # Mantener alineado con el primer nombre de línea
        c.drawString(135, y_position + line_spacing, str(quantity))
        c.drawString(190, y_position + line_spacing, f"${total_price:.2f}")
        
        # Dejar un pequeño espacio antes del siguiente producto
        y_position -= line_spacing + 5

    # Total
    y_position -= 10
    c.setFont("Helvetica-Bold", 7)
    c.drawString(2, y_position, "----------------------------------------")
    y_position -= 10
    c.drawString(2, y_position, f"Total General: ${total:.2f}")

    # Dibujar un borde alrededor del ticket
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1)
    c.rect(1, 1, width - 2, height - 2, stroke=1, fill=0)

    c.showPage()
    c.save()
    
    buffer.seek(0)
    
    # Guardar el archivo PDF en la carpeta 'bills'
    with open(f"static/bills/bill_{bill_id}.pdf", "wb") as f:
        f.write(buffer.getvalue())









# Marcar orden como completada y registrar venta
@app.route('/complete_order', methods=['POST'])
def complete_order():
    order_id = request.form['id']

    conn = get_db()
    cur = conn.cursor()
    
    # Obtener la orden y actualizar inventario
    cur.execute("SELECT * FROM tickets WHERE id = ?", (order_id,))
    order = cur.fetchone()
    
    cur.execute("SELECT * FROM products WHERE id = ?", (order['product_id'],))
    product = cur.fetchone()
    
    new_stock = product['stock'] - order['quantity']
    cur.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, order['product_id']))
    
    # Marcar como completado
    cur.execute("UPDATE tickets SET status = 'completed' WHERE id = ?", (order_id,))
    
    conn.commit()
    return redirect(url_for('kitchen'))












# Crear la base de datos
def init_db():
    conn = get_db()
    cur = conn.cursor()
    
    # Crear tabla de usuarios
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL)''')
    
    # Crear tabla de productos
    cur.execute('''CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price REAL NOT NULL,
                    stock INTEGER NOT NULL)''')
    
    # Crear tabla de tickets
    cur.execute('''CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    quantity INTEGER,
                    table_number TEXT,
                    lugar TEXT,
                    time_ordered TEXT,
                    status TEXT DEFAULT 'pending')''')
    
    # Crear tabla de cuentas
    cur.execute('''CREATE TABLE IF NOT EXISTS bills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_number TEXT,
                    lugar TEXT,
                    total REAL,
                    time_created TEXT)''')
    
    # Crear tabla de ventas
    cur.execute('''CREATE TABLE IF NOT EXISTS sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bill_id INTEGER,
                    product_id INTEGER,
                    quantity INTEGER,
                    FOREIGN KEY (bill_id) REFERENCES bills(id),
                    FOREIGN KEY (product_id) REFERENCES products(id))''')
    
    conn.commit()
    conn.close()









if __name__ == '__main__':
    init_db()  # Iniciar la base de datos
    app.run(debug=True, host='0.0.0.0')  # Ejecutar la app en la red local
