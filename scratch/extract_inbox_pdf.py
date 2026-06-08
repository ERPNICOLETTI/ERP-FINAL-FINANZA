import PyPDF2
import sys
import os

# Ensure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r"c:\Users\essao\Desktop\ERP FINAL\modulo_bancos\inbox_bancos\50d6c0d8-22a7-44e9-90ba-2c62c95abcad.pdf"

if not os.path.exists(pdf_path):
    print("PDF not found at:", pdf_path)
    sys.exit(1)

print(f"Reading: {pdf_path}")
with open(pdf_path, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    print(f"Total pages: {len(reader.pages)}")
    
    # Extract first 3 pages
    for i in range(min(5, len(reader.pages))):
        print(f"\n--- PAGE {i+1} ---")
        text = reader.pages[i].extract_text()
        print(text)
