import sqlite3
import os
import json
import sys

# Windows console encoding handling
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# STORAGE GASTOS - v1.0.0 (Módulo de Gastos / DDD) 🏛️🧱🧠⚖️
# Aislamiento físico de la taxonomía financiera: Cuentas y Tipos de Gastos.

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'erp_nicoletti.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db_gastos():
    """Inicializa la estructura de datos del módulo de gastos."""
    conn = get_db_connection()
    print("🧱 [GASTOS] Inicializando tablas de Cuentas y Tipos de Gastos...")
    
    # 1. Cuentas/Áreas
    conn.execute('''
        CREATE TABLE IF NOT EXISTS gastos_cuentas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre          TEXT UNIQUE NOT NULL,
            codigo          TEXT UNIQUE NOT NULL,
            emoji           TEXT,
            color_css       TEXT,
            descripcion     TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. Tipos de Gastos (Asociados a Cuentas)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS gastos_tipos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cuenta_codigo   TEXT REFERENCES gastos_cuentas(codigo),
            nombre          TEXT NOT NULL,
            tipo            TEXT DEFAULT 'EGRESO', -- 'INGRESO' | 'EGRESO' | 'OTRO'
            emoji           TEXT,
            color_css       TEXT,
            palabras_clave  TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(cuenta_codigo, nombre)
        )
    ''')
    
    # 3. Registros de Gastos Manuales (Transacciones)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS gastos_registros (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            gasto_tipo_id   INTEGER REFERENCES gastos_tipos(id),
            monto           REAL NOT NULL DEFAULT 0,
            fecha           TEXT NOT NULL, -- YYYY-MM-DD
            descripcion     TEXT,
            fuente          TEXT DEFAULT 'Efectivo',
            fecha_compra    TEXT,          -- YYYY-MM-DD
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try:
        conn.execute("ALTER TABLE gastos_registros ADD COLUMN fecha_compra TEXT")
        conn.commit()
    except Exception:
        pass
    
    # Sembrar cuentas por defecto si está vacía
    cursor = conn.execute("SELECT COUNT(*) FROM gastos_cuentas")
    if cursor.fetchone()[0] == 0:
        default_cuentas = [
            ("Lo de Karlota", "LDK", "🏪", "rgba(16, 185, 129, 0.2); color: #10b981", "Operación comercial y proveedores del local"),
            ("Joaquín", "JOA", "👤", "rgba(56, 189, 248, 0.2); color: #38bdf8", "Gastos y retiros personales de Joa"),
            ("Jorgelina", "JOR", "👩", "rgba(244, 114, 182, 0.2); color: #f472b6", "Gastos y retiros personales de Jor"),
            ("En Común", "COMUN", "🏠", "rgba(234, 179, 8, 0.2); color: #eab308", "Gastos compartidos 50/50 de convivencia")
        ]
        conn.executemany('''
            INSERT INTO gastos_cuentas (nombre, codigo, emoji, color_css, descripcion)
            VALUES (?, ?, ?, ?, ?)
        ''', default_cuentas)
        print("🌱 [GASTOS] Cuentas sembradas por defecto.")
        
    conn.commit()
    conn.close()

# ==========================================
# REPOSITORIO DE CUENTAS (gastos_cuentas)
# ==========================================

def get_cuentas():
    """Retorna todas las cuentas registradas."""
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM gastos_cuentas ORDER BY nombre").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def save_cuenta(data: dict):
    """Guarda o actualiza una cuenta."""
    conn = get_db_connection()
    try:
        cuenta_id = data.get('id')
        nombre = data.get('nombre')
        codigo = data.get('codigo').upper().strip()
        emoji = data.get('emoji', '')
        color_css = data.get('color_css', '')
        descripcion = data.get('descripcion', '')
        
        if cuenta_id:
            conn.execute('''
                UPDATE gastos_cuentas 
                SET nombre=?, codigo=?, emoji=?, color_css=?, descripcion=?
                WHERE id=?
            ''', (nombre, codigo, emoji, color_css, descripcion, cuenta_id))
            ret_id = cuenta_id
        else:
            cursor = conn.execute('''
                INSERT INTO gastos_cuentas (nombre, codigo, emoji, color_css, descripcion)
                VALUES (?, ?, ?, ?, ?)
            ''', (nombre, codigo, emoji, color_css, descripcion))
            ret_id = cursor.lastrowid
        conn.commit()
        return ret_id
    except Exception as e:
        print(f"Error guardando cuenta: {e}")
        return None
    finally:
        conn.close()

def delete_cuenta(cuenta_id):
    """Elimina una cuenta."""
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM gastos_cuentas WHERE id=?", (cuenta_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error eliminando cuenta: {e}")
        return False
    finally:
        conn.close()

# ==========================================
# REPOSITORIO DE TIPOS DE GASTOS (gastos_tipos)
# ==========================================

def get_gastos_tipos(cuenta_codigo=None):
    """Retorna los tipos de gastos, opcionalmente filtrados por cuenta."""
    conn = get_db_connection()
    try:
        if cuenta_codigo:
            rows = conn.execute("SELECT * FROM gastos_tipos WHERE cuenta_codigo = ? ORDER BY tipo, nombre", (cuenta_codigo,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM gastos_tipos ORDER BY cuenta_codigo, tipo, nombre").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_gasto_tipo_by_id(gasto_id):
    """Retorna un tipo de gasto específico por su ID."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM gastos_tipos WHERE id = ?", (gasto_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def save_gasto_tipo(data: dict):
    """Guarda o actualiza un tipo de gasto (categoría)."""
    conn = get_db_connection()
    try:
        tipo_id = data.get('id')
        cuenta_codigo = data.get('cuenta_codigo')
        nombre = data.get('nombre')
        tipo = data.get('tipo', 'EGRESO')
        emoji = data.get('emoji', '')
        color_css = data.get('color_css', '')
        palabras_clave = data.get('palabras_clave', '')
        
        if cuenta_codigo == "":
            cuenta_codigo = None
            
        if tipo_id:
            conn.execute('''
                UPDATE gastos_tipos 
                SET cuenta_codigo=?, nombre=?, tipo=?, emoji=?, color_css=?, palabras_clave=?
                WHERE id=?
            ''', (cuenta_codigo, nombre, tipo, emoji, color_css, palabras_clave, tipo_id))
            ret_id = tipo_id
        else:
            cursor = conn.execute('''
                INSERT INTO gastos_tipos (cuenta_codigo, nombre, tipo, emoji, color_css, palabras_clave)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (cuenta_codigo, nombre, tipo, emoji, color_css, palabras_clave))
            ret_id = cursor.lastrowid
        conn.commit()
        return ret_id
    except Exception as e:
        print(f"Error guardando tipo de gasto: {e}")
        return None
    finally:
        conn.close()

def delete_gasto_tipo(tipo_id):
    """Elimina un tipo de gasto."""
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM gastos_tipos WHERE id=?", (tipo_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error eliminando tipo de gasto: {e}")
        return False
    finally:
        conn.close()

# ==========================================
# REPOSITORIO DE REGISTROS DE GASTOS (gastos_registros)
# ==========================================

def get_gastos_registros(cuenta_codigo=None, anio=None, mes=None, fuente=None, q=None):
    """Retorna los registros de gastos manuales, opcionalmente filtrados por cuenta, periodo, fuente y busqueda."""
    conn = get_db_connection()
    try:
        query = '''
            SELECT r.*, t.nombre as gasto_tipo_nombre, t.emoji as gasto_tipo_emoji, t.cuenta_codigo
            FROM gastos_registros r
            JOIN gastos_tipos t ON r.gasto_tipo_id = t.id
            WHERE 1=1
        '''
        params = []
        if cuenta_codigo:
            query += " AND t.cuenta_codigo = ?"
            params.append(cuenta_codigo)
        if anio and mes:
            query += " AND r.fecha LIKE ?"
            params.append(f"{anio}-{mes}%")
        elif anio:
            query += " AND r.fecha LIKE ?"
            params.append(f"{anio}%")
        if fuente:
            if fuente == 'Efectivo':
                query += " AND (r.fuente IS NULL OR r.fuente = '' OR r.fuente = 'Manual' OR r.fuente = 'Efectivo')"
            else:
                query += " AND r.fuente = ?"
                params.append(fuente)
        if q and q.strip():
            query += " AND (COALESCE(r.descripcion, '') LIKE ? OR t.nombre LIKE ?)"
            params.extend([f"%{q.strip()}%", f"%{q.strip()}%"])
        
        query += " ORDER BY r.fecha DESC, r.id DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_gasto_registro_by_id(registro_id):
    conn = get_db_connection()
    try:
        row = conn.execute('''
            SELECT r.*, t.nombre as gasto_tipo_nombre, t.cuenta_codigo
            FROM gastos_registros r
            JOIN gastos_tipos t ON r.gasto_tipo_id = t.id
            WHERE r.id = ?
        ''', (registro_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def save_gasto_registro(data: dict):
    """Guarda o actualiza un registro de gasto."""
    conn = get_db_connection()
    try:
        registro_id = data.get('id')
        gasto_tipo_id = data.get('gasto_tipo_id')
        monto = data.get('monto')
        fecha = data.get('fecha')
        descripcion = data.get('descripcion', '')
        fuente = data.get('fuente', 'Efectivo')
        
        fecha_compra = data.get('fecha_compra') or data.get('fecha')
        if registro_id:
            conn.execute('''
                UPDATE gastos_registros
                SET gasto_tipo_id=?, monto=?, fecha=?, descripcion=?, fuente=?, fecha_compra=?
                WHERE id=?
            ''', (gasto_tipo_id, monto, fecha, descripcion, fuente, fecha_compra, registro_id))
            ret_id = registro_id
        else:
            cursor = conn.execute('''
                INSERT INTO gastos_registros (gasto_tipo_id, monto, fecha, descripcion, fuente, fecha_compra)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (gasto_tipo_id, monto, fecha, descripcion, fuente, fecha_compra))
            ret_id = cursor.lastrowid
        conn.commit()
        return ret_id
    except Exception as e:
        print(f"Error guardando registro de gasto: {e}")
        return None
    finally:
        conn.close()

def delete_gasto_registro(registro_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM gastos_registros WHERE id=?", (registro_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error eliminando registro de gasto: {e}")
        return False
    finally:
        conn.close()

def get_gastos_resumen(anio, mes):
    """Retorna un resumen de gastos agrupados por cuenta y tipo para un periodo."""
    conn = get_db_connection()
    try:
        query = '''
            SELECT t.cuenta_codigo, t.nombre as gasto_tipo_nombre, SUM(r.monto) as total
            FROM gastos_registros r
            JOIN gastos_tipos t ON r.gasto_tipo_id = t.id
            WHERE r.fecha LIKE ?
            GROUP BY t.cuenta_codigo, t.id
            ORDER BY t.cuenta_codigo, total DESC
        '''
        rows = conn.execute(query, (f"{anio}-{mes}%",)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def normalize_desc(desc):
    import re
    if not desc:
        return ""
    # Convert to lowercase
    d = desc.lower()
    # Strip leading * and k prefixes
    d = re.sub(r'^[\*k\s]+', '', d)
    # Remove cuotas like 01/06 or 1/3
    d = re.sub(r'\b\d{1,2}/\d{1,2}\b', '', d)
    # Remove long numbers (references, cards, etc.)
    d = re.sub(r'\b\d{4,}\b', '', d)
    # Remove special prefix/suffix characters
    d = re.sub(r'[\*\#\-]', '', d)
    # Strip whitespace
    return d.strip()

def buscar_clasificacion_previa(conn, descripcion_nueva, monto_nuevo=None):
    """
    Busca en el historial de gastos de la base de datos la última categoría 
    que el usuario asignó para una descripción similar.
    Retorna (gasto_tipo_id, nombre_categoria, cuenta_codigo) o None.
    """
    norm_nueva = normalize_desc(descripcion_nueva)
    if not norm_nueva:
        return None
        
    # Buscar registros ordenados por fecha descendente
    cursor = conn.execute("""
        SELECT r.gasto_tipo_id, r.descripcion, r.monto, t.nombre, t.cuenta_codigo
        FROM gastos_registros r
        JOIN gastos_tipos t ON r.gasto_tipo_id = t.id
        ORDER BY r.fecha DESC, r.id DESC
    """)
    rows = cursor.fetchall()
    
    for row in rows:
        if normalize_desc(row['descripcion']) == norm_nueva:
            # Caso especial para ESCO: el monto debe ser similar
            if "esco" in norm_nueva and monto_nuevo is not None:
                if abs(row['monto'] - monto_nuevo) > 10.0:
                    continue
            return {
                "id": row['gasto_tipo_id'],
                "nombre": row['nombre'],
                "cuenta": row['cuenta_codigo']
            }
    return None

if __name__ == "__main__":
    init_db_gastos()
