# 🧬 NEURONA: MÓDULO PAGOS (Vencimientos & Impuestos) 💳🧠
**Versión 6.0.0 — Consolidado con pagos_recurrentes.md**

Este módulo gestiona la digitalización de boletas de servicios, sindicatos e impuestos, y la vinculación de sus correspondientes comprobantes de pago, manteniendo la trazabilidad financiera de vencimientos duales.

---

## 📂 Componentes del Módulo y Lectura de Código
1.  **[storage_pagos.py](storage_pagos.py)**: Capa repositorio. Único archivo que realiza consultas SQL directas sobre la tabla `pagos_vencimientos`. Prohíbe el uso de `sqlite3` externo. Realiza conversiones transparentes de centavos enteros a flotantes en lectura.
2.  **[lectores/lector_pagos.py](lectores/lector_pagos.py)**: Orquestador y enrutador central de parseo. Identifica la firma del documento y deriva a los lectores específicos:
    *   `lector_sec.py`: Parser para boletas y tickets del Sindicato Empleados de Comercio.
    *   `lector_faecys.py`: Parser para la Federación Argentina de Empleados de Comercio.
    *   `lector_inacap.py`: Parser de aportes obligatorios INACAP.
    *   `lector_policia.py`: Parser de tasas de la Secretaría de Trabajo.
3.  **[logic_pagos.py](logic_pagos.py)**: Implementa el pipeline de datos ELT en dos fases (Fase 1: Ingesta Raw a Staging y Archivado en Bóveda; Fase 2: Transformación Atómica a tablas de Producción).
4.  **Vistas Web**:
    -   `pagos.html`: Panel principal con la tabla general y terminal de arrastre (Dropzone).
    -   `tabla_pagos.html`: Renderiza dinámicamente las filas de la tabla de vencimientos con un semáforo de prioridades (Rojo/Amarillo/Naranja/Verde).

---

## 🏛️ Estructura de Datos (Tabla `pagos_vencimientos`)

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Auto-incremental |
| `categoria` | TEXT | `SERVICIOS` | `IMPUESTOS` | `SINDICALES` |
| `concepto` | TEXT | Identificador único del servicio/sindicato (ej: SEC, FAECYS, SERVICOOP) |
| `periodo_mes` | TEXT | Mes de la obligación (MM, ej: "01") |
| `periodo_anio` | TEXT | Año de la obligación (YYYY, ej: "2026") |
| `monto` | INTEGER | Importe primer vencimiento (almacenado en **Centavos Enteros**) |
| `fecha_vencimiento` | TEXT | Vencimiento 1 (ISO YYYY-MM-DD) |
| `monto_2` | INTEGER | Importe segundo vencimiento (almacenado en **Centavos Enteros**, 0 si no aplica) |
| `fecha_vencimiento_2` | TEXT | Vencimiento 2 (ISO YYYY-MM-DD, NULL si no aplica) |
| `estado` | TEXT | `PENDIENTE` (al ingestar boleta) | `PAGADO` (al vincular comprobante) |
| `path_boleta` | TEXT | Ruta del PDF de la boleta (relativa, SASH-SAFE con `/`) |
| `path_comprobante` | TEXT | Ruta del PDF de pago (relativa, SASH-SAFE con `/`, NULL si pendiente) |
| `hash_boleta` | TEXT | Hash SHA-256 para evitar duplicaciones |
| `codigo_barras` | TEXT | Código de barras para conciliación por barras |
| `meta_json` | TEXT | JSON con textos planos y campos intermedios |
| `raw_ingesta_id` | INTEGER | Linaje: Referencia al ID original en `core_staging_raw` |
| `numero_linea` | INTEGER | Número de línea/transacción (1-indexed) dentro de la ingesta |

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
-   **Detalle vs. Comprobante**: La boleta se detecta al caer en `inbox_pagos/` por palabras clave. El comprobante de pago correspondiente se sube directamente a la fila desde el visor web y se valida de forma segura leyendo el texto interno del PDF (verificando el código de barras, CUIT y montos esperados en centavos), sin importar el nombre físico que tenga el archivo.
-   **Ruta de Archivación (Bóveda Relativa)**:
    `/modulo_pagos/archivos_pagos/[CATEGORIA]/[CONCEPTO]/[YYYY]/[MM]/`
    -   Nombre Boleta: `Boleta_[CONCEPTO]_[MM]_[YYYY].pdf`
    -   Nombre Comprobante: `Comprobante_[CONCEPTO]_[MM]_[YYYY].pdf`
