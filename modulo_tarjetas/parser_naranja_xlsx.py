import pandas as pd
import os
import sys
import re

# Parser Naranja XLSX (Digitalización Bit a Bit) 🏗️🧱🧠⚖️🚀
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core_sistema import db_ingesta as ingesta

def normalizar_importe(val):
    if pd.isna(val) or val is None: return 0.0
    if isinstance(val, (int, float)): return float(val)
    # Si es string "$ 100.369,49"
    s = str(val).replace("$", "").replace(" ", "").strip()
    s = "".join(c for c in s if c in "0123456789.,-")
    if not s: return 0.0
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."): s = s.replace(".", "").replace(",", ".")
        else: s = s.replace(",", "")
    elif "," in s: s = s.replace(",", ".")
    try: return float(s)
    except: return 0.0

def parse_naranja_xlsx(file_path):
    print(f"💎 PROCESANDO NARANJA XLSX: {os.path.basename(file_path)}")
    try:
        df = pd.read_excel(file_path)
        
        # Mapeo de meses en español a números (por si la fecha viene en texto)
        meses = {
            'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04', 'MAY': '05', 'JUN': '06',
            'JUL': '07', 'AGO': '08', 'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'
        }

        for _, row in df.iterrows():
            # Normalizar Fecha (Naranja usa 27/ENE/26)
            fecha_raw = str(row['Fecha'])
            fecha_iso = None
            m = re.search(r'(\d+)/([A-Z]+)/(\d+)', fecha_raw)
            if m:
                dia = m.group(1).zfill(2)
                mes_esp = m.group(2)
                anio = "20" + m.group(3)
                mes_num = meses.get(mes_esp, "01")
                fecha_iso = f"{anio}-{mes_num}-{dia}"
            
            periodo = fecha_iso[:7] if fecha_iso else "Desconocido"

            header = {
                "fuente": "NARANJA",
                "tipo": "DIARIA",
                "marca": "NARANJA",
                "fecha_liquidacion": fecha_iso,
                "periodo": periodo,
                "total_bruto": normalizar_importe(row.get('Monto bruto')),
                "total_neto": normalizar_importe(row.get('Monto neto')),
                "costo_arancel": normalizar_importe(row.get('Arancel')),
                "costo_financiero": normalizar_importe(row.get('Interes por plan', 0)) + normalizar_importe(row.get('Interes por pago anticipado', 0)),
                "iva_21": normalizar_importe(row.get('IVA', 0)) + normalizar_importe(row.get('Percepción IVA', 0)),
                "retenciones": normalizar_importe(row.get('Retención de ingresos brutos', 0)) + normalizar_importe(row.get('SIRTAC', 0)) + normalizar_importe(row.get('Retención IVA', 0)) + normalizar_importe(row.get('Retención ganancias', 0)),
                "establecimiento": str(row.get('N° de comercio', '')),
                "metadata": row.to_dict()
            }

            # Persistencia Capa 1
            liq_id = ingesta.persistir_liquidacion(header)
            
            # Capa 2: Fragmentos Atómicos (Cada columna es un detalle)
            fragmentos = []
            for col, val in row.items():
                if pd.notna(val) and val != 0:
                    fragmentos.append({
                        "fecha": fecha_iso,
                        "descripcion": f"Col: {col}",
                        "monto_bruto": normalizar_importe(val) if isinstance(val, (int, float, str)) and any(c.isdigit() for c in str(val)) else 0.0,
                        "metadata_raw": {"valor_original": str(val)}
                    })
            
            if liq_id:
                ingesta.persistir_liquidacion_detalle(liq_id, fragmentos)
        
        print(f"🧱 Éxito: XLSX Naranja procesado. {len(df)} liquidaciones diarias ingresadas.")

    except Exception as e:
        print(f"Error procesando Naranja XLSX: {e}")

if __name__ == "__main__":
    import glob
    path = r"C:\Users\essao\Downloads\Naranja\*.xlsx"
    archivos = glob.glob(path)
    for a in archivos:
        parse_naranja_xlsx(a)
