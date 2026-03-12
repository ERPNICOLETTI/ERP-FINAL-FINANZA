import pandas as pd
import os

def check(file):
    try:
        df = pd.read_excel(file, header=None)
        text = " ".join(df.iloc[0:20].astype(str).values.flatten().tolist()).upper()
        if 'CAJA DE AHORRO' in text or 'CAJA DE AHORROS' in text:
            return "CAJA DE AHORRO"
        if 'CUENTA CORRIENTE' in text:
            return "CUENTA CORRIENTE"
        # Return a snippet if not found
        return f"NOT FOUND (Snippet: {text[:300]})"
    except Exception as e:
        return f"Error: {e}"

print("File 5 (CA?):", check(r"C:\Users\Usuario\Downloads\Extracto_00032954997 (5).xlsx"))
print("File 6 (CC?):", check(r"C:\Users\Usuario\Downloads\Extracto_00032954997 (6).xlsx"))
