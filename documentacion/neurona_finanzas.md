# 🧬 NEURONA: MÓDULO FINANZAS (Conciliación Cruzada & Tesorería) 📊🧠

Este módulo consolida la conciliación en cascada cruzando las ventas del local, las liquidaciones de cobro de tarjetas y las acreditaciones reales en las cuentas bancarias del ERP.

---

## 🏛️ Propósito e Integridad Contable
El módulo de Finanzas es de carácter estrictamente analítico (solo lectura) y opera mediante el acoplamiento dinámico de bases de datos utilizando el motor SQLite.
*   **Base Adjunta (`admglobal.db`):** Provee el historial comercial de ventas del local en tiempo real (`Documentos`).
*   **Persistencia Local (`erp_nicoletti.db`):** Consulta las tablas de acreditación (`bancos_movimientos`) y las de control impositivo (`tarjetas_liquidaciones`, `movimientos_mp`).

---

## 📂 Estructura de Archivos
*   **[storage_finanzas.py](file:///c:/Users/essao/Desktop/ERP%20FINAL/modulo_finanzas/storage_finanzas.py):** Capa de datos del módulo. Ejecuta las consultas del cruce de bases y calcula los KPIs consolidados de ventas del local.
*   **`routes_finanzas.py`:** API Gateway que expone los endpoints HTTP `/api/finanzas/reporte` y `/api/finanzas/kpis` para HTMX.
*   **`finanzas.html`:** Interfaz de usuario donde se listan las transacciones y se colorean según su estado de conciliación.

---

## 🔄 Flujo de Conciliación en Cascada (El Camino del Dinero)
```
[ 1. admglobal.db (Ventas) ] ───► [ 2. liquidaciones_tarjetas ] ───► [ 3. bancos_movimientos ]
```

## ⚖️ Regla de Oro Bancaria (Lógica Definitiva de Conciliación)
1.  **Agrupamiento de Depósitos Diarios:**
    Dado que el Banco Chubut a veces desdobla la transferencia de un lote de Payway en varios créditos menores en el mismo día, el motor de conciliación **DEBE agrupar y sumar** todas las acreditaciones diarias de tarjetas (`ACREDIT   LIQUID COMERC ADINTA...`) de ese día antes de compararlas con el neto de la liquidación.
2.  **Tolerancia de Match (Sircreb y Diferencias de Centavos):**
    Si la diferencia entre la sumatoria de depósitos del banco de ese día y el neto esperado de la liquidación es **menor al 2%**, el lote se considera **ACREDITADO (Verde)** de forma automática, imputando el desvío como gasto impositivo/bancario implícito (Sircreb local de Chubut o CFT).
3.  **Linaje 1:1:**
    Todos los cupones individuales del local que correspondan al lote diario verificado por sumatoria se marcan automáticamente como **ACREDITADO** en la interfaz del usuario.
