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
    "row_dump": row.to_dict()  # Metadata cruda JSON
})
```

---

## 🛰️ Flujo de Datos 4.0 (Ingesta e Inbox)
1.  **Entrada Centralizada**: Los CSV de AFIP y Excels de CALIM se depositan en `/inbox/`.
2.  **Parsing Híbrido**: El `importador_afip.py` y `importador_calim.py` extraen columnas duras y guardan la fila original en el JSON de metadata.
3.  **Archivado Legal**: Tras la inserción, el `archiver_service.py` mueve el archivo a `static/archivadas/COMPRAS/YYYY/MM/ARCA_AFIP/`.
4.  **Sincronización**: Match por `numero_completo` entre fuentes AFIP y CALIM.

---

## 🧱 Tablas Clave
- `facturas`: Tabla maestra digitalizada. 
- **Idempotencia**: `UNIQUE(cuit_proveedor, punto_venta, numero_completo, tipo_comprobante)` + `INSERT OR IGNORE`.

---

## 🛠️ Comandos y Herramientas
- `resumen [anio]`: Análisis de IVA Ventas vs IVA Compras.
- `buscar <termino>`: Búsqueda 360 vía FTS5 (indexa metadata JSON).
- `procesar_archivo(path)`: Firma estándar para el orquestador.
