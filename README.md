# 🧠 ERP Final - Inteligencia Financiera Modular 💳🏦🧾🦾

Bienvenido al repositorio central de **ERP Final**. Este sistema está construido bajo una arquitectura de **Monolito Modular (DDD / Vertical Slicing)** para asegurar mantenibilidad y aislamiento total de datos.

---

## 🚀 Inicio Rápido (Quick Start)

1.  **Instalar dependencias**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Levantar el Motor (API)**:
    ```bash
    python erp_api.py
    ```
3.  **Abrir el Cerebro (CLI)**:
    ```bash
    python cerebro.py
    ```

---

## 🏛️ LEER ANTES DE TOCAR (Arquitectura)

Cualquier cambio en este repositorio debe respetar la estructura modular. El punto de entrada para entender "cómo se hace qué" es:

👉 **[Cerebro_ERP.md](Cerebro_ERP.md)**: El "Tronco Cerebral" (Reglas de Oro y Mapa de Neuronas).
👉 **[DB_ARCHITECTURE.md](DB_ARCHITECTURE.md)**: La "Biblia de Datos" (Propiedad de Tablas y Esquema).

---

## 🧬 Neuronas por Dominio (Vertical Slices)
Cada módulo tiene su propio manual interno:
- 💳 [**Tarjetas**](modulo_tarjetas/NEURONA.md)
- 🏦 [**Bancos**](modulo_bancos/NEURONA.md)
- 🧾 [**Compras**](modulo_compras/NEURONA.md)
- 🧠 [**Core**](core_sistema/)

---

> [!CAUTION]
> **AVISO PARA ASISTENTES IA**: El incumplimiento de las leyes de aislamiento modular (ej. accesos directos cross-module) se considera una falla arquitectónica grave. Busca siempre la **NEURONA.md** del módulo correspondiente antes de proponer código.
