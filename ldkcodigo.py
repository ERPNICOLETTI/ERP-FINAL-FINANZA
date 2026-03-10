import os
import time
import csv
import re
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import win32print

# ================= CONFIG =================

# ACTUALIZADO A LA RUTA DE LA NOTEBOOK
CARPETA = r"C:\Users\DELL"
ARCHIVO = "Etiquetas.csv"
IMPRESORA = "Xprinter XP-410B"

ANCHO_TOTAL_ROLLO = 800
ALTO_ETIQUETA = 160
OFFSETS_X = [8, 275, 545]

# ================= UTIL =================

def formatear_precio(valor):
    try:
        # Limpia el valor de símbolos de moneda o espacios
        valor_limpio = ''.join(c for c in str(valor) if c.isdigit() or c in '.,')
        valor_limpio = valor_limpio.replace(',', '.')
        numero = float(valor_limpio)
        return f"{int(round(numero)):,}".replace(",", ".")
    except:
        return valor

# ================= ZPL =================

def generar_bloque_etiqueta(data, base_x):
    """Genera el contenido ZPL para una etiqueta en una posición X dada"""
    codigo = data.get("CodBarras", "").strip()
    if not codigo: 
        return ""
    
    nombre = data.get("Nombre", "").strip()[:40]
    precio = formatear_precio(data.get("Precio", "0"))
    barcode_x = base_x + 10
    
    # Diseño original ajustado
    return f"^FO{barcode_x},5^BY2^BCN,50,N,N,N^FD{codigo}^FS^FO{base_x+5},60^A0N,22,22^FB210,1,0,C^FD{codigo}^FS^FO{base_x+5},85^A0N,20,20^FB210,2,0,C^FD{nombre}^FS^FO{base_x+30},130^A0N,25,25^FD$ {precio}^FS"

# ================= IMPRESIÓN =================

def imprimir_zpl(zpl):
    if not zpl.strip(): return
    try:
        h = win32print.OpenPrinter(IMPRESORA)
        win32print.StartDocPrinter(h, 1, ("Etiquetas_ERP", None, "RAW"))
        win32print.StartPagePrinter(h)
        win32print.WritePrinter(h, zpl.encode("latin-1"))
        win32print.EndPagePrinter(h)
        win32print.EndDocPrinter(h)
        win32print.ClosePrinter(h)
    except Exception as e:
        print(f"❌ Error Impresora: {e}")

# ================= PROCESAMIENTO ESPECIAL =================

def procesar_csv(path):
    time.sleep(1.2) # Tiempo extra para sincronización de OneDrive
    if not os.path.exists(path): return

    filas = []
    try:
        # LEER ARCHIVO TRATANDO EL FORMATO PEGADO
        with open(path, 'r', encoding='utf-8') as f:
            raw = f.read().strip()
            
        if not raw:
            return

        # El ERP pega todo sin saltos de línea: CodBarras,Nombre,PrecioVALOR1,NOMBRE1,PRECIO1...
        # Usamos Regex para buscar el patrón: Alfanumérico (Código), Texto (Nombre), Numero (Precio)
        import re
        # El patrón busca: Letras/Números (Código), cualquier texto hasta la coma (Nombre), y números con punto (Precio)
        items = re.findall(r'([A-Z0-9]+),([^,]+),([\d.]+)', raw)
        
        for item in items:
            cod, nom, pre = item
            if cod == "CodBarras" or "Precio" in cod: continue 
            filas.append({"CodBarras": cod, "Nombre": nom, "Precio": pre})
            
    except Exception as e:
        print(f"❌ Error leyendo archivo: {e}")
        return

    if not filas:
        print("⚠ No se encontraron datos válidos en el archivo.")
        return

    impresas = 0
    # Procesar de a 3 (3 bandas)
    for i in range(0, len(filas), 3):
        grupo = filas[i:i+3]
        zpl = f"^XA\n^PW{ANCHO_TOTAL_ROLLO}\n^LL{ALTO_ETIQUETA}\n"
        count = 0
        for idx, f in enumerate(grupo):
            bloque = generar_bloque_etiqueta(f, OFFSETS_X[idx])
            if bloque:
                zpl += bloque
                count += 1
        zpl += "\n^XZ"
        
        if count > 0:
            imprimir_zpl(zpl)
            impresas += count

    print(f"✅ Impresión finalizada: {impresas} etiquetas procesadas.")

# ================= MONITOR =================

class Handler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory and os.path.basename(event.src_path) == ARCHIVO:
            procesar_csv(event.src_path)
    def on_created(self, event):
        if not event.is_directory and os.path.basename(event.src_path) == ARCHIVO:
            procesar_csv(event.src_path)

def main():
    if not os.path.exists(CARPETA):
        print(f"❌ Error: La carpeta {CARPETA} no existe.")
        return

    observer = Observer()
    observer.schedule(Handler(), CARPETA, recursive=False)
    observer.start()

    print(f"👀 Monitoreando: {os.path.join(CARPETA, ARCHIVO)}")
    
    # Procesar al inicio si ya existe
    ruta_csv = os.path.join(CARPETA, ARCHIVO)
    if os.path.exists(ruta_csv):
        procesar_csv(ruta_csv)

    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
