# 🧬 NEURONA: MÓDULO COMPRAS (Fiscal & Facturación) 🧾🧠
**Versión 6.0.0 — Optimizado y Consolidado**

Este módulo controla las compras comerciales de la tienda (facturas, notas de crédito/débito y libro IVA), vinculándolas con sus respectivas evidencias digitales y físicas.

---

## 📂 Componentes del Módulo
1.  **[storage_compras.py](storage_compras.py)**: Capa de persistencia. Contiene operaciones SQL para la tabla `compras_facturas` y el buscador elástico (FTS5) en `meta_json`.
2.  **Parsers / Importadores**:
    -   `importador_afip.py`: Ingesta planillas CSV del portal AFIP "Mis Comprobantes".
    -   `importador_calim.py`: Ingesta planillas Excel de la gestoría contable CALIM.
    -   `generador_libro_iva.py`: Exporta resúmenes para control contable.
3.  **Vistas Web**:
    -   `compras.html`: Interfaz de ingesta. Contiene el visor interactivo de PDFs/imágenes con zoom/paneo integrados.
    -   `tabla_compras.html`: Sub-vista dinámica de facturas cargadas.

---

## 🛰️ Flujo de Match Atómico y Sala de Espera

El operario procesa las facturas en papel/PDF soltándolas en el visor:
1.  **Match Atómico Omni-Direccional:** Se ingresa el número de comprobante o el **CAE** en el buscador único. El sistema limpia ceros y guiones y busca en la base de datos (incluso dentro del `meta_json` si es por CAE).
    -   *Caso Exitoso:* Si existe el comprobante en la base, se fusiona el PDF subido con la factura y se archiva automáticamente en la bóveda permanente.
    -   *Engrapadora Virtual:* Si el registro ya tenía una imagen o PDF asociado, el sistema **los une en un solo archivo PDF multi-página** en caliente.
2.  **Sala de Espera (Cuarentena contable):** Si el comprobante subido no existe digitalmente en la base de datos, se utiliza el botón **"Archivar como Pendiente CALIM"**.
    -   El archivo físico se guarda en una carpeta temporal de pendientes.
    -   El registro se muestra en **amarillo** con la leyenda `⏳ PENDIENTE` en el visor hasta que se importen las planillas digitales mensuales.
3.  **Archivado Legal Nominal:** Las facturas procesadas se almacenan bajo la estructura inmutable y normalizada (SASH-SAFE):
    `/modulo_compras/archivos_compras/Facturas/[CUIT] - [PROVEEDOR]/[YYYY]/[MM]/`
