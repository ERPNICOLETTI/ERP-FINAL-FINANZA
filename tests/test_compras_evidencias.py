import io
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from PyPDF2 import PdfWriter, PdfReader
from fastapi import FastAPI
from fastapi.testclient import TestClient
from modulo_compras import storage_compras as storage, evidencias
from erp_api import routes_compras as routes


def pdf(width=100):
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=100)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


class ComprasEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / 'test.db'
        self.patches = [patch.object(storage,'DB_PATH',str(self.db)),
                        patch.object(evidencias,'ROOT',self.root), patch.object(routes,'WORKSPACE',self.root)]
        for p in self.patches: p.start()
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute('''CREATE TABLE core_staging_raw(id INTEGER PRIMARY KEY,
                nombre_archivo TEXT,hash_sha256 TEXT UNIQUE,modulo TEXT,tipo_fuente TEXT,
                formato_raw TEXT,parser_version TEXT,contenido_raw TEXT,filas_leidas INTEGER,
                estado TEXT,fecha_procesado TEXT)''')
        storage.init_db_compras()
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("""INSERT INTO compras_facturas(id,proveedor,fecha,numero_comprobante,
                punto_venta,status,calim_estado,tipo_operacion) VALUES
                (1,'Proveedor','2026-08-01','1234','00001','SOLO_AFIP','CONCILIADO_ARCA_CALIM','COMPRA')""")
        app = FastAPI()
        app.include_router(routes.router)
        self.client = TestClient(app)

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def test_append_preserves_existing_and_repeated_upload_is_idempotent(self):
        old = self.root / 'modulo_compras/archivos_compras/Facturas/old.pdf'
        old.parent.mkdir(parents=True)
        old.write_bytes(pdf())
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute('UPDATE compras_facturas SET path_archivo=?,tiene_foto=1 WHERE id=1',('Facturas/old.pdf',))
        for _ in range(2):
            result = self.client.post('/api/compras/vincular?id_factura=1',files={'file':('new.pdf',pdf(200),'application/pdf')})
            self.assertEqual(result.json()['status'],'success',result.text)
        row = storage.get_factura_by_id(1)
        self.assertEqual(old.read_bytes(),pdf())
        self.assertEqual(len(PdfReader(row['path_archivo']).pages),2)
        self.assertEqual(row['calim_estado'],'CONCILIADO_ARCA_CALIM')
        self.assertEqual(row['status'],'SOLO_AFIP')
        with closing(sqlite3.connect(self.db)) as con, con:
            self.assertEqual(con.execute('SELECT count(*) FROM compras_evidencias').fetchone()[0],1)
            self.assertEqual(list(con.execute('PRAGMA foreign_key_check')),[])
        self.assertEqual(self.client.get('/api/compras/archivo/1').status_code,200)

    def test_invalid_file_and_missing_old_file_preserve_invoice(self):
        result = self.client.post('/api/compras/vincular?id_factura=1',files={'file':('bad.pdf',b'bad')})
        self.assertEqual(result.json()['status'],'error')
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("UPDATE compras_facturas SET path_archivo='missing.pdf' WHERE id=1")
        result = self.client.post('/api/compras/vincular?id_factura=1',files={'file':('new.pdf',pdf())})
        self.assertEqual(result.json()['status'],'error')
        self.assertEqual(storage.get_factura_by_id(1)['path_archivo'],'missing.pdf')

    def test_pending_is_idempotent_and_does_not_invent_cuit(self):
        for _ in range(2):
            result = self.client.post('/api/compras/vincular',data={'is_pending_calim':'true',
                'proveedor_nombre':'Prueba','numero_factura':'54321'},files={'file':('pending.pdf',pdf())})
            self.assertEqual(result.json()['status'],'success',result.text)
        with closing(sqlite3.connect(self.db)) as con, con:
            rows = con.execute("SELECT cuit_proveedor FROM compras_facturas WHERE status='SALA_ESPERA'").fetchall()
            self.assertEqual(rows,[(None,)])

    def test_import_uses_updated_readers_and_reports_each_failure(self):
        with patch('modulo_compras.lector_calim_compras.procesar_archivo',return_value=(True,{'filas':2})) as calim, \
             patch('modulo_compras.lector_arca_comprobantes.procesar_archivo',return_value=(False,{'error':'CSV inválido'})) as arca:
            result = self.client.post('/api/compras/importar-multiples',files=[
                ('files',('compras.xlsx',b'fixture')),('files',('recibidos.csv',b'fixture2'))])
            self.assertEqual(result.json()['status'],'partial')
            calim.assert_called_once()
            arca.assert_called_once()
            self.assertTrue(Path(calim.call_args.args[0]).is_file())

    def test_inbox_traversal_is_rejected(self):
        result = self.client.post('/api/compras/vincular?id_factura=1',data={'inbox_filename':'../test.db'})
        self.assertEqual(result.json()['status'],'error')


if __name__ == '__main__': unittest.main()
