# 🧬 NEURONA: MÓDULO COMPRAS (Fiscal & Facturación) 🧾🧠
**Versión 7.0.0 — ELT ARCA + CALIM conciliado**

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

---

## ELT de comprobantes recibidos ARCA v7

- `lector_arca_comprobantes.py` acepta el ZIP original o un CSV suelto.
- `arca_comprobantes_parser.py` valida el ZIP, normaliza encabezados y convierte importes a centavos exactos.
- El ZIP entra en `core_staging_raw` como manifiesto y evidencia física; cada CSV interno entra completo en otro raw.
- `compras_arca_ingestas` relaciona ZIP, CSV, período, hashes y ruta archivada.
- `compras_facturas` conserva compatibilidad en pesos y agrega columnas canónicas en centavos, CAE, código ARCA, signo y linaje raw.
- Facturas repetidas en exportaciones superpuestas se actualizan por CUIT + tipo + punto de venta + número; no se duplican.
- Las notas de crédito se guardan con signo negativo para los totales contables.
- El tipo 63 se conserva como `Liquidación A`; no se transforma artificialmente en Factura A.
- `importador_afip.py` permanece como wrapper de compatibilidad, sin lógica duplicada.

---

## ELT de facturas de compra CALIM v7

- `lector_calim_compras.py` coordina la ingesta y el archivo físico del XLSX original; `calim_facturas_parser.py` concentra la lectura y normalización.
- Cada libro entra primero en `core_staging_raw` como JSON normalizado y queda relacionado con su archivo inmutable en `compras_calim_ingestas`.
- Los importes numéricos de las exportaciones CALIM se interpretan como **centavos**. Los valores de texto con formato monetario se interpretan como pesos; esta regla evita el error histórico de multiplicar por 100 importes pequeños.
- La identidad semántica usa fecha, CUIT del proveedor, tipo ARCA, punto de venta y número. El CUIT se extrae del campo compuesto `CUIT - Proveedor`.
- Cuando ARCA y CALIM coinciden, ARCA es la fuente autoritativa del desglose fiscal y el registro queda `CONCILIADO_ARCA_CALIM`.
- Si los totales difieren queda `DIFERENCIA_ARCA_CALIM`; si sólo existe en el libro contable queda `SOLO_CALIM`.
- `SOLO_CALIM` no siempre es una anomalía. Las liquidaciones de tarjetas/banco cargadas manualmente por Joaquín como factura no necesariamente aparecen como comprobantes recibidos en ARCA; el estudio usa esa registración para imputar IVA y considerar el gasto en Ganancias. Deben conservar su origen manual y evidencia documental.
- Los registros redundantes del importador CALIM anterior no se borran: quedan auditables como `DUPLICADO_LEGACY_CALIM` y se excluyen de listados, búsquedas y totales operativos.
- `importador_calim.py` permanece como wrapper de compatibilidad, sin una segunda implementación del parser.
- En las facturas manuales de liquidaciones del Banco del Chubut, Joaquín usa el primer bloque del número (`00005-00002026`) para codificar el mes imputado: `00005` = mayo, `00006` = junio. No interpretarlo como punto de venta fiscal; conservar también la fecha informada por CALIM.
