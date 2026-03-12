import pandas as pd
import os

file_path = r"C:\Users\Usuario\Downloads\MovimientosHistoricos (2).xlsx"

def inspect_chubut(file):
    print(f"\n--- Investigando Chubut: {file} ---")
    try:
        df = pd.read_excel(file, header=None)
        # Mostrar filas clave para detectar encabezado y tipos
        for r in range(min(20, len(df))):
            row_vals = [str(df.iloc[r, c]) for c in range(min(10, len(df.columns)))]
            print(f"Row {r:02}: {' | '.join(row_vals)}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_chubut(file_path)
