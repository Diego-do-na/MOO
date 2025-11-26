from flask import Flask, request, jsonify, render_template
import psycopg2
from dotenv import load_dotenv
import os
# Eliminamos: import requests

app = Flask(__name__)

# Load environment variables from .env
load_dotenv()

# Fetch variables
CONNECTION_STRING = os.getenv("CONNECTION_STRING")

# --- Funciones de Utilidad ---

def get_connection():
    """Establishes a connection to the PostgreSQL database."""
    return psycopg2.connect(CONNECTION_STRING)

# --- Funciones Auxiliares para el Dashboard ---

def get_all_device_ids():
    """Fetches all unique sensor IDs from the database (table: sensors)."""
    conn = None
    device_ids = []
    try:
        conn = get_connection()
        cur = conn.cursor()
        # Query para obtener todos los IDs únicos de la tabla sensors
        cur.execute("SELECT DISTINCT sensor_id FROM sensors ORDER BY sensor_id;")
        device_ids = [row[0] for row in cur.fetchall()]
        cur.close()
    except psycopg2.Error as e:
        print(f"Database error fetching IDs: {e}")
        return []
    finally:
        if conn:
            conn.close()
    return device_ids

def get_data_from_api(sensor_id):
    """
    Función modificada para OBTENER DATOS DIRECTAMENTE DE LA DB.
    Elimina la dependencia de hacer llamadas HTTP a tu propia URL externa.
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # 1. Obtener la última lectura para el resumen del dashboard
        cur.execute("""
            SELECT value, created_at
            FROM sensors
            WHERE sensor_id = %s
            ORDER BY created_at DESC
            LIMIT 1;
        """, (sensor_id,))
        row = cur.fetchone()
        
        # 2. (Opcional) Obtener el conteo total de lecturas
        # Esto es más eficiente que contar todas las filas en la tabla
        cur.execute("""
            SELECT count(*) FROM sensors WHERE sensor_id = %s;
        """, (sensor_id,))
        total_readings = cur.fetchone()[0]

        cur.close()
        
        if not row:
            return {"error": "No readings found in DB"}

        # Devolvemos el formato JSON esperado por el dashboard.html
        return {
            "sensor_id": sensor_id,
            "latest_value": row[0],
            "latest_timestamp": row[1].strftime('%Y-%m-%d %H:%M:%S'),
            "total_readings": total_readings
        }
        
    except Exception as e:
        return {"error": f"DB access error for sensor {sensor_id}: {str(e)}"}
        
    finally:
        if conn:
            conn.close()

# --- NUEVA RUTA: Dashboard IoT ---

@app.route("/dashboard")
def dashboard():
    # 1. Obtener la lista de todos los dispositivos de la DB
    all_device_ids = get_all_device_ids()
    
    # 2. Obtener el ID seleccionado del parámetro de consulta (Query parameter)
    default_id = all_device_ids[0] if all_device_ids else None
    selected_id_str = request.args.get("device_id", default=str(default_id))
    
    dashboard_data = {}
    is_all = (selected_id_str.lower() == 'all')
    
    # 3. Determinar qué datos consultar
    if is_all:
        # Si se selecciona "Todos", llama a la función que accede DIRECTAMENTE a la DB por cada ID
        for device_id in all_device_ids:
            data = get_data_from_api(device_id)
            dashboard_data[device_id] = data
            
    elif selected_id_str and selected_id_str.isdigit():
        # Si se selecciona un ID específico, llama a la función DIRECTAMENTE a la DB
        selected_id = int(selected_id_str)
        data = get_data_from_api(selected_id)
        dashboard_data[selected_id] = data
        
    # 4. Renderizar el template
    return render_template(
        "dashboard.html",
        all_device_ids=all_device_ids, 
        selected_id=selected_id_str,   
        dashboard_data=dashboard_data, 
        is_all=is_all                  
    )

@app.route('/')
def home():
    return 'Hello, World!'
# ... (Otras rutas como /about, /sensor, /sensor/<int:sensor_id>, /pagina permanecen iguales)
# ... [Incluye aquí el resto de tu código base, como 'insert_sensor_value', 'get_sensor', etc.]
@app.route('/about')
def about():
    return 'About'

@app.route('/sensor')
def sensor():
    try:
        # Connect to the database
        connection = psycopg2.connect(
            CONNECTION_STRING
        )
        print("Connection successful!")
        
        # Create a cursor to execute SQL queries
        cursor = connection.cursor()
        
        # Example query
        cursor.execute("SELECT NOW();")
        result = cursor.fetchone()
        print("Current Time:", result)
        
        # Close the cursor and connection
        cursor.close()
        connection.close()
        print("Connection closed.")
        
        return f"Sensor endpoint OK — Current time: {result[0]}"
    
    except Exception as e:
        print(f"Failed to connect: {e}")
        return f"Database connection failed: {e}"

@app.route("/sensor/<int:sensor_id>", methods=["POST"])
def insert_sensor_value(sensor_id):
    value = request.args.get("value", type=float)
    if value is None:
        return jsonify({"error": "Missing 'value' query parameter"}), 400

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Insert into sensors table
        cur.execute(
            "INSERT INTO sensors (sensor_id, value) VALUES (%s, %s)",
            (sensor_id, value)
        )
        conn.commit()

        return jsonify({
            "message": "Sensor value inserted successfully",
            "sensor_id": sensor_id,
            "value": value
        }), 201

    except psycopg2.Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if 'conn' in locals():
            conn.close()
@app.route('/pagina')
def pagina():
    return render_template("pagina.html",user="BigH")

@app.route("/sensor/<int:sensor_id>")
def get_sensor(sensor_id):
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Get the latest 10 values
        cur.execute("""
            SELECT value, created_at
            FROM sensors
            WHERE sensor_id = %s
            ORDER BY created_at DESC
            LIMIT 10;
        """, (sensor_id,))
        rows = cur.fetchall()

        # Convert to lists for graph
        values = [r[0] for r in rows][::-1]        # reverse for chronological order
        timestamps = [r[1].strftime('%Y-%m-%d %H:%M:%S') for r in rows][::-1]
        
        return render_template("sensor.html", sensor_id=sensor_id, values=values, timestamps=timestamps, rows=rows)

    except Exception as e:
        return f"<h3>Error: {e}</h3>"

    finally:
        if 'conn' in locals():
            conn.close()