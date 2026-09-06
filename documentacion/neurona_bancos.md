# 🧬 NEURONA: MÓDULO BANCOS (Tesorería & Conciliación) 🏦🧠
**Versión 7.0.0 — JOA y Visa Hipotecario conciliados**

Este módulo registra y procesa los extractos bancarios de Chubut, Credicoop e Hipotecario (Pesos/USD), y maneja el clasificador automático de transacciones.

---

## 📂 Componentes del Módulo
1.  **[storage_bancos.py](storage_bancos.py)**: Capa de persistencia. Contiene las operaciones SQL para movimientos bancarios e historiales de archivos.
2.  **[conciliacion_bancaria.py](conciliacion_bancaria.py)**: Algoritmo de emparejamiento entre movimientos del banco y facturas de compras o pagos de servicios.
3.  **Parsers Específicos**:
    -   `parser_chubut.py` / `parser_credicoop_joaquin.py` / `parser_hipotecario.py` (e `hipotecario_usd`): Traducen los formatos de planilla bancaria a diccionarios normalizados.
    -   `parser_visa_hipotecario.py` (y demás parsers de tarjetas de crédito como `parser_visa_galicia.py`, `parser_mastercard_galicia.py`, `parser_naranja_pdf.py`, `parser_patagonia_pdf.py`): Extraen consumos del PDF de liquidación, detectan cuotas (ej. `05/06`), pesifican dólares, guardan la fecha original de la compra en la columna `fecha_compra` y aplican un clasificador dinámico ordenado por prioridad de cuenta según la tarjeta para evitar asignaciones erróneas.
4.  **Vistas Web**:
    -   `bancos.html`: Panel de tesorería. Contiene la barra de búsqueda y filtros rápidos.
    -   `tabla_bancos.html`: Listado dinámico de movimientos.

---

## 🏛️ Base de Datos (`bancos_movimientos`)
-   **Esquema:** Registra cada movimiento con fecha, importe, saldo, banco, cuenta, categoría y el identificador de trazabilidad `raw_ingesta_id`.
-   **Eliminación de Clave Única Restrictiva (v6.2.0):** Se removió de forma definitiva la restricción `UNIQUE(banco, cuenta, fecha, descripcion, importe, saldo)` a nivel de SQLite. Esto permite que transacciones legítimas idénticas del mismo día (ej: cobro de dos servicios idénticos o cobro de dos facturas del mismo monto) sean guardadas independientemente sin colapsarse ni generar pérdida contable.
-   **Trazabilidad Probatoria Directa:** Cada registro persistido en `bancos_movimientos` conserva su `raw_ingesta_id` enlazado al Staging ID original para auditorías físicas en un click.

---

## 🛡️ Control de Integridad y Verificación Cruzada (Data Integrity)
Se desplegó el motor **`VerificadorIntegridadERP`** en [core_sistema/verificador_integridad.py](file:///c:/Users/essao/Desktop/ERP%20FINAL/core_sistema/verificador_integridad.py) para auditar cada carga de extractos.
- **Conciliación Matemática 1:1:** Realiza una sumatoria cruzada de filas y montos acumulados de débitos y créditos del archivo físico Excel original contra lo importado en la base de datos de producción.
- **Estado de Control Galicia (Junio 2026):**
  - **Cuenta Corriente (72 filas):** Conciliación Perfecta (Desvío: $0.00).
  - **Caja de Ahorro (500 filas):** Conciliación Perfecta (Desvío: $0.00).

---

## 🗂️ Motor Dinámico de Categorías y Auditoría UI
La lógica de categorización se autogestiona en caliente desde la base de datos:
-   **Asignación Automática:** Durante la ingesta de extractos bancarios (en `save_movimiento_banco`), el sistema lee las palabras clave de `categorias_maestras` y las compara con la descripción del movimiento. Si coincide alguna, se auto-categoriza; de lo contrario, entra como `Sin Categorizar ❓`.
-   **Edición Inline y Feedback Loop (HTMX):** Al hacer clic sobre el badge de categoría de una fila en el navegador, se despliega un `<select>` nativo. Elegir una nueva categoría envía una solicitud `PUT` a `/api/bancos/movimientos/{id}/categoria`, la cual actualiza el registro y llama a `aprender_categoria_maestra(categoria, descripcion)` en `erp_api.py` para extraer la palabra clave del comercio y guardarla como regla para futuras ingestas.
-   **Edición Masiva con Aprendizaje (Bulk Edit):** Permite reclasificar todos los movimientos coincidentes con la búsqueda y filtros mediante `bulk_edit_categoria`. Si la re-clasificación se realiza habiendo ingresado una consulta de búsqueda `q` (mínimo 3 letras), el término buscado se aprende y se guarda como palabra clave para dicha categoría.
-   **Filtro de Palabras Genéricas**: Para evitar contaminar las reglas, el helper `extraer_palabra_clave` en `erp_api.py` filtra automáticamente prefijos de tarjeta y palabras genéricas (como `DEBITO`, `PAGO`, `TRANSFERENCIA`, `AUTOMATICO`, `RECIBIDA`, etc.), capturando únicamente el nombre real del comercio.
-   **Filtro por Similitud (Agrupación):** Enviando `agrupar=1`, la base de datos agrupa descripciones idénticas y muestra la cantidad de repeticiones (ej. "15 repeticiones").

---

## 🏠 Integración Analítica con Ventas del Local (`admglobal.db`)
*   **Estrategia de Conciliación de Cobros:**
    *   La base de datos `admglobal.db` (enlazada al backend mediante `ATTACH`) provee la tabla `Documentos` con los campos `PagoTarjeta` y `idTarjeta`.
    *   Se implementa el cruce analítico de transacciones entre los movimientos netos liquidados de Mercado Pago (`movimientos_mp`) / Payway y las ventas brutas registradas en el local.
    *   **Detección de Fugas:** Permite auditar si existen ventas marcadas como cobradas con tarjeta en el local que no impactaron en los bancos, o calcular la tasa de deducción real por comisiones y retenciones impositivas de cada canal de venta.

---

## Saneamiento JOA e idempotencia Hipotecario (v6.3.0)

- Los extractos solapados se consolidan por cuenta e intervalo; el más reciente sustituye solamente las fechas que cubre.
- `core_staging_raw` es inmutable y un hash existente nunca se borra.
- La identidad productiva es `UNIQUE(raw_ingesta_id, numero_linea)`, por lo que se conservan movimientos gemelos legítimos.
- Las categorías del usuario y los saldos conocidos se preservan al reconstruir.
- `moneda` separa `ARS` de `USD`; los KPI no suman monedas distintas.
- Un saldo ausente se guarda como `NULL` y se muestra como “No informado”.
- La vista JOA usa un rango calendario inclusivo (`fecha_desde` / `fecha_hasta`) con atajos de mes, 30 días, 90 días, año y período completo.

## Cierre del lector Visa Hipotecario (v7.0.0)

- `visa_hipotecario_parser.py` es puro y entrega importes firmados como centavos enteros. Reconoce comprobantes terminados en `K`, moneda `USD` pegada a una referencia y reintegros con signo final.
- Antes de persistir exige conciliación exacta de saldo anterior + operaciones = saldo actual, de forma independiente para ARS y USD.
- La identidad física sigue siendo el SHA-256 del RAW; la identidad comercial es cuenta + número de resumen + fecha de cierre. Dos descargas distintas del mismo resumen no duplican producción.
- Un reproceso conserva los IDs y las categorías manuales de todos los consumos equivalentes. Si alguna fila anterior quedara sin equivalencia, la transacción completa se revierte.
- El resumen del 20/08/2026 quedó conciliado con 36 operaciones, 33 movimientos de gasto/reintegro y diferencias ARS/USD iguales a cero.

## Visa Galicia ELT y titulares separados (v7.1.0)

- `visa_galicia_parser.py` es puro, usa centavos y exige que saldo anterior + pagos + cargos sea igual al total a pagar.
- `lector_visa_galicia.py` registra primero el texto completo y SHA-256 en `core_staging_raw`; el PDF queda en `crudos_bancos/VISA_GALICIA/[anio]/[mes]` relacionado por hash.
- La cabecera vive en `gastos_tarjeta_resumenes`; los pagos sólo concilian y no se registran como gastos.
- Cada consumo conserva `titular_codigo` como dato documental del bloque/tarjeta, pero eso no determina su entidad financiera. Todos ingresan como `Pendiente de clasificación`; JOA/JOR/COMUN/LDK se decide después con revisión humana.
- El resumen `VI00000000004401517`, cierre 20/08/2026, quedó conciliado con diferencia cero: total ARS 10.972.348,88, pago mínimo ARS 1.331.500,00, intereses ARS 573.874,31 y 15 cargos.
- El mismo resumen advierte que el IVA discriminado no puede computarse como crédito fiscal; el parser conserva esa señal y el ERP no debe sugerir su imputación automática.

## Mastercard Galicia ELT propio (v7.2.0)

- `lector_mastercard_galicia.py` es la única implementación del formato: contiene una función pura de parsing y la orquestación ELT, sin reutilizar parsers de Visa Galicia ni Visa Hipotecario.
- Lee y concilia ARS/USD, transferencias financieras, consumos de cada bloque, cargos, impuestos y las 23 alternativas de financiación. No inventa tipo de cambio para consumos facturados en USD.
- Titular/adicional se conserva sólo como evidencia documental. Los 23 cargos ingresan en `Pendiente de clasificación` y no asignan JOA/JOR/COMUN/LDK automáticamente.
- El resumen `027031698448`, cierre 27/08/2026, quedó conciliado con diferencias ARS/USD iguales a cero: total ARS 7.204.073,18, USD 38,68, pago mínimo ARS 799.320,00 e intereses ARS 329.644,05.
- El documento imprime `CONSUMIDOR FINAL` y advierte que el IVA discriminado no puede computarse como crédito fiscal; esta evidencia debe revisarse antes de cualquier imputación fiscal de JOR.

## Cuenta Corriente Galicia PDF (v7.3.0)

- `lector_galicia_cuenta_corriente.py` es el único lector del resumen PDF consolidado; no comparte parsing con tarjetas ni con el exporte Excel Galicia.
- Registra cabecera y 33 movimientos en centavos, conserva saldo tras cada operación y exige conciliación tanto corrida como global. La cabecera vive en `bancos_extractos_resumenes` y las filas en `bancos_movimientos`, ambas vinculadas al RAW.
- Período 31/07/2026–28/08/2026, cuenta `0005537-6 256-9`: saldo inicial ARS -4.901.257,69; créditos ARS 7.261.000,00; débitos ARS -5.884.475,69; saldo final ARS -3.524.733,38; diferencia cero.
- Saldos deudores de julio: intereses ARS 475.527,28, IVA ARS 99.860,73 y sellos ARS 6.484,46; el total ARS 581.872,47 concilia exactamente. Impuesto Ley 25.413 del período: ARS 35.096,26.
- La cuenta imprime CUIT `27-32954997-1` pero condición `Consumidor Final` y advierte que el IVA no puede computarse como crédito fiscal. Aunque el origen económico sea comercial, bloquear la sugerencia de crédito fiscal hasta que Galicia corrija la condición y emita respaldo válido.
