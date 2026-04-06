# CEREBRO ERP FINAL - Versión 5.0.0 (Ecosistema Estable)
# Ingesta CAE, Sala de Espera y Bóveda Anti-Corrupción

Bienvenido al repositorio central de **ERP Final**. Este sistema utiliza una arquitectura de **Monolito Modular (Vertical Slicing)** con un motor de **Ingesta Híbrida** (Relacional + JSON) y cumplimiento legal automatizado.

---

## 🏛️ Ecosistema Unificado y Flujo Atómico (v4.8.0)

1.  **Terminal de Ingesta HD**: Interfaz única con Visor HD. Soporta *Drop*, Zoom dinámico y Paneo (Drag-to-Pan).
2.  **Match Atómico Inteligente (AFIP/CALIM/CAE)**:
    - Un input único para la vinculación. Soporta búsqueda elástica por número y búsqueda por **CAE** (dentro de metadatos JSON).
    - **Sala de Espera**: Gestión de excepciones para facturas no encontradas en AFIP/CALIM (Cuarentena).
3.  **Bóveda Jerárquica y Engrapadora Virtual**:
    - **Engrapadora de PDFs**: Fusión automática en memoria de documentos multi-página.
    - **Bóveda Anti-Corrupción**: Rutas normalizadas con `/` para evitar errores de escape en Windows.
4.  **Sanitización y Limpieza**:
    - El comprobante cargado en la terminal es movido permanentemente a la bóveda y limpiado del `inbox`.

---

## 🏛️ Documentación Maestra (Arquitectura)

Cualquier cambio en este repositorio debe respetar la estructura modular y el **Patrón Repositorio** (acceso a DB solo vía `storage_*.py`).

> [!IMPORTANT]
> **REGLA DE EVOLUCIÓN CONTINUA**: Siempre que surjan modificaciones críticas en el código, lógica, bases de datos o arquitectura que deban ser registradas, la IA DEBE modificar proactivamente los archivos instructivos `.md` correspondientes para mantener el Zero-Shot Context actualizado para futuras sesiones.

👉 **[cerebro.md](cerebro.md)**: Reglas de Oro, Flujo de Ingesta y Mapa de Neuronas.
👉 **[db_architecture.md](db_architecture.md)**: Diseño Híbrido, Nomenclatura Universal, Idempotencia y FTS5.

---

## 🧬 Neuronas por Dominio (Vertical Slices)
Cada módulo tiene su propio manual interno:
- 💳 [**Tarjetas**](modulo_tarjetas/neurona_tarjetas.md)
- 🏦 [**Bancos**](modulo_bancos/neurona_bancos.md)
- 🧾 [**Compras**](modulo_compras/neurona_compras.md)
- 🧠 [**Core**](core_sistema/)

---

> [!CAUTION]
> **AVISO PARA ASISTENTES IA**: Está prohibido el uso de `sqlite3` fuera de los archivos `storage_*.py`. El incumplimiento de las leyes de aislamiento modular se considera una falla arquitectónica crítica.
