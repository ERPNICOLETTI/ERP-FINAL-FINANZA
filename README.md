# CEREBRO ERP FINAL - Versión 4.6.2 (Consolidación)
# Sistema de Ingesta Inteligente

Bienvenido al repositorio central de **ERP Final**. Este sistema utiliza una arquitectura de **Monolito Modular (Vertical Slicing)** con un motor de **Ingesta Híbrida** (Relacional + JSON) y cumplimiento legal automatizado.

---

## 🏛️ El Flujo de "Zelosa Custodia" v4.6.2

1.  **Recepción (Inbox)**: Puerta única de entrada.
2.  **Histórico (Crudos)**: Archivo inmutable de reportes masivos (AFIP, CALIM, Bancos).
    - **Política de Hash Único**: Los duplicados se eliminan del inbox para mantener el histórico limpio.
    - **Sin Sufijos**: Los reportes se sobreescriben si el nombre coincide pero el contenido cambió.
3.  **Bóveda (Archivos)**: Reservada para la verdad física (PDFs, Fotos) vinculada manualmente.

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
