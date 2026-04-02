import pandas as pd
import os

def check(file):
    print(f"\n--- Checking {file} ---")
    try:
        df = pd.read_excel(file, header=None)
        # Check first 20 rows and 5 columns
        for r in range(min(20, len(df))):
            row_str = " | ".join([str(df.iloc[r, c]) for c in range(min(5, len(df.columns)))])
            print(f"Row {r}: {row_str}")
    except Exception as e:
        print(f"Error: {e}")

check(r"C:\Users\Usuario\Downloads\Extracto_00032954997 (5).xlsx")
check(r"C:\Users\Usuario\Downloads\Extracto_00032954997 (6).xlsx")
