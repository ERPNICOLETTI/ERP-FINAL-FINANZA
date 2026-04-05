# 🧬 NEURONA: MÓDULO COMPRAS (Facturación) 🧾🧠
# Versión 4.8.0 - Ecosistema Unificado y Match Atómico

Esta neurona gestiona el **Ecosistema de Compras**, unificado en una sola terminal de asalto visual y rápido, encargada de la conciliación fiscal y archivado permanente.

---

## 🏛️ Patrón Repositorio (Regla Inquebrantable)
> [!CAUTION]
> **Prohibición de SQL Directo**: Ningún archivo de este módulo (parsers o lógica) puede importar `sqlite3`.
> Toda la persistencia debe pasar por `storage_compras.py`.

### Ejemplo de Uso del Repositorio:
```python
from . import storage_compras as storage

# Guardar factura con volcado de fila completo (Diseño Híbrido)
storage.save_factura({
    "punto_venta": "00005",
    "numero_comprobante": "00007365",
    "proveedor": "TELECOM SA",
    "monto_total": 45000.00,
    "meta_json": row.to_dict()  # Metadata cruda JSON (Estándar v4.5)
})
```

---

## 🛰️ Ecosistema de Ingesta Unificado (v4.8.0)
El módulo ha evolucionado hacia un diseño de una sola pantalla potente y minimalista:

### 1. Match Atómico Inteligente 🔍
El formulario de la bóveda cuenta con un **único input** para el número de factura. 
La función `smart_search_invoice()` en `storage_compras.py` realiza búsquedas elásticas eliminando ceros y guiones en tiempo real. Cuando hay coincidencia, el sistema arroja metadatos completos y origen (AFIP/CALIM).

### 2. Flujo de Ingesta a Bóveda (3 Pasos)
1. **Drop & Zoom (UI)**: Se suelta el PDF/Imagen directamente en el panel. Se permite Zoom libre mediante scroll y paneo con drag en el área de visualización.
2. **Match (UI/DB)**: Se busca el comprobante y se relaciona automágicamente.
3. **Archivado Nominal y Limpieza de Origen**:
    Al confirmar, la API:
    - **Renombra** la evidencia siguiendo el estricto formato: `YYYY-MM-DD_NombreProveedor_Factura_PV-NUM.pdf` (Ej: `2026-04-05_FARMACITY_Factura_0001-00000123.pdf`).
    - **Archiva** en la bóveda sagrada `/modulo_compras/archivos_compras/[CUIT] - [Proveedor]/[Año]/[Mes]/`.
    - **Limpia** (elimina/mueve) el archivo original que estaba temporalmente en la carpeta `inbox_compras`. (Limpieza atómica sin registros huérfanos).

### 3. Filtros Cronológicos ML-Style
La bóveda listando las facturas ya procesadas filtra masivamente la base de datos usando `anio` y `mes`.

---

## 🧱 Tablas Clave
- `facturas`: Tabla maestra digitalizada. 
- **Idempotencia**: `UNIQUE(cuit_proveedor, punto_venta, numero_comprobante, tipo_comprobante)` + `INSERT OR IGNORE`.

---

## 🛠️ Comandos y Herramientas
- `resumen [anio]`: Análisis de IVA Ventas vs IVA Compras.
- `buscar <termino>`: Búsqueda 360 vía FTS5 (indexa metadata JSON).
- `procesar_archivo(path)`: Firma estándar para el orquestador.
