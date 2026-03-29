import pdfplumber

with pdfplumber.open(r'C:\Users\essao\Downloads\LiqMensual202601.pdf') as pdf:
    for i, page in enumerate(pdf.pages):
        print(f"--- PAGINA {i+1} ---")
        text = page.extract_text()
        if text:
            print(text)
        else:
            print("No se pudo extraer texto")
