# 🗺️ Mapa de Inicio y Activación Contextual (Fast Startup)

Este archivo es el punto de partida para que la IA (Antigravity) comprenda el sistema en segundos con consumo mínimo de tokens.

---

## 🏛️ Core de Arquitectura y Reglas Críticas
*   **Modelo:** Monolito Modular (Vertical Slicing en `modulo_[bancos|compras|gastos|pagos|tarjetas]`).
*   **Persistencia:** SQL encapsulado en `storage_*.py` de cada módulo. Prohibido hacer consultas cruzadas entre módulos y usar `sqlite3` fuera de estos repositorios.
*   **Base de Datos:** SQLite (`erp_nicoletti.db`) en modo **WAL** (`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;`).
*   **Regla de Dinero:** Todos los importes se manejan en centavos enteros (`int`). Egresos (-) e Ingresos (+).
*   **Regla de Rutas:** Guardar rutas en DB siempre con diagonales frontales `/`.
*   **Frontend Congelado:** 0% modificaciones a HTML, CSS o JS. Foco en parseo, lógica contable y base de datos.

---

## 🔄 Flujo ELT (Ingesta)
1. **Extract & Load:** `inbox_[modulo]/` ➔ [erp_master.py](file:///c:/Users/essao/Desktop/ERP%20FINAL/erp_master.py) (deduplica por hash SHA-256, convierte a Markdown/JSON/CSV vía [conversores.py](file:///c:/Users/essao/Desktop/ERP%20FINAL/core_sistema/conversores.py)) ➔ Guarda en `core_staging_raw` (`PENDIENTE`) ➔ Mueve original a la **Bóveda de Crudos**.
2. **Transform:** `storage_*.py` ➔ Recupera `PENDIENTE` de staging ➔ Procesa y parsea con regex ➔ Escribe en la tabla definitiva usando transacciones SQL asociando `raw_ingesta_id` y `numero_linea` para unicidad.

---

## 💰 Las 4 Esferas Financieras
*   `LDK` (Lo de Karlota): Comercial (proveedores, haberes, impuestos del negocio, intereses bancarios).
*   `JOA` (Joaquín): Privado y personal de Joaquín.
*   `JOR` (Jorgelina): Privado y personal de Jorgelina.
*   `COMUN` (En Común): Gastos de convivencia compartidos (alquiler residencial, servicios, súper). División automática al 50%.

---

## 🧠 Red Neuronal de Documentos (Carga en Demanda)
Al iniciar un chat, leé inmediatamente el Markdown correspondiente para activar la lógica específica:

*   🏛️ [Arquitectura Detallada](file:///c:/Users/essao/Desktop/ERP%20FINAL/documentacion/arquitectura.md)
*   🏦 [Neurona Bancos](file:///c:/Users/essao/Desktop/ERP%20FINAL/documentacion/neurona_bancos.md) (Extractos, conciliaciones y transferencias)
*   🛍️ [Neurona Compras](file:///c:/Users/essao/Desktop/ERP%20FINAL/documentacion/neurona_compras.md) (Facturas de proveedores y LDK)
*   💸 [Neurona Gastos](file:///c:/Users/essao/Desktop/ERP%20FINAL/documentacion/neurona_gastos.md) (Gastos diarios, comprobantes y esferas)
*   💳 [Neurona Tarjetas](file:///c:/Users/essao/Desktop/ERP%20FINAL/documentacion/neurona_tarjetas.md) (Resúmenes, cuotas y cierres)
*   🤝 [Neurona Pagos](file:///c:/Users/essao/Desktop/ERP%20FINAL/documentacion/neurona_pagos.md) (Ordenación de pagos y flujo contable)
