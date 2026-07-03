# 🧠 Filosofía, Reglas de Negocio y Planificación del ERP 🏛️

Este documento centraliza la filosofía financiera, reglas de negocio y prioridades estratégicas del ERP Nicoletti. Sirve como brújula de diseño y desarrollo para mantener el motor del sistema robusto, predecible e inteligente.

---

## 🎯 1. Directiva de Desarrollo (Regla de Oro)
*   **0% Frontend:** La interfaz de usuario queda congelada. No se tocan archivos HTML, CSS ni JavaScript en esta etapa.
*   **100% Back-End y Datos:** Toda la energía se concentra en la lógica de procesamiento, motores de parseo, ingesta de datos, integridad de la base de datos SQLite y analítica financiera.

---

## ⚖️ 2. Filosofía Financiera: Separación de Esferas (Cuentas)
El ERP clasifica estrictamente cada egreso e ingreso en una de las cuatro cuentas maestras definidas en `gastos_cuentas`:

1.  **Lo de Karlota (LDK) [🏪 Negocio]:** Actividad puramente comercial. Sueldos, proveedores mayoristas, cargas sociales, impuestos, tasas de interés bancarias, alquiler comercial. Es el motor económico.
2.  **En Común (COMUN) [🏠 Hogar]:** Gastos compartidos de convivencia (alquiler familiar, obra social compartida, Netflix, compras de supermercado para la casa). **El balance consolida y divide estos gastos automáticamente al 50%.**
3.  **Joaquín (JOA) [👤 Personal]:** Consumos estrictamente privados y personales de Joaquín (ocio, Steam, transferencias personales).
4.  **Jorgelina (JOR) [👩 Personal]:** Consumos estrictamente privados y personales de Jorgelina (obra social individual, ahorros personales, consumos propios).

---

## 🛡️ 3. Reglas de Ingesta e Idempotencia
*   **Sin Pérdida de Datos (No-Drop):** Queda prohibido el uso de `DROP TABLE` en las inicializaciones de producción. Los cambios de esquema se realizan mediante migraciones o alteraciones de tabla seguras.
*   **Ingesta Acumulativa Inteligente:** El sistema debe permitir subir archivos o extractos con rangos solapados (ej. reportes mensuales acumulativos) sin duplicar transacciones, utilizando restricciones multi-columna únicas (`UNIQUE`) y firmas de archivo SHA-256.

---

## 📈 4. Objetivos y Diagnóstico de Crisis (Prioridades de Ingesta)
El negocio actualmente arrastra deudas bancarias bajo financiación que generan altos costos financieros. El objetivo inmediato del ERP es dar **visibilidad total y control sobre el flujo de dinero**:

*   **Control de Intereses Bancarios:** Identificar cuánto interés se está perdiendo mensualmente (ej. los 1.5 millones estimados) mediante categorización correcta en la esfera **LDK**.
*   **Auditoría de Pagos Olvidados:** Detectar de forma automática si existen meses sin pagar de servicios recurrentes (ej. Servicoop) o boletas sindicales (SEC, FAECYS) cruzando las deudas registradas contra los movimientos de cuenta bancarios reales.
*   **Estado de Tarjetas:** Conciliar los cierres y liquidaciones de tarjetas (Patagonia 365, Naranja, Mastercard) para prever las fechas de débito y evitar entrar en financiación de tarjeta de crédito (puerta de entrada a intereses usurarios).

---

## 🛠️ 5. Próximos Pasos Técnicos
1.  **Mapear y consolidar los parsers de bancos:** (Patagonia PDF, Naranja PDF, etc.) asegurando que apliquen las reglas de idempotencia.
2.  **Ingesta de Extractos Recientes:** Depositar los crudos de los últimos meses en el inbox correspondiente y correr la ingesta global.
3.  **Consultas de Control:** Ejecutar las primeras consultas de control de servicios/sindicatos pendientes.
