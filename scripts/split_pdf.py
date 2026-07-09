import os
from PyPDF2 import PdfReader, PdfWriter

INBOX_DIR = r"C:\Users\essao\Desktop\Facturas inbox"
OUTPUT_DIR = os.path.join(INBOX_DIR, "divididas")

def split_all_pdfs():
    if not os.path.exists(INBOX_DIR):
        print(f"[ERROR] La carpeta no existe: {INBOX_DIR}")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    files = [f for f in os.listdir(INBOX_DIR) if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(INBOX_DIR, f))]

    if not files:
        print("[INFO] No se encontraron archivos PDF para dividir.")
        return

    print(f"[OK] Analizando {len(files)} archivos PDF en: {INBOX_DIR}\n")

    for f in files:
        file_path = os.path.join(INBOX_DIR, f)
        base_name, _ = os.path.splitext(f)
        
        try:
            reader = PdfReader(file_path)
            total_pages = len(reader.pages)
            
            if total_pages <= 1:
                print(f"[INFO] {f} tiene solo 1 pagina, no requiere division.")
                continue
                
            print(f"[PROCESANDO] Dividiendo '{f}' ({total_pages} paginas)...")
            
            for page_num in range(total_pages):
                writer = PdfWriter()
                writer.add_page(reader.pages[page_num])
                
                # Nombre del archivo para la página individual
                out_filename = f"{base_name}_pag_{page_num + 1}.pdf"
                out_filepath = os.path.join(OUTPUT_DIR, out_filename)
                
                with open(out_filepath, "wb") as out_file:
                    writer.write(out_file)
                    
            print(f"   [OK] {total_pages} paginas guardadas en la carpeta 'divididas'.")
            
        except Exception as e:
            print(f"[ERROR] Error procesando {f}: {e}")

    print(f"\n[FIN] ¡Proceso finalizado! Los PDFs divididos estan en: {OUTPUT_DIR}")

if __name__ == "__main__":
    split_all_pdfs()
