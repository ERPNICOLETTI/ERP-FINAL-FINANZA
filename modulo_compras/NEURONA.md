# 🧬 NEURONA: MÓDULO COMPRAS (Facturación) 🧾🧠

Esta neurona es responsable del **ciclo de vida de los comprobantes**: desde la descarga en ARCA (AFIP) hasta el envío al estudio contable (CALIM) y el archivo físico.

## 🛰️ Flujo de Datos al Milímetro

1.  **Ingesta AFIP**: Se importan los CSV de "Mis Comprobantes recibidos". Las facturas entran con estado `SOLO_AFIP`.
2.  **Importación CALIM**: Se importan los Excel del contador. Se hace match por `numero_completo`. Si existe, el estado pasa a `CONCILIADO_CALIM`.
3.  **Sincronización de Archivos**: Un script recorre la carpeta física de facturas.
    - Si el PDF existe y está bien nombrado, se marca como `ARCHIVADO`.
    - Si el nombre está mal, el `organizador_carpetas.py` lo normaliza por CUIT y Fecha.

## 🧱 Tablas Clave
- `facturas`: Tabla maestra que guarda facturas, notas de crédito y débito.
- Campos Críticos: `status` (controla si está en AFIP, CALIM o Archivado) y `path_archivo`.

## ⚠️ Reglas de Oro (No romper)
- **Integridad del Número**: No modificar el formato del punto de venta y número (ej: 0001-00001234). Es la clave primaria lógica.
- **Diferencia de Céntimos**: CALIM y AFIP a veces difieren por céntimos. El sistema debe ser tolerante en el match de montos, pero estricto en el número de comprobante.
- **Relaciones de Carpeta**: La ruta física debe seguir el patrón `CUIT/AÑO/MES/FACTURA.pdf`.

## 🛠️ Comandos de Neurona
- `resumen [anio]`: Total de IVA Ventas vs IVA Compras.
- `buscar <termino>`: Detective de facturas por Cuit, Proveedor o Número.
- `sync`: El "bibliotecario" que ordena los archivos PDF y limpia la DB.
- `importar <AFIP|CALIM> <path>`: Inyección manual de datos.
