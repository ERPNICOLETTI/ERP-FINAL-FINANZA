# 🗄️ Arquitectura de Base de Datos - ERP FINAL (Modular DDD) 🏗️🧱🧠
# Versión 4.5 - MANDAMIENTOS UNIVERSALES ⚖️💎

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
| **Identificadores** | `cuit`, `numero_comprobante` | `cuit` es universal para clientes/proveedores. |
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

## 🏛️ Trazabilidad Física
- `path_archivo`: Ubicación final en `static/archivadas/`.
- `hash_archivo`: Vínculo lógico con la ingesta.
- `tiene_foto`: Booleano para vincular evidencias físicas.
