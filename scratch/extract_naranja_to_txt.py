import PyPDF2
import sys

pdf_path = r"c:\Users\essao\Desktop\ERP FINAL\modulo_bancos\inbox_bancos\resumen-tarjeta-naranja-1780932133.pdf"
out_path = r"c:\Users\essao\Desktop\ERP FINAL\scratch\naranja_text.txt"

with open(pdf_path, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    print("Num pages:", len(reader.pages))
    with open(out_path, 'w', encoding='utf-8') as out:
        for i in range(len(reader.pages)):
            out.write(f"\n--- PAGE {i+1} ---\n")
            text = reader.pages[i].extract_text()
            if text:
                out.write(text)
            out.write("\n")
print("Saved to:", out_path)
