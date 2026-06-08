# 🧬 NEURONA: MÓDULO BANCOS (Tesorería & Conciliación) 🏦🧠
**Versión 6.0.0 — Optimizado y Consolidado**

Este módulo registra y procesa los extractos bancarios de Chubut, Credicoop e Hipotecario (Pesos/USD), y maneja el clasificador automático de transacciones.

---

## 📂 Componentes del Módulo
1.  **[storage_bancos.py](storage_bancos.py)**: Capa de persistencia. Contiene las operaciones SQL para movimientos bancarios e historiales de archivos.
2.  **[conciliacion_bancaria.py](conciliacion_bancaria.py)**: Algoritmo de emparejamiento entre movimientos del banco y facturas de compras o pagos de servicios.
3.  **Parsers Específicos**:
    -   `parser_chubut.py` / `parser_credicoop_joaquin.py` / `parser_hipotecario.py` (e `hipotecario_usd`): Traducen los formatos de planilla bancaria a diccionarios normalizados.
    -   `parser_visa_hipotecario.py`: Extrae consumos del PDF de liquidación, detecta cuotas (ej. `05/06`), pesifica dólares e inserta los registros limpios en `gastos_registros` indicando la fuente.
4.  **Vistas Web**:
    -   `bancos.html`: Panel de tesorería. Contiene la barra de búsqueda y filtros rápidos.
    -   `tabla_bancos.html`: Listado dinámico de movimientos.

---

## 🏛️ Base de Datos (`bancos_movimientos`)
-   **Esquema:** Registra cada movimiento con fecha, importe, saldo, banco, cuenta y la categoría asociada.
-   **Idempotencia:** Restricción `UNIQUE(banco, cuenta, fecha, descripcion, importe, saldo)` + `INSERT OR IGNORE`.
-   **Estrategia Anti-Colisión:** En transacciones legítimas idénticas del mismo día, el parser añade un sufijo numérico `(2)`, `(3)` al final de la descripción para evitar que SQLite ignore el registro debido a la clave única.

---

## 🗂️ Motor Dinámico de Categorías y Auditoría UI
La lógica de categorización se autogestiona en caliente desde la base de datos:
-   **Asignación Automática:** Los parsers leen de la tabla `categorias_maestras` las `palabras_clave` configuradas para clasificar los movimientos al momento de la ingesta.
-   **Edición Inline (HTMX):** Al hacer clic sobre el badge de categoría de una fila en el navegador, se despliega un `<select>` nativo de forma asíncrona. Al elegir una categoría nueva, se envía una solicitud `PUT` a `/api/bancos/movimientos/{id}/categoria` para persistir el cambio en caliente.
-   **Filtro por Similitud (Agrupación):** Enviando `agrupar=1`, la base de datos agrupa descripciones idénticas y muestra la cantidad de repeticiones (ej. "15 repeticiones").
-   **Edición Masiva (Bulk Edit):** Permite reclasificar de un solo golpe todos los movimientos que coincidan con la búsqueda y filtros activos mediante `bulk_edit_categoria`.
