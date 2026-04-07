# 🧬 NEURONA: MÓDULO PAGOS (Vencimientos) 💳🧠
# Versión 5.0.0 - Control de Servicios e Impuestos

Este módulo gestiona la vida útil de un pago: desde la digitalización del vencimiento hasta la vinculación del comprobante final, manteniendo una bóveda independiente y jerarquizada.

---

## 🏛️ Patrón Repositorio (Regla Inquebrantable)
> [!CAUTION]
> **Prohibición de SQL Directo**: Ningún archivo de este módulo (parsers o lógica) puede importar `sqlite3`.
> Toda la persistencia debe pasar por `storage_pagos.py` para garantizar la integridad de las rutas relativas.

---

## 🛰️ Ecosistema de Pagos (v5.0)

### 1. Digitalización de Vencimientos
- Se registran en la tabla `pagos` con estado `PENDIENTE`.
- Se asocia una `categoria` (Servicios, Impuestos, Sindicales) según la lista en `pagos_recurrentes.md`.

### 2. Archivador de Pagos (Bóveda Independiente)
Al vincular una boleta o comprobante a un registro:
- **Normalización**: Las rutas se guardan con diagonales frontales (`/`).
- **Relativización**: No se guardan prefijos de disco (`C:\`). El visor usa el "Steel Link" para resolver la ruta dinámicamente.
- **Jerarquía**: `modulo_pagos/archivos_pagos/[CATEGORIA]/[AÑO]/[MES]/[CONCEPTO].pdf`.

### 3. Estados del Dato
- **PENDIENTE**: Boleta cargada pero no pagada o sin comprobante asociado.
- **PAGADO**: Comprobante de pago vinculado y cerrado.

---

## 🧱 Tablas Clave
- `pagos`: Tabla maestra de vencimientos. 
- **UNIQUE**: Se recomienda evitar duplicados mediante `INSERT OR IGNORE` basado en `concepto + fecha_vencimiento`.

---
*Documentación inicial para Módulo Pagos v5.0.0 - 07/04/2026*
