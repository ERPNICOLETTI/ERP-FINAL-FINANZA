import sqlite3
import json
import os
import logging

# STORAGE TARJETAS - Dueño de tablas Payway, Naranja, Patagonia 💳🧱🧠
# Diseño Híbrido: Columnas Duras + metadata_cruda (JSON) + hash_archivo

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'erp_nicoletti.db')


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db_tarjetas():
    """Crea las tablas del dominio Tarjetas con diseño híbrido."""
    conn = get_db_connection()
    print("🧱 [TARJETAS] Inicializando tablas (Diseño Híbrido)...")

    # ── Liquidaciones (Cabecera) ───────────────────────────────────
    conn.execute('''
        CREATE TABLE IF NOT EXISTS liquidaciones_tarjetas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fuente          TEXT,
            marca           TEXT,
            tipo            TEXT DEFAULT 'MENSUAL', -- DIARIA o MENSUAL
            fecha_liquidacion TEXT,
            periodo         TEXT,
            establecimiento TEXT,
            total_bruto     REAL DEFAULT 0,
            costo_arancel   REAL DEFAULT 0,
            costo_financiero REAL DEFAULT 0,
            iva_21          REAL DEFAULT 0,
            iva_105         REAL DEFAULT 0,
            retenciones     REAL DEFAULT 0,
            total_neto      REAL DEFAULT 0,
            hash_archivo    TEXT, -- REMOVIDO UNIQUE: Idempotencia por core_registro_ingestas
            metadata_cruda  TEXT DEFAULT '{}',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Liquidaciones (Detalle línea por línea) ────────────────────
    conn.execute('''
        CREATE TABLE IF NOT EXISTS liquidaciones_detalles (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            liquidacion_id  INTEGER,
            fecha           TEXT,
            descripcion     TEXT,
            monto_bruto     REAL DEFAULT 0,
            arancel         REAL DEFAULT 0,
            financiero      REAL DEFAULT 0,
            iva             REAL DEFAULT 0,
            retenciones     REAL DEFAULT 0,
            monto_neto      REAL DEFAULT 0,
            metadata_cruda  TEXT DEFAULT '{}',
            FOREIGN KEY(liquidacion_id) REFERENCES liquidaciones_tarjetas(id)
        )
    ''')

    # ── Payway Records (Cupones / Ventas Individuales) ──────────────
    # Reemplaza a 'cupones_tarjetas' para coherencia con DB_ARCHITECTURE.md
    conn.execute('''
        CREATE TABLE IF NOT EXISTS payway_records (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fuente          TEXT,
            fecha_compra    TEXT,
            fecha_pago      TEXT,
            lote            TEXT,
            cupon           TEXT,
            marca           TEXT,
            monto_bruto     REAL DEFAULT 0,
            matching_tx_id  INTEGER, -- Relación con bancos_movimientos
            hash_archivo    TEXT,
            metadata_cruda  TEXT DEFAULT '{}',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(fecha_compra, cupon, lote, marca, monto_bruto)
        )
    ''')

    conn.commit()
    conn.close()


def save_liquidacion(data: dict):
    """Persistencia híbrida de cabecera de liquidación."""
    conn = get_db_connection()
    try:
        columnas_duras = {
            'fuente', 'marca', 'tipo', 'fecha_liquidacion', 'periodo',
            'establecimiento', 'total_bruto', 'costo_arancel', 'costo_financiero',
            'iva_21', 'iva_105', 'retenciones', 'total_neto', 'hash_archivo'
        }
        metadata = {k: v for k, v in data.items() if k not in columnas_duras}

        cursor = conn.execute('''
            INSERT OR IGNORE INTO liquidaciones_tarjetas (
                fuente, marca, tipo, fecha_liquidacion, periodo, establecimiento,
                total_bruto, costo_arancel, costo_financiero, iva_21, iva_105,
                retenciones, total_neto, hash_archivo, metadata_cruda
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('fuente', 'DESCONOCIDA').upper(),
            data.get('marca'), data.get('tipo', 'MENSUAL').upper(),
            data.get('fecha_liquidacion'), data.get('periodo'),
            data.get('establecimiento'),
            data.get('total_bruto', 0), data.get('costo_arancel', 0),
            data.get('costo_financiero', 0), data.get('iva_21', 0),
            data.get('iva_105', 0), data.get('retenciones', 0),
            data.get('total_neto', 0), data.get('hash_archivo'),
            json.dumps(metadata, ensure_ascii=False, default=str)
        ))

        last_id = cursor.lastrowid
        if last_id == 0:
            res = conn.execute(
                "SELECT id FROM liquidaciones_tarjetas WHERE hash_archivo = ?",
                (data.get('hash_archivo'),)
            ).fetchone()
            if res:
                last_id = res['id']

        conn.commit()
        return last_id
    except Exception as e:
        logger.warning(f"Error guardando liquidación: {e}")
        return None
    finally:
        conn.close()


def save_payway_records(lista_cupones: list, hash_archivo: str = None):
    """Persistencia masiva de registros de Payway."""
    conn = get_db_connection()
    try:
        agregados = 0
        for c in lista_cupones:
            columnas_duras = {
                'fuente', 'fecha_compra', 'fecha_pago', 'lote',
                'cupon', 'marca', 'monto_bruto', 'hash_archivo', 'matching_tx_id'
            }
            metadata = {k: v for k, v in c.items() if k not in columnas_duras}

            try:
                conn.execute('''
                    INSERT OR IGNORE INTO payway_records (
                        fuente, fecha_compra, fecha_pago, lote, cupon,
                        marca, monto_bruto, hash_archivo, matching_tx_id, metadata_cruda
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    c.get('fuente', 'PAYWAY'), c.get('fecha_compra'),
                    c.get('fecha_pago'), c.get('lote'), c.get('cupon'),
                    c.get('marca'), c.get('monto_bruto', 0),
                    c.get('hash_archivo', hash_archivo),
                    c.get('matching_tx_id'),
                    json.dumps(metadata, ensure_ascii=False, default=str)
                ))
                agregados += 1
            except sqlite3.IntegrityError:
                pass
        conn.commit()
        return agregados
    except Exception as e:
        logger.warning(f"Error guardando payway_records: {e}")
        return 0
    finally:
        conn.close()


def get_resumen_tarjetas(anio=None):
    """Estadísticas consolidadas (Movido de logica_tarjetas.py)."""
    conn = get_db_connection()
    cur = conn.cursor()
    params = [f"{anio}%"] if anio else []
    
    # 1. Ventas por Posnet
    q_ventas = "SELECT COUNT(*), SUM(monto_bruto) FROM payway_records"
    if anio: q_ventas += " WHERE fecha_compra LIKE ?"
    res_v = cur.execute(q_ventas, params).fetchone()

    # 2. Liquidaciones Consolidadas
    q_liq = """
        SELECT fuente, tipo, COUNT(*), SUM(total_bruto), SUM(total_neto), 
               SUM(costo_arancel + costo_financiero + retenciones + iva_21 + iva_105) 
        FROM liquidaciones_tarjetas
    """
    if anio: q_liq += " WHERE (fecha_liquidacion LIKE ? OR periodo LIKE ?)"
    
    p_liq = [f"{anio}%", f"{anio}%"] if anio else []
    res_l = cur.execute(q_liq + " GROUP BY fuente, tipo", p_liq).fetchall()
    
    conn.close()
    
    return {
        "ventas_posnet": {"total_count": res_v[0] or 0, "monto_bruto": res_v[1] or 0.0},
        "liquidaciones": [
            {
                "fuente": r[0], "tipo": r[1], "cantidad": r[2],
                "bruto": r[3] or 0.0, "neto": r[4] or 0.0, "gastos": r[5] or 0.0
            } for r in res_l
        ]
    }


def get_cupon_detalle(cupon_id):
    """Busca detalle de un cupón (Movido de logica_tarjetas.py)."""
    conn = get_db_connection()
    cur = conn.cursor()
    # Padding para cupones Payway que suelen ser de 8 dígitos
    q_pad = str(cupon_id).zfill(8)
    row = cur.execute("""
        SELECT * FROM payway_records 
        WHERE cupon = ? OR cupon LIKE ? OR id = ?
    """, (q_pad, f"%{cupon_id}", cupon_id)).fetchone()
    conn.close()
    
    if row:
        res = dict(row)
        try:
            res['metadata_cruda'] = json.loads(res['metadata_cruda'])
        except:
            pass
        return res
    return None


def get_data_auditoria():
    """Extrae datos crudos para el cruce 360 (Movido de logica_tarjetas.py)."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    records = cur.execute("SELECT fecha_compra as fecha, marca, monto_bruto FROM payway_records").fetchall()
    liquidaciones = cur.execute("""
        SELECT fecha_liquidacion as fecha, marca, total_bruto, fuente 
        FROM liquidaciones_tarjetas WHERE tipo = 'DIARIA'
    """).fetchall()
    
    conn.close()
    return {
        "records": [dict(r) for r in records],
        "liquidaciones": [dict(r) for r in liquidaciones]
    }
def get_unmatched_payway_records():
    """Busca ventas en Payway que no tienen match en movimientos bancarios (Movido de erp_master.py)."""
    conn = get_db_connection()
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT id, fecha_compra, cupon, monto_bruto 
        FROM payway_records 
        WHERE matching_tx_id IS NULL AND monto_bruto > 0 
        ORDER BY fecha_compra DESC LIMIT 50
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_record_path(record_id, new_path):
    """Actualiza la ruta física del archivo tras el archivado legal."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE payway_records SET path_archivo = ? WHERE id = ?", (new_path, record_id))
    conn.commit()
    conn.close()
