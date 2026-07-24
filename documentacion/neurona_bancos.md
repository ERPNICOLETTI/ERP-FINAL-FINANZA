# 🧬 NEURONA: MÓDULO BANCOS (Tesorería & Conciliación) 🏦🧠
**Versión 6.1.0 — Optimizado y Consolidado**

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

