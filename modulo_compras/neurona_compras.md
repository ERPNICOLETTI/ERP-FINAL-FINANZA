# 🧬 NEURONA: MÓDULO COMPRAS (Facturación) 🧾🧠
# Versión 4.0 - Diseño Híbrido y Archivador Legal

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
    "numero_completo": "001-00005-00007365",
    "proveedor": "TELECOM SA",
    "monto_total": 45000.00,
    "meta_json": row.to_dict()  # Metadata cruda JSON (Estándar v4.5)
})
```

---

## 🛰️ Flujo de Datos 4.5 (Ingesta, Vinculación Visual y Carga Manual)
1.  **Ingesta AFIP/Calim (Regla Inbox)**: Los CSV/Excels se depositan estrictamente en `/modulo_compras/inbox_compras/` y se procesan automáticamente extrayendo columnas duras (neto, iva21) y guardando la fila en `meta_json`.
2.  **Vinculación Visual (CLI/Frontend)**: Se sube una evidencia fotográfica (PDF/Foto), se ingresa el número de comprobante y, si hace match en DB, se archiva automáticamente bajo la **Regla de Archivado Legal**.
3.  **Carga Manual con Fuzzy Search**: Si el comprobante no existe (ej: Gasto manual tipo ticket), se busca al proveedor usando búsqueda difusa en el **Maestro de Proveedores**. Si no existe, se crea. 
4.  **Archivado Automático (Regla Proveedor)**: El destino final de la evidencia utiliza jerarquía obligatoria: `/static/archivadas/compras/[Nombre_Proveedor]/[Año]/[Mes]/`. Se renombra como `YYYYMMDD_NombreProveedor_PV-NUM.ext` y se actualiza `tiene_foto = 1` en la DB.

---

## 🧱 Tablas Clave
- `facturas`: Tabla maestra digitalizada. 
- **Idempotencia**: `UNIQUE(cuit_proveedor, punto_venta, numero_completo, tipo_comprobante)` + `INSERT OR IGNORE`.

---

## 🛠️ Comandos y Herramientas
- `resumen [anio]`: Análisis de IVA Ventas vs IVA Compras.
- `buscar <termino>`: Búsqueda 360 vía FTS5 (indexa metadata JSON).
- `procesar_archivo(path)`: Firma estándar para el orquestador.
