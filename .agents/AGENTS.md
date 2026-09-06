# AGENTS.md — Constitución operativa y memoria de continuidad del ERP FINAL

**Workspace canónico:** `C:/Users/essao/Desktop/ERP FINAL`

**Base de producción:** `C:/Users/essao/Desktop/ERP FINAL/erp_nicoletti.db`

**Propietario funcional:** Joaquín
**Colaboradores de IA:** Codex, Antigravity y cualquier agente futuro.

Este archivo es la primera lectura obligatoria de toda IA. Es el contrato común para continuar entre herramientas, chats y modelos sin perder contexto, criterios ni seguridad. No pertenece a una IA: pertenece al ERP.

## 1. Protocolo obligatorio de inicio

Antes de proponer o modificar código, datos o interfaz:

1. Leer este archivo completo.
2. Confirmar la raíz del workspace y revisar `git status --short`. El árbol puede estar sucio por trabajo legítimo de Joaquín u otra IA; nunca descartar cambios ajenos.
3. Leer `documentacion/arquitectura.md` y la neurona del dominio en `documentacion/neurona_*.md`.
4. Inspeccionar el código y esquema real antes de creer afirmaciones históricas de los `.md`. Código y base son evidencia; la documentación orienta y debe corregirse si quedó vieja.
5. Buscar primero si ya existe parser, lector, storage, ruta o vista. Mejorar y unificar lo existente antes de crear implementaciones paralelas.
6. Si hay archivos de entrada, reconstruir el linaje: original → hash → `core_staging_raw` → transformación → tabla final.
7. Al terminar, verificar pruebas, sintaxis, idempotencia, conciliación y, si corresponde, endpoint o pantalla real.
8. Actualizar este archivo cuando cambien arquitectura, reglas, estado o prioridad. Actualizar también la neurona del módulo. Es parte del trabajo.

### Eficiencia de contexto y tokens

Toda IA debe buscar activamente la forma de usar menos contexto y tokens **sin perjudicar el resultado ni la calidad**:

- empezar con búsquedas dirigidas (`rg`) y leer sólo los archivos o fragmentos relevantes;
- no volver a leer ni explicar material que ya está vigente en el contexto;
- agrupar inspecciones y verificaciones compatibles para reducir rondas innecesarias;
- reutilizar parsers, helpers, pruebas y documentación existentes antes de generar código nuevo;
- resumir hallazgos intermedios y registrar en este archivo únicamente hechos reproducibles;
- evitar pegar salidas extensas, esquemas completos o transcripciones cuando alcanza una selección precisa;
- delegar o paralelizar sólo cuando realmente reduzca costo/tiempo y no duplique contexto;
- preferir soluciones simples, deterministas y mantenibles.

El ahorro de tokens jamás justifica omitir lectura obligatoria, controles ELT, conciliación centavo a centavo, pruebas relevantes, seguridad, trazabilidad o una explicación necesaria para Joaquín. Si eficiencia y calidad entran en conflicto, manda la calidad.

No hace falta presentarse como Antigravity ni Codex. La IA debe explicar brevemente qué contexto cargó y continuar desde el estado existente.

## 2. Propósito y forma de pensar

El ERP es simultáneamente:

- sistema contable y operativo de **Lo de Karlota (LDK)**;
- herramienta de orden financiero personal para **Joaquín (JOA)** y **Jorgelina (JOR)**;
- bóveda auditable de documentos originales;
- proyecto colaborativo construido por Joaquín con distintas IAs.

La forma de trabajo es fría, verificable y sin dramatizar números negativos: primero completar ingesta, después conciliar y recién entonces interpretar. Nunca presentar saldos incompletos como diagnóstico definitivo.

Priorizar una secuencia corta y cerrable. Terminar un frente antes de mezclar otro. Si Joaquín pide “paso a paso”, entregar una sola acción concreta por vez.

## 3. Dominios y aislamiento real

Existen tres ecosistemas independientes:

- **JOA:** finanzas personales de Joaquín.
- **JOR:** finanzas personales de Jorgelina.
- **LDK:** Lo de Karlota: bancos, ventas, cobros, compras, impuestos, gastos y pagos.

`COMUN` **no es una cuarta entidad**. Es una clasificación/origen de gastos compartidos. Debe imputarse a JOA y JOR según la regla acordada, sin mezclar sus cuentas ni movimientos originales.

Reglas:

- No fusionar dashboards, saldos o decisiones de JOA, JOR y LDK por comodidad técnica.
- Cada movimiento conserva cuenta, entidad, origen documental y categoría.
- Ningún módulo consulta directamente tablas de otro módulo; usar funciones públicas, servicios del core o endpoints.
- `sqlite3` sólo en repositorios `storage_*.py` o infraestructura explícita del core. Los parsers puros no escriben la base.
- No duplicar parsing en rutas, HTML, orquestadores o storages.

### Modelo particular de JOA

- **Caja de ahorro/banco:** movimientos y saldos bancarios, filtrados por rango de calendario.
- **Visa Hipotecario:** consumos separados de la caja, navegados y analizados por mes/resumen, respetando cierre y vencimiento.
- **Categorías:** cada movimiento puede clasificarse y corregirse desde la interfaz. `COMUN` puede ser clasificación del gasto, no cuenta bancaria.

No sacar conclusiones sobre JOA hasta completar y conciliar lectores, resúmenes y movimientos del período.

## 4. Arquitectura y mapa de rutas

Monolito modular Python + FastAPI + SQLite + HTML/HTMX.

### Entradas

- `run_server.bat`: inicia el servidor local.
- `erp_api.py`: entrypoint del servidor.
- `erp_api/main.py`: FastAPI, routers y montajes estáticos.
- `erp_master.py`: detección y orquestación de ingestas.
- URL habitual: `http://127.0.0.1:5005/`.

### Directorios

- `core_sistema/`: staging, hashes, archivado, conversión e integridad compartida.
- `erp_api/`: rutas HTTP por dominio.
- `frontend/`: HTML/HTMX; `joa.html` es JOA y `payway.html` la auditoría Payway.
- `modulo_bancos/`: cuentas, extractos, Visa Hipotecario y lectores bancarios.
- `modulo_tarjetas/`: liquidaciones, adquirentes y Payway.
- `modulo_compras/`: ARCA, CALIM, facturas recibidas e IVA compras.
- `modulo_gastos/`: categorías y asignación JOA/JOR/LDK/COMUN.
- `modulo_pagos/`: vencimientos, impuestos, servicios, sindicatos y comprobantes.
- `documentacion/`: arquitectura y neuronas canónicas.
- `tests/`: pruebas de parsers y ELT.
- `scratch/` y `tmp/`: diagnóstico temporal, no producción.

### Lectura por dominio

- Global: `documentacion/arquitectura.md`.
- Bancos/Visa personal: `documentacion/neurona_bancos.md`.
- Tarjetas/Payway: `documentacion/neurona_tarjetas.md`.
- Compras/CALIM/ARCA/IVA: `documentacion/neurona_compras.md`.
- Gastos/entidades/categorías: `documentacion/neurona_gastos.md`.
- Pagos: `documentacion/neurona_pagos.md`.
- UI: `frontend/frontend_vision.md`.

Si una neurona está duplicada en `documentacion/` y `modulo_*/`, ambas copias deben quedar byte a byte sincronizadas.

## 5. Ley suprema ELT

Todo PDF, CSV, XLSX, ZIP, imagen, extracto, resumen, factura, boleta o comprobante externo sigue:

```text
original
  → hash SHA-256 y fuente
  → copia física inmutable en crudos/bóveda
  → contenido normalizado en core_staging_raw
  → parser puro y trazable
  → storage del módulo en transacción
  → tabla final con raw_ingesta_id/linaje
  → conciliación y presentación
```

- Prohibido derivar un archivo directamente a producción sin RAW.
- El original no se borra, edita ni sobrescribe. El mismo hash debe reingestarse sin efectos duplicados.
- Guardar hash, versión de parser, fuente, nombre original, RAW normalizado y vínculo con filas producidas.
- Un ZIP crudo de ARCA no es evidencia visual de una factura ni debe poblar `path_archivo` como foto/PDF individual.
- Idempotencia tanto por archivo como por fila de negocio.
- No usar deduplicación pobre que elimine movimientos gemelos válidos. La identidad debe ser semántica y conservar `numero_linea` cuando corresponda.
- Ante error: `ROLLBACK`, detalle suficiente y original conservado para reproceso.

## 6. Dinero, fechas, rutas y SQLite

- Todo cálculo y persistencia monetaria nueva usa **centavos enteros**. Campos legacy en pesos pueden mantenerse por compatibilidad, derivados de centavos.
- No usar `float` para igualdad contable. Comparar enteros y declarar cualquier tolerancia.
- Conservar moneda y signo. No mezclar ARS/USD ni convertir sin tasa, fecha y fuente.
- Fecha canónica: `YYYY-MM-DD`; la UI puede mostrar `DD/MM/YYYY`.
- Rutas persistidas con `/`, aun en Windows. Resolver y validar antes de mover/borrar.
- Producción usa `PRAGMA journal_mode=WAL` y `PRAGMA synchronous=NORMAL`, con transacciones.
- No editar `erp_nicoletti.db` a mano para forzar números. La corrección repetible vive en parser/storage/migración y queda auditada.
- `admglobal.db`, si existe, es histórico de LDK y **sólo lectura**.

## 7. Separación de responsabilidades

- **Parser:** puro; archivo/contenido → datos normalizados y advertencias. Sin movimientos ni SQL.
- **Lector/ingestor:** coordina parser, RAW, storage y archivado.
- **Storage:** única capa del dominio autorizada para SQL y migraciones aditivas.
- **API:** valida y llama servicios; sin parsing ni SQL.
- **Frontend:** presenta/edita mediante endpoints; no replica reglas contables.

Antes de agregar un lector, buscar por entidad, banco, formato y texto. Si existe, corregirlo o envolverlo. `importador_*.py` legacy puede ser wrapper, pero debe existir una sola implementación real.

## 8. Cambios y seguridad

- Preservar cambios preexistentes. Nunca `git reset --hard`, `git checkout --`, limpieza masiva o borrado recursivo sin pedido inequívoco.
- No hacer commit, push, backup ni despliegue salvo pedido explícito.
- Antes de tocar producción, consultar esquema y cantidades; después comprobar cantidades, estados y muestras.
- Migraciones aditivas y repetibles. No destruir historia para simplificar.
- Duplicados históricos: marcar y excluir antes que borrar, salvo saneamiento expresamente auditado.
- No ocultar errores financieros con `except: pass`; registrar causa y estado accionable.
- Se puede mejorar HTML/CSS/JS cuando la tarea lo requiera. Datos primero, pero ninguna prohibición antigua obliga a mantener una UI inutilizable.
- Mantener archivos enfocados y separar responsabilidades cuando crecen, sin abstracciones vacías.

### Freno de mano

Si un pedido contradice ELT, inmutabilidad, aislamiento o exactitud monetaria, detener sólo esa acción, explicar el riesgo y ofrecer la alternativa compatible. El apuro no autoriza corrupción; continuar con todo lo seguro que sí pueda resolverse.

## 9. Definición de terminado

Según corresponda:

- original archivado y RAW trazable;
- parser determinista;
- persistencia transaccional e idempotente;
- importes conciliados centavo a centavo;
- duplicados controlados sin perder gemelos reales;
- pruebas o verificación reproducible;
- endpoint/pantalla comprobados si fueron afectados;
- neurona y este archivo actualizados si cambió mapa o estado;
- resumen final: cambios, verificación, pendiente y siguiente paso.

## 10. Estado operativo compartido

**Última actualización:** 2026-09-06.

### Compras / IVA

- ELT de comprobantes recibidos ARCA desde ZIP/CSV con RAW y tablas finales.
- Lector CALIM XLSX corregido: celdas numéricas interpretadas como centavos y CUIT extraído del proveedor.
- Última carga: 9 libros, 107 filas; 88 conciliadas con ARCA, 19 `SOLO_CALIM`, 0 diferencias. Cuatro libros vacíos.
- ARCA manda en el desglose fiscal al coincidir. Legacy redundante marcado `DUPLICADO_LEGACY_CALIM` y excluido de operación.
- Las liquidaciones de tarjetas/banco que Joaquín carga manualmente en CALIM como factura pueden no existir en ARCA. En ese circuito `SOLO_CALIM` es un estado esperado: el estudio usa esa imputación para computar IVA y gastos de Ganancias. No marcar como faltante ni intentar fusionar con ARCA sin identificar antes el documento y su circuito contable.
- Convención manual Banco del Chubut en CALIM: en comprobantes como `00005-00002026`, el primer bloque (`00005`) codifica el **mes imputado por Joaquín**, no un punto de venta fiscal. Así, `00005` es mayo y `00006` es junio aunque la fecha de carga de ambos sea 30/06/2026. Conservar por separado fecha del comprobante y período imputado.
- Payway 2026-08-05: neto ARS 304,00; IVA 21% ARS 63,84; total ARS 367,84.
- Agosto 2026: carga manual de ventas con tarjeta completada en CALIM. Banco del Chubut quedó separado de Payway; Banco Chubut usa IVA 21% ARS 50.953,95 + IVA 10,5% ARS 7.960,41, y Payway liquidaciones usa IVA 21% ARS 3.347,80. Naranja tuvo cero ventas, por lo que no corresponde factura manual ni debe marcarse como faltante. Falta descargar el nuevo Excel CALIM de agosto e ingerirlo al ERP para cerrar la trazabilidad.
- Frente inmediato: reingerir el exporte actualizado de agosto y luego volver al módulo JOA aislado.

### Payway / LDK

- Lectores separados para resúmenes PDF y movimientos CSV, con RAW y conciliación.
- Agosto 2026: 45 movimientos; bruto ARS 2.673.800,00; descuentos ARS 276.412,53; neto ARS 2.397.387,47.
- Auditoría en `/payway`.
- La liquidación de ventas Patagonia 365 de LDK (no la tarjeta personal 365 de JOR) quedó separada como `PATAGONIA365_LIQUIDACIONES_VENTAS`. Agosto 2026: resumen `00330064`, 8 liquidaciones, bruto ARS 1.142.530,00, arancel ARS 34.275,90, costo financiero ARS 75.813,40, IVA RI ARS 15.158,35 y neto ARS 1.017.282,35. El lector anterior cruzaba columnas; no usar sus resultados previos como autoridad.

### JOA — prioridad posterior al IVA

- JOA está aislado de JOR y LDK en `/joa`.
- Caja de ahorro y Visa Hipotecario se presentan separadas.
- Banco usa rango calendario; Visa debe analizarse por mes/resumen.
- Existe parser/lector Visa Hipotecario y categorización, pero antes de analizar saldos hay que completar ingesta y configuración del período.
- Próximo objetivo: auditar JOA de punta a punta, cerrar ingestores, clasificación y dashboard sin mezclar LDK.

### Galicia — auditoría del rojo iniciada

- Visa Galicia agosto 2026 fue el primer documento recibido: resumen `VI00000000004401517`, cierre 20/08, total ARS 10.972.348,88, pago mínimo ARS 1.331.500,00 e intereses ARS 573.874,31.
- El lector legacy fue reemplazado porque escribía sin RAW, usaba `float` y asignaba todo a JOR. El ELT nuevo concilia en centavos. Conserva como evidencia qué bloque/tarjeta figura a nombre de JOA o JOR, pero los 15 cargos quedan en `Pendiente de clasificación`: adicional/titular no decide la entidad financiera.
- Visa también imprime que el IVA discriminado no puede computarse como crédito fiscal. Aunque no se extrajo una condición fiscal junto al nombre, esa leyenda manda para la automatización: no sugerir crédito fiscal por esos cargos.
- Mastercard Galicia agosto 2026 quedó en RAW 259 mediante un único `lector_mastercard_galicia.py`, sin compartir parser con Visa. Resumen `027031698448`, cierre 27/08, total ARS 7.204.073,18 + USD 38,68, mínimo ARS 799.320,00, intereses ARS 329.644,05, 26 operaciones documentales y 23 cargos neutrales. Conciliación ARS/USD cero. La oferta leída incluye 24 cuotas base de ARS 595.092,69 sobre capital ARS 7.263.253,58, sin comisión ni IVA, vigente hasta 01/10/2026.
- Mastercard figura como `CONSUMIDOR FINAL` y el propio resumen dice que el IVA discriminado no puede computarse como crédito fiscal. No imputarlo automáticamente a JOR RI; primero corregir/revisar la condición fiscal con Galicia y el estudio.
- Cuenta Corriente Galicia PDF quedó en RAW 260 y tabla `bancos_extractos_resumenes`, con 33 movimientos en `bancos_movimientos`. Período 31/07–28/08: saldo inicial ARS -4.901.257,69 + créditos ARS 7.261.000,00 − débitos ARS 5.884.475,69 = saldo final ARS -3.524.733,38. Intereses ARS 475.527,28; IVA ARS 99.860,73; sellos ARS 6.484,46; conciliación corrida y global cero.
- La Cuenta Corriente también figura `Consumidor Final` pese al CUIT de JOR y prohíbe computar el IVA. El destino comercial de la deuda no corrige un comprobante fiscal mal emitido: bloquear el IVA hasta regularizar la condición con Galicia.
- Pendiente del mismo frente: caja de ahorro Galicia. No emitir diagnóstico consolidado hasta ingerir y conciliar los cuatro documentos.

## 11. Relevo entre IAs

Toda IA que deje trabajo estructural incompleto actualiza la sección anterior con fecha, archivos/módulos tocados, cantidades ingeridas, verificaciones, decisiones, riesgos reales y siguiente acción concreta.

No pegar conversaciones extensas: registrar hechos reproducibles. Si este archivo contradice el código o una decisión actual de Joaquín, corregirlo en el mismo trabajo y dejar la nueva verdad explícita.

---

**Principio final:** ninguna IA es dueña del contexto. Codex, Antigravity y agentes futuros son relevos del mismo trabajo. La continuidad vive en el código, el RAW, la base auditada y esta memoria compartida.
