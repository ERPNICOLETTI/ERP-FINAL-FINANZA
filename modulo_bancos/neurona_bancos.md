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
-   **Asignación Automática:** Durante la ingesta de extractos bancarios (en `save_movimiento_banco`), el sistema lee las palabras clave de `categorias_maestras` y las compara con la descripción del movimiento. Si coincide alguna, se auto-categoriza; de lo contrario, entra como `Sin Categorizar ❓`.
-   **Edición Inline y Feedback Loop (HTMX):** Al hacer clic sobre el badge de categoría de una fila en el navegador, se despliega un `<select>` nativo. Elegir una nueva categoría envía una solicitud `PUT` a `/api/bancos/movimientos/{id}/categoria`, la cual actualiza el registro y llama a `aprender_categoria_maestra(categoria, descripcion)` en `erp_api.py` para extraer la palabra clave del comercio y guardarla como regla para futuras ingestas.
-   **Edición Masiva con Aprendizaje (Bulk Edit):** Permite reclasificar todos los movimientos coincidentes con la búsqueda y filtros mediante `bulk_edit_categoria`. Si la re-clasificación se realiza habiendo ingresado una consulta de búsqueda `q` (mínimo 3 letras), el término buscado se aprende y se guarda como palabra clave para dicha categoría.
-   **Filtro de Palabras Genéricas**: Para evitar contaminar las reglas, el helper `extraer_palabra_clave` en `erp_api.py` filtra automáticamente prefijos de tarjeta y palabras genéricas (como `DEBITO`, `PAGO`, `TRANSFERENCIA`, `AUTOMATICO`, `RECIBIDA`, etc.), capturando únicamente el nombre real del comercio.
-   **Filtro por Similitud (Agrupación):** Enviando `agrupar=1`, la base de datos agrupa descripciones idénticas y muestra la cantidad de repeticiones (ej. "15 repeticiones").
