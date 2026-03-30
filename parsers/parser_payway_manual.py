import re
import os
import sys
import json

# Motor de Extracción de Resúmenes Mensuales Payway (Texto Manual) 💎🏗️🧱🧠
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import ingesta

def normalizar_importe(texto):
    if not texto: return 0.0
    texto = str(texto).replace(".", "").replace(",", ".")
    try: return float(texto)
    except: return 0.0

def parse_payway_manual_text(text):
    print("💎 PROCESANDO RESUMEN MENSUAL PAYWAY (TEXTO MANUAL)...")
    
    # 1. Extraer Cabecera General
    # TOTAL PRESENTADO $ 1.164.900,00
    m_bruto = re.search(r'TOTAL PRESENTADO \$ ([\d\.,]+)', text)
    m_descuento = re.search(r'TOTAL DESCUENTO \$ ([\d\.,]+)', text)
    m_neto_total = re.search(r'SALDO \$ ([\d\.,]+)', text)
    m_fecha = re.search(r'FECHA DE EMISION:\s+(\d{2}/\d{2}/\d{4})', text)
    m_est = re.search(r'Nº DE ESTABLECIMIENTO:\s+(\d+)', text)
    
    fecha_emision = m_fecha.group(1) if m_fecha else "2026-02-28"
    # Convertir a ISO
    if "/" in fecha_emision:
        dia, mes, anio = fecha_emision.split('/')
        fecha_iso = f"{anio}-{mes}-{dia}"
        periodo = f"{anio}-{mes}"
    else:
        fecha_iso = "2026-02-28"
        periodo = "2026-02"

    header = {
        "fuente": "PAYWAY_RESUMEN",
        "tipo": "MENSUAL",
        "fecha_liquidacion": fecha_iso,
        "periodo": periodo,
        "marca": "MULTIPLES",
        "establecimiento": m_est.group(1) if m_est else "0029271756",
        "total_bruto": normalizar_importe(m_bruto.group(1)) if m_bruto else 0.0,
        "total_neto": normalizar_importe(m_neto_total.group(1)) if m_neto_total else 0.0,
        "metadata": {"tipo_fuente": "TEXT_COPY_PASTE"}
    }
    
    # Extraer Datos de Desglose (Si existen en el texto)
    m_arancel_c = re.search(r'Arancel Tj.Crédito [\d\.,]+ % \$ ([\d\.,]+)', text)
    m_arancel_d = re.search(r'Arancel Tj.Débito [\d\.,]+ % \$ ([\d\.,]+)', text)
    m_iva_21 = re.search(r'IVA 21,00 % \$ ([\d\.,]+)', text)
    m_iva_105 = re.search(r'IVA 10,50 % Ley 25.063 \$ ([\d\.,]+)', text)
    m_retenciones = re.search(r'Percep./Retenc.AFIP - DGI \$ ([\d\.,]+)', text)
    m_c_financiero = re.search(r'Servicio Costos Financieros.*?\$ ([\d\.,]+)', text, re.S)
    m_c_adelanto = re.search(r'Servicio Cobro Anticipado \$ ([\d\.,]+)', text)

    header["costo_arancel"] = -(normalizar_importe(m_arancel_c.group(1)) if m_arancel_c else 0.0) - (normalizar_importe(m_arancel_d.group(1)) if m_arancel_d else 0.0)
    header["costo_financiero"] = -(normalizar_importe(m_c_financiero.group(1)) if m_c_financiero else 0.0)
    header["iva_21"] = normalizar_importe(m_iva_21.group(1)) if m_iva_21 else 0.0
    header["iva_105"] = normalizar_importe(m_iva_105.group(1)) if m_iva_105 else 0.0
    header["retenciones"] = -(normalizar_importe(m_retenciones.group(1)) if m_retenciones else 0.0)

    # 2. Extraer "Bits" (Liquidaciones Diarias en el Resumen)
    bits = []
    # Buscar patrones como: FECHA DE PAGO 03/02 ... Total del día $ 154.000,00 $ 4.490,61 $ 149.509,39
    p_bits = re.findall(r'FECHA DE PAGO (\d{2}/\d{2}).*?Total del día \$ ([\d\.,]+) \$ ([\d\.,]+) \$ ([\d\.,]+)', text, re.S)
    for b in p_bits:
        dia, mes_b = b[0].split('/')
        bits.append({
            "fecha": f"{periodo}-{dia}",
            "descripcion": f"Liq Mensual Payway Pago {b[0]}",
            "monto_bruto": normalizar_importe(b[1]),
            "arancel": -normalizar_importe(b[2]), # El resumen lo pone como positivo pero es un descuento
            "monto_neto": normalizar_importe(b[3]),
            "metadata_raw": {"pago": b[0], "bruto": b[1], "descuento": b[2]}
        })

    # 3. Persistencia
    liq_id = ingesta.persistir_liquidacion(header)
    if liq_id:
        ingesta.persistir_liquidacion_detalle(liq_id, bits)
        print(f"🧱 Éxito: Resumen Payway {periodo} digitalizado con {len(bits)} liquidaciones diarias.")
        return True
    return False

if __name__ == "__main__":
    # Si se corre directo, intentamos leer de un archivo temporal de texto
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            parse_payway_manual_text(f.read())
