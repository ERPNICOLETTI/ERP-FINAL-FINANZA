# 🧬 NEURONA: MÓDULO TARJETAS (Recaudación) 💳🧠

Esta neurona es responsable de toda la lógica de **ingesta, normalización y auditoría** de transacciones con tarjeta de crédito y débito.

## 🛰️ Flujo de Datos al Milímetro

1.  **Ingesta Física**: Los archivos (PDF de Payway, Excel de Patagonia, XLSX de Naranja) se reciben vía API o CLI.
2.  **Parsing Dinámico**: Cada fuente tiene su propio parser (`parser_payway_liq.py`, `parser_naranja_xlsx.py`, etc.) que extrae montos brutos, netos, aranceles e impuestos.
3.  **Unificación en DB**: Todos los datos convergen en la tabla `liquidaciones_tarjetas`.
4.  **Auditoría 360**: Se cruzan las ventas diarias de los POS (`payway_records`) contra las liquidaciones reales del banco para detectar falta de depósitos.

## 🧱 Tablas Clave
- `payway_records`: Registro individual de cada cupón/ticket pasado por el posnet.
- `liquidaciones_tarjetas`: Resumen consolidado de lo que el banco depositó efectivamente.

## ⚠️ Reglas de Oro (No romper)
- **Normalización de Importes**: Los importes siempre deben ser `float`. Ojo con las comas y puntos en los Excels argentinos.
- **Tipos de Liquidación**: Se debe diferenciar entre `DIARIA` (Payway) y `MENSUAL/OTRO` (Naranja/Patagonia) para que la auditoría no dé falsos positivos.
- **Base Ingesta**: Siempre usar `core_sistema.db_ingesta` para asegurar integridad referencial.

## 🛠️ Comandos de Neurona
- `resumen [anio]`: Visión gerencial de ingresos por marca.
- `audit`: El "detective" que busca dinero perdido en el aire.
- `importar <fuente> <path>`: La puerta de entrada de nuevos datos.
