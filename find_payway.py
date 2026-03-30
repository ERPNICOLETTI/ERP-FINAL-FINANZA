import pandas as pd
df = pd.read_csv('C:/Users/essao/Downloads/Liquidaciones diarias en pesos delimitadas por comas.csv', sep=',', encoding='latin1', skiprows=1)
for col in df.columns:
    if 'Neto' in col:
        print(f"Col: '{col}'")
for _, row in df.iterrows():
    if '135.884' in str(row.to_dict()):
        for k, v in row.items():
            print(f"{k}: {v}")
        break
