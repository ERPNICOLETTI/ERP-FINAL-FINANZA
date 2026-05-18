import os
import hashlib
import json
import pandas as pd
import datetime
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modulo_bancos.storage_bancos import save_movimiento_banco
from modulo_bancos.motor_categorias import categorizar_movimiento

def parse_galicia_excel(filepath: str):
    """
    Parser Híbrido para Banco Galicia (Caja de Ahorro).
    Soporta formato asimétrico y cabeceras flotantes.
    """
    print(f"[BANCOS] Iniciando Parser Galicia: {os.path.basename(filepath)}")
    
    # 1. Calcular hash para idempotencia
    with open(filepath, "rb") as f:
        hash_archivo = hashlib.sha256(f.read()).hexdigest()
        
    # 2. Extraer contexto superior (Cuenta) usando Pandas para leer el crudo
    df_raw = pd.read_excel(filepath, header=None, nrows=10)
    
    cuenta_detectada = "DESCONOCIDA"
    tipo_cuenta_prefijo = ""
    fila_cabecera = None
    
    # [NUEVO] Capturar TODA la cabecera "fuera de la tabla" para el JSON crudo
    metadatos_globales = {}
    
    for i, row in df_raw.iterrows():
        fila_texto = " | ".join([str(c) for c in row.values if pd.notna(c) and str(c).strip() != ''])
        if fila_texto:
            metadatos_globales[f"cabecera_fila_{i}"] = fila_texto
            
            # Detectar el tipo de cuenta desde el texto (ej: "Banco Galicia - Caja Ahorro Pesos")
            texto_upper = fila_texto.upper()
            if "CAJA AHORRO PESOS" in texto_upper:
                tipo_cuenta_prefijo = "CA$ "
            elif "CUENTA CORRIENTE" in texto_upper:
                tipo_cuenta_prefijo = "CC$ "
            elif "DOLARES" in texto_upper or "DÓLARES" in texto_upper:
                tipo_cuenta_prefijo = "CA U$D "
            
        for cell in row.values:
            if isinstance(cell, str) and "Cuenta:" in cell:
                cuenta_detectada = tipo_cuenta_prefijo + cell.replace("Nro. de Cuenta:", "").strip()
            
            if isinstance(cell, str) and "Fecha" in cell and "Movimiento" in row.values:
                fila_cabecera = i
                break
        if fila_cabecera is not None:
            break
            
    if fila_cabecera is None:
        print("Error: No se encontró la fila 'Fecha' de cabecera en el extracto.")
        return False, {}
        
    # 3. Leer la tabla real saltando la basura de arriba
    df = pd.read_excel(filepath, skiprows=fila_cabecera)
    
    # 4. Limpieza básica (quitar filas vacías decorativas del banco)
    df = df.dropna(subset=['Fecha']) 
    
    lista_movimientos = []
    
    # [ESTRATEGIA ANTI-COLISIÓN DE FILAS IDÉNTICAS]
    # Memoria temporal para rastrear firmas exactas dentro de este mismo archivo.
    # Si un usuario compra 2 veces en el mismo lugar por el mismo monto en el mismo día,
    # el banco emite dos filas idénticas. Para que SQLite no las descarte como "archivos subidos 2 veces",
    # les agregamos un contador secuencial (2), (3) a la descripción.
    firmas_vistas = {}
    
    for _, row in df.iterrows():
        # Ignorar si dice "Fecha" de nuevo por algún error de paginación
        if str(row['Fecha']).strip().lower() == 'fecha':
            continue
            
        # Parsear fecha a ISO YYYY-MM-DD
        fecha_val = row['Fecha']
        if isinstance(fecha_val, datetime.datetime):
            fecha_iso = fecha_val.strftime("%Y-%m-%d")
        else:
            try:
                fecha_str = str(fecha_val).split(" ")[0]
                fecha_iso = datetime.datetime.strptime(fecha_str, "%d/%m/%Y").strftime("%Y-%m-%d")
            except ValueError:
                fecha_iso = str(fecha_val)
                
        # Función para limpiar dinero con puntos y comas latinas
        def clean_money(val):
            if pd.isna(val): return 0.0
            # Si el valor ya es float o int, retornarlo
            if isinstance(val, (int, float)): return float(val)
            
            s = str(val).replace('$', '').strip()
            # Si tiene formato "-300.000,00"
            s = s.replace('.', '')  # Quita separador de miles
            s = s.replace(',', '.') # Cambia coma decimal por punto
            try: return float(s)
            except: return 0.0
            
        debito = clean_money(row.get('Débito', 0))
        # Algunos bancos ponen el débito positivo, si es así lo forzamos a negativo
        if debito > 0: debito = -debito
            
        credito = clean_money(row.get('Crédito', 0))
        
        importe_final = debito if debito != 0 else credito
        saldo = clean_money(row.get('Saldo Parcial', 0))
        
        # Limpiar saltos de linea para la columna dura
        mov_raw = str(row.get('Movimiento', ''))
        desc_limpia = " | ".join([line.strip() for line in mov_raw.split('\n') if line.strip()])
        desc_limpia = desc_limpia[:240] # Trucamos por seguridad
        
        # --- Lógica Anti-Colisión ---
        firma_fila = f"{fecha_iso}_{desc_limpia}_{importe_final}_{saldo}"
        
        if firma_fila in firmas_vistas:
            firmas_vistas[firma_fila] += 1
            desc_limpia = f"{desc_limpia} ({firmas_vistas[firma_fila]})"
        else:
            firmas_vistas[firma_fila] = 1
            
        # 5. Aplicar la Regla Core vs Meta_JSON y Categorizar
        categoria_asignada = categorizar_movimiento(desc_limpia, importe_final)
        
        mov_dict = {
            # --- Columnas Duras (Core) ---
            'banco': 'GALICIA',
            'cuenta': cuenta_detectada,
            'fecha': fecha_iso,
            'descripcion': desc_limpia,
            'importe': importe_final,
            'saldo': saldo,
            'categoria': categoria_asignada,
            'path_archivo': filepath,
            'hash_archivo': hash_archivo,
            
            # --- Bolsón Meta JSON ---
            'galicia_movimiento_raw': mov_raw,
        }
        
        # Inyectar TODOS los datos sobrantes de la fila de excel original
        for col in df.columns:
            if col not in ['Fecha', 'Movimiento']:
                mov_dict[col] = str(row.get(col, ''))
                
        lista_movimientos.append(mov_dict)
        
    print(f"Detectados {len(lista_movimientos)} movimientos de Galicia.")
    
    # 6. Inyección Híbrida a la DB (Patrón Repositorio)
    agregados, last_id = save_movimiento_banco(lista_movimientos, hash_archivo, metadatos_archivo=metadatos_globales)
    
    if last_id is None and agregados == 0:
        print("No se guardaron registros nuevos (Es posible que el archivo ya fue ingestido o son duplicados exactos).")
        return False, {}
        
    print(f"Exito! {agregados} movimientos insertados en bancos_movimientos.")
    
    return True, {
        "modulo": "BANCOS",
        "entidad": "GALICIA",
        "db_table": "bancos_movimientos",
        "id_insertado": last_id,
        "registros_nuevos": agregados
    }

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        parse_galicia_excel(sys.argv[1])
    else:
        print("Uso: python parser_galicia.py <ruta_al_excel>")
