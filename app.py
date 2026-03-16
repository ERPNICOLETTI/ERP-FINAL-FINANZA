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
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS payway_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            compra_date TEXT,
            presentacion_date TEXT,
            lote INTEGER,
            cupon TEXT,
            marca TEXT,
            monto_bruto REAL,
            estado TEXT DEFAULT 'pendiente',
            matching_tx_id INTEGER,
            FOREIGN KEY(matching_tx_id) REFERENCES transactions(id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS facturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_completo TEXT UNIQUE,
            tipo_comprobante TEXT,
            proveedor TEXT,
            fecha_emision TEXT,
            neto_gravado REAL,
            monto_iva REAL,
            monto_total REAL,
            esta_en_afip INTEGER DEFAULT 0,
            esta_en_calim INTEGER DEFAULT 0,
            estado_proceso TEXT DEFAULT 'PENDIENTE',
            ruta_archivo TEXT
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
@app.route('/api/payway', methods=['GET'])
def get_payway():
    try:
        conn = get_db_connection()
        records = conn.execute('SELECT * FROM payway_records ORDER BY compra_date DESC').fetchall()
        conn.close()
        return jsonify([dict(row) for row in records])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/payway', methods=['POST'])
def add_payway_batch():
    try:
        data = request.get_json() # List of records
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for item in data:
            # Check for duplicates (same batch, coupon and date)
            exists = cursor.execute('SELECT id FROM payway_records WHERE lote = ? AND cupon = ? AND compra_date = ?', 
                                  (item.get('lote'), item.get('cupon'), item.get('compra_date'))).fetchone()
            if not exists:
                cursor.execute('''
                    INSERT INTO payway_records (compra_date, presentacion_date, lote, cupon, marca, monto_bruto)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    item.get('compra_date'),
                    item.get('presentacion_date'),
                    item.get('lote'),
                    item.get('cupon'),
                    item.get('marca'),
                    item.get('monto_bruto')
                ))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/facturas', methods=['POST'])
def add_facturas_batch():
    try:
        data = request.get_json() # List of records
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for item in data:
            # Determinar banderas basadas en el origen
            es_afip = 1 if item.get('origen') == 'AFIP' else 0
            es_calim = 1 if item.get('origen') == 'CALIM' else 0

            cursor.execute('''
                INSERT INTO facturas (numero_completo, tipo_comprobante, proveedor, fecha_emision, neto_gravado, monto_iva, monto_total, esta_en_afip, esta_en_calim)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(numero_completo, proveedor) DO UPDATE SET
                    tipo_comprobante=excluded.tipo_comprobante,
                    fecha_emision=excluded.fecha_emision,
                    neto_gravado=excluded.neto_gravado,
                    monto_iva=excluded.monto_iva,
                    monto_total=excluded.monto_total,
                    esta_en_afip=CASE WHEN excluded.esta_en_afip=1 THEN 1 ELSE facturas.esta_en_afip END,
                    esta_en_calim=CASE WHEN excluded.esta_en_calim=1 THEN 1 ELSE facturas.esta_en_calim END,
                    estado_proceso=CASE 
                        WHEN facturas.ruta_archivo IS NOT NULL THEN 'ARCHIVADO' 
                        ELSE facturas.estado_proceso 
                    END
            ''', (
                item.get('numero_completo'),
                item.get('tipo_comprobante'),
                item.get('proveedor'),
                item.get('fecha_emision'),
                item.get('neto_gravado'),
                item.get('monto_iva'),
                item.get('monto_total'),
                es_afip,
                es_calim
            ))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/facturas', methods=['DELETE'])
def clear_facturas():
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM facturas')
        conn.commit()
        conn.close()
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/facturas', methods=['GET'])
def get_facturas():
    try:
        conn = get_db_connection()
        records = conn.execute('SELECT * FROM facturas ORDER BY fecha_emision DESC').fetchall()
        conn.close()
        return jsonify([dict(row) for row in records])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

import os
from werkzeug.utils import secure_filename
import shutil

UPLOAD_FOLDER = os.path.join('static', 'facturas_archivadas')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'a_subir'), exist_ok=True)

@app.route('/api/facturas/upload', methods=['POST'])
def upload_factura_image():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    numero = request.form.get('numero_completo')
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file and numero:
        # Normalizamos el numero que viene del formulario para buscar
        clean_numero = numero.replace('-', '').lstrip('0')
        
        conn = get_db_connection()
        # Buscamos coincidencias usando LIKE para atrapar variaciones de ceros o guiones
        factura = conn.execute("SELECT * FROM facturas WHERE REPLACE(numero_completo, '-', '') LIKE ?", (f"%{clean_numero}",)).fetchone()
        
        # Doble verificación para evitar falsos positivos
        if factura:
            db_numero = factura['numero_completo'].replace('-', '').lstrip('0')
            if db_numero != clean_numero:
                factura = None

        if factura:
            # Factura EXISTE en DB (AFIP o CALIM) -> Archivamos
            fecha_val = factura['fecha_emision'] or "00000000"
            fecha_str = str(fecha_val).replace('-', '')
            
            prov_val = factura['proveedor'] or "DESCONOCIDO"
            prov_text = prov_val.split('-')[-1].strip() if '-' in prov_val else prov_val.strip()
            prov_clean = secure_filename(prov_text[0:20])
            
            num_clean = clean_numero # Usamos el limpio
            
            ext = file.filename.rsplit('.', 1)[-1].lower()
            new_filename = f"{fecha_str}_{prov_clean}_{num_clean}.{ext}"
            
            file_path = os.path.join(UPLOAD_FOLDER, new_filename)
            file.save(file_path)
            
            ruta_web = f"/static/facturas_archivadas/{new_filename}"
            estado = "ARCHIVADO" 
            
            conn.execute('UPDATE facturas SET ruta_archivo = ?, estado_proceso = ? WHERE id = ?', (ruta_web, estado, factura['id']))
            conn.commit()
            fecha_final = factura['fecha_emision']
            conn.close()
            return jsonify({
                'success': True, 
                'status': estado, 
                'path': ruta_web, 
                'fecha': fecha_final, # Devolver fecha para que el frontend avise
                'msg': 'Factura vinculada y ARCHIVADA correctamente.'
            })
        else:
            # Factura NO EXISTE en DB (Ni AFIP ni CALIM) -> A Subir a CALIM
            new_filename = secure_filename(f"A_SUBIR_{numero}_{file.filename}")
            file_path = os.path.join(UPLOAD_FOLDER, 'a_subir', new_filename)
            file.save(file_path)
            
            ruta_web = f"/static/facturas_archivadas/a_subir/{new_filename}"
            
            # Guardamos el registro fantasma para que quede pendiente
            conn.execute('''
                INSERT INTO facturas (numero_completo, esta_en_afip, esta_en_calim, estado_proceso, ruta_archivo)
                VALUES (?, 0, 0, 'A_SUBIR', ?)
            ''', (numero, ruta_web))
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'status': 'A_SUBIR', 'path': ruta_web, 'msg': 'Factura no encontrada en los sistemas. Moviendo a bandeja de CALIM.'})
            
    return jsonify({'error': 'Invalid request'}), 400

if __name__ == '__main__':
    init_db()
    # Ejecuta el servidor Flask en el puerto 5001
    app.run(debug=True, host='0.0.0.0', port=5001)
