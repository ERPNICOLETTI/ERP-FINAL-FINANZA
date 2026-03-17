from flask import Flask, render_template, request, jsonify, send_file
import hashlib
import sqlite3
import shutil
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from pathlib import Path

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_NAME = os.path.join(BASE_DIR, 'erp_nicoletti.db')

def get_file_hash(filepath):
    """Calcula el hash SHA-256 de un archivo para comparación exacta de contenido."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Leer en bloques para no saturar memoria con archivos grandes
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

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
            es_afip = 1 if item.get('origen') == 'ARCA' else 0
            es_calim = 1 if item.get('origen') == 'CALIM' else 0

            cursor.execute('''
                INSERT INTO facturas (numero_completo, tipo_comprobante, proveedor, fecha_emision, neto_gravado, monto_iva, monto_total, esta_en_afip, esta_en_calim)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(numero_completo) DO UPDATE SET
                    tipo_comprobante=excluded.tipo_comprobante,
                    -- Si ya tenía proveedor con CUIT (CALIM), lo conservamos, sino actualizamos
                    proveedor=CASE WHEN length(facturas.proveedor) > length(excluded.proveedor) THEN facturas.proveedor ELSE excluded.proveedor END,
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

@app.route('/api/facturas/archivados', methods=['GET'])
def list_archivados():
    """Lista todos los archivos en facturas_archivadas, incluyendo subcarpetas de proveedor."""
    files = []
    try:
        for entry in sorted(os.scandir(UPLOAD_FOLDER), key=lambda e: e.name):
            if entry.is_dir() and entry.name != 'a_subir':
                # Subcarpeta de proveedor
                for fname in sorted(os.listdir(entry.path)):
                    fpath = os.path.join(entry.path, fname)
                    if os.path.isfile(fpath):
                        size_kb = os.path.getsize(fpath) / 1024
                        files.append({
                            'nombre': fname,
                            'proveedor': entry.name,
                            'ruta': f'/static/facturas_archivadas/{entry.name}/{fname}',
                            'size_kb': round(size_kb, 1)
                        })
            elif entry.is_file():
                # Archivos en la raíz (compatibilidad con archivos viejos)
                size_kb = os.path.getsize(entry.path) / 1024
                files.append({
                    'nombre': entry.name,
                    'proveedor': '',
                    'ruta': f'/static/facturas_archivadas/{entry.name}',
                    'size_kb': round(size_kb, 1)
                })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify(files)

@app.route('/api/facturas/upload_ruta', methods=['POST'])
def upload_factura_por_ruta():
    """
    Modo ruta local (igual que GestorFacturas):
    - Recibe la ruta absoluta del archivo en el disco del servidor/usuario
    - Copia al archivo de proveedor con el nombre correcto
    - BORRA el archivo original
    """
    data = request.get_json()
    source_path = data.get('source_path', '').strip().strip('"').replace('/', os.sep)
    numero = data.get('numero_completo', '').strip()
    
    if not source_path or not numero:
        return jsonify({'error': 'Ruta y número requeridos'}), 400
    
    if not os.path.exists(source_path):
        return jsonify({'error': f'El archivo no existe en la ruta: {source_path}'}), 404
    
    if not os.path.isfile(source_path):
        return jsonify({'error': 'La ruta no apunta a un archivo'}), 400
    
    clean_numero = numero.replace('-', '').lstrip('0')
    
    conn = get_db_connection()
    all_rows = conn.execute("SELECT * FROM facturas WHERE esta_en_afip=1 OR esta_en_calim=1").fetchall()
    factura = None
    for f_row in all_rows:
        db_num = str(f_row['numero_completo'] or '').replace('-', '').lstrip('0')
        if db_num == clean_numero or db_num.endswith(clean_numero):
            factura = f_row
            break

    if factura:
        # --- LÓGICA MULTI-PÁGINA / ANEXO ---
        existing_paths = (factura['ruta_archivo'] or '').split('|')
        
        fecha_val = factura['fecha_emision'] or "00000000"
        fecha_str = str(fecha_val).replace('-', '')
        prov_val = factura['proveedor'] or "DESCONOCIDO"
        prov_nombre = prov_val.split(' - ', 1)[-1].strip() if ' - ' in prov_val else prov_val.strip()
        prov_clean = secure_filename(prov_nombre)
        numero_simple = ''.join(filter(str.isdigit, clean_numero)).lstrip('0') or clean_numero
        ext = source_path.rsplit('.', 1)[-1].lower()
        
        prov_folder = os.path.join(UPLOAD_FOLDER, prov_clean)
        os.makedirs(prov_folder, exist_ok=True)
        
        # Generar nombre único si ya hay archivos
        new_filename_base = f"{fecha_str}_{prov_clean}_{numero_simple}"
        new_filename = f"{new_filename_base}.{ext}"
        counter = 2
        
        # ADN del archivo que queremos subir
        source_hash = get_file_hash(source_path)
        
        # Smart Check con HASH: Si el archivo ya existe, comparamos ADN
        while os.path.exists(os.path.join(prov_folder, new_filename)):
            existing_file_full = os.path.join(prov_folder, new_filename)
            # Comparación exacta por Hash (ADN único del archivo)
            if source_hash == get_file_hash(existing_file_full):
                os.remove(source_path) # Borramos el origen para limpiar
                conn.close()
                return jsonify({
                    'success': True, 
                    'status': 'ARCHIVADO', 
                    'msg': 'Este archivo ya estaba archivado (ADN idéntico). Se limpió el origen.',
                    'path': factura['ruta_archivo']
                })
            
            new_filename = f"{new_filename_base}_{counter}.{ext}"
            counter += 1
            
        dest_path = os.path.join(prov_folder, new_filename)
        
        try:
            shutil.copy2(source_path, dest_path)   # Copia al destino
            os.remove(source_path)                 # Borra el original
        except PermissionError:
            conn.close()
            return jsonify({'error': 'El archivo está abierto por otro programa. Cerralo e intentá de nuevo.'}), 409
        except Exception as e:
            conn.close()
            return jsonify({'error': f'Error al mover el archivo: {str(e)}'}), 500
        
        ruta_nueva = f"/static/facturas_archivadas/{prov_clean}/{new_filename}"
        
        # Si ya había archivos, concatenamos con |
        if factura['estado_proceso'] == 'ARCHIVADO' and factura['ruta_archivo']:
            final_ruta_db = f"{factura['ruta_archivo']}|{ruta_nueva}"
            msg_succ = f'Página/archivo ADJUNTO correctamente a la factura. Original borrado.'
        else:
            final_ruta_db = ruta_nueva
            msg_succ = f'Factura archivada y original BORRADO correctamente.'
            # Si era un pendiente (A_SUBIR), limpiar
            conn.execute("DELETE FROM facturas WHERE estado_proceso='A_SUBIR' AND REPLACE(numero_completo,'-','')=?", (clean_numero,))

        conn.execute('UPDATE facturas SET ruta_archivo = ?, estado_proceso = ? WHERE id = ?', (final_ruta_db, 'ARCHIVADO', factura['id']))
        conn.commit()
        fecha_final = factura['fecha_emision']
        conn.close()
        return jsonify({'success': True, 'status': 'ARCHIVADO', 'path': final_ruta_db, 'fecha': fecha_final, 'msg': msg_succ})
    else:
        # No encontrada -> mover a a_subir
        new_filename = secure_filename(f"A_SUBIR_{clean_numero}_{os.path.basename(source_path)}")
        dest_path = os.path.join(UPLOAD_FOLDER, 'a_subir', new_filename)
        try:
            shutil.copy2(source_path, dest_path)
            os.remove(source_path)
        except Exception as e:
            conn.close()
            return jsonify({'error': str(e)}), 500
        ruta_web = f"/static/facturas_archivadas/a_subir/{new_filename}"
        conn.execute('''INSERT INTO facturas (numero_completo, esta_en_afip, esta_en_calim, estado_proceso, ruta_archivo)
            VALUES (?, 0, 0, 'A_SUBIR', ?)
            ON CONFLICT(numero_completo) DO UPDATE SET ruta_archivo=excluded.ruta_archivo, estado_proceso='A_SUBIR'
        ''', (clean_numero, ruta_web))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'status': 'A_SUBIR', 'path': ruta_web,
                        'msg': 'No encontrado en ARCA/CALIM. Movido a bandeja de pendientes.'})

@app.route('/api/facturas/upload', methods=['POST'])
def upload_factura_image():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    numero = request.form.get('numero_completo')
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file and numero:
        clean_numero = numero.replace('-', '').lstrip('0')
        
        conn = get_db_connection()

        # Buscar la factura cuyo número limpio TERMINA en lo que ingresó el usuario
        all_rows = conn.execute("SELECT * FROM facturas WHERE esta_en_afip=1 OR esta_en_calim=1").fetchall()
        factura = None
        for f_row in all_rows:
            db_num = str(f_row['numero_completo'] or '').replace('-', '').lstrip('0')
            if db_num == clean_numero or db_num.endswith(clean_numero):
                factura = f_row
                break
        
        if factura:
            # --- LÓGICA MULTI-PÁGINA ---
            fecha_val = factura['fecha_emision'] or "00000000"
            fecha_str = str(fecha_val).replace('-', '')
            prov_val = factura['proveedor'] or "DESCONOCIDO"
            prov_nombre = prov_val.split(' - ', 1)[-1].strip() if ' - ' in prov_val else prov_val.strip()
            prov_clean = secure_filename(prov_nombre)
            numero_simple = ''.join(filter(str.isdigit, clean_numero)).lstrip('0') or clean_numero
            ext = file.filename.rsplit('.', 1)[-1].lower()
            
            prov_folder = os.path.join(UPLOAD_FOLDER, prov_clean)
            os.makedirs(prov_folder, exist_ok=True)
            
            new_filename_base = f"{fecha_str}_{prov_clean}_{numero_simple}"
            new_filename = f"{new_filename_base}.{ext}"
            counter = 2
            
            # Smart Check para Upload clásico
            while os.path.exists(os.path.join(prov_folder, new_filename)):
                existing_file_full = os.path.join(prov_folder, new_filename)
                if file.content_length > 0 and file.content_length == os.path.getsize(existing_file_full):
                    conn.close()
                    return jsonify({'success': True, 'msg': 'El archivo ya existe para esta factura. Ignorado por duplicidad.', 'path': factura['ruta_archivo']})
                
                new_filename = f"{new_filename_base}_{counter}.{ext}"
                counter += 1
            
            file_path = os.path.join(prov_folder, new_filename)
            file.save(file_path)
            
            ruta_nueva = f"/static/facturas_archivadas/{prov_clean}/{new_filename}"
            
            if factura['estado_proceso'] == 'ARCHIVADO' and factura['ruta_archivo']:
                final_ruta_db = f"{factura['ruta_archivo']}|{ruta_nueva}"
                msg_succ = 'Archivo ADJUNTO a la factura correctamente.'
            else:
                final_ruta_db = ruta_nueva
                msg_succ = 'Factura vinculada y ARCHIVADA correctamente.'
                conn.execute("DELETE FROM facturas WHERE estado_proceso='A_SUBIR' AND REPLACE(numero_completo,'-','')=?", (clean_numero,))

            conn.execute('UPDATE facturas SET ruta_archivo = ?, estado_proceso = ? WHERE id = ?', (final_ruta_db, 'ARCHIVADO', factura['id']))
            conn.commit()
            fecha_final = factura['fecha_emision']
            conn.close()
            return jsonify({'success': True, 'status': 'ARCHIVADO', 'path': final_ruta_db, 'fecha': fecha_final, 'msg': msg_succ})
        else:
            # Factura NO existe -> A Subir
            new_filename = secure_filename(f"A_SUBIR_{clean_numero}_{file.filename}")
            file_path = os.path.join(UPLOAD_FOLDER, 'a_subir', new_filename)
            file.save(file_path)
            ruta_web = f"/static/facturas_archivadas/a_subir/{new_filename}"
            conn.execute('''
                INSERT INTO facturas (numero_completo, esta_en_afip, esta_en_calim, estado_proceso, ruta_archivo)
                VALUES (?, 0, 0, 'A_SUBIR', ?)
                ON CONFLICT(numero_completo) DO UPDATE SET ruta_archivo=excluded.ruta_archivo, estado_proceso='A_SUBIR'
            ''', (clean_numero, ruta_web))
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'status': 'A_SUBIR', 'path': ruta_web, 'msg': 'Factura no encontrada en los sistemas. Moviendo a bandeja de CALIM.'})
            
    return jsonify({'error': 'Invalid request'}), 400 # Corrected: Removed extra line 'uest'}), 400'


@app.route('/api/preview')
def preview_local_file():
    """
    Sirve un archivo local para previsualización en el browser.
    Bypassea la restricción de seguridad de archivos locales del navegador.
    """
    path = request.args.get('path', '').strip().strip('"').replace('/', os.sep)
    if not path or not os.path.exists(path) or not os.path.isfile(path):
        return "Archivo no encontrado", 404
        
    try:
        return send_file(path)
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    init_db()
    # Ejecuta el servidor Flask en el puerto 5001
    app.run(debug=True, host='0.0.0.0', port=5001)
