import PyPDF2
import sys
import os

pdf_path = r"c:\Users\essao\Desktop\ERP FINAL\modulo_bancos\inbox_bancos\50d6c0d8-22a7-44e9-90ba-2c62c95abcad.pdf"
out_path = r"C:\Users\essao\Desktop\ERP FINAL\scratch\mastercard_text.txt"

with open(pdf_path, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    with open(out_path, 'w', encoding='utf-8') as out:
        for i in range(len(reader.pages)):
            out.write(f"\n--- PAGE {i+1} ---\n")
            text = reader.pages[i].extract_text()
            if text:
                out.write(text)
            out.write("\n")
print("Saved to:", out_path)
