import PyPDF2
import pdfplumber
import sys

pdf_path = r"c:\Users\essao\Desktop\ERP FINAL\modulo_bancos\inbox_bancos\Resumen P365 Mayo 2026.pdf"

print("--- PyPDF2 ---")
try:
    with open(pdf_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        print("Num pages:", len(reader.pages))
        text = ""
        for i, page in enumerate(reader.pages):
            t = page.extract_text()
            print(f"Page {i+1} length: {len(t) if t else 0}")
            if t:
                text += t + "\n"
        with open(r"c:\Users\essao\Desktop\ERP FINAL\scratch\p365_text_pypdf.txt", "w", encoding="utf-8") as out:
            out.write(text)
        print("Saved PyPDF2 text")
except Exception as e:
    print("PyPDF2 Error:", e)

print("\n--- pdfplumber ---")
try:
    with pdfplumber.open(pdf_path) as pdf:
        print("Num pages:", len(pdf.pages))
        text = ""
        for i, page in enumerate(pdf.pages):
            t = page.extract_text()
            print(f"Page {i+1} length: {len(t) if t else 0}")
            if t:
                text += t + "\n"
        with open(r"c:\Users\essao\Desktop\ERP FINAL\scratch\p365_text_plumber.txt", "w", encoding="utf-8") as out:
            out.write(text)
        print("Saved pdfplumber text")
except Exception as e:
    print("pdfplumber Error:", e)
