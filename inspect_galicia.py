import pandas as pd
import sys
import json

def inspect_excel(filepath):
    try:
        # Intentamos leer el archivo. 
        # Si es un extracto viejo de Galicia a veces es un HTML con extension XLS, 
        # o un CSV con extension XLS. Pero pandas suele resolverlo.
        df = pd.read_excel(filepath, header=None)
        
        # Mostramos las primeras 15 filas para entender la estructura
        print(f"--- PRIMERAS 15 FILAS DE {filepath} ---")
        print(df.head(15).to_string())
        print("\n--- INFO DE COLUMNAS ---")
        print(df.dtypes)
        
    except Exception as e:
        print(f"Error leyendo el archivo: {e}")

if __name__ == "__main__":
    path = r"C:\Users\Usuario\Downloads\Extracto_00032954997 (5).xlsx"
    inspect_excel(path)
