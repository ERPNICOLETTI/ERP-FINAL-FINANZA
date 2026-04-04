# 🧠 ERP Final - Inteligencia Financiera Modular 💳🏦🧾🦾
# Versión 4.0 - Ecosistema de Ingesta Inteligente

Bienvenido al repositorio central de **ERP Final**. Este sistema utiliza una arquitectura de **Monolito Modular (Vertical Slicing)** con un motor de **Ingesta Híbrida** (Relacional + JSON) y cumplimiento legal automatizado.

---

## 🚀 Flujo de Trabajo v4.0 (Soltar y Procesar)

A diferencia de versiones anteriores, el sistema ahora centraliza la entrada de datos:

1.  **Depositar**: Arroja tus archivos (PDF Payway, Excel Bancos, CSV AFIP) en la carpeta `/inbox/`.
2.  **Procesar**: Ejecuta el orquestador:
    ```bash
    python erp_master.py
    ```
3.  **Resultado**: El sistema identifica el archivo, extrae los datos, los indexa en el **Buscador 360** y mueve el documento original al **Archivo Legal** (`static/archivadas/`).

---

## 🏛️ Documentación Maestra (Arquitectura)

Cualquier cambio en este repositorio debe respetar la estructura modular y el **Patrón Repositorio** (acceso a DB solo vía `storage_*.py`).

👉 **[Cerebro_ERP.md](Cerebro_ERP.md)**: Reglas de Oro, Flujo de Ingesta y Mapa de Neuronas.
👉 **[DB_ARCHITECTURE.md](DB_ARCHITECTURE.md)**: Diseño Híbrido, Idempotencia y FTS5.

---

## 🧬 Neuronas por Dominio (Vertical Slices)
Cada módulo tiene su propio manual interno:
- 💳 [**Tarjetas**](modulo_tarjetas/NEURONA.md)
- 🏦 [**Bancos**](modulo_bancos/NEURONA.md)
- 🧾 [**Compras**](modulo_compras/NEURONA.md)
- 🧠 [**Core**](core_sistema/)

---

> [!CAUTION]
> **AVISO PARA ASISTENTES IA**: Está prohibido el uso de `sqlite3` fuera de los archivos `storage_*.py`. El incumplimiento de las leyes de aislamiento modular se considera una falla arquitectónica crítica.
