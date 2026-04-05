# CEREBRO ERP FINAL - Versión 4.8.0 (Ecosistema Unificado)
# Sistema de Ingesta Inteligente y Bóveda Nominal

Bienvenido al repositorio central de **ERP Final**. Este sistema utiliza una arquitectura de **Monolito Modular (Vertical Slicing)** con un motor de **Ingesta Híbrida** (Relacional + JSON) y cumplimiento legal automatizado.

---

## 🏛️ Ecosistema Unificado y Flujo Atómico (v4.8.0)

1.  **Terminal de Ingesta (Split-Screen)**: Interfaz única con Visor HD integrado. Soporta *Drop* de PDFs/Imágenes, Zoom por rueda de ratón (Mousewheel) y Paneo (Drag-to-Pan).
2.  **Match Atómico Inteligente**:
    - Un input único para la vinculación. Al escribir el número de factura, el sistema busca de forma elástica eliminando guiones y ceros.
    - Devuelve instantáneamente el "Match" indicando orígenes (AFIP / CALIM) y los totales.
3.  **Archivado Nominal en Bóveda**:
    - Al vincular, se asegura la jerarquía por CUIT: `[Modulo]/archivos_[modulo]/[CUIT - Proveedor]/[Año]/[Mes]`.
    - **Nomenclatura**: Imposición del renombrado automático: `YYYY-MM-DD_Proveedor_Factura_PV-NUM.ext`.
4.  **Limpieza de Origen**:
    - El comprobante cargado en la terminal es movido permanentemente a la bóveda. Desaparece de origen (`inbox`), garantizando una ingesta sin archivos huérfanos.

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
