# 🧬 NEURONA: MÓDULO PAGOS (Vencimientos & Impuestos) 💳🧠
**Versión 6.0.0 — Consolidado con pagos_recurrentes.md**

Este módulo gestiona la digitalización de boletas de servicios, sindicatos e impuestos, y la vinculación de sus correspondientes comprobantes de pago, manteniendo la trazabilidad financiera de vencimientos duales.

---

## 📂 Componentes del Módulo y Lectura de Código
1.  **[storage_pagos.py](storage_pagos.py)**: Capa repositorio. Único archivo que realiza consultas SQL directas sobre la tabla `pagos`. Prohíbe el uso de `sqlite3` externo.
2.  **[parser_pagos.py](parser_pagos.py)**: Motor de extracción de textos y patrones en PDFs. Identifica conceptos, periodos, montos y fechas de vencimiento.
3.  **[logic_pagos.py](logic_pagos.py)**: Orquestador de flujo de entrada. Ingesta las boletas desde el `inbox_pagos`, las procesa y las archiva.
4.  **Vistas Web**:
    -   `pagos.html`: Panel principal con la tabla general y terminal de arrastre (Dropzone).
    -   `tabla_pagos.html`: Renderiza dinámicamente las filas de la tabla de vencimientos con un semáforo de prioridades (Rojo/Amarillo/Naranja/Verde).

---

## 🏛️ Estructura de Datos (Tabla `pagos`)

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Auto-incremental |
| `categoria` | TEXT | `SERVICIOS` | `IMPUESTOS` | `SINDICALES` |
| `concepto` | TEXT | Identificador único del servicio/sindicato (ej: SEC, FAECYS, SERVICOOP) |
| `periodo_mes` | TEXT | Mes de la obligación (MM, ej: "01") |
| `periodo_anio` | TEXT | Año de la obligación (YYYY, ej: "2026") |
| `monto` | REAL | Importe primer vencimiento |
| `fecha_vencimiento` | TEXT | Vencimiento 1 (ISO YYYY-MM-DD) |
| `monto_2` | REAL | Importe segundo vencimiento (0.0 si no aplica) |
| `fecha_vencimiento_2` | TEXT | Vencimiento 2 (ISO YYYY-MM-DD, NULL si no aplica) |
| `estado` | TEXT | `PENDIENTE` (al ingestar boleta) | `PAGADO` (al vincular comprobante) |
| `path_boleta` | TEXT | Ruta del PDF de la boleta (relativa, SASH-SAFE con `/`) |
| `path_comprobante` | TEXT | Ruta del PDF de pago (relativa, SASH-SAFE con `/`, NULL si pendiente) |
| `hash_boleta` | TEXT | Hash SHA-256 para evitar duplicaciones |
| `meta_json` | TEXT | JSON con textos planos y campos intermedios |

---

## ⚡ Taxonomía de Conceptos

-   **SERVICIOS**:
    -   `Servicoop` (Cooperativa de servicios públicos).
    -   `Reduno` (Internet).
    -   `Alquiler` (Locación de inmuebles).
    -   `Tiendanube` (Pasarela/tienda web).
    -   `Contador` (Honorarios contables).
-   **IMPUESTOS**:
    -   `931` (Cargas sociales AFIP).
    -   `Autonomo` (Aportes jubilatorios).
    -   `IVA` (F.2002).
    -   `IIBB` (Ingresos Brutos).
-   **SINDICALES** (Crítico: SEC y FAECYS admiten doble vencimiento/monto):
    -   `SEC` (Sindicato Empleados de Comercio Trelew).
    -   `FAECYS` (Federación de Comercio).
    -   `POLICIA` (Tasas Secretaría de Trabajo Trelew, vencimiento único).
    -   `INACAP` (Capacitación de Comercio, vencimiento único).

---

## 📋 Reglas de Extracción del Parser (PDF)

El parser `parser_pagos.py` resuelve en cascada:
1.  **Concepto**: Identificado por cadenas duras (ej. "FAECYS", "INACAP", "POLICÍA DEL TRABAJO").
2.  **Periodo**: Extraído estrictamente del PDF (representa la obligación, no la fecha de cobro):
    -   *FAECYS / INACAP*: `PERIODO: MM/YYYY`
    -   *POLICIA*: `PERIODO: YYYYMM`
    -   *SEC*: `YYYY-MM` en líneas de la tabla del documento.
    -   *Fallback*: Si no hay coincidencia, lee patrones `_MM-YYYY_` en el nombre de archivo.
3.  **Montos y Vencimientos**:
    -   *SEC y FAECYS*: Doble vencimiento. Se parsean `Fecha 1er Vto` y `Fecha 2do Vto` con sus importes respectivos.
    -   *INACAP y POLICIA*: Un solo vencimiento. Se busca `Monto Total` o `TOTAL A PAGAR` y su fecha única.

---

## 📥 Ingesta y Archivado Legal (Bóveda)
-   **Detalle vs. Comprobante**: La boleta contiene palabras como "PAGO" (ej: "VOLANTE DE PAGO"). Por tanto, las boletas se detectan al caer en `inbox_pagos/`. Los comprobantes de pago correspondientes se detectan **exclusivamente por nombre de archivo** que contenga `comprobante` o similar.
-   **Ruta de Archivación (Bóveda Relativa)**:
    `/modulo_pagos/archivos_pagos/[CATEGORIA]/[CONCEPTO]/[YYYY]/[MM]/`
    -   Nombre Boleta: `Boleta_[CONCEPTO]_[MM]_[YYYY].pdf`
    -   Nombre Comprobante: `Comprobante_[CONCEPTO]_[MM]_[YYYY].pdf`
