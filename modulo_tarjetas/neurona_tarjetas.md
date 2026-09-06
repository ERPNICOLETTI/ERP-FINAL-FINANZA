# NEURONA: MODULO TARJETAS (Recaudacion)

**Version 7.1.0 - Payway y Patagonia 365 ELT trazables**

El modulo registra la venta presentada, el costo de cobrarla y el neto acreditado. Pertenece al ecosistema LDK y no escribe directamente en Compras, Bancos, JOA ni JOR.

## Lectores Payway

- `lector_resumen_payway.py`: orquesta resúmenes mensuales PDF.
- `payway_resumen_parser.py`: parser puro. Identifica marca, establecimiento, pagador y numero de resumen; extrae dias y conceptos; exige conciliacion exacta al centavo.
- `lector_movimientos_payway.py`: orquesta Movimientos Presentados CSV.
- `payway_movimientos_parser.py`: parser puro de cupones/movimientos.
- `lector_payway_liq.py` y `lector_payway_csv.py`: wrappers de compatibilidad, sin logica duplicada.

## Contrato ELT

1. El archivo se lee sin modificar.
2. El contenido completo, SHA-256 y version del parser entran primero en `core_staging_raw`.
3. Raw y tablas Payway se confirman en una sola transaccion SQLite.
4. El master archiva el original en `crudos_tarjetas` sin sobrescribir otro archivo distinto.
5. La ruta final se actualiza por SHA-256, nunca por un ID ambiguo.

Los importes nuevos se guardan como `INTEGER` en centavos. Cada fila de negocio conserva `raw_ingesta_id` y `numero_linea`.

## Modelo Payway normalizado

- `tarjetas_payway_resumenes`: cabecera mensual. Identidad semantica unica por establecimiento + pagador + numero de resumen + fecha de emision.
- `tarjetas_payway_resumen_dias`: bruto, descuentos y neto por fecha de pago, con todas las liquidaciones/lotes del bloque.
- `tarjetas_payway_resumen_conceptos`: aranceles, costo por Plan Cuotas, financiacion/cobro anticipado, servicio Payway, IVA y retenciones separados.
- `tarjetas_payway_movimientos`: movimientos presentados individuales, con fechas, lote, cupon, marca, establecimiento, cuotas y autorizacion.
- `vw_payway_conciliacion_diaria`: compara movimientos y resumen por fecha de pago + marca + establecimiento; informa `CONCILIADO`, `DIFERENCIA`, `NO_LIQUIDADO` o `FALTA_MOVIMIENTOS`.

El panel `/payway` permite consultar esta conciliacion por rango calendario. El endpoint de datos es `/api/tarjetas/payway/conciliacion`.

Las tablas historicas `tarjetas_liquidaciones`, `tarjetas_liquidaciones_detalles` y `tarjetas_payway` se conservan por compatibilidad; los lectores Payway v7 ya no escriben en ellas.

## Reglas de control

- Un binario repetido reutiliza su raw por SHA-256.
- Otro binario del mismo resumen conserva otro raw pero actualiza el mismo registro de negocio.
- Un resumen se rechaza si `bruto - descuentos != neto` o si dias/conceptos no reconcilian con la cabecera.
- No se usan `float` para dinero.
- El lector no registra impuestos en Compras. La exposicion contable futura debe hacerse mediante API/servicio explicito.

## Liquidación mensual de ventas Patagonia 365 (LDK)

Esta fuente es una liquidación del adquirente por ventas del comercio LDK. No es el resumen de la tarjeta de crédito Patagonia 365 personal de JOR; sus RAW, tablas y rutas no deben mezclarse.

- `patagonia365_resumen_parser.py` es el parser puro; entrega importes como centavos y rechaza el documento si las liquidaciones no concilian con la cabecera o el neto.
- `lector_patagonia.py` coordina la ingesta. El lector legacy dejó de interpretar columnas por posición con `float`.
- `tarjetas_patagonia_resumenes` conserva la cabecera mensual y `tarjetas_patagonia_liquidaciones` sus liquidaciones por fecha de pago/presentación.
- El PDF completo entra primero en `core_staging_raw` con SHA-256 y versión del parser. La identidad comercial es comercio + número de resumen + período.
- `tarjetas_liquidaciones` y su detalle se actualizan como compatibilidad, pero los centavos de las tablas Patagonia son la autoridad.
- El archivo original se archiva en `crudos_tarjetas/PATAGONIA365_LIQUIDACIONES_VENTAS/[anio]/[mes]` y la ruta se actualiza por hash.

Control agosto 2026: resumen `00330064`, 8 liquidaciones, bruto ARS 1.142.530,00, arancel ARS 34.275,90, costo financiero ARS 75.813,40, IVA RI ARS 15.158,35 y neto ARS 1.017.282,35; diferencia cero.
