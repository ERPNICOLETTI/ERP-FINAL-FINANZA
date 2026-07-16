# 🧬 NEURONA: MÓDULO TARJETAS (Recaudación) 💳🧠
**Versión 6.0.0 — Optimizado y Consolidado**

Este módulo controla las ventas cobradas a través de terminales de pago, procesando liquidaciones y cupones individuales para cruzar contra los depósitos bancarios.

---

## 📂 Componentes del Módulo
1.  **[storage_tarjetas.py](storage_tarjetas.py)**: Capa de persistencia. Procesa y almacena las liquidaciones y cupones individuales.
2.  **[logica_tarjetas.py](logica_tarjetas.py)**: Motor de analíticas. Realiza cálculos de aranceles y reconciliaciones.
3.  **Parsers de Liquidación**:
    -   `parser_payway_liq.py`: Ingesta cupones y resúmenes de Payway.
    -   `parser_naranja_xlsx.py`: Ingesta liquidaciones de Tarjeta Naranja.
    -   `parser_patagonia.py`: Ingesta liquidaciones de Patagonia 365.
4.  **[neuron_tarjetas.py](neuron_tarjetas.py)**: Router CLI para disparar comandos y reportes manuales.

---

## 🗄️ Estructura de Datos

### Tabla `payway_records` (Cupones individuales)
-   Guarda el detalle de cada ticket o cobro individual en los POS de la tienda.
-   **Idempotencia:** Restricción `UNIQUE(fecha_compra, cupon, lote, marca, monto_bruto)`.

### Tabla `liquidaciones_tarjetas` (Resúmenes consolidados)
-   Registra las liquidaciones bancarias periódicas de las tarjetas de crédito y débito.
-   **Diseño Híbrido:** Las columnas core guardan totales brutos/netos y fechas, mientras que el resto de las variables se inyecta en `meta_json` (indexado por FTS5).

---

## 📥 Ingesta
-   **Flujo de 3 Capas:** Los resúmenes originales se colocan en `inbox_tarjetas/`. Al procesarse correctamente, se verifica su hash SHA-256 para evitar duplicaciones, se eliminan del inbox y se guardan de forma permanente en `modulo_tarjetas/archivos_tarjetas/[Marca]/[Año]/[Mes]/`.
