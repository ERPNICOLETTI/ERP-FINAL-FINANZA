"""Revisión documental transaccional. Nunca modifica importes ARCA/CALIM."""
import hashlib
import json
from pathlib import Path
from . import storage_compras as storage, evidencias


def schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS compras_scan_revisiones (
        hash_sha256 TEXT NOT NULL, pagina INTEGER NOT NULL,
        scan_id INTEGER NOT NULL REFERENCES compras_scan_extracciones(id),
        estado TEXT NOT NULL, factura_id INTEGER REFERENCES compras_facturas(id),
        nota TEXT NOT NULL, datos_json TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(hash_sha256,pagina))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS compras_scan_eventos (
        id INTEGER PRIMARY KEY, scan_id INTEGER NOT NULL REFERENCES compras_scan_extracciones(id),
        paginas_json TEXT NOT NULL, accion TEXT NOT NULL, factura_id INTEGER,
        nota TEXT NOT NULL, datos_json TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')


def original(scan_id):
    conn = storage.get_db_connection()
    try:
        row = conn.execute('SELECT * FROM compras_scan_extracciones WHERE id=?',(scan_id,)).fetchone()
        if not row:
            raise ValueError('Escaneo inexistente.')
        data = dict(row)
    finally:
        conn.close()
    root = (evidencias.ROOT/'modulo_compras/crudos_compras/EVIDENCIAS').resolve()
    path = Path(data['path_original']).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Original fuera de la bóveda o no disponible.')
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest()!=data['hash_sha256']:
        raise ValueError('El original no coincide con su hash; operación bloqueada.')
    return data, content, path.suffix.lower()


def revisar(scan_id, paginas, accion, factura_id=0, nota='', datos=None, permitir_adjunto=False):
    if accion not in {'CONFIRMADO','PENDIENTE'}:
        raise ValueError('Acción inválida.')
    if not paginas or len(paginas)>100 or any(type(p) is not int or p<1 for p in paginas) or len(set(paginas))!=len(paginas):
        raise ValueError('Seleccioná páginas únicas y válidas.')
    paginas = sorted(paginas)
    if not nota.strip():
        raise ValueError('Registrá el motivo o la verificación realizada.')
    if len(nota)>2000 or not isinstance(datos or {},dict) or len(json.dumps(datos or {}))>10000:
        raise ValueError('Revisión demasiado extensa o inválida.')
    scan, content, ext = original(scan_id)
    result = json.loads(scan['resultado_json'] or '{}')
    if scan['estado']!='LEIDO' or any(p>len(result.get('paginas',[])) for p in paginas):
        raise ValueError('Primero completá la lectura de esas páginas.')
    conn = storage.get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        schema(conn)
        existing = [conn.execute('SELECT * FROM compras_scan_revisiones WHERE hash_sha256=? AND pagina=?',
                                (scan['hash_sha256'],p)).fetchone() for p in paginas]
        closed = [r for r in existing if r and r['estado']=='CONFIRMADO']
        if closed:
            if len(closed)==len(paginas) and accion=='CONFIRMADO' and all(r['factura_id']==factura_id for r in closed):
                conn.rollback()
                return {'status':'success','message':'Estas páginas ya estaban vinculadas; no se duplicaron.','id_factura':factura_id}
            raise ValueError('Hay páginas ya confirmadas. No se permite reasignarlas ni mezclarlas con otras.')
        if accion=='CONFIRMADO':
            invoice = conn.execute('SELECT * FROM compras_facturas WHERE id=?',(factura_id,)).fetchone()
            if not invoice or invoice['status']=='DUPLICADO_LEGACY_CALIM':
                raise ValueError('Seleccioná una factura activa.')
            previous = conn.execute('SELECT 1 FROM compras_scan_revisiones WHERE factura_id=? AND estado=?',
                                    (factura_id,'CONFIRMADO')).fetchone()
            has_visual = bool(invoice['path_archivo']) and Path(invoice['path_archivo']).suffix.lower() in evidencias.EXTENSIONS
            if (previous or has_visual) and not permitir_adjunto:
                raise ValueError('La factura ya tiene evidencia. Revisá si es duplicado y autorizá agregar páginas si corresponde.')
            derived, derived_ext = evidencias.seleccionar_paginas(content,ext,paginas)
            storage.vincular_evidencia(derived,Path(scan['nombre_original']).stem+'_paginas_'+'_'.join(map(str,paginas))+derived_ext,
                                       factura_id,_conn=conn)
        else:
            factura_id = None
        snapshot = json.dumps(datos or {},ensure_ascii=False)
        for p in paginas:
            conn.execute('''INSERT INTO compras_scan_revisiones
                (hash_sha256,pagina,scan_id,estado,factura_id,nota,datos_json) VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(hash_sha256,pagina) DO UPDATE SET scan_id=excluded.scan_id,estado=excluded.estado,
                factura_id=excluded.factura_id,nota=excluded.nota,datos_json=excluded.datos_json,updated_at=CURRENT_TIMESTAMP''',
                (scan['hash_sha256'],p,scan_id,accion,factura_id,nota.strip(),snapshot))
        conn.execute('INSERT INTO compras_scan_eventos(scan_id,paginas_json,accion,factura_id,nota,datos_json) VALUES (?,?,?,?,?,?)',
                     (scan_id,json.dumps(paginas),accion,factura_id,nota.strip(),snapshot))
        conn.commit()
        return {'status':'success','message':'Páginas vinculadas y evidencia conservada.' if accion=='CONFIRMADO' else 'Pendiente registrado sin crear factura fiscal.',
                'id_factura':factura_id}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def revisiones():
    conn = storage.get_db_connection()
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='compras_scan_revisiones'").fetchone():
            return []
        return [dict(r) for r in conn.execute('SELECT * FROM compras_scan_revisiones')]
    finally:
        conn.close()


def historial(scan_id):
    conn = storage.get_db_connection()
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='compras_scan_eventos'").fetchone():
            return []
        return [dict(r) for r in conn.execute('''SELECT e.* FROM compras_scan_eventos e JOIN compras_scan_extracciones s ON s.id=e.scan_id
            WHERE s.hash_sha256=(SELECT hash_sha256 FROM compras_scan_extracciones WHERE id=?) ORDER BY e.id DESC''',(scan_id,))]
    finally:
        conn.close()


def cobertura():
    conn = storage.get_db_connection()
    try:
        result = {}
        for source, table in [('ARCA','compras_arca_ingestas'),('CALIM','compras_calim_ingestas')]:
            if conn.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone():
                result[source] = dict(conn.execute(f'''SELECT count(*) archivos,min(fecha_min) primera_fecha,
                    max(fecha_max) ultima_fecha,max(created_at) ultima_importacion FROM {table}''').fetchone())
            else:
                result[source] = {'archivos':0}
        return result
    finally:
        conn.close()


def bandeja():
    scans = storage.listar_scans()
    reviewed = {(r['hash_sha256'],r['pagina']):r for r in revisiones()}
    for scan in scans:
        for page in scan['paginas']:
            page['revision'] = reviewed.get((scan['hash_sha256'],page['pagina']))
    return {'scans':scans,'cobertura':cobertura()}
