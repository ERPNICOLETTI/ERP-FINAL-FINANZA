# 📅 Pagos Recurrentes y Taxonomía de Gastos 💳🧾
# Versión 5.4.1 - Con formatos de periodo por sindicato documentados

Este documento centraliza los conceptos de pagos recurrentes para el **Módulo de Pagos**. Sirve como guía de referencia para la categorización en el sistema y como mapa de aprendizaje para el parser.

---

## 🏗️ Estructura de Categorías

### ⚡ Servicios (SERVICIOS)
- **Servicoop**: Cooperativa de servicios públicos.
- **Reduno**: Servicio de internet/conectividad.
- **Alquiler**: Locación de inmuebles.
- **Tiendanube**: Plataforma de E-commerce.
- **Contador**: Honorarios profesionales contables.
- **Seguro**: Pólizas de seguros generales.

### ⚖️ Impuestos (IMPUESTOS)
- **931**: Cargas sociales (AFIP).
- **Autonomo**: Aportes previsionales.
- **IVA**: Impuesto al Valor Agregado.
- **IIBB**: Ingresos Brutos.

### 🤝 Sindicales (SINDICALES)
- **SEC**: Sindicato de Empleados de Comercio Trelew.
- **FAECYS**: Federación Argentina de Empleados de Comercio y Servicios.
- **POLICIA**: Secretaría de Trabajo — Tasas Ley X N°15. *(también llamado "Policía del Trabajo")*
- **INACAP**: Instituto de Capacitación Profesional y Tecnológica para el Comercio.

---

## 📋 Formatos de Periodo por Sindicato (Crítico para el Parser)

Cada entidad usa un formato diferente para indicar el periodo dentro del PDF.
El parser `parser_pagos.py` maneja los 3 formatos en cascada:

| Sindicato | Formato en PDF | Ejemplo real |
|---|---|---|
| **FAECYS** | `PERIODO: MM/YYYY` | `CUIT: 27329549971 PERIODO: 01/2026` |
| **INACAP** | `PERIODO: MM/YYYY` | `PERÍODO: 01/2026 SECUENCIA: 0` |
| **POLICIA** | `PERIODO: YYYYMM` | `POLICÍA DEL TRABAJO - TRELEW - PERIODO: 202601` |
| **SEC** | `YYYY-MM` en línea de tabla | `2026-01 Sec.00 FONDO SOCIAL ART.100 C.C.T. 130/75` |
| **Fallback** | Nombre de archivo | `27329549971_01-2026_BOLETA_SINDICAL_...pdf` |

> [!IMPORTANT]
> El período del PDF refleja el **período de la obligación** (ej: Enero), no el mes en que se emitió la boleta (ej: Febrero). Siempre **usar el periodo del PDF**, no el del nombre del archivo, salvo como último fallback.

---

## 💰 Formatos de Montos por Sindicato

| Sindicato | ¿Doble vencimiento? | Patrón de monto |
|---|---|---|
| **SEC** | ✅ Sí | `Fecha 1er Vto: DD/MM/YYYY` + importe en tabla |
| **FAECYS** | ✅ Sí | `Fecha Primer Vto. : DD/MM/YYYY $ X.XXX,XX` |
| **INACAP** | ❌ No | `Monto Total: $ X.XXX,XX` |
| **POLICIA** | ❌ No | `TOTAL A PAGAR $ X.XXX,XX` |

---

## 🏛️ Regla de Archivado
Al digitalizar cualquiera de estos pagos, el sistema los rutea automáticamente:
```
modulo_pagos/archivos_pagos/[CATEGORIA]/[CONCEPTO]/[YYYY]/[MM]/
```
Ejemplo: `modulo_pagos/archivos_pagos/SINDICALES/SEC/2026/01/Boleta_SEC_01_2026.pdf`

> [!TIP]
> Al crear un nuevo concepto manual, usar los nombres exactos listados arriba para mantener la limpieza en el buscador 360 del ERP.
