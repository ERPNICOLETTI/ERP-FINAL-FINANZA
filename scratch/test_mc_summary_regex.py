import re

def main():
    path = r"c:\Users\essao\Desktop\ERP FINAL\scratch\mastercard_text.txt"
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
        
    lines = text.split('\n')
    summary_re = re.compile(
        r'^(INTERESES DE FINANCIACION|IMPUESTO DE SELLOS|I\.V\.A\.\s+\d+,\d+%|PERCEPCION IVA DTO \d+/\d+|PERCEP\.AFIP RG \d+ \d*%|DEV PER RG \d+ \d*%)\s+(-?\d+(?:\.\d{3})*,?\d{2})(?:\s+(-?\d+(?:\.\d{3})*,?\d{2}))?\s*$'
    )
    
    print("Matched summary lines:")
    for line in lines:
        m = summary_re.match(line.strip())
        if m:
            print(f"Line: {repr(line.strip())}")
            print(f"  Name:  {repr(m.group(1))}")
            print(f"  Pesos: {repr(m.group(2))}")
            print(f"  USD:   {repr(m.group(3))}\n")

if __name__ == '__main__':
    main()
