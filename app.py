from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from dotenv import load_dotenv
import os

app = Flask(__name__)

# Habilitar CORS para que Vercel pueda conectarse
CORS(app, origins=["*"])  # luego se puede restringir solo a tu dominio Vercel

load_dotenv()

CONNECTION_STRING = os.getenv("CONNECTION_STRING")

# ---------------- CONEXIÓN ----------------

def get_connection():
    return psycopg2.connect(CONNECTION_STRING)

# ---------------- UTILIDAD ----------------

def get_all_device_ids():
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT DISTINCT sensor_id FROM sensors ORDER BY sensor_id;")
        device_ids = [row[0] for row in cur.fetchall()]

        cur.close()
        conn.close()
        return device_ids

    except Exception as e:
        print("Error en get_all_device_ids:", e)
        return []

def get_sensor_data(sensor_id):
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Última lectura
        cur.execute("""
            SELECT value, created_at
            FROM sensors
            WHERE sensor_id = %s
            ORDER BY created_at DESC
            LIMIT 1;
        """, (sensor_id,))
        latest = cur.fetchone()

        # Total lecturas
        cur.execute("""
            SELECT COUNT(*) FROM sensors WHERE sensor_id = %s;
        """, (sensor_id,))
        total = cur.fetchone()[0]

        cur.close()
        conn.close()

        if not latest:
            return {"error": "No data found"}

        return {
            "sensor_id": sensor_id,
            "latest_value": latest[0],
            "latest_timestamp": latest[1].strftime('%Y-%m-%d %H:%M:%S'),
            "total_readings": total
        }

    except Exception as e:
        return {"error": str(e)}

# ---------------- RUTAS API ----------------

@app.route("/", methods=["GET"])
def status():
    return jsonify({"status": "Backend running correctly 🚀"})

@app.route("/devices", methods=["GET"])
def devices():
    ids = get_all_device_ids()
    return jsonify({"devices": ids})

@app.route("/sensor/latest/<int:sensor_id>", methods=["GET"])
def latest_sensor(sensor_id):
    data = get_sensor_data(sensor_id)
    return jsonify(data)

@app.route("/sensor/history/<int:sensor_id>", methods=["GET"])
def sensor_history(sensor_id):
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT value, created_at
            FROM sensors
            WHERE sensor_id = %s
            ORDER BY created_at DESC
            LIMIT 10;
        """, (sensor_id,))

        rows = cur.fetchall()

        cur.close()
        conn.close()

        history = [{
            "value": r[0],
            "timestamp": r[1].strftime('%Y-%m-%d %H:%M:%S')
        } for r in rows[::-1]]

        return jsonify({
            "sensor_id": sensor_id,
            "history": history
        })

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/sensor/<int:sensor_id>", methods=["POST"])
def insert_sensor(sensor_id):
    try:
        data = request.get_json()
        value = data.get("value")

        if value is None:
            return jsonify({"error": "Missing value"}), 400

        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO sensors (sensor_id, value) VALUES (%s, %s)",
            (sensor_id, value)
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "message": "Inserted successfully ✅",
            "sensor_id": sensor_id,
            "value": value
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- EJECUCIÓN ----------------

if __name__ == "__main__":
    # IMPORTANTE: en producción no uses debug=True
    app.run(host="0.0.0.0", port=5000)