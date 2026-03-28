import os
import sys
import pdfplumber
import sqlite3
import re

# Setup utf-8
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(WORKSPACE, 'erp_nicoletti.db')

def parse_money(m_str):
    try:
        clean = m_str.replace('$', '').replace('.', '').replace(',', '.').strip()
        return float(clean)
    except:
        return 0.0

def procesar_dj_iva(filepath):
    print(f"[{os.path.basename(filepath)}] Digitalizando Declaración Jurada F.2051...")
    
    periodo = None
    debito = 0.0
    credito = 0.0
    saldo_tecnico = 0.0
    saldo_ld = 0.0
    
    try:
        with pdfplumber.open(filepath) as pdf:
            text = '\n'.join([page.extract_text() for page in pdf.pages if page.extract_text()])
            
            # Buscar período (Ej: Período\n202601)
            # Como la extracción de PDF a veces pega las palabras: "Período\n202601"
            match_per = re.search(r'Período[^\d]*(\d{6})', text)
            if match_per:
                p_raw = match_per.group(1)
                periodo = f"{p_raw[:4]}-{p_raw[4:]}" # 202601 -> 2026-01
            
            # Recorrer línea por línea buscando los valores clave
            for line in text.split('\n'):
                if "Total del débito fiscal del período" in line:
                    m_str = line.split('$')[-1]
                    debito = parse_money(m_str)
                elif "Total del crédito fiscal del período" in line:
                    m_str = line.split('$')[-1]
                    credito = parse_money(m_str)
                elif "Saldo técnico a favor del contribuyente" in line and "$" in line:
                    # Capturamos el último que aparezca por si repiten
                    m_str = line.split('$')[-1]
                    saldo_tecnico = parse_money(m_str)
                elif "Saldo de libre disponibilidad a favor del contribuyente del período" in line:
                    m_str = line.split('$')[-1]
                    saldo_ld = parse_money(m_str)
                    
            if not periodo:
                print(f"Error: No pudimos encontrar el 'Período' en {filepath}.")
                return
                
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            
            # Upsert a la tabla libroiva
            cur.execute('''
                INSERT INTO libroiva (
                    periodo, debito_fiscal, credito_fiscal, saldo_tecnico, saldo_libre_disponibilidad
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(periodo) DO UPDATE SET
                    debito_fiscal = excluded.debito_fiscal,
                    credito_fiscal = excluded.credito_fiscal,
                    saldo_tecnico = excluded.saldo_tecnico,
                    saldo_libre_disponibilidad = excluded.saldo_libre_disponibilidad
            ''', (periodo, debito, credito, saldo_tecnico, saldo_ld))
            
            conn.commit()
            conn.close()
            
            print(f"✅ ¡Guardado Exitoso! Período [ {periodo} ]")
            print(f"   -> Débito (Ventas): $ {debito:,.2f}")
            print(f"   -> Crédito (Compras): $ {credito:,.2f}")
            print(f"   -> Saldo Técnico: $ {saldo_tecnico:,.2f}")
            print(f"   -> Libre Disponib.: $ {saldo_ld:,.2f}")
            print("---------------------------------------------------------")
            
    except Exception as e:
        print(f"Error procesando el PDF: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("💡 Uso: python import/parser_libroiva.py <archivos.pdf>")
        sys.exit(1)
        
    for file in sys.argv[1:]:
        procesar_dj_iva(file)
