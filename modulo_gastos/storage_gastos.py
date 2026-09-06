import sqlite3
import os
import json
import sys
from collections import defaultdict, deque
from decimal import Decimal, ROUND_HALF_UP

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
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
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
            raw_ingesta_id  INTEGER,
            numero_linea    INTEGER,
            moneda_original TEXT DEFAULT 'ARS',
            monto_original  REAL,
            tipo_cambio     REAL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try:
        conn.execute("ALTER TABLE gastos_registros ADD COLUMN fecha_compra TEXT")
        conn.commit()
    except Exception:
        pass
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(gastos_registros)")}
    new_columns = {
        "raw_ingesta_id": "INTEGER",
        "numero_linea": "INTEGER",
        "moneda_original": "TEXT DEFAULT 'ARS'",
        "monto_original": "REAL",
        "tipo_cambio": "REAL",
        "resumen_id": "INTEGER",
        "tipo_movimiento": "TEXT DEFAULT 'CONSUMO'",
        "comprobante": "TEXT",
        "monto_centavos": "INTEGER",
        "monto_original_centavos": "INTEGER",
        "tipo_cambio_milesimas": "INTEGER",
        "titular_codigo": "TEXT",
    }
    for column, definition in new_columns.items():
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE gastos_registros ADD COLUMN {column} {definition}")
    pending = conn.execute("SELECT id FROM gastos_tipos WHERE cuenta_codigo IS NULL AND nombre='Pendiente de clasificación' LIMIT 1").fetchone()
    if not pending:
        conn.execute("""INSERT INTO gastos_tipos(cuenta_codigo,nombre,tipo,emoji,color_css,palabras_clave)
                        VALUES (NULL,'Pendiente de clasificación','EGRESO','?','#6b7280','')""")
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_gastos_raw_linea
        ON gastos_registros(raw_ingesta_id, numero_linea)
        WHERE raw_ingesta_id IS NOT NULL AND numero_linea IS NOT NULL
    """)

    # Cabecera contable de cada liquidación. Los totales oficiales se guardan
    # separados de los consumos y siempre como centavos enteros.
    conn.execute('''
        CREATE TABLE IF NOT EXISTS gastos_tarjeta_resumenes (
            id                                  INTEGER PRIMARY KEY AUTOINCREMENT,
            fuente                              TEXT NOT NULL,
            titular_codigo                      TEXT NOT NULL,
            numero_cuenta                       TEXT,
            numero_resumen                      TEXT,
            documento_clave                     TEXT UNIQUE NOT NULL,
            hash_contenido_sha256               TEXT NOT NULL,
            periodo                             TEXT NOT NULL,
            fecha_cierre                        TEXT NOT NULL,
            fecha_vencimiento                   TEXT NOT NULL,
            fecha_cierre_anterior               TEXT,
            fecha_vencimiento_anterior          TEXT,
            fecha_proximo_cierre                TEXT,
            fecha_proximo_vencimiento           TEXT,
            cuenta_debito                       TEXT,
            condicion_iva_impresa               TEXT,
            iva_computable_segun_leyenda        INTEGER,
            financiacion_ofrecida_json          TEXT,
            saldo_anterior_ars_centavos         INTEGER NOT NULL DEFAULT 0,
            saldo_anterior_usd_centavos         INTEGER NOT NULL DEFAULT 0,
            saldo_actual_ars_centavos           INTEGER NOT NULL DEFAULT 0,
            saldo_actual_usd_centavos           INTEGER NOT NULL DEFAULT 0,
            pago_minimo_ars_centavos            INTEGER NOT NULL DEFAULT 0,
            pago_minimo_anterior_ars_centavos   INTEGER,
            consumos_declarados_ars_centavos    INTEGER NOT NULL DEFAULT 0,
            consumos_declarados_usd_centavos    INTEGER NOT NULL DEFAULT 0,
            nuevos_cargos_ars_centavos          INTEGER NOT NULL DEFAULT 0,
            nuevos_cargos_usd_centavos          INTEGER NOT NULL DEFAULT 0,
            intereses_ars_centavos              INTEGER NOT NULL DEFAULT 0,
            impuestos_ars_centavos              INTEGER NOT NULL DEFAULT 0,
            pagos_ars_centavos                  INTEGER NOT NULL DEFAULT 0,
            transferencia_deuda_ars_centavos    INTEGER NOT NULL DEFAULT 0,
            transferencia_deuda_usd_centavos    INTEGER NOT NULL DEFAULT 0,
            diferencia_ars_centavos             INTEGER NOT NULL DEFAULT 0,
            diferencia_usd_centavos             INTEGER NOT NULL DEFAULT 0,
            tna_ars_milesimas                    INTEGER,
            tem_ars_milesimas                    INTEGER,
            tea_ars_milesimas                    INTEGER,
            cftea_ars_iva_milesimas              INTEGER,
            conciliado                           INTEGER NOT NULL DEFAULT 0,
            cantidad_operaciones                 INTEGER NOT NULL DEFAULT 0,
            cantidad_consumos                    INTEGER NOT NULL DEFAULT 0,
            raw_ingesta_id                       INTEGER UNIQUE NOT NULL,
            parser_version                       TEXT NOT NULL,
            created_at                           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at                           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    summary_existing_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(gastos_tarjeta_resumenes)")
    }
    summary_new_columns = {
        "condicion_iva_impresa": "TEXT",
        "iva_computable_segun_leyenda": "INTEGER",
        "financiacion_ofrecida_json": "TEXT",
    }
    for column, definition in summary_new_columns.items():
        if column not in summary_existing_columns:
            conn.execute(
                f"ALTER TABLE gastos_tarjeta_resumenes ADD COLUMN {column} {definition}"
            )
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_gastos_tarjeta_resumen_periodo
        ON gastos_tarjeta_resumenes(fuente, titular_codigo, periodo DESC)
    ''')
    conn.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_gastos_resumen_linea
        ON gastos_registros(resumen_id, numero_linea)
        WHERE resumen_id IS NOT NULL AND numero_linea IS NOT NULL
    ''')
    
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
                INSERT INTO gastos_registros (
                    gasto_tipo_id, monto, fecha, descripcion, fuente, fecha_compra,
                    raw_ingesta_id, numero_linea, moneda_original, monto_original, tipo_cambio
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                gasto_tipo_id, monto, fecha, descripcion, fuente, fecha_compra,
                data.get('raw_ingesta_id'), data.get('numero_linea'),
                data.get('moneda_original', 'ARS'), data.get('monto_original', monto),
                data.get('tipo_cambio'),
            ))
            ret_id = cursor.lastrowid
        conn.commit()
        return ret_id
    except Exception as e:
        print(f"Error guardando registro de gasto: {e}")
        return None
    finally:
        conn.close()


def actualizar_linaje_gasto(registro_id, *, raw_ingesta_id, numero_linea,
                            moneda_original, monto_original, tipo_cambio,
                            fecha_compra=None, descripcion=None):
    """Adjunta trazabilidad a un registro existente sin cambiar su categoría."""
    conn = get_db_connection()
    try:
        updates = [
            "raw_ingesta_id=?", "numero_linea=?", "moneda_original=?",
            "monto_original=?", "tipo_cambio=?",
        ]
        params = [raw_ingesta_id, numero_linea, moneda_original, monto_original, tipo_cambio]
        if fecha_compra is not None:
            updates.append("fecha_compra=?")
            params.append(fecha_compra)
        if descripcion is not None:
            updates.append("descripcion=?")
            params.append(descripcion)
        params.append(registro_id)
        conn.execute(f"UPDATE gastos_registros SET {', '.join(updates)} WHERE id=?", params)
        conn.commit()
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
    # Hipotecario antepone a veces el comprobante y una marca K/* pegada al
    # comercio. Se elimina antes de comparar para preservar clasificaciones al
    # reprocesar con una versión nueva del lector.
    d = re.sub(r'^\s*\d{6}[\*k]?\s*', '', d)
    d = re.sub(r'^[\*k\s]+', '', d)
    # Remove cuotas like 01/06 or 1/3
    d = re.sub(r'\b\d{1,2}/\d{1,2}\b', '', d)
    # Remove long numbers (references, cards, etc.)
    d = re.sub(r'\d{4,}(?=usd\b)', '', d)
    d = re.sub(r'\b\d{4,}\b', '', d)
    d = re.sub(r'\busd\b', '', d)
    # Remove special prefix/suffix characters
    d = re.sub(r'[\*\#\-]', '', d)
    # Compactar espacios evita perder memoria por diferencias de maquetación
    # entre dos versiones de extracción del mismo PDF.
    return re.sub(r'\s+', ' ', d).strip()

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


def _decimal_to_cents(value):
    if value is None:
        return 0
    return int(
        (Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def _clasificar_consumo_visa(conn, operacion, titular_codigo="JOA"):
    """Clasifica un consumo sin invadir el ecosistema del titular indicado."""
    description = operacion["descripcion"]
    valued_amount = Decimal(operacion["monto_ars_valorizado_centavos"]) / 100
    previous = buscar_clasificacion_previa(conn, description, float(valued_amount))
    allowed = {titular_codigo, "COMUN"}
    if previous and previous["cuenta"] in allowed:
        return previous["id"]

    rows = conn.execute("""
        SELECT id, cuenta_codigo, nombre, palabras_clave
        FROM gastos_tipos
        WHERE cuenta_codigo IN (?, 'COMUN')
        ORDER BY CASE cuenta_codigo WHEN ? THEN 1 WHEN 'COMUN' THEN 2 ELSE 3 END,
                 CASE WHEN nombre IN ('Gastos Personales', 'Tarjeta') THEN 2 ELSE 1 END,
                 id
    """, (titular_codigo, titular_codigo)).fetchall()
    description_normalized = normalize_desc(description).replace(".", "")
    for row in rows:
        keywords = [
            item.strip().lower().replace(".", "")
            for item in (row["palabras_clave"] or "").split(",")
            if item.strip()
        ]
        if any(keyword in description_normalized for keyword in keywords):
            return row["id"]

    upper_description = description_normalized.upper()
    if operacion["tipo_movimiento"] in {"INTERES", "IMPUESTO"} or any(
        token in upper_description for token in ("IVA", "SELLO", "PERCEP", "INTERES", "FINANCIA")
    ):
        tarjeta = next(
            (row["id"] for row in rows if row["cuenta_codigo"] == titular_codigo and row["nombre"] == "Tarjeta"),
            None,
        )
        if tarjeta:
            return tarjeta

    fallback = next(
        (row["id"] for row in rows if row["cuenta_codigo"] == titular_codigo and row["nombre"] in ("Gastos Personales", "Gastos de Vida")),
        None,
    )
    if fallback is None:
        raise ValueError(f"Falta una categoría de respaldo para {titular_codigo}")
    return fallback


def _clave_consumo_existente(row):
    row_keys = set(row.keys()) if hasattr(row, "keys") else set(row)
    original_cents = (
        row["monto_original_centavos"]
        if "monto_original_centavos" in row_keys else None
    )
    if original_cents is None:
        original_cents = _decimal_to_cents(
            row["monto_original"] if row["monto_original"] is not None else row["monto"]
        )
    return (
        normalize_desc(row["descripcion"]),
        row["fecha_compra"] or row["fecha"],
        (row["moneda_original"] or "ARS").upper(),
        int(original_cents),
    )


def _clave_consumo_parseado(operacion):
    return (
        normalize_desc(operacion["descripcion"]),
        operacion["fecha_compra"],
        operacion["moneda_original"],
        int(operacion["monto_original_centavos"]),
    )


def guardar_resumen_tarjeta(
    parsed, *, staging_id, parser_version="v7.0.0", reconstruir=False
):
    """Persiste un resumen de tarjeta ya parseado como transacción conciliada.

    Un reproceso conserva IDs y categorías de los consumos ya reconocidos. Si
    el parser deja afuera una fila productiva previa, se aborta toda la
    operación para no perder una clasificación del usuario silenciosamente.
    """
    summary = dict(parsed["resumen"])
    if parsed.get("financiacion_ofrecida") is not None:
        summary["financiacion_ofrecida_json"] = json.dumps(
            parsed["financiacion_ofrecida"], ensure_ascii=False, sort_keys=True
        )
    consumptions = [dict(item) for item in parsed["consumos"]]
    if not summary.get("conciliado"):
        raise ValueError(
            "El resumen de tarjeta no concilia; se rechazó su paso a producción"
        )

    init_db_gastos()
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        raw = conn.execute(
            "SELECT id FROM core_staging_raw WHERE id=?", (staging_id,)
        ).fetchone()
        if not raw:
            raise ValueError("El resumen no posee una entrada previa en core_staging_raw")

        existing_summary = conn.execute("""
            SELECT * FROM gastos_tarjeta_resumenes WHERE documento_clave=?
        """, (summary["documento_clave"],)).fetchone()
        if existing_summary and existing_summary["raw_ingesta_id"] != staging_id:
            conn.rollback()
            return False, {
                "motivo": "RESUMEN_EXISTENTE",
                "resumen_id": existing_summary["id"],
                "raw_canonico_id": existing_summary["raw_ingesta_id"],
            }
        if existing_summary and not reconstruir:
            conn.rollback()
            return False, {
                "motivo": "RESUMEN_EXISTENTE",
                "resumen_id": existing_summary["id"],
                "raw_canonico_id": staging_id,
            }

        summary_columns = [
            "fuente", "titular_codigo", "numero_cuenta", "numero_resumen",
            "documento_clave", "hash_contenido_sha256", "periodo", "fecha_cierre",
            "fecha_vencimiento", "fecha_cierre_anterior", "fecha_vencimiento_anterior",
            "fecha_proximo_cierre", "fecha_proximo_vencimiento", "cuenta_debito",
            "condicion_iva_impresa", "iva_computable_segun_leyenda",
            "financiacion_ofrecida_json",
            "saldo_anterior_ars_centavos", "saldo_anterior_usd_centavos",
            "saldo_actual_ars_centavos", "saldo_actual_usd_centavos",
            "pago_minimo_ars_centavos", "pago_minimo_anterior_ars_centavos",
            "consumos_declarados_ars_centavos", "consumos_declarados_usd_centavos",
            "nuevos_cargos_ars_centavos", "nuevos_cargos_usd_centavos",
            "intereses_ars_centavos", "impuestos_ars_centavos", "pagos_ars_centavos",
            "transferencia_deuda_ars_centavos", "transferencia_deuda_usd_centavos",
            "diferencia_ars_centavos", "diferencia_usd_centavos", "tna_ars_milesimas",
            "tem_ars_milesimas", "tea_ars_milesimas", "cftea_ars_iva_milesimas",
            "conciliado", "cantidad_operaciones", "cantidad_consumos",
        ]
        values = [summary.get(column) for column in summary_columns]
        values[summary_columns.index("conciliado")] = int(bool(summary["conciliado"]))
        if summary.get("iva_computable_segun_leyenda") is not None:
            values[summary_columns.index("iva_computable_segun_leyenda")] = int(
                bool(summary["iva_computable_segun_leyenda"])
            )
        if existing_summary:
            assignments = ", ".join(f"{column}=?" for column in summary_columns)
            conn.execute(
                f"UPDATE gastos_tarjeta_resumenes SET {assignments}, parser_version=?, "
                "updated_at=datetime('now','localtime') WHERE id=?",
                (*values, parser_version, existing_summary["id"]),
            )
            summary_id = existing_summary["id"]
        else:
            columns_sql = ", ".join(summary_columns + ["raw_ingesta_id", "parser_version"])
            placeholders = ", ".join("?" for _ in summary_columns + ["raw_ingesta_id", "parser_version"])
            cursor = conn.execute(
                f"INSERT INTO gastos_tarjeta_resumenes ({columns_sql}) VALUES ({placeholders})",
                (*values, staging_id, parser_version),
            )
            summary_id = cursor.lastrowid

        source_name = summary["fuente"]
        old_rows = conn.execute("""
            SELECT * FROM gastos_registros
            WHERE fuente=?
              AND (resumen_id=? OR (resumen_id IS NULL AND raw_ingesta_id=? AND substr(fecha,1,7)=?))
            ORDER BY id
        """, (source_name, summary_id, staging_id, summary["periodo"])).fetchall()
        remembered = defaultdict(deque)
        for row in old_rows:
            remembered[_clave_consumo_existente(row)].append(row)

        # Libera temporalmente el índice de línea para poder reordenar el mismo
        # RAW sin colisiones intermedias entre dos filas que conservan su ID.
        if old_rows:
            old_ids = [row["id"] for row in old_rows]
            conn.execute(
                f"UPDATE gastos_registros SET numero_linea=NULL WHERE id IN ({','.join('?' for _ in old_ids)})",
                old_ids,
            )

        inserted = 0
        updated = 0
        used_ids = set()
        auto_classify = summary.get("clasificar_automaticamente", True)
        pending_category = None
        if not auto_classify:
            pending_category = conn.execute(
                "SELECT id FROM gastos_tipos WHERE cuenta_codigo IS NULL AND nombre='Pendiente de clasificación' LIMIT 1"
            ).fetchone()["id"]
        for operation in consumptions:
            key = _clave_consumo_parseado(operation)
            old = remembered[key].popleft() if remembered[key] else None
            holder = operation.get("titular_codigo") or summary["titular_codigo"]
            category_id = pending_category if not auto_classify else (
                old["gasto_tipo_id"] if old else _clasificar_consumo_visa(conn, operation, holder)
            )
            description = operation["descripcion"]
            if operation.get("cuota"):
                description = f"{description} {operation['cuota']}"
            amount_cents = int(operation["monto_ars_valorizado_centavos"])
            original_cents = int(operation["monto_original_centavos"])
            exchange_milli = int(operation["tipo_cambio_milesimas"])
            params = (
                category_id, amount_cents / 100, summary["fecha_cierre"], description,
                operation["fecha_compra"], staging_id, operation["linea_origen"],
                operation["moneda_original"], original_cents / 100,
                exchange_milli / 1000, summary_id, operation["tipo_movimiento"],
                operation.get("comprobante"), amount_cents, original_cents,
                exchange_milli, holder,
            )
            if old:
                conn.execute("""
                    UPDATE gastos_registros
                    SET gasto_tipo_id=?, monto=?, fecha=?, descripcion=?, fecha_compra=?,
                        raw_ingesta_id=?, numero_linea=?, moneda_original=?, monto_original=?,
                        tipo_cambio=?, resumen_id=?, tipo_movimiento=?, comprobante=?,
                        monto_centavos=?, monto_original_centavos=?, tipo_cambio_milesimas=?, titular_codigo=?
                    WHERE id=?
                """, (*params, old["id"]))
                used_ids.add(old["id"])
                updated += 1
            else:
                conn.execute("""
                    INSERT INTO gastos_registros (
                        gasto_tipo_id, monto, fecha, descripcion, fuente, fecha_compra,
                        raw_ingesta_id, numero_linea, moneda_original, monto_original,
                        tipo_cambio, resumen_id, tipo_movimiento, comprobante,
                        monto_centavos, monto_original_centavos, tipo_cambio_milesimas, titular_codigo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (category_id, amount_cents / 100, summary["fecha_cierre"], description,
                      source_name, operation["fecha_compra"], staging_id, operation["linea_origen"],
                      operation["moneda_original"], original_cents / 100, exchange_milli / 1000,
                      summary_id, operation["tipo_movimiento"], operation.get("comprobante"), amount_cents,
                      original_cents, exchange_milli, holder))
                inserted += 1

        stale_ids = [row["id"] for row in old_rows if row["id"] not in used_ids]
        if stale_ids:
            raise ValueError(
                f"El reproceso dejaría {len(stale_ids)} consumos previos sin equivalencia; operación cancelada"
            )

        conn.execute("""
            UPDATE core_staging_raw
            SET parser_version=?, filas_leidas=?, estado='PROCESADO',
                fecha_procesado=datetime('now','localtime'), mensaje_error=NULL
            WHERE id=?
        """, (parser_version, len(parsed["operaciones"]), staging_id))
        conn.execute("""
            INSERT INTO core_staging_logs(staging_id, resultado, detalles)
            VALUES (?, 'PROCESADO', ?)
        """, (
            staging_id,
            f"Tarjeta conciliada: {len(parsed['operaciones'])} operaciones; "
            f"{len(consumptions)} consumos; {updated} actualizados; {inserted} agregados",
        ))
        conn.commit()
        return True, {
            "resumen_id": summary_id,
            "staging_id": staging_id,
            "operaciones": len(parsed["operaciones"]),
            "consumos": len(consumptions),
            "actualizados": updated,
            "agregados": inserted,
            "conciliado": True,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def guardar_resumen_visa_hipotecario(
    parsed, *, staging_id, parser_version="v7.0.0", reconstruir=False
):
    """Alias compatible para lectores existentes; la persistencia es genérica."""
    return guardar_resumen_tarjeta(
        parsed,
        staging_id=staging_id,
        parser_version=parser_version,
        reconstruir=reconstruir,
    )


def get_resumenes_tarjeta(fuente="Visa Hipotecario", titular_codigo="JOA"):
    """Lista resúmenes cerrados para el selector de la vista personal."""
    init_db_gastos()
    conn = get_db_connection()
    try:
        return [dict(row) for row in conn.execute("""
            SELECT * FROM gastos_tarjeta_resumenes
            WHERE fuente=? AND titular_codigo=?
            ORDER BY fecha_cierre DESC, id DESC
        """, (fuente, titular_codigo)).fetchall()]
    finally:
        conn.close()

if __name__ == "__main__":
    init_db_gastos()
