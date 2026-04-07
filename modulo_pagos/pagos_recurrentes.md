# 📅 Pagos Recurrentes y Taxonomía de Gastos 💳🧾

Este documento centraliza los conceptos de pagos recurrentes para el **Módulo de Pagos**. Sirve como guía de referencia para la categorización en el sistema.

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
- **Autónomo**: Aportes previsionales.
- **IVA**: Impuesto al Valor Agregado.

### 🤝 Sindicales (SINDICALES)
- **SEC**: Sindicato de Empleados de Comercio.
- **Faecys**: Federación Argentina de Empleados de Comercio y Servicios.
- **Policia**: Servicios de seguridad/adicionales.
- **Inacap**: Instituto de Capacitación Profesional y Tecnológica para el Comercio.

---

## 🏛️ Regla de Archivado
Al digitalizar cualquiera de estos pagos, el sistema los rutea automáticamente siguiendo la jerarquía:
`modulo_pagos/archivos_pagos/[CATEGORIA]/[AÑO]/[MES]/`

> [!TIP]
> **Consistencia de Nombres**: Al crear un nuevo vencimiento manual, intenta usar los nombres exactos listados arriba para mantener la limpieza en el buscador 360 del ERP.
