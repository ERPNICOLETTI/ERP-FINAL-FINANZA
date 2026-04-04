import sqlite3
import json
import os
import logging

# STORAGE BANCOS - v4.0 GOLDEN MASTER 🏦🧱🧠⚖️
# Diseño Híbrido: Columnas Duras + metadata_cruda (JSON) + path_archivo

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'erp_nicoletti.db')


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db_bancos():
    """Crea las tablas del dominio Bancos con diseño híbrido v4.0."""
    conn = get_db_connection()
    print("🧱 [BANCOS] Construyendo tablas Golden Master (Híbrido)...")

    # [CAUTION] Si ya existe, se intentará migrar o recrear. 
    # El usuario ha solicitado una limpieza pre-test.
    conn.execute('DROP TABLE IF EXISTS bancos_movimientos')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bancos_movimientos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            banco           TEXT,
            cuenta          TEXT,
            fecha           TEXT,
            descripcion     TEXT,
            tipo_movimiento TEXT,
            importe         REAL DEFAULT 0,
            saldo           REAL,
            path_archivo    TEXT, -- [NUEVO v4.0]
            hash_archivo    TEXT,
            metadata_cruda  TEXT DEFAULT '{}',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(banco, cuenta, fecha, descripcion, importe, saldo)
        )
    ''')

    conn.commit()
    conn.close()


def save_movimiento_banco(lista_movimientos: list, hash_archivo: str = None):
    """Guarda masivamente movimientos bancarios con volcado híbrido v4.0. Retorna (agregados, last_id)."""
    conn = get_db_connection()
    agregados = 0
    last_id = None
    try:
        for b in lista_movimientos:
            columnas_duras = {
                'banco', 'cuenta', 'fecha', 'descripcion',
                'tipo_movimiento', 'importe', 'saldo', 'hash_archivo', 'path_archivo'
            }
            metadata = {k: v for k, v in b.items() if k not in columnas_duras}

            try:
                cursor = conn.execute('''
                    INSERT OR IGNORE INTO bancos_movimientos (
                        banco, cuenta, fecha, descripcion, tipo_movimiento,
                        importe, saldo, hash_archivo, path_archivo, metadata_cruda
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    b.get('banco'), b.get('cuenta', 'SIN_ASIGNAR'),
                    b.get('fecha'), b.get('descripcion'),
                    b.get('tipo_movimiento', b.get('codigo_movimiento', 'MOV')),
                    b.get('importe', 0), b.get('saldo'),
                    b.get('hash_archivo', hash_archivo),
                    b.get('path_archivo'),
                    json.dumps(metadata, ensure_ascii=False, default=str)
                ))
                
                row_id = cursor.lastrowid
                
                # Fallback on IGNORE
                if row_id == 0 or row_id is None:
                    res = conn.execute('''
                        SELECT id FROM bancos_movimientos 
                        WHERE banco = ? AND cuenta = ? AND fecha = ? AND descripcion = ? AND importe = ? AND saldo = ?
                    ''', (b.get('banco'), b.get('cuenta', 'SIN_ASIGNAR'), b.get('fecha'), b.get('descripcion'), b.get('importe', 0), b.get('saldo'))).fetchone()
                    if res: row_id = res['id']

                if cursor.rowcount > 0:
                    agregados += 1
                
                last_id = row_id

            except sqlite3.IntegrityError:
                pass  # Duplicado
        conn.commit()
        return agregados, last_id
    except Exception as e:
        logger.warning(f"Error guardando movimientos bancarios: {e}")
        return 0, None
    finally:
        conn.close()


def update_record_path(record_id, new_path):
    """Actualiza la ruta física del archivo tras el archivado legal v4.0."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE bancos_movimientos SET path_archivo = ? WHERE id = ?", (new_path, record_id))
        conn.commit()
    except Exception as e:
        logger.warning(f"Error actualizando path en bancos_movimientos: {e}")
    finally:
        conn.close()


def get_sueldos(anio):
    """Consulta especializada v4.0 para detectar haberes/sueldos."""
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT fecha, descripcion, importe
            FROM bancos_movimientos
            WHERE (descripcion LIKE ? OR descripcion LIKE ?)
            AND fecha LIKE ?
            ORDER BY fecha DESC
        """, ("%SUELDOS%", "%PINO SUB SA%", f"%{anio}%")).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
