# Arquitectura General del ERP
**Nombre del Plano: arquitectura.md**

Este documento describe la arquitectura global, patrones de diseño y flujo de datos unificado del ERP, sirviendo como guía de referencia inmutable para desarrolladores y asistentes de IA.

---

## 🏛️ 1. Estilo Arquitectónico: Monolito Modular (Vertical Slicing)

El sistema se organiza en dominios autónomos (módulos) representados por directorios físicos (ej. `modulo_bancos`, `modulo_compras`, `modulo_tarjetas`, `modulo_gastos`, `modulo_pagos`).

### ⚖️ Reglas de Aislamiento Lógico:
1.  **Sin Cruce de SQL:** Ningún módulo puede realizar consultas SQL sobre tablas pertenecientes a otro módulo. Toda comunicación inter-módulo se hace mediante APIs en código Python o servicios del core.
2.  **Patrón Repositorio Estricto:** Está **estrictamente prohibido** importar `sqlite3` fuera de los archivos `storage_*.py` de cada módulo. Toda la persistencia e interacción con la base de datos se delega a las funciones del repositorio de su respectivo dominio.

---

## 🔄 2. Flujo de Datos en Tres Capas (Arquitectura ELT)

El flujo de procesamiento de archivos (extractos bancarios, cupones, facturas, comprobantes) adopta el modelo **ELT (Extract, Load, Transform)**:

```
  [ INBOX ] 
      │
      ▼  (Fase 1: Ingesta Raw)
[ erp_master.py ] ───► [ Bóveda de Crudos ] (Histórico Físico Normalizado)
      │
      ▼
[ core_staging_raw ] (Staging con JSON/Markdown/CSV)
      │
      ▼  (Fase 2: Transformación Atómica)
[ storage_*.py ] ───► [ Tablas de Producción ] (LDK, JOA, JOR, COMUN en Centavos)
```

### Capa 1: Ingesta y Archivado (Extract & Load)
*   **Origen:** El usuario deposita archivos en los directorios `inbox_[modulo]`.
*   **Orquestador (`erp_master.py`):** 
    1.  Verifica duplicación calculando el hash SHA-256 del archivo.
    2.  Verifica que el archivo no esté vacío (0 bytes); si está vacío o no supera la validación de firma, se desvía a `/no_reconocidos/`.
    3.  Lee el archivo y lo convierte a formato de texto plano (`MD` para PDFs, `JSON` para Excels, `CSV` para CSVs) a través de `core_sistema/conversores.py`.
    4.  Guarda el contenido en la tabla temporal única **`core_staging_raw`** con estado `PENDIENTE`.
    5.  Mueve el archivo original a la **Bóveda de Crudos** (organizado por módulo, fuente, año, mes) y lo elimina del inbox.

### Capa 2: Transformación y Carga (Transform)
*   **Procesador Modular:** Cada storage (`storage_*.py`) recupera sus registros en Staging con `estado = 'PENDIENTE'`.
*   **Lógica Contable:**
    1.  Normaliza importes a **Enteros en Centavos** (evitando redondeos de punto flotante) con signos correctos (egresos negativos, ingresos positivos).
    2.  Asigna la transacción a una de las 4 esferas financieras (`LDK`, `JOA`, `JOR`, `COMUN`).
    3.  Aplica deduplicación en memoria para no saltar secuenciadores de IDs en SQLite.
    4.  Escribe en la tabla definitiva de producción asociando el `raw_ingesta_id` (linaje) y el `numero_linea` para unicidad compuesta.
    5.  Se ejecuta dentro de transacciones SQL (`BEGIN` / `COMMIT`). Si falla, hace `ROLLBACK` y loguea el `traceback.format_exc()` completo en `core_staging_logs`.

### Capa 3: Presentación y Consumo (Presentation)
*   **FastAPI Gateway (`erp_api.py`):** Expone las rutas de control, APIs de datos y endpoints HTMX.
*   **CLI Orchestrator:** Acceso por consola a auditorías (`--audit`), búsquedas globales indexadas (`--search`) y reprocesamiento selectivo (`--reprocess`).

---

## 💰 3. Clasificación Financiera: Las 4 Esferas

El ERP clasifica estrictamente cada egreso e ingreso en una de las cuatro cuentas/esferas maestras para garantizar la salud del negocio y las finanzas personales:

1.  **Lo de Karlota (LDK):** Actividad comercial pura del negocio (proveedores, haberes, cargas sociales, impuestos comerciales, comisiones e intereses bancarios comerciales).
2.  **Joaquín (JOA):** Consumos y retiros estrictamente privados y personales de Joaquín.
3.  **Jorgelina (JOR):** Consumos y retiros estrictamente privados y personales de Jorgelina.
4.  **En Común (COMUN):** Gastos de convivencia del hogar (alquiler residencial, servicios familiares, supermercado compartido). El balance consolidado divide estos gastos automáticamente al 50%.

---

## ⚡ 4. Reglas de Programación y Concurrencia de SQLite

*   **0% Frontend:** La interfaz de usuario queda congelada. No se modifican archivos HTML, CSS ni JS para centrar todo el esfuerzo de desarrollo en motores de parseo, consistencia de datos y lógica financiera.
*   **Rutas SASH-SAFE:** Todas las rutas físicas de archivos almacenadas en base de datos (`path_archivo`, `path_boleta`, `path_comprobante`) deben guardarse obligatoriamente utilizando diagonales frontales `/` para evitar fallos de escape en Windows.
*   **Concurrencia WAL:** Toda inicialización de conexión a la base de datos debe forzar la ejecución de:
    *   `PRAGMA journal_mode=WAL;` (permite lecturas concurrentes simultáneas mientras se escribe).
    *   `PRAGMA synchronous=NORMAL;` (mejora el rendimiento de escritura en disco).
