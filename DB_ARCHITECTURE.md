# 🗄️ Arquitectura de Base de Datos - ERP FINAL (Modular DDD) 🏗️🧱🧠
# Versión 4.0 - GOLDEN MASTER 💎

Este documento detalla la estructura lógica de `erp_nicoletti.db`. Siguiendo los principios de **Domain-Driven Design (DDD)** y **Vertical Slicing**, la base de datos está dividida en dominios autónomos que no comparten estado directo.

---

## 🏛️ Propiedad de los Datos (Data Ownership) - Patrón Repositorio

La regla de oro inquebrantable de la v4.0 es: **Ningún módulo puede importar `sqlite3` ni ejecutar SQL directo sobre tablas ajenas.** 

-   La persistencia se delega exclusivamente a los archivos `storage_*.py` de cada módulo (Capa de Infraestructura).
-   La comunicación cross-module se realiza mediante funciones de servicio (Ej: `modulo_compras.storage_compras.save_factura()`).

### 💳 1. Dominio Tarjetas (`modulo_tarjetas`)
*Dueño absoluto de la recaudación por POS y tarjetas.*
-   **`payway_records`**: Registros individuales de ventas. Clave Única: `(fecha_compra, cupon, lote, marca, monto_bruto)`.
-   **`liquidaciones_tarjetas`**: Cabeceras de depósitos bancarios.

### 🧾 2. Dominio Compras (`modulo_compras`)
*Dueño de la facturación fiscal y conciliación contable.*
-   **`facturas`**: Tabla maestra de comprobantes (AFIP/CALIM). Clave Única: `(cuit_proveedor, punto_venta, numero_completo, tipo_comprobante)`.
-   **`libroiva`**: Declaraciones Juradas consolidadas (F.2051).

### 🏦 3. Dominio Bancos (`modulo_bancos`)
*Dueño de la tesorería y el flujo de caja real.*
-   **`bancos_movimientos`**: Extractos bancarios unificados. Clave Única: `(banco, cuenta, fecha, descripcion, tipo_movimiento, importe)`.

---

## 🛠️ Diseño Híbrido (Relacional + Documental)

Para garantizar la integridad total y no perder datos en el proceso de normalización, implementamos el **Diseño Híbrido**:

1.  **Columnas Duras (Tipadas)**: Campos esenciales para cálculos (id, fecha, monto, cuit).
2.  **Columna Blanda (`metadata_cruda`)**: Objeto JSON con el volcado absoluto de la fuente.

### 🖼️ Ejemplo de `metadata_cruda` (JSON):
```json
{
  "texto_ocr_completo": "RESUMEN DE PAGO... PRISMA MEDIOS... ESTABLECIMIENTO: 1234567... TOTAL: $1500.50",
  "datos_adicionales": {
    "terminal_id": "POS-001",
    "autorizacion": "987654",
    "nombre_comercio": "NICOLETTI SA"
  }
}
```

### 🔍 Buscador 360 (Indexación FTS5)
La tabla virtual `search_index` (FTS5) indexa automáticamente el contenido de la columna `metadata_cruda`.
```sql
-- Ejemplo de búsqueda global por cualquier término en el JSON
SELECT * FROM search_index WHERE content MATCH 'terminal_id:POS-001';
```

---

## 🛡️ Idempotencia de Doble Capa

1.  **Capa Archivo**: `core_registro_ingestas` rechaza archivos duplicados mediante el hash SHA256 del binario.
2.  **Capa Fila**: Las tablas transaccionales usan `INSERT OR IGNORE` sobre restricciones `UNIQUE` multi-columna. Esto permite subir archivos solapados sin duplicar transacciones individuales.

---

## 🏛️ Trazabilidad Física y Archivamiento
Todo registro mantiene un puntero a su origen:
-   `path_archivo`: Ubicación final en `static/archivadas/` (gestionado por `archiver_service.py`).
-   `hash_archivo`: Vínculo lógico con la ingesta original.

---

## 🔩 Mantenimiento: Reconstrucción FTS5
Si agregas nuevas tablas o experimentas inconsistencias en el buscador, puedes reconstruir el índice global con esta consulta SQL:
```sql
-- Borrar y re-indexar todo
DELETE FROM search_index;
INSERT INTO search_index(source, record_id, content)
SELECT 'FACTURAS', id, metadata_cruda FROM facturas;
-- Repetir para cada tabla de interés...
```
