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
            UNIQUE(banco, cuenta, fecha, descripcion, tipo_movimiento, importe)
        )
    ''')

    conn.commit()
    conn.close()


def save_movimiento_banco(lista_movimientos: list, hash_archivo: str = None):
    """Guarda masivamente movimientos bancarios con volcado híbrido v4.0."""
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
                    b.get('tipo_movimiento', b.get('codigo_movimiento')),
                    b.get('importe', 0), b.get('saldo'),
                    b.get('hash_archivo', hash_archivo),
                    b.get('path_archivo'),
                    json.dumps(metadata, ensure_ascii=False, default=str)
                ))
                if cursor.rowcount > 0:
                    agregados += 1
                    last_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                pass  # Movimiento duplicado
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
