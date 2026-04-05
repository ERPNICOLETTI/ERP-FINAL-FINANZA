# 🧠 ERP Final - Inteligencia Financiera Modular 💳🏦🧾🦾
# Versión 4.5 - Ecosistema de Ingesta Inteligente

Bienvenido al repositorio central de **ERP Final**. Este sistema utiliza una arquitectura de **Monolito Modular (Vertical Slicing)** con un motor de **Ingesta Híbrida** (Relacional + JSON) y cumplimiento legal automatizado.

---

## 🚀 Flujo de Trabajo v4.5 (Ingesta Descentralizada)

A diferencia de versiones anteriores, el sistema utiliza un **Inbox Descentralizado**:

1.  **Depositar**: Arroja tus archivos (PDF, Excel, CSV) en las bandejas de entrada correspondientes de cada módulo (ej. `/modulo_compras/inbox_compras/`, `/modulo_bancos/inbox_bancos/`).
2.  **Procesar**: Ejecuta el orquestador maestro:
    ```bash
    python erp_master.py
    ```
3.  **Resultado**: El sistema identifica el archivo, extrae los datos, los indexa en el **Buscador 360** y lo archiva bajo la **Regla Legal Centrada en Entidad** dentro de `static/archivadas/`.

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
