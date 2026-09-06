# 🧬 NEURONA: MÓDULO GASTOS (Libro Diario & Cuentas) 🏛️🧠
**Versión 7.0.0 — Resúmenes Visa conciliados**

Este módulo gestiona la asignación manual de consumos diarios e imputaciones a titulares o esferas de imputación financiera.

---

## 📂 Componentes del Módulo
1.  **[storage_gastos.py](storage_gastos.py)**: Capa de persistencia. Expone la API para guardar cuentas, tipos y registros individuales.
2.  **Vistas Web**:
    -   `gastos.html`: Dashboard principal. Integra botones para sincronizar tarjetas, registrar gastos y barra de filtros rápidos interactivos (por Cuenta, Fuente de origen y Período Mensual).
    -   `gastos_list.html`: Renderiza el listado histórico de gastos filtrado con ordenamiento client-side interactivo por columnas, incluyendo badges visuales para identificar gastos automáticos a revisar (`⚠️ Revisar`) y una columna dedicada para la fecha real de consumo (`Fecha Compra`).
    -   `gastos_form.html`: Formulario modal de creación/edición, incluyendo un selector de fecha real para la compra (`Fecha de Compra (Real)`).
    -   `gastos_resumen.html`: Desglose analítico lateral consolidado por mes y cuenta (COMUN divide al 50%).

---

## 🗄️ Esquema de Base de Datos

### Tabla `gastos_cuentas`
-   Titulares o esferas (`LDK` Lo de Karlota | `JOA` Joaquín | `JOR` Jorgelina | `COMUN` En Común).
-   Columnas Core: `codigo` (TEXT PK), `nombre` (TEXT), `emoji` (TEXT).

### Tabla `gastos_tipos`
-   Categorías asociadas a cada cuenta.
-   **Clave Compuesta:** `UNIQUE(cuenta_codigo, nombre)` para permitir el mismo concepto en distintas cuentas (ej. "Servicoop" en COMUN y JOA).
-   Columnas Core: `id` (INTEGER PK), `cuenta_codigo` (TEXT FK), `nombre` (TEXT), `tipo` (TEXT), `emoji` (TEXT), `color_css` (TEXT), `palabras_clave` (TEXT).

### Tabla `gastos_registros`
-   El libro diario de transacciones manuales e importadas.
-   **Columna `fuente`:** Almacena el origen de la transacción (`Manual`, `Visa Hipotecario`, `Visa Galicia`, `Mastercard Galicia`, `Tarjeta Naranja`, `Patagonia 365`).
-   Columnas Core: `id` (INTEGER PK), `gasto_tipo_id` (INTEGER FK), `monto` (REAL de compatibilidad), `fecha` (TEXT - cierre del resumen), `descripcion`, `fuente`, `fecha_compra`, `resumen_id`, `tipo_movimiento` y `comprobante`.
-   Importes contables nuevos: `monto_centavos`, `monto_original_centavos` y `tipo_cambio_milesimas` son enteros. Las columnas REAL se conservan sólo por compatibilidad con las demás tarjetas y vistas históricas.

### Tabla `gastos_tarjeta_resumenes`
-   Una fila por liquidación comercial, identificada de forma única por `documento_clave` (`fuente + cuenta + número de resumen + fecha de cierre`).
-   Guarda en centavos enteros saldos anterior/actual ARS y USD, pago mínimo, consumos, intereses, impuestos, pagos, transferencia de deuda y diferencias de conciliación.
-   `raw_ingesta_id` vincula la liquidación con su RAW canónico y es único. Un PDF físicamente diferente del mismo resumen queda auditado como `DUPLICADO`, sin recrear consumos.

---

## ⚡ Reactividad del Formulario
-   **Auto-Arranque de Filtros:** Al abrir el formulario desde el dashboard, se pre-selecciona automáticamente la cuenta del filtro activo (gracias a `hx-include`).
-   **Filtrado Dinámico de Conceptos:** Al cambiar el selector de "Cuenta / Área" en el formulario modal, se dispara una petición `/api/gastos/form/tipos` vía HTMX que reemplaza el selector de "Concepto Gasto" mostrando **únicamente** las categorías de la cuenta seleccionada.
-   **Creación On-the-fly:** Permite crear conceptos nuevos en el momento eligiendo la opción `➕ [Crear Concepto Nuevo...]`. El backend autogenera los colores CSS según el titular.

---

## 🧠 Memoria de Clasificación & Aprendizaje del Usuario
-   **Aprendizaje del Historial:** Para evitar que las sincronizaciones periódicas sobrescriban o ignoren la categorización que el usuario definió para un comercio, el sistema implementa una **lógica de memoria de clasificación** (mediante `buscar_clasificacion_previa` en `storage_gastos.py`).
-   **Prioridad Absoluta de Personalizaciones:** Antes de aplicar cualquier regla de palabras clave por defecto de la taxonomía, el clasificador busca el último registro en la base de datos `gastos_registros` con la misma descripción normalizada (ignorando asteriscos, números de cuotas y espacios). Si el usuario ya asignó una categoría anteriormente (ej. para `LA SEGUNDA` o `EMSRL`), esa categoría se reutiliza automáticamente para el nuevo movimiento importado.
-   **Inmutabilidad y Preservación:**
    1.  **Registros existentes:** Una vez que un registro está insertado en la base de datos, el proceso de sincronización **nunca** modificará ni sobrescribirá su categoría (`gasto_tipo_id`), garantizando que las personalizaciones manuales hechas en el frontend se mantengan inalteradas.
    2.  **Advertencia de Reprocesamiento:** El script de prueba `test_reprocess.py` ejecuta un borrado masivo (`DELETE FROM gastos_registros`) para reimportar desde cero. **No debe ejecutarse en producción** ya que esto eliminaría el historial de gastos del cual se alimenta el sistema de aprendizaje del usuario, perdiendo la memoria de las personalizaciones manuales.

---

## 🛑 Directivas Críticas para IAs (Reglas de Desarrollo Obligatorias)

> [!IMPORTANT]
> Si eres una nueva IA que ingresa al proyecto, debes cumplir estrictamente con las siguientes reglas sin excepción alguna:

1. **PROHIBIDO hacer Backups sin Permiso:**
   * **Bajo ninguna circunstancia** debes ejecutar el script `backup.py`, hacer commits automáticos en Git, o generar archivos `.zip` de respaldo de la base de datos o código del proyecto sin solicitar y recibir **autorización previa y explícita por escrito del usuario** en el chat.

2. **Inmutabilidad de Clasificaciones del Usuario:**
   * Jamás debes sobrescribir ni modificar la categoría (`gasto_tipo_id`) o el titular (`cuenta_codigo`) de las transacciones guardadas en la base de datos al realizar sincronizaciones o importaciones.
   * Prioriza siempre la memoria del usuario a través de `buscar_clasificacion_previa()`.

3. **Conversión Obligatoria de Consumos en Dólares (USD):**
   * Todos los consumos de tarjetas de crédito en moneda extranjera (USD) **deben ser pesificados** multiplicando el monto original por **`1400.0`** y redondeando a 2 decimales (`round(val * 1400.0, 2)`).
   * Ningún parser o script de sincronización/histórico debe guardar consumos en USD con su valor bruto original.

4. **Limpieza Rigurosa de Prefijos de Tarjeta:**
   * Las descripciones leídas de extractos bancarios (ej. Visa Galicia) que contengan prefijos de tarjetas/titulares como `*` o `K` al principio de la descripción deben ser limpiadas de inmediato utilizando la expresión regular:
     ```python
     description = re.sub(r'^[\*K\s]+', '', description).strip()
     ```
   * Esto previene que se almacenen descripciones como `KMERPAGO*ESCO2605` en lugar de `MERPAGO*ESCO2605`, asegurando un correcto funcionamiento de la deduplicación por comparación de descripciones normalizadas.

---

## Lector Visa Hipotecario (v7.0.0)

- El parser puro reconoce importes firmados: consumos, reintegros, pagos, transferencia de deuda, intereses e impuestos. Ningún PDF pasa a producción si la ecuación ARS/USD no concilia contra el saldo oficial.
- Los pagos y la transferencia de deuda viven en la cabecera del resumen; sólo consumos y reintegros alimentan `gastos_registros`.
- El origen permanece aislado en JOA. La imputación manual admite categorías `JOA`, `COMUN` y `JOR`, y siempre se conserva durante un reproceso.
- Los prefijos de comprobante `K/*`, referencias largas y espacios de maquetación se normalizan para reaplicar la memoria de categoría sin mezclar comercios.
- La vista JOA selecciona una liquidación real por `resumen_id` y muestra por separado saldo a pagar ARS, saldo USD, pago mínimo y consumos netos.
