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

## 🛠️ El Ciclo de Vida del Dato

1.  **Inicialización**: Cada módulo tiene una función `init_db_*()` dentro de su propio `storage_*.py`.
2.  **Reset Total**: El script central `reset_database.py` elimina el archivo `.db` y llama a la orquestación del **Core** para reconstruir el esquema modular.
3.  **Ingesta Aislada**: Los parsers guardan datos usando su **Storage Local** (ej. `storage_tarjetas.save_liquidacion()`).
4.  **Sincronización Search**: Al finalizar una ingesta, el módulo notifica al Core mediante `db_ingesta.update_search_index()` para que el buscador global refleje los nuevos datos.

---

## 🚫 Restricciones de Integridad
-   **Aislamiento**: Prohibido hacer `SELECT * FROM facturas` desde el `modulo_bancos`. Usar servicios de `modulo_compras`.
-   **Unicidad**: Cada dominio define sus propias claves `UNIQUE` para evitar duplicados en ingestas repetidas.
-   **Tipado**: Todos los montos monetarios deben ser `REAL` (Float) y las fechas en formato ISO `YYYY-MM-DD`.
