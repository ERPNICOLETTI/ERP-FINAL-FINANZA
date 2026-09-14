import base64
import json
import sqlite3
from contextlib import closing
from unittest.mock import patch
from modulo_compras.facturas_scan_parser import extraer
from modulo_compras import storage_compras as storage, evidencias
from modulo_compras.lector_facturas_scan import procesar_archivo
from tests.test_compras_evidencias import pdf


def test_review_page_and_missing_qr():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from erp_api.routes_compras import router
    app = FastAPI()
    app.include_router(router)
    with patch.object(storage,'listar_scans',return_value=[]):
        response = TestClient(app).get('/compras/ocr')
        assert response.status_code==200
        assert 'Control de lectura' in response.text
    assert extraer({'codigos':[]})['estado']=='REVISAR'


def qr(**changes):
    data = dict(fecha='2026-08-15',cuit=30716557363,tipoCmp=1,ptoVta=6,
        nroCmp=258,importe='59500.00',moneda='PES')
    data.update(changes)
    return 'https://www.afip.gob.ar/fe/qr/?p='+base64.b64encode(json.dumps(data).encode()).decode()


def test_qr_exact_cents_and_reject_invalid():
    assert extraer({'codigos':[qr()]})['qr'][0]['total_centavos']==5950000
    for changes in ({'cuit':30716557364},{'importe':'1.001'},{'fecha':'2026-99-20'}):
        assert extraer({'codigos':[qr(**changes)]})['estado']=='REVISAR'
    assert extraer({'codigos':[qr(),qr(nroCmp=259)]})['estado']=='REVISAR'
    assert not extraer({'codigos':['https://evil.example/?p=test']})['qr']


def test_text_candidates_keep_evidence_and_conflicts():
    page = {'codigos':[qr()], 'texto':'CUIT 30-71655736-3\nNro. 0006-00000258\nTOTAL $ 59.500,00',
            'texto_alternativo':'TOTAL\n$ 58,500.00'}
    result = extraer(page)
    assert result['estado']=='REVISAR'
    assert 'CONTRADICCION_TOTAL_OCR_QR' in result['advertencias']
    assert result['texto']['numeros'][0]['valor']==[6,258]
    assert result['texto']['cuits'][0]['valor']=='30716557363'
    assert {v['valor'] for v in result['texto']['totales']}=={5950000,5850000}
    assert not extraer({'texto':'SUBTOTAL 100,00\nIMPORTE TOTAL IVA 21,00'})['texto']['totales']


def test_malformed_qr_never_truncates_or_crashes():
    for value in (1.9,True,-1,100000):
        result = extraer({'codigos':[qr(ptoVta=value)]})
        assert not result['qr']
        assert result['estado']=='REVISAR'
    for code in ('http://[broken',None,'https://www.afip.gob.ar/fe/qr/?p=W10='):
        assert extraer({'codigos':[code]})['estado']=='REVISAR'


def test_authorization_and_ocr_total_disagreements():
    result = extraer({'codigos':[qr(codAut=12345678901234)],'texto':'CAE 98765432109876'})
    assert 'CONTRADICCION_AUTORIZACION_OCR_QR' in result['advertencias']
    result = extraer({'texto':'TOTAL 1.000,00','texto_alternativo':'TOTAL 2.000,00'})
    assert 'TOTALES_OCR_DIVERGENTES' in result['advertencias']


def test_raw_before_ocr_retry_and_idempotency(tmp_path):
    db = tmp_path/'test.db'
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute('''CREATE TABLE core_staging_raw(id INTEGER PRIMARY KEY,
            nombre_archivo TEXT,hash_sha256 TEXT UNIQUE,modulo TEXT,tipo_fuente TEXT,
            formato_raw TEXT,parser_version TEXT,contenido_raw TEXT,filas_leidas INTEGER,
            estado TEXT,fecha_procesado TEXT)''')
    source = tmp_path/'test.pdf'
    source.write_bytes(pdf())
    with patch.object(storage,'DB_PATH',str(db)), patch.object(evidencias,'ROOT',tmp_path):
        with patch('modulo_compras.lector_facturas_scan.leer',side_effect=RuntimeError('motor no disponible')):
            failed = procesar_archivo(source)
        assert failed['estado']=='ERROR'
        with closing(sqlite3.connect(db)) as conn:
            raw = json.loads(conn.execute('SELECT contenido_raw FROM core_staging_raw').fetchone()[0])
            assert base64.b64decode(raw['contenido_base64'])==source.read_bytes()
        result = {'paginas':[{'pagina':1,'codigos':[qr()]}]}
        with patch('modulo_compras.lector_facturas_scan.leer',return_value=result) as reader:
            assert procesar_archivo(source)['estado']=='LEIDO'
            assert procesar_archivo(source)['estado']=='LEIDO'
            assert reader.call_count==1
        with closing(sqlite3.connect(db)) as conn:
            assert conn.execute('SELECT count(*) FROM core_staging_raw').fetchone()[0]==1
            assert conn.execute('SELECT count(*) FROM compras_scan_extracciones').fetchone()[0]==1
        assert source.read_bytes()==pdf()
