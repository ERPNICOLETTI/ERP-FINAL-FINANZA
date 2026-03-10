import sqlite3
import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_NAME = os.path.join(BASE_DIR, 'erp_nicoletti.db')

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Mantenemos la misma estructura de la base de datos de Electron
    conn.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY,
            entity TEXT,
            account TEXT,
            category TEXT,
            type TEXT,
            amount REAL,
            desc TEXT,
            date TEXT,
            groupId INTEGER,
            currency TEXT DEFAULT 'ARS'
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    try:
        conn = get_db_connection()
        transactions = conn.execute('SELECT * FROM transactions ORDER BY id DESC').fetchall()
        conn.close()
        return jsonify([dict(row) for row in transactions])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/transactions', methods=['POST'])
def add_transaction():
    try:
        data = request.get_json()
        conn = get_db_connection()
        
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO transactions (id, entity, account, category, type, amount, desc, date, groupId, currency)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('id'),
            data.get('entity'),
            data.get('account'),
            data.get('category'),
            data.get('type'),
            data.get('amount'),
            data.get('desc'),
            data.get('date'),
            data.get('groupId'),
            data.get('currency', 'ARS')
        ))
        
        conn.commit()
        last_id = cursor.lastrowid
        conn.close()
        
        return jsonify({'id': last_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/transactions/<int:id>', methods=['DELETE'])
def delete_transaction(id):
    try:
        group_id = request.args.get('groupId')
        conn = get_db_connection()
        
        if group_id and group_id != 'null':
            conn.execute('DELETE FROM transactions WHERE groupId = ?', (group_id,))
        else:
            conn.execute('DELETE FROM transactions WHERE id = ?', (id,))
            
        conn.commit()
        conn.close()
        
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    # Ejecuta el servidor Flask en el puerto 5001
    app.run(debug=True, host='0.0.0.0', port=5001)
