# 🗄️ Arquitectura de Base de Datos - ERP FINAL (Modular DDD) 🏗️🧱🧠

Este documento detalla la estructura lógica de `erp_nicoletti.db`. Siguiendo los principios de **Domain-Driven Design (DDD)** y **Vertical Slicing**, la base de datos está dividida en dominios autónomos.

---

## 🏛️ Propiedad de los Datos (Data Ownership)

La regla de oro es: **Ningún módulo puede consultar o modificar tablas que no le pertenecen.** Si un módulo necesita datos de otro, debe hacerlo a través de una función de servicio del módulo dueño.

### 💳 1. Dominio Tarjetas (`modulo_tarjetas`)
*Dueño absoluto de la recaudación por POS y tarjetas.*
-   **`payway_records`**: Cupones individuales (Ventas brutas).
-   **`liquidaciones_tarjetas`**: Cabecera de lo depositado por el banco.
-   **`liquidaciones_detalles`**: Desglose bit-a-bit de cada liquidación.

### 🧾 2. Dominio Compras (`modulo_compras`)
*Dueño de la facturación fiscal y conciliación contable.*
-   **`facturas`**: Tabla maestra de comprobantes (ARCA/AFIP).
-   **`facturas_calim`**: Datos importados del estudio contable.
-   **`libroiva`**: Declaraciones juradas mensuales.

### 🏦 3. Dominio Bancos (`modulo_bancos`)
*Dueño de la tesorería y el flujo de caja real.*
-   **`bancos_movimientos`**: Extractos bancarios unificados.

### 🧠 4. Dominio Core (`core_sistema`)
*Orquestador de infraestructura y búsqueda global.*
-   **`search_index`**: Tabla virtual **FTS5** (Full-Text Search). Unifica la visibilidad de todos los módulos.

---

## 🛠️ El Ciclo de Vida del Dato (Ingesta Híbrida)

El sistema utiliza un **Diseño Híbrido (Relacional + Documental)** para garantizar que no se pierda ni un bit de información durante el parseo.

1.  **Columnas Duras (Normalizadas)**:
    -   Solo lo esencial para cálculos: `id`, `fecha`, `monto_total`, `tipo_comprobante`, `hash_archivo`.
2.  **Columna Blanda (JSON `metadata_cruda`)**:
    -   Un volcado total de la información cruda del archivo en formato JSON. Si un dato no tiene columna propia, **debe** ir aquí.

### 🛡️ Protocolo de Idempotencia (Anti-Duplicados)
- Todo registro debe incluir un `hash_archivo` (SHA-256) generado por `checksum_service.py`.
- Las tablas deben definir este hash como `UNIQUE`.
- Al insertar, se debe usar `INSERT OR IGNORE` para evitar colisiones sin romper el flujo catastróficamente.

### 🔍 Visibilidad 360 (Buscador Global)
- Tras cada ingesta, el módulo **está obligado** a notificar al Core.
- El Core actualiza la tabla virtual `search_index` (FTS5).
- El buscador indexa tanto las columnas duras como el texto dentro del JSON de `metadata_cruda`.

---

## 🚫 Restricciones de Integridad
-   **Aislamiento**: Prohibido hacer `SELECT * FROM facturas` desde el `modulo_bancos`. Usar servicios de `modulo_compras`.
-   **Unicidad**: Uso obligatorio de `hash_archivo` Único para garantizar que un PDF/Excel no se "chupe" dos veces.
-   **Trazabilidad**: Todo registro debe tener un `path_archivo` o `hash_archivo` para rastrear el origen físico.
-   **Tipado**: Todos los montos monetarios deben ser `REAL` y las fechas en formato ISO `YYYY-MM-DD`.
