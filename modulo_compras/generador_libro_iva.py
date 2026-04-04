import os
import sys
import pdfplumber
import re
import hashlib
from . import storage_compras as storage

# GENERADOR/PARSER LIBRO IVA - v4.0 GOLDEN MASTER 🧾🏗️⚖️🚀
# Refactorizado para cumplir con el Patrón Repositorio y el flujo Inbox.

def parse_money(m_str):
    try:
        clean = m_str.replace('$', '').replace('.', '').replace(',', '.').strip()
        return float(clean)
    except:
        return 0.0

def procesar_archivo(filepath):
    """Parsea el PDF F.2051 y lo guarda en la DB vía Repository Pattern."""
    print(f"📄 [LIBRO IVA] Digitalizando Declaración Jurada F.2051: {os.path.basename(filepath)}")
    
    periodo = None
    debito = 0.0
    credito = 0.0
    saldo_tecnico = 0.0
    saldo_ld = 0.0
    
    try:
        # 1. Generar Hash para Idempotencia
        with open(filepath, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

        # 2. Extracción de Datos
        with pdfplumber.open(filepath) as pdf:
            text = '\n'.join([page.extract_text() for page in pdf.pages if page.extract_text()])
            
            # Período (Ej: 202601 -> 2026-01)
            match_per = re.search(r'Período[^\d]*(\d{6})', text)
            if match_per:
                p_raw = match_per.group(1)
                periodo = f"{p_raw[:4]}-{p_raw[4:]}"
            
            for line in text.split('\n'):
                if "Total del débito fiscal del período" in line:
                    debito = parse_money(line.split('$')[-1])
                elif "Total del crédito fiscal del período" in line:
                    credito = parse_money(line.split('$')[-1])
                elif "Saldo técnico a favor del contribuyente" in line and "$" in line:
                    saldo_tecnico = parse_money(line.split('$')[-1])
                elif "Saldo de libre disponibilidad a favor del contribuyente del período" in line:
                    saldo_ld = parse_money(line.split('$')[-1])
                    
            if not periodo:
                return False, {"error": "No se encontró el período fiscal en el PDF"}
            
            # 3. Persistencia vía Storage (Sin SQL directo)
            success = storage.save_libro_iva({
                "periodo": periodo,
                "debito_fiscal": debito,
                "credito_fiscal": credito,
                "saldo_tecnico": saldo_tecnico,
                "saldo_libre_disponibilidad": saldo_ld,
                "hash_archivo": file_hash,
                "path_archivo": filepath,
                "metadata": {"source": "F.2051_PDF", "full_text_length": len(text)}
            })
            
            if success:
                return True, {
                    "modulo": "COMPRAS",
                    "entidad": "AFIP_DJ",
                    "anio": periodo[:4],
                    "mes": periodo[5:],
                    "db_table": "libroiva",
                    "info": f"Libro IVA {periodo} procesado correctamente"
                }
            else:
                return False, {"error": "Fallo en persistencia del Libro IVA"}

    except Exception as e:
        return False, {"error": f"Error procesando Libro IVA: {e}"}

if __name__ == "__main__":
    # Retrocompatibilidad CLI
    if len(sys.argv) < 2:
        print("Uso: python generador_libro_iva.py <archivos.pdf>")
        sys.exit(1)
        
    for f in sys.argv[1:]:
        success, info = procesar_archivo(f)
        print(f"Resultado: {success} | {info}")
