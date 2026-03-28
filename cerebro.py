import os
import requests
import sys

# Motor de Inteligencia (Cerebro) interactivo para consultar la API
API_URL = "http://127.0.0.1:5005"

def query_api(endpoint, params=None, method="GET", data=None):
    try:
        if method.upper() == "POST":
            response = requests.post(f"{API_URL}/{endpoint}", json=data, params=params)
        else:
            response = requests.get(f"{API_URL}/{endpoint}", params=params)
            
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error conectando a la API: {e}")
        return None

def trigger_sync():
    try:
        response = requests.post(f"{API_URL}/sync")
        return response.json()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("🧠 CEREBRO ERP - CONSOLA DE INTERACCIÓN")
    if len(sys.argv) < 2:
        print("Uso: python cerebro.py [resumen | notas_credito | auditar_iva <2026-01> | discrepancias | sync | buscar <texto> | adjuntar <ticket> <ruta> | forzar_adjunto <ticket> <proveedor> <ruta>]")
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    if command == "notas_credito":
        res = query_api("facturas", params={"tipo": "Nota de Crédito", "operacion": "VENTA"})
        if res and not "error" in res:
            print("\n=== TOTAL NOTAS DE CRÉDITO EMITIDAS (HISTÓRICO) ===")
            print(f"Total Encontradas: {res['count']}")
            print(f"💰 Suma Total Impactada: $ {res['total_monto']:,.2f}")
            print("============================================================\n")
    elif command == "resumen":
        anio = sys.argv[2] if len(sys.argv) > 2 else ""
        res = query_api("summary", params={"anio": anio} if anio else None)
        if res and "error" not in res:
            titulo = f"DEL AÑO {anio}" if anio else "GLOBAL"
            print(f"\n=== RESUMEN DE LA BASE DE DATOS ({titulo}) ===")
            print(f"💰 Transacciones Bancarias y Manuales:")
            print(f"   - Total: {res['transacciones']['total_registros']} registros")
            print(f"   - Período: {res['transacciones']['fecha_inicio']} a {res['transacciones']['fecha_fin']}")
            print(f"   - Monto Histórico: $ {res['transacciones']['monto_total']:,.2f}")
            print(f"\n💳 Cupones Payway (POSnet):")
            print(f"   - Total: {res['payway']['total_cupones']} cupones")
            print(f"   - Período: {res['payway']['fecha_inicio']} a {res['payway']['fecha_fin']}")
            print(f"   - Monto Bruto: $ {res['payway']['monto_total_bruto']:,.2f}")
            print(f"\n🧾 Facturas ARCA (Compras y Ventas):")
            print(f"   - Total: {res['facturas']['total_comprobantes']} comprobantes")
            print(f"   - Período: {res['facturas']['fecha_inicio']} a {res['facturas']['fecha_fin']}")
            print(f"   - Total Ventas: $ {res['facturas']['monto_ventas']:,.2f}")
            print(f"   - Total Compras: $ {res['facturas']['monto_compras']:,.2f}")
            print("===================================\n")
    elif command == "audit":
        res = query_api("audit")
        if res:
            print(f"Payway sin conciliar: {res['unmatched_payway_count']}")
    elif command == "adjuntar":
        if len(sys.argv) < 4:
            print("Uso: python cerebro.py adjuntar <numero_completo_o_id> <ruta_pdf_u_foto>")
            sys.exit(1)
        identificador = sys.argv[2]
        ruta = sys.argv[3]
        res = query_api("facturas/adjuntar", method="POST", data={"identificador": identificador, "ruta": ruta})
        print(f"\n[SISTEMA] {res.get('status', 'Error')}: {res.get('mensaje', res.get('error'))}\n")
        
    elif command == "forzar_adjunto":
        if len(sys.argv) < 5:
            print("\n🚨 USO DE URGENCIA MANUAL (Archivo Fantasma):")
            print("python cerebro.py forzar_adjunto <numero_completo> <proveedor_nombre> <ruta_pdf>\n")
            print("Ej: python cerebro.py forzar_adjunto 006-00005-00007685 'VIA CARGO SA' 'C:/ruta/foto.pdf'")
            sys.exit(1)
        identificador = sys.argv[2]
        proveedor = sys.argv[3]
        ruta = sys.argv[4]
        res = query_api("facturas/forzar_adjunto", method="POST", data={"identificador": identificador, "proveedor": proveedor, "ruta": ruta})
        print(f"\n[MODO FORZADO] {res.get('status', 'Error')}: {res.get('mensaje', res.get('error'))}\n")
    
    elif command == "buscar":
        termino = sys.argv[2] if len(sys.argv) > 2 else ""
        if not termino:
            print("ERROR: Ingrese un término. (Ej: python cerebro.py buscar 'DUO COCO')")
            sys.exit(1)
            
        res = query_api("facturas", params={"q": termino, "operacion": "COMPRA"})
        if res and "error" not in res:
            print(f"\n🔍 RESULTADOS DE AUDITORIA PARA: '{termino}'")
            print(f"Total encontrados: {res['count']}")
            print("-" * 110)
            print(f"{'FECHA':<12} | {'TICKET':<20} | {'PROVEEDOR':<30} | {'MONTO':<12} | {'ESTADOS'}")
            print("-" * 110)
            for r in res['results']:
                # Calcular íconos de estado
                afip = "✅ AFIP" if r.get('esta_en_afip') else "❌ AFIP"
                calim = "✅ CALIM" if r.get('esta_en_calim') else "❌ CALIM"
                pdf = f"📁 STATIC (PDF)" if r.get('ruta_archivo') else "📄 SIN DOC"
                
                info_line = f"-> {r['fecha_emision']:<12} | {r['numero_completo']:<20} | {r['proveedor'][:30]:<30} | $ {r['monto_total']:>10,.2f} | [{afip}] [{calim}] [{pdf}]"
                print(info_line)
            print("-" * 110 + "\n")
            
    elif command == "discrepancias":
        res = query_api("facturas/discrepancias")
        if res:
            print("\n=== ALERTAS ROJAS Y DISCREPANCIAS ===")
            
            print("\n🚨 SÓLO EN AFIP (Te olvidaste de enviar a CALIM):")
            if res['afip_pendientes_en_calim']:
                for f in res['afip_pendientes_en_calim']:
                    print(f"   -> FC {f['numero_completo']} | {f['proveedor'][:30]} | $ {f['monto_total']:,.2f}")
            else:
                print("   [Excelente] Todas las de AFIP están volcadas a CALIM.")
                
            print("\n⚠️ SÓLO EN CALIM (Manuales de Intereses, o no figuran en AFIP):")
            if res['calim_huerfanas_de_afip']:
                for f in res['calim_huerfanas_de_afip']:
                    print(f"   -> FC {f['numero_completo']} | {f['proveedor'][:30]} | $ {f['monto_total']:,.2f}")
            else:
                 print("   [Excelente] Todo CALIM coincide nativamente con AFIP.")
            print("=====================================\n")
    elif command == "iva":
        anio = sys.argv[2] if len(sys.argv) > 2 else "2026"
        res = query_api("iva", params={"anio": anio})
        if res and "error" not in res:
            print(f"\n=== BALANCE DE IVA ({res['periodo']}) ===")
            print(f"🟢 Crédito Fiscal (COMPRAS): $ {res['iva_compras_credito']:,.2f}")
            print(f"🔴 Débito Fiscal (VENTAS)  : $ {res['iva_ventas_debito']:,.2f}")
            print("------------------------------------------")
            if res['saldo_a_depositar'] > 0:
                print(f"🧾 SALDO A PAGAR: $ {res['saldo_a_depositar']:,.2f}")
            else:
                print(f"✅ SALDO A FAVOR: $ {abs(res['saldo_a_depositar']):,.2f}")
            print("==========================================\n")
    elif command == "auditar_iva":
        periodo = sys.argv[2] if len(sys.argv) > 2 else "2026-01"
        res = query_api("iva/auditar", params={"periodo": periodo})
        if res and not "error" in res:
            print(f"\n=== AUDITORÍA IMPOSITIVA PROFUNDA (PERÍODO {res['periodo']}) ===")
            print("\n[ 🔴 DÉBITO FISCAL / TUS VENTAS AL ESTADO ]")
            print(f"1. AFIP (Tus CSV Reales) : $ {res['afip_crudo']['ventas_debito']:,.2f}")
            print(f"2. Contador (PDF F.2051) : $ {res['contador_f2051']['ventas_debito']:,.2f}")
            print(f"-> BRECHA MATEMÁTICA     : $ {res['diferencias_vs_afip']['brecha_debito']:,.2f}  (Diferencia a revisar)")
            
            print("\n[ 🟢 CRÉDITO FISCAL / TUS INGRESOS COMPROBABLES ]")
            print(f"1. AFIP (Tu CSV Público) : $ {res['afip_crudo']['compras_credito']:,.2f}")
            print(f"2. CALIM (Sistema Oculto): $ {res['calim_interno']['compras_credito']:,.2f}")
            print(f"3. Contador (Libro IVA)  : $ {res['contador_f2051']['compras_credito']:,.2f}")
            print(f"-> BRECHA A TU FAVOR     : $ {res['diferencias_vs_afip']['brecha_credito']:,.2f}  (Extras salvados p/ AFIP)")
            print("=================================================================\n")
    elif command == "sync":
        trigger_sync()
        print("[OK] Sincronización de índices completada por la API.")
    else:
        print("Comando no reconocido.")
