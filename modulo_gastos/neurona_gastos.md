# 🧬 NEURONA: MÓDULO GASTOS (Libro Diario & Cuentas) 🏛️🧠
**Versión 6.0.0 — Optimizado y Consolidado**

Este módulo gestiona la asignación manual de consumos diarios e imputaciones a titulares o esferas de imputación financiera.

---

## 📂 Componentes del Módulo
1.  **[storage_gastos.py](storage_gastos.py)**: Capa de persistencia. Expone la API para guardar cuentas, tipos y registros individuales.
2.  **Vistas Web**:
    -   `gastos.html`: Dashboard principal. Integra botones para sincronizar tarjetas y registrar gastos.
    -   `gastos_list.html`: Renderiza el listado histórico de gastos con ordenamiento client-side interactivo por columnas.
    -   `gastos_form.html`: Formulario modal de creación/edición.
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
-   **Columna `fuente`:** Almacena el origen de la transacción (`Manual` o `Visa Hipotecario`).
-   Columnas Core: `id` (INTEGER PK), `gasto_tipo_id` (INTEGER FK), `monto` (REAL), `fecha` (TEXT), `descripcion` (TEXT), `fuente` (TEXT DEFAULT 'Manual').

---

## ⚡ Reactividad del Formulario
-   **Auto-Arranque de Filtros:** Al abrir el formulario desde el dashboard, se pre-selecciona automáticamente la cuenta del filtro activo (gracias a `hx-include`).
-   **Filtrado Dinámico de Conceptos:** Al cambiar el selector de "Cuenta / Área" en el formulario modal, se dispara una petición `/api/gastos/form/tipos` vía HTMX que reemplaza el selector de "Concepto Gasto" mostrando **únicamente** las categorías de la cuenta seleccionada.
-   **Creación On-the-fly:** Permite crear conceptos nuevos en el momento eligiendo la opción `➕ [Crear Concepto Nuevo...]`. El backend autogenera los colores CSS según el titular.
