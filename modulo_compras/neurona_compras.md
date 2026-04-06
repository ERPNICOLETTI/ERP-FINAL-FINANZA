# 🧬 NEURONA: MÓDULO COMPRAS (Facturación) 🧾🧠
# Versión 4.9.4 - Match Atómico CAE, Jerarquía de Bóveda y Engrapadora PDF

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

### 1. Match Atómico Inteligente con Búsqueda CAE 🔍
El formulario de la bóveda cuenta con un **único input** para búsqueda omnidireccional. 
La función `smart_search_invoice()` en `storage_compras.py` realiza búsquedas elásticas eliminando ceros y guiones en tiempo real. Adicionalmente de buscar por número, busca en texto libre dentro del campo `meta_json`, permitiendo al usuario rutear comprobantes largos simplemente ingresando el número de **metadato CAE**. Cuando hay coincidencia, el sistema arroja metadatos completos y origen (AFIP/CALIM).

### 2. Flujo de Ingesta a Bóveda (3 Pasos)
1. **Drop & Zoom (UI)**: Se suelta el PDF/Imagen directamente en el panel. Se permite Zoom libre mediante scroll y paneo con drag en el área de visualización.
2. **Match (UI/DB)**: Se busca el comprobante y se relaciona automágicamente.
3. **Archivado Nominal, Sub-Capas y Engrapadora Virtual PDF**:
    Al confirmar, el Motor Orquestador de la API:
    - **Renombra** la evidencia siguiendo el estricto formato: `YYYY-MM-DD_[Proveedor]_Factura_PV-NUM.pdf`.
    - **Archiva en Bóveda Jerárquica**: Envía el archivo a la bóveda sagrada añadiendo la etiqueta a la subcategoría Facturas: `/modulo_compras/archivos_compras/Facturas/[CUIT] - [Proveedor]/[Año]/[Mes]/`. Evita colocar "NONE" en CUITs ausentes.
    - **Engrapadora Virtual PDF**: Si la factura ya tenía un documento asociado (tiene_foto = 1), el motor ensamblará un Buffer en memoria RAM utilizando PyPDF2 y Pillow para armar un PDF en tiempo real concatenándolo con la nueva imagen, sobreescribiendo una versión multi-hoja.
    - **Limpia** el archivo entrante del `inbox_compras` de origen.

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
