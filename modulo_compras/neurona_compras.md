# 🧬 NEURONA: MÓDULO COMPRAS (Facturación) 🧾🧠
# Versión 4.6.2 - Consolidación de Flujo (Hash Único)

Esta neurona gestiona el **ciclo de vida fiscal** de los comprobantes y su conciliación contable.

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

## 🛰️ Flujo de Datos 4.6.2 (Consolidación)
1.  **Ingesta de 3 Capas (Inbox -> Crudos -> Archivos)**:
    - `inbox_compras/`: Puerta de entrada (API/UI). El Orquestador escanea aquí.
    - `crudos_compras/` (Histórico): Los reportes (CSV/Excel) se mueven aquí tras la ingesta exitosa.
    - **Política de Hash Único**: Si un archivo es un duplicado exacto, se elimina del Inbox sin ensuciar la zona histórica.
    - **Sin Sufijos**: Los reportes se sobreescriben si el nombre es igual pero el contenido cambió, eliminando ruidos visuales.
2.  **Vinculación Visual (Bóveda)**: Se sube una evidencia individual (PDF/Foto) desde el Sidebar.
3.  **Archivos de Bóveda**: Se almacenan en `/modulo_compras/archivos_compras/` (Reservado para evidencias manuales).

---

## 🧱 Tablas Clave
- `facturas`: Tabla maestra digitalizada. 
- **Idempotencia**: `UNIQUE(cuit_proveedor, punto_venta, numero_comprobante, tipo_comprobante)` + `INSERT OR IGNORE`.

---

## 🛠️ Comandos y Herramientas
- `resumen [anio]`: Análisis de IVA Ventas vs IVA Compras.
- `buscar <termino>`: Búsqueda 360 vía FTS5 (indexa metadata JSON).
- `procesar_archivo(path)`: Firma estándar para el orquestador.
