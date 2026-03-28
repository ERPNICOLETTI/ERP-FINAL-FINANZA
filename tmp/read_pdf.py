import pdfplumber
import sys

with pdfplumber.open('C:/Users/essao/Downloads/F.2051 - DJ IVA - SIMPLE.pdf') as pdf:
    text = '\n'.join([page.extract_text() for page in pdf.pages if page.extract_text()])
    # Extraer las partes importantes
    for line in text.split('\n'):
        if 'Débito' in line or 'Crédito' in line or '$' in line or 'Saldo' in line or 'Total' in line:
            print(line)
