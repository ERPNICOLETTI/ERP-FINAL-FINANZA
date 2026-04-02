import sqlite3
import pandas as pd
import os

def conciliar_credicoop_hipotecario():
    print(f"🕵️ [CONCILIACIÓN] BUSCANDO TRANSFERENCIAS ENTRE CREDICOOP E HIPOTECARIO...")
    
    db_path = "erp_nicoletti.db"
    if not os.path.exists(db_path):
        print("❌ No se encontró la base de datos.")
        return

    conn = sqlite3.connect(db_path)
    
    # Traemos todos los movimientos de ambos bancos
    query = "SELECT banco, fecha, descripcion, importe FROM bancos_movimientos WHERE banco IN ('CREDICOOP', 'HIPOTECARIO')"
    df = pd.read_sql_query(query, conn)
    conn.close()

    # Separamos en Tablas de Salidas y Entradas
    if df.empty:
        print("❌ No hay movimientos en la base de datos.")
        return

    # Creamos subconjuntos: 
    # Debitos en CREDICOOP (salida) vs Creditos en HIPOTECARIO (entrada)
    # Debitos en HIPOTECARIO (salida) vs Creditos en CREDICOOP (entrada)
    
    credicoop = df[df['banco'] == 'CREDICOOP']
    hipotecario = df[df['banco'] == 'HIPOTECARIO']
    
    results = []
    
    print("-" * 50)
    print("SALIDAS CREDICOOP -> ENTRADAS HIPOTECARIO")
    print("-" * 50)
    
    # Buscamos coincidencias de montos aproximados (abs) y fechas
    for i, row_c in credicoop[credicoop['importe'] < 0].iterrows():
        monto_salida = abs(row_c['importe'])
        fecha_c = row_c['fecha']
        
        # Buscamos en Hipotecario una entrada (+monto_salida) cerca de la fecha_c
        # El importe debe de ser exacto
        match = hipotecario[(hipotecario['importe'] == monto_salida) | 
                            (hipotecario['importe'] == -monto_salida)].head(1) # Por si se invierte el signo en el log
        
        if not match.empty:
            row_h = match.iloc[0]
            results.append({
                'Origen': 'CREDICOOP',
                'Destino': 'HIPOTECARIO',
                'Fecha Origen': fecha_c,
                'Fecha Destino': row_h['fecha'],
                'Monto': monto_salida,
                'Estado': '✅ CONCILIADO'
            })
        else:
            results.append({
                'Origen': 'CREDICOOP',
                'Destino': 'HIPOTECARIO',
                'Fecha Origen': fecha_c,
                'Fecha Destino': 'PENDIENTE',
                'Monto': monto_salida,
                'Estado': '⚠️ SIN ENTRADA'
            })

    # Mostrar resultados en DataFrame para que se vea prolijo
    df_res = pd.DataFrame(results)
    if not df_res.empty:
        print(df_res.to_string(index=False))
        print(f"\n📊 Resumen: {len(df_res[df_res['Estado'] == '✅ CONCILIADO'])} Conciliados / {len(df_res)} Totales")
    else:
        print("No se encontraron transferencias salientes de Credicoop.")

if __name__ == "__main__":
    conciliar_credicoop_hipotecario()
