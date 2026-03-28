# 🧠 Cerebro Analítico: Proyecto ERP FINAL

Este documento es la **Fuente de Verdad Técnica** del proyecto. Este sistema ha pivotado 180° desde una aplicación web tradicional a una arquitectura centralizada, analítica y orientada a la Inteligencia Artificial (IA).

## 🎯 Misión del Proyecto
Digitalizar, consolidar y auditar la información financiera de **Lo de Karlota**, **Joaquín** y **Jorgelina**. El objetivo central es cruzar la facturación (ARCA/CALIM) con los cobros por medios electrónicos (Payway) y los movimientos bancarios reales (Galicia, Chubut, MercadoPago) en una única base de datos inteligente para detectar discrepancias y automatizar análisis.

---

## 🏗️ Arquitectura del Sistema (Modo IA Centralizada)

### 1. El Motor Analítico: `erp_master.py`
Se encarga de conectarse con la base de datos `erp_nicoletti.db` y provee:
- **Indexación Inmediata**: Mantiene un índice de búsqueda inteligente `search_index` (FTS5) cruzando Transacciones, Payway y Facturas.
- **Auditoría Local**: Tiene funciones para detectar automáticamente cupones de Payway sin conciliar y discrepancias de sistema (ej. Facturas en ARCA pero no en CALIM).

### 2. La API de Servicio: `erp_api.py` (FastAPI)
Expone el poder analítico a nivel de red (por defecto `http://127.0.0.1:5005`):
- Endpoint `/search?q=...`: Búsqueda de cualquier término en todos los módulos como si fuese Google.
- Endpoint `/audit`: Arroja las falencias detectadas directo en JSON.
- Endpoint `/facturas/discrepancias`: Lista los conflictos impositivos.

### 3. El Cerebro: `cerebro.py`
Es el CLI o script principal de contacto para el usuario y la IA. Se utiliza para lanzar comandos analíticos, registrar correcciones y dialogar directamente con la API mediante peticiones HTTP.

---

## 🛠️ Instrucciones para el Asistente IA
Si se te pide realizar una inspección o corrección:
1. Usa el script `cerebro.py` invocándolo (ej. `python cerebro.py buscar <término>`).
2. Conéctate a `erp_master.py` si necesitas crear una función nueva de parseo o carga masiva (csv, excel).
3. Toda la información de verdad reside en `erp_nicoletti.db` (Tablas: `transactions`, `payway_records`, `facturas`, `search_index`).
4. **CERO WEB**: Este proyecto ya no utiliza Flask templates, HTML, CSS o carpetas `static`. Todo es CLI + API + IA.

---
*Generado bajo el nuevo paradigma de interacción por el Asistente Antigravity.*
