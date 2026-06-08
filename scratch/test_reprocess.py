import os
import sqlite3
import sys
import logging

# Set up logging to stdout
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

# Ensure modules in root folder are importable
sys.path.append(r"c:\Users\essao\Desktop\ERP FINAL")

from modulo_bancos import parser_visa_hipotecario
from modulo_bancos import parser_visa_galicia
from modulo_bancos import parser_mastercard_galicia
from modulo_bancos import parser_naranja_pdf
from modulo_bancos import parser_patagonia_pdf

DB_PATH = 'erp_nicoletti.db'

PDFS = {
    "VISA_HIPOTECARIO": r"c:\Users\essao\Desktop\ERP FINAL\modulo_bancos\crudos_bancos\VISA_HIPOTECARIO\2026\05\UltimaLiquidacion__2_.pdf",
    "VISA_GALICIA": r"c:\Users\essao\Desktop\ERP FINAL\modulo_bancos\crudos_bancos\VISA_GALICIA\2026\05\9bf9797a-3eab-4377-9c52-4d0ea58ee5da.pdf",
    "MASTERCARD_GALICIA": r"c:\Users\essao\Desktop\ERP FINAL\modulo_bancos\crudos_bancos\MASTERCARD_GALICIA\2026\05\50d6c0d8-22a7-44e9-90ba-2c62c95abcad.pdf",
    "TARJETA_NARANJA": r"c:\Users\essao\Desktop\ERP FINAL\modulo_bancos\crudos_bancos\TARJETA_NARANJA\2026\05\resumen-tarjeta-naranja-1780932133.pdf",
    "PATAGONIA365": r"c:\Users\essao\Desktop\ERP FINAL\modulo_bancos\crudos_bancos\PATAGONIA365\2026\05\Resumen_P365_Mayo_2026.pdf"
}

def clean_database():
    print("🧹 Cleaning database records from credit cards...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Delete from gastos_registros
    cur.execute("""
        DELETE FROM gastos_registros 
        WHERE fuente IN ('Visa Hipotecario', 'Visa Galicia', 'Mastercard Galicia', 'Tarjeta Naranja', 'Patagonia 365')
    """)
    print(f"Deleted {cur.rowcount} records from gastos_registros.")
    
    # Delete from bancos_archivos_metadata
    cur.execute("""
        DELETE FROM bancos_archivos_metadata 
        WHERE banco IN ('MASTERCARD_GALICIA', 'PATAGONIA365', 'TARJETA_NARANJA', 'VISA_GALICIA', 'VISA_HIPOTECARIO')
    """)
    print(f"Deleted {cur.rowcount} records from bancos_archivos_metadata.")
    
    conn.commit()
    conn.close()

def run_parsers():
    print("\n🚀 Running credit card parsers...")
    for name, path in PDFS.items():
        if not os.path.exists(path):
            print(f"❌ File not found: {path}")
            continue
            
        print(f"\n--- Processing {name} ({os.path.basename(path)}) ---")
        if name == "VISA_HIPOTECARIO":
            success, info = parser_visa_hipotecario.procesar_archivo(path)
        elif name == "VISA_GALICIA":
            success, info = parser_visa_galicia.procesar_archivo(path)
        elif name == "MASTERCARD_GALICIA":
            success, info = parser_mastercard_galicia.procesar_archivo(path)
        elif name == "TARJETA_NARANJA":
            success, info = parser_naranja_pdf.procesar_archivo(path)
        elif name == "PATAGONIA365":
            success, info = parser_patagonia_pdf.procesar_archivo(path)
        print(f"Result: Success={success}, Info={info}")

def show_results():
    print("\n📊 Current Database Classifications:")
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT gr.fuente, gt.cuenta_codigo, gt.nombre, count(*), sum(gr.monto) 
        FROM gastos_registros gr 
        JOIN gastos_tipos gt ON gr.gasto_tipo_id = gt.id 
        GROUP BY gr.fuente, gt.cuenta_codigo, gt.nombre
        ORDER BY gr.fuente, gt.cuenta_codigo, gt.nombre
    """).fetchall()
    
    for r in rows:
        print(f" - {r[0]} | Account: {r[1]} | Category: {r[2]} | Count: {r[3]} | Total: ${r[4]:.2f}")
    conn.close()

if __name__ == '__main__':
    clean_database()
    run_parsers()
    show_results()
