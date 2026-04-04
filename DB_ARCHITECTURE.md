# 🗄️ Arquitectura de Base de Datos - ERP FINAL (Modular DDD) 🏗️🧱🧠
# Versión 4.0 - Diseño Híbrido y Persistencia Blindada

Este documento detalla la estructura lógica de `erp_nicoletti.db`. Siguiendo los principios de **Domain-Driven Design (DDD)** y **Vertical Slicing**, la base de datos está dividida en dominios autónomos que no comparten estado directo.

---

## 🏛️ Propiedad de los Datos (Data Ownership) - Patrón Repositorio

La regla de oro inquebrantable es: **Ningún módulo puede importar `sqlite3` ni ejecutar SQL directo sobre tablas ajenas.** 

-   La persistencia se delega exclusivamente a los archivos `storage_*.py` de cada módulo.
-   La comunicación cross-module se realiza mediante funciones de servicio (Ej: `modulo_compras.storage_compras.save_factura()`).

### 💳 1. Dominio Tarjetas (`modulo_tarjetas`)
*Dueño absoluto de la recaudación por POS y tarjetas.*
-   **`payway_records`**: Cupones individuales.
-   **`liquidaciones_tarjetas`**: Cabeceras disciplinadas de depósitos bancarios.

### 🧾 2. Dominio Compras (`modulo_compras`)
*Dueño de la facturación fiscal y conciliación contable.*
-   **`facturas`**: Tabla maestra de comprobantes (AFIP/CALIM). Incluye `row_dump` en JSON.

### 🏦 3. Dominio Bancos (`modulo_bancos`)
*Dueño de la tesorería y el flujo de caja real.*
-   **`bancos_movimientos`**: Extractos bancarios unificados de Chubut, Credicoop e Hipotecario.

---

## 🛠️ Diseño Híbrido (Relacional + Documental)

Para garantizar la integridad total y no perder datos en el proceso de normalización, implementamos el **Diseño Híbrido**:

1.  **Columnas Duras (Tipadas)**: Campos esenciales para cálculos y cruces (id, fecha, monto, cuit, hash_archivo).
2.  **Columna Blanda (`metadata_cruda`)**: Columna de tipo `TEXT` que almacena un objeto JSON con el volcado absoluto de la fuente (OCR completo en PDFs o diccionario de la fila en Excels).

### 🔍 Buscador 360 (Indexación FTS5)
La tabla virtual `search_index` (FTS5) en el Core indexa automáticamente el contenido de la columna `metadata_cruda`. Esto permite buscar facturas por cualquier palabra clave que aparezca en el PDF original, incluso si no tiene una columna propia en la DB.

---

## 🛡️ Protocolo de Idempotencia y Id (Anti-Duplicados)

El sistema utiliza una **Estrategia de Doble Capa** para evitar la duplicación de datos sin bloquear la ingesta legítima.

### 1. Nivel Archivo (Preventivo)
La tabla `core_registro_ingestas` almacena el `hash_sha256` (HEX UNIQUE) de cada archivo procesado. 
-   **Acción**: Si el hash ya existe, el Orquestador rechaza el archivo de entrada inmediatamente.

### 2. Nivel Fila (Row-Level Dedup)
En las tablas transaccionales (`facturas`, `payway_records`), el `hash_archivo` **NO es UNIQUE**, ya que múltiples filas pertenecen al mismo archivo.
-   **Regla**: Se utilizan restricciones `UNIQUE` multi-columna (Ej: `UNIQUE(fecha, cupon, lote, monto)`) junto con `INSERT OR IGNORE`.
-   **Efecto**: Si se suben dos archivos con solapamiento de fechas, el sistema solo descarta las filas individuales repetidas, preservando la continuidad del archivo.

---

## 🏛️ Trazabilidad Física y Archivamiento
Todo registro debe mantener un puntero a su origen físico:
-   `path_archivo`: Ruta absoluta final en el servidor (ubicación en `static/archivadas/`).
-   `hash_archivo`: Vínculo lógico con la ingesta original.

> [!TIP]
> **Snippet de Actualización de Ruta**: Tras el archivado legal, es obligatorio llamar a `update_record_path(id, new_path)` para que la DB no pierda el rastro del archivo PDF/Excel.
