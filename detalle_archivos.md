# 🗺️ Mapa y Detalle de Archivos - ERP FINAL (AI Context / Zero-Shot)

Este documento detalla la función exacta de cada archivo dentro de la arquitectura de monolito modular (Vertical Slicing) del proyecto ERP FINAL. Está optimizado para proveer contexto arquitectónico rápido a sistemas de Inteligencia Artificial (Gemini, Copilot, etc.).

> [!IMPORTANT]
> **REGLA PARA LA IA (GEMINI):** El proyecto usa **Patrón Repositorio** y **Domain-Driven Design (DDD)**. Nunca uses `sqlite3` fuera de los archivos `storage_*.py`. Los dominios son aislados. Las rutas físicas de archivos deben normalizarse usando `/` (SASH-SAFE) para evitar corrupción en Windows. Todo metadato extra o variable se inyecta obligatoriamente en el campo `meta_json` el cual es indexado por FTS5 para búsquedas.

## 📂 Raíz del Proyecto

*   **`cerebro.py`**: `[AI Context: CLI Entry Point / DDD Hub]` Es la Consola de Control Central. Delega comandos de terminal a la "neurona" lógica del módulo. **Instrucción:** No alterar para introducir lógica de negocio profunda; solo usar para mapear argumentos.
*   **`erp_api.py`**: `[AI Context: FastAPI Gateway]` Servidor principal. Expone endpoints de API, devuelve fragmentos HTML vía HTMX (Jinja2) y monta directorios estáticos. **Instrucción:** Si se crean nuevas rutas de archivos, montarlas aquí con `StaticFiles`.
*   **`erp_master.py`**: `[AI Context: Golden Master / System Orchestration]` CLI para mantenimiento global. Procesa todas las carpetas `inbox_*` disparando inyecciones. **Instrucción:** Al agregar un nuevo parser, debe ser registrado dentro de su función `ingest_inbox()`.
*   **`erp_nicoletti.db`**: `[AI Context: Primary SQLite DB]` Base de datos. **Instrucción:** Nunca conectar directamente, usar los storages.
*   **`requirements.txt`**: Dependencias de entorno.
*   **`readme.md`**, **`cerebro.md`**, **`db_architecture.md`**: `[AI Context: System Constraints & Schema Docs]` Reglas maestras del sistema. **Instrucción:** Gemini debe actualizar estos archivos proactivamente si implementa cambios estructurales.

---

## 🧠 Directorio `core_sistema/`
Infraestructura transversal compartida (Shared Kernel).

*   **`db_ingesta.py`**: `[AI Context: Schema Init & FTS5 Indexing]` Crea las tablas a nivel global. **Instrucción:** Si agregas una tabla, añádela a su función `initialize_all()`.
*   **`archiver_service.py`**: `[AI Context: File Vault Manager]` Archiva los archivos físicos en una estructura jerárquica: `/año/mes/proveedor`.
*   **`checksum_service.py`**: `[AI Context: SHA256 Idempotency Check]` Lógica para rechazar archivos binariamente idénticos.

---

## 🧾 Directorio `modulo_compras/`
Dominio Fiscal: AFIP, CALIM y Libro IVA.

*   **`storage_compras.py`**: `[AI Context: Repository Pattern]` Único archivo que puede hacer operaciones SQL sobre facturas (`compras_facturas`, etc).
*   **`importador_afip.py`** / **`importador_calim.py`**: `[AI Context: Data Extraction Parsers]` Analizan CSV/Excel estructurados para inyectarlos como diccionarios normalizados.
*   **`generador_libro_iva.py`**: Extractor especializado del PDF fiscal.
*   **`neuron_compras.py`**: `[AI Context: CLI Domain Router]` Mapeo de sub-comandos para compras.
*   **`visor_discrepancias.py`**: Scripts de mantenimiento local.
*   **`neurona_compras.md`**: `[AI Context: Domain Specific Knowledge]`.

---

## 💳 Directorio `modulo_tarjetas/`
Dominio Recaudación: Payway, Naranja, Patagonia 365.

*   **`storage_tarjetas.py`**: `[AI Context: Repository Pattern]` Manejo SQL de liquidaciones.
*   **`parser_payway_liq.py`**, **`parser_naranja_xlsx.py`**, **`parser_patagonia.py`**: `[AI Context: Regex & Data Parsers]` Extraen tablas complejas y devuelven el esquema base: `(bool, dict)`.
*   **`logica_tarjetas.py`**: `[AI Context: Analytics Engine]` Métricas y cálculos sobre lo recaudado.
*   **`neuron_tarjetas.py`**: `[AI Context: CLI Domain Router]`.
*   **`neurona_tarjetas.md`**: `[AI Context: Domain Specific Knowledge]`.

---

## 🏦 Directorio `modulo_bancos/`
Dominio Tesorería: Conciliación bancaria (Chubut, Credicoop, Hipotecario).

*   **`storage_bancos.py`**: `[AI Context: Repository Pattern]`.
*   **`parser_chubut.py`**, **`parser_credicoop_joaquin.py`**, **`parser_hipotecario.py`** (+USD): `[AI Context: Excel Extractors]` Traducen extractos a un JSON/Dict estándar.
*   **`conciliacion_bancaria.py`**: `[AI Context: Matching Algorithm]` Algoritmo que liga movimientos en banco con compras o pagos.
*   **`compare_banks.py`**: Utilidad aislada de auditoría.
*   **`neuron_bancos.py`**: `[AI Context: CLI Domain Router]`.
*   **`neurona_bancos.md`**: `[AI Context: Domain Specific Knowledge]`.

---

## 💰 Directorio `modulo_pagos/`
Dominio Vencimientos (Sindicatos, Servicios, Impuestos).

*   **`storage_pagos.py`**: `[AI Context: Repository Pattern]` Manejo SQL exclusivo de la tabla `pagos`.
*   **`parser_pagos.py`**: `[AI Context: NLP/Regex PDF Extraction]` Aísla fechas y montos para el *1er* y *2do vencimiento* (clave para entidades sindicales).
*   **`logic_pagos.py`**: `[AI Context: Autonomous Ingestion Pipeline]` Ingesta en cascada exclusiva para pagos.
*   **`neurona_pagos.md`** y **`pagos_recurrentes.md`**: `[AI Context: Domain Rules & Taxonomy]` Reglas fijas para catalogar qué es un servicio vs. un sindicato.

---

## 🖥️ Directorio `frontend/`
Capa de Presentación Web UI (HTMX + Jinja2).

*   **`index.html`**: `[AI Context: UI / Main View]` Terminal HD principal.
*   **`compras.html`**, **`pagos.html`**: Sub-vistas contenedoras de la interfaz.
*   **`tabla_pagos.html`**, **`tabla_compras.html`**: Plantillas Jinja2 devueltas por el servidor e inyectadas de forma invisible por HTMX. (Cero JavaScript pesado).
*   **`style.css`**: `[AI Context: UI Design System]`.
*   **`frontend_vision.md`**: `[AI Context: Frontend Directives]` Reglas visuales. **Instrucción:** Gemini debe consultar esto antes de modificar componentes visuales para mantener el estilo consistente.
