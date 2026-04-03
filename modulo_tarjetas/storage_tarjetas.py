import sqlite3
import json
import os
import logging

# STORAGE TARJETAS - Dueño de tablas Payway, Naranja, Patagonia 💳🧱🧠
# Diseño Híbrido: Columnas Duras + metadata_cruda (JSON)

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'erp_nicoletti.db')


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
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
            tipo            TEXT DEFAULT 'MENSUAL',
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
            hash_archivo    TEXT UNIQUE,
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

    # ── Cupones / Ventas Individuales ──────────────────────────────
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cupones_tarjetas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fuente          TEXT,
            fecha_compra    TEXT,
            fecha_pago      TEXT,
            lote            TEXT,
            cupon           TEXT,
            marca           TEXT,
            monto_bruto     REAL DEFAULT 0,
            hash_archivo    TEXT,
            metadata_cruda  TEXT DEFAULT '{}',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(fuente, lote, cupon, fecha_compra, monto_bruto)
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
                last_id = res[0]

        conn.commit()
        return last_id
    except sqlite3.IntegrityError:
        logger.info(f"Liquidación duplicada (hash): {data.get('hash_archivo')}")
        return None
    except Exception as e:
        logger.warning(f"Error guardando liquidación: {e}")
        return None
    finally:
        conn.close()


def save_liquidacion_detalle(liq_id, detalle_lista: list):
    """Persistencia de líneas de detalle con JSON crudo."""
    conn = get_db_connection()
    try:
        for d in detalle_lista:
            columnas_duras = {
                'fecha', 'descripcion', 'monto_bruto', 'arancel',
                'financiero', 'iva', 'retenciones', 'monto_neto'
            }
            metadata = {k: v for k, v in d.items() if k not in columnas_duras}

            conn.execute('''
                INSERT INTO liquidaciones_detalles (
                    liquidacion_id, fecha, descripcion, monto_bruto, arancel,
                    financiero, iva, retenciones, monto_neto, metadata_cruda
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                liq_id, d.get('fecha'), d.get('descripcion'),
                d.get('monto_bruto', 0), d.get('arancel', 0),
                d.get('financiero', 0), d.get('iva', 0),
                d.get('retenciones', 0), d.get('monto_neto', 0),
                json.dumps(metadata, ensure_ascii=False, default=str)
            ))
        conn.commit()
    except Exception as e:
        logger.warning(f"Error guardando detalles de liquidación: {e}")
    finally:
        conn.close()


def save_cupones(lista_cupones: list, hash_archivo: str = None):
    """Persistencia masiva de cupones/ventas individuales."""
    conn = get_db_connection()
    try:
        agregados = 0
        for c in lista_cupones:
            columnas_duras = {
                'fuente', 'fecha_compra', 'fecha_pago', 'lote',
                'cupon', 'marca', 'monto_bruto', 'hash_archivo'
            }
            metadata = {k: v for k, v in c.items() if k not in columnas_duras}

            try:
                conn.execute('''
                    INSERT OR IGNORE INTO cupones_tarjetas (
                        fuente, fecha_compra, fecha_pago, lote, cupon,
                        marca, monto_bruto, hash_archivo, metadata_cruda
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    c.get('fuente', 'PAYWAY'), c.get('fecha_compra'),
                    c.get('fecha_pago'), c.get('lote'), c.get('cupon'),
                    c.get('marca'), c.get('monto_bruto', 0),
                    c.get('hash_archivo', hash_archivo),
                    json.dumps(metadata, ensure_ascii=False, default=str)
                ))
                agregados += 1
            except sqlite3.IntegrityError:
                pass  # Cupón duplicado, ignorar silenciosamente
        conn.commit()
        return agregados
    except Exception as e:
        logger.warning(f"Error guardando cupones: {e}")
        return 0
    finally:
        conn.close()
