import pdfplumber
import os
import re
import json

# PARSER PAGOS SINDICALES v5.4.0 🧠🧾
# Lee el contenido exacto del PDF y lo refleja en DB sin interpretación.
# Soporta formato SEC/POLICIA y formato FAECYS/INACAP.

def procesar_pago(filepath):
    """
    Extrae exactamente lo que dice el PDF: concepto, periodo, montos y vencimientos.
    Nunca infiere ni presupone valores.
    Retorna (True, dict) o (False, None).
    """
    if not os.path.exists(filepath):
        return False, None

    info = {
        'modulo':            'PAGOS',
        'categoria':         'SINDICALES',
        'concepto':          'DESCONOCIDO',
        'periodo_mes':       None,
        'periodo_anio':      None,
        'monto':             None,   # None = no encontrado, no 0
        'fecha_vencimiento': None,
        'monto_2':           None,
        'fecha_vencimiento_2': None,
        'es_comprobante':    False,  # SOLO True si el NOMBRE del archivo lo indica
        'meta_json':         {}
    }

    try:
        with pdfplumber.open(filepath) as pdf:
            if not pdf.pages:
                return False, None

            # Juntar todo el texto de todas las páginas
            full_text = ""
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    full_text += t + "\n"

            info['meta_json']['full_text'] = full_text
            TU = full_text.upper()

            # ─────────────────────────────────────────────
            # 1. IDENTIFICAR CONCEPTO / SINDICATO
            # ─────────────────────────────────────────────
            if "INACAP" in TU:
                info['concepto']  = 'INACAP'
            elif "FAECYS" in TU:
                info['concepto']  = 'FAECYS'
            elif re.search(r'\bSEC\b', TU) or "SINDICATO DE EMPLEADOS DE COMERCIO" in TU:
                info['concepto']  = 'SEC'
            elif "TRABAJO - TASAS" in TU or "SECRETARIA DE TRABAJO" in TU or "MINISTERIO DE TRABAJO" in TU:
                info['concepto']  = 'POLICIA'
            elif "SERVICOOP" in TU:
                info['concepto']  = 'SERVICOOP'
                info['categoria'] = 'SERVICIOS'
            elif "RED UNO" in TU or "REDUNO" in TU:
                info['concepto']  = 'REDUNO'
                info['categoria'] = 'SERVICIOS'
            else:
                info['concepto']  = 'SINDICAL_GENERICO'

            # ─────────────────────────────────────────────
            # 2. EXTRAER PERIODO
            #    Soporta 3 formatos según sindicato:
            #    - FAECYS/INACAP: PERIODO: MM/YYYY  → regex estándar
            #    - POLICIA:       PERIODO: YYYYMM   → ej. 202601
            #    - SEC:           YYYY-MM dentro de ítems de tabla → ej. 2026-01
            # ─────────────────────────────────────────────

            # Formato A: PERIODO: MM/YYYY (FAECYS, INACAP)
            m = re.search(r'PER[IÍI]ODO[:\s]+(\d{2})/(\d{4})', TU)
            if m:
                info['periodo_mes']  = m.group(1)
                info['periodo_anio'] = m.group(2)

            # Formato B: PERIODO: YYYYMM (POLICIA) → ej. "PERIODO: 202601"
            if not info['periodo_mes']:
                m2 = re.search(r'PER[IÍI]ODO[:\s]+(\d{4})(\d{2})\b', TU)
                if m2:
                    info['periodo_anio'] = m2.group(1)
                    info['periodo_mes']  = m2.group(2)

            # Formato C: YYYY-MM dentro de ítems de tabla (SEC) → ej. "2026-01 Sec.00 ..."
            if not info['periodo_mes'] and info['concepto'] == 'SEC':
                m3 = re.search(r'\b(\d{4})-(\d{2})\s+SEC', TU)
                if m3:
                    info['periodo_anio'] = m3.group(1)
                    info['periodo_mes']  = m3.group(2)

            # Fallback: nombre del archivo  _MM-YYYY_
            if not info['periodo_mes']:
                fname = os.path.basename(filepath)
                mf = re.search(r'_(\d{2})-(\d{4})_', fname.upper())
                if mf:
                    info['periodo_mes']  = mf.group(1)
                    info['periodo_anio'] = mf.group(2)

            # ─────────────────────────────────────────────
            # 3. EXTRAER VENCIMIENTOS Y MONTOS
            #    Hay 2 formatos en estos PDFs:
            #
            #    FORMATO A (SEC / POLICIA):
            #      "Fecha 1er Vto: 16/02/2026"
            #      "Fecha 2do Vto: 26/02/2026"
            #      El monto está en la tabla → buscar patrón "$ X.XXX,XX"
            #      precedido por un concepto de la fila
            #
            #    FORMATO B (FAECYS / INACAP):
            #      "MONTO TOTAL A DEPOSITAR"
            #      "Fecha Primer Vto. : 09/02/2026 $ 3.996,94"
            #      "Fecha Segundo Vto. : 28/02/2026 $ X.XXX,XX"
            # ─────────────────────────────────────────────

            # --- FORMATO B: FAECYS / INACAP ---
            # Busca "Fecha Primer Vto" con monto justo después
            patron_b1 = re.search(
                r'FECHA PRIMER VTO\.?\s*:?\s*(\d{2}/\d{2}/\d{4})\s*\$\s*([\d\.]+,\d{2})',
                TU
            )
            patron_b2 = re.search(
                r'FECHA SEGUNDO VTO\.?\s*:?\s*(\d{2}/\d{2}/\d{4})\s*\$\s*([\d\.]+,\d{2})',
                TU
            )

            if patron_b1:
                info['fecha_vencimiento'] = _iso(patron_b1.group(1))
                info['monto']             = _parse_monto(patron_b1.group(2))
            if patron_b2:
                info['fecha_vencimiento_2'] = _iso(patron_b2.group(1))
                info['monto_2']             = _parse_monto(patron_b2.group(2))

            # --- FORMATO C: INACAP ---
            # "VENCIMIENTO: 18/02/2026" + "Monto Total: $ 5.278,97"
            if not info['fecha_vencimiento'] and "INACAP" in TU:
                pat_vto = re.search(r'VENCIMIENTO:\s*(\d{2}/\d{2}/\d{4})', TU)
                pat_monto = re.search(r'MONTO TOTAL:\s*\$\s*([\d\.]+,\d{2})', TU)
                if pat_vto:
                    info['fecha_vencimiento'] = _iso(pat_vto.group(1))
                if pat_monto:
                    info['monto'] = _parse_monto(pat_monto.group(1))

            # --- FORMATO D: POLICIA (TASAS) ---
            # "VENCIMIENTO: 18/02/2026" + "TOTAL A PAGAR $ 5.859,52"
            if not info['fecha_vencimiento'] and "POLICIA" == info['concepto']:
                pat_vto = re.search(r'VENCIMIENTO:\s*(\d{2}/\d{2}/\d{4})', TU)
                pat_monto = re.search(r'TOTAL A PAGAR\s*\$\s*([\d\.]+,\d{2})', TU)
                if pat_vto:
                    info['fecha_vencimiento'] = _iso(pat_vto.group(1))
                if pat_monto:
                    info['monto'] = _parse_monto(pat_monto.group(1))

            # --- FORMATO A: SEC (tabla con Fecha 1er/2do Vto y montos separados) ---
            if not info['fecha_vencimiento'] and "SEC" == info['concepto']:
                pat_a1 = re.search(r'FECHA\s+1ER\s+VTO\.?\s*:?\s*(\d{2}/\d{2}/\d{4})', TU)
                pat_a2 = re.search(r'FECHA\s+2DO\s+VTO\.?\s*:?\s*(\d{2}/\d{2}/\d{4})', TU)
                if pat_a1:
                    info['fecha_vencimiento'] = _iso(pat_a1.group(1))
                if pat_a2:
                    info['fecha_vencimiento_2'] = _iso(pat_a2.group(1))
                # En SEC el monto está en formato: fecha $ importe  (2 veces, por cada vto)
                # Buscamos pares DD/MM/AAAA seguido de $ X.XXX,XX
                pares_sec = re.findall(r'(\d{2}/\d{2}/\d{4})\s*\$?\s*([\d\.]+,\d{2})', TU)
                montos_sec = []
                for fecha_str, monto_str in pares_sec:
                    val = _parse_monto(monto_str)
                    if val and val > 1000:  # Montos sindicales > $1000
                        iso = _iso(fecha_str)
                        if iso not in [x[0] for x in montos_sec]:  # no duplicar misma fecha
                            montos_sec.append((iso, val))
                montos_sec.sort(key=lambda x: x[0])
                if montos_sec:
                    info['fecha_vencimiento'] = montos_sec[0][0]
                    info['monto'] = montos_sec[0][1]
                    if len(montos_sec) > 1:
                        info['fecha_vencimiento_2'] = montos_sec[1][0]
                        info['monto_2'] = montos_sec[1][1]

            # ─────────────────────────────────────────────
            # 4. es_comprobante: SOLO por nombre de archivo
            #    (el texto de la boleta contiene "PAGO" pero NO es comprobante)
            # ─────────────────────────────────────────────
            # Esta lógica se maneja en logic_pagos.py por nombre de archivo.
            # El parser NUNCA setea es_comprobante=True.
            info['es_comprobante'] = False

        return True, info

    except Exception as e:
        print(f"❌ [PARSER] Error en {os.path.basename(filepath)}: {e}")
        return False, None


def _iso(fecha_str):
    """Convierte DD/MM/AAAA → AAAA-MM-DD para SQL."""
    try:
        partes = fecha_str.strip().split('/')
        return f"{partes[2]}-{partes[1]}-{partes[0]}"
    except:
        return None


def _parse_monto(monto_str):
    """Convierte '15.987,77' → 15987.77"""
    try:
        return float(monto_str.replace('.', '').replace(',', '.'))
    except:
        return None


if __name__ == "__main__":
    import sys
    test_files = {
        'SEC':    r'C:\Users\essao\Downloads\boletas\27329549971_02-2026_BOLETA_SINDICAL_05-02-2026-13_05_23.pdf',
        'INACAP': r'C:\Users\essao\Downloads\boletas\27329549971_02-2026_BOLETA_SINDICAL_05-02-2026-15_58_47.pdf',
        'POLICIA':r'C:\Users\essao\Downloads\boletas\27329549971_02-2026_BOLETA_SINDICAL_05-02-2026-13_05_00.pdf',
        'FAECYS': r'C:\Users\essao\Downloads\boletas\27329549971_02-2026_BOLETA_SINDICAL_06-02-2026-15_12_42.pdf',
    }
    for nombre, path in test_files.items():
        ok, d = procesar_pago(path)
        if ok:
            print(f"\n✅ {nombre}")
            print(f"   Periodo:  {d['periodo_mes']}/{d['periodo_anio']}")
            print(f"   Monto 1:  ${d['monto']}  vto: {d['fecha_vencimiento']}")
            print(f"   Monto 2:  ${d['monto_2']}  vto: {d['fecha_vencimiento_2']}")
            print(f"   Comprobante: {d['es_comprobante']}")
        else:
            print(f"\n❌ {nombre}: falló el parser")
