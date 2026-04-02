# 🧬 NEURONA: MÓDULO BANCOS (Tesorería) 🏦🧠

Esta neurona es la **"Cámara Acorazada"** del sistema. Registra cada peso que entra o sale de las cuentas bancarias de la empresa.

## 🛰️ Flujo de Datos al Milímetro

1.  **Extracción de Homebanking**: Se descargan los Excel/CSV (Chubut, Hipotecario, Credicoop).
2.  **Modularidad de Banco**: Cada banco tiene su propio parser especializado:
    -   `parser_chubut.py`: Para Excel de movimientos históricos.
    -   `parser_hipotecario.py`: Para archivos `.xls` de Home Banking.
    -   `parser_credicoop_joaquin.py`: Especializado para la cuenta de Joaquín (CA 9087).
3.  **Unificación Bancaria**: Todos los registros terminan en la tabla `bancos_movimientos`.

## 🧱 Tablas Clave
- `bancos_movimientos`: Tabla única para todos los bancos.
  - Campos Críticos: `banco` (CHUBUT|HIPOTECARIO|CREDICOOP), `fecha`, `descripcion`, `importe`.

## ⚠️ Reglas de Oro (No romper)
- **Evitar Duplicados**: El `INSERT OR IGNORE` en la DB es vital. No quitarlo; de lo contrario, importar dos veces el mismo extracto duplicará los montos de caja.
- **Códigos de Movimiento**: Cada banco llama a las operaciones de forma distinta. No intentar unificar descripciones; guardar el string original para búsquedas futuras.
- **Conciliación**: El módulo debe permitir cruzar estos movimientos con las liquidaciones de tarjetas (`modulo_tarjetas`) para cerrar el círculo del dinero.

## 🛠️ Comandos de Neurona
- `importar <banco> <path>`: Procesa el extracto y lo mete en la tabla unificada.
- `audit`: (En desarrollo) Cruce de extracto vs liquidaciones de tarjetas.
