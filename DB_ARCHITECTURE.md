# 🗄️ Arquitectura de Base de Datos - ERP FINAL (Modular DDD) 🏗️🧱🧠
# Versión 5.0.0 - Ecosistema Estable con Rutas Blindadas (/) ⚖️💎🛡️

Este documento es la autoridad central para todas las bases de datos del ERP. Todo módulo presente y futuro **DEBE** obedecer estas reglas innegociables.

---

## 🏛️ Propiedad de los Datos (Data Ownership) - Patrón Repositorio

Ningún módulo puede importar `sqlite3` ni ejecutar SQL directo sobre tablas ajenas. La persistencia se delega exclusivamente a los archivos `storage_*.py`.

---

## 🛑 MANDAMIENTOS INNEGOCIABLES 🛑

### 📏 REGLA 1: Nomenclatura Universal (El mismo dato, el mismo nombre)
Si un campo representa el mismo concepto financiero o temporal, debe llamarse **exactamente igual** en todas las tablas del sistema.

| Concepto | Nombre de Columna Único | Notas |
| :--- | :--- | :--- |
| **Fechas** | `fecha`, `fecha_emision`, `fecha_vencimiento` | No usar prefijos por tabla. |
| **Pto. Venta** | `punto_venta` | TEXT de 5 ceros (zfill 5). En UI se muestra sin ceros. |
| **Num. Comprobante** | `numero_comprobante` | TEXT de 8 ceros (zfill 8). En UI se muestra sin ceros. |
| **Dinero (Neto)** | `neto` | El monto imponible base. |
| **IVA 21%** | `iva21` | Sin puntos ni prefijos tipo '21iva'. |
| **IVA 10.5%** | `iva105` | Estandarizado. |
| **IVA 27%** | `iva27` | Estandarizado. |
| **Exento** | `exento` | Montos no gravados. |
| **Percepciones** | `percepcion_iva` | Percepciones de IVA específicas. |
| **Totales** | `total` | Monto final del comprobante. |
| **Balance** | `saldo` | El remanente financiero. |

---

### 🧠 REGLA 2: Metodología 'Core vs. meta_json'
Todo Parser nuevo debe seguir esta división estricta de responsabilidades:

1.  **Columnas Core (Duras)**: Solo se crean columnas tipadas (REAL, TEXT, ISO-DATE) para datos que requieran:
    *   **Calcular**: Sumar, restar o promediar en SQL.
    *   **Filtrar**: Cláusulas `WHERE` frecuentes.
    *   **Cruzar**: `JOIN` entre tablas o módulos.
2.  **Bolsa de Metadatos (`meta_json`)**: Toda la información adicional (CAE, leyendas, IDs internos de origen) se encapsula obligatoriamente en este campo JSON.
3.  **Extracción Limpia**: Los Parsers deben asegurar que los datos Core lleguen limpios y con el formato correcto (ej: decimales con punto `.`). Nada de valor calculable debe quedar atrapado en el JSON.

---

## 🔍 Buscador 360 (Indexación FTS5)
La tabla virtual `search_index` (FTS5) indexa automáticamente el contenido del campo `meta_json`.

---

## 🛡️ Idempotencia de Doble Capa
1.  **Capa Archivo**: `core_registro_ingestas` rechaza archivos duplicados por hash SHA256.
2.  **Capa Fila**: Restricciones `UNIQUE` multi-columna + `INSERT OR IGNORE`.

---

## 🏛️ Trazabilidad Física y Archivado Anti-Corrupción (v5.0.0)
- `path_archivo`: Ubicación física inmutable en `archivos_[modulo]/`. 
  - **SASH-SAFE**: Todas las rutas deben guardarse con `/` (forward slash) para evitar errores de escape en Windows.
  - **Formato**: `[CUIT - Entidad]/[Año]/[Mes]/[Fecha]_[Nombre]_Factura_[PV-NUM].ext`.
- `status`: Campo vital para el ciclo de vida del dato (`NORMAL` | `SALA_ESPERA`).
- `tiene_foto`: Booleano vital para el semáforo (Rojo/Verde) de vinculación de evidencias físicas.

---

## 🏦 Tabla: `pagos` — Schema v5.4.1 (Módulo Pagos)

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Auto-incremental |
| `categoria` | TEXT | SINDICALES / SERVICIOS / IMPUESTOS |
| `concepto` | TEXT | SEC / FAECYS / INACAP / POLICIA / SERVICOOP / ... |
| `periodo_mes` | TEXT | MM (ej: `"01"`) |
| `periodo_anio` | TEXT | YYYY (ej: `"2026"`) |
| `monto` | REAL | Monto del 1er vencimiento (exacto del PDF) |
| `fecha_vencimiento` | TEXT | ISO `YYYY-MM-DD` — 1er vencimiento |
| `monto_2` | REAL | Monto del 2do vencimiento (0 si no aplica) |
| `fecha_vencimiento_2` | TEXT | ISO `YYYY-MM-DD` — 2do vencimiento (NULL si no aplica) |
| `estado` | TEXT | `PENDIENTE` al ingestar boleta / `PAGADO` al vincular comprobante |
| `path_boleta` | TEXT | Ruta **relativa** con `/` — se llena al procesar la boleta |
| `path_comprobante` | TEXT | Ruta **relativa** con `/` — se llena al vincular el comprobante |
| `hash_boleta` | TEXT | SHA256 para idempotencia |
| `meta_json` | TEXT | JSON con `full_text` del PDF y montos auxiliares |

> [!IMPORTANT]
> `monto_2` y `fecha_vencimiento_2` se usan cuando el sindicato ofrece 2 opciones de pago (con/sin recargo). SEC y FAECYS siempre tienen doble vencimiento. INACAP y POLICIA tienen vencimiento único.
