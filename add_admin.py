import sqlite3
from werkzeug.security import generate_password_hash

# Conexión a la base de datos
def get_db():
    conn = sqlite3.connect('pos.db')
    return conn

# Agregar un usuario a la base de datos
def add_user(username, password, role):
    conn = get_db()
    cur = conn.cursor()

    # Generar hash de la contraseña
    hashed_password = generate_password_hash(password)

    # Insertar el usuario con el rol correspondiente
    cur.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, hashed_password, role))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    username = input("Introduce el nombre de usuario: ")
    password = input("Introduce la contraseña: ")

    # Asegurarse de que el rol sea válido
    role = ""
    while role not in ['admin', 'kitchen', 'worker']:
        role = input("Introduce el rol (admin, kitchen, worker): ").lower()

    add_user(username, password, role)
    print(f"Usuario '{username}' con rol '{role}' añadido con éxito.")
