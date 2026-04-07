# 🧬 NEURONA: MÓDULO PAGOS (Vencimientos Sindicales y Servicios) 💳🧠
# Versión 5.4.1 - Parser Inteligente Multi-Formato + Schema Dual-Vencimiento

Este módulo gestiona el ciclo de vida completo de un pago: desde la digitalización de la boleta hasta la vinculación del comprobante. Mantiene una bóveda física independiente y una tabla SQL con trazabilidad dual (2 montos + 2 vencimientos por registro).

---

## 🏛️ Patrón Repositorio (Regla Inquebrantable)
> [!CAUTION]
> **Prohibición de SQL Directo**: Ningún archivo de este módulo puede importar `sqlite3`.
> Toda la persistencia debe pasar por `storage_pagos.py`.

---

## 🛰️ Flujo Completo de Ingesta (v5.4)

```
boleta.pdf → inbox_pagos/
    ↓
erp_master.py detecta INBOX_PAGOS → llama logic_pagos.procesar_inbox_pagos(inbox_path)
    ↓
parser_pagos.procesar_pago(filepath) → extrae concepto, periodo, monto(s), vencimiento(s)
    ↓
archiver_service.archivar_documento(entidad=concepto, subcategoria=categoria)
    → modulo_pagos/archivos_pagos/[CATEGORIA]/[CONCEPTO]/[YYYY]/[MM]/Boleta_CONCEPTO_MM_YYYY.pdf
    ↓
storage_pagos.save_pago(data_sql) → tabla `pagos` en erp_nicoletti.db
    ↓
Inbox limpiado (archivo eliminado tras procesar)
```

> [!IMPORTANT]
> `erp_master.py` llama `procesar_inbox_pagos(inbox_path)` pasando el **path del inbox directamente**, no el workspace. La función NO debe volver a agregar `modulo_pagos/inbox_pagos`.

---

## 🧠 Parser Inteligente (`parser_pagos.py`)

### Regla Crítica: `es_comprobante` NUNCA desde el PDF
El texto de las boletas contiene la palabra "PAGO" (ej: "VOLANTE DE PAGO SINDICAL"), lo que causaría falsos positivos. La detección de comprobante se hace **exclusivamente por nombre de archivo** en `logic_pagos.py`.

### Formatos de Periodo por Sindicato
Cada sindicato usa un formato distinto para indicar el periodo:

| Concepto | Formato en PDF | Ejemplo | Regex |
|---|---|---|---|
| **FAECYS / INACAP** | `PERIODO: MM/YYYY` | `PERIODO: 01/2026` | `PER[IÍ]ODO[:\s]+(\d{2})/(\d{4})` |
| **POLICIA** | `PERIODO: YYYYMM` | `PERIODO: 202601` | `PER[IÍ]ODO[:\s]+(\d{4})(\d{2})\b` |
| **SEC** | `YYYY-MM` en ítems tabla | `2026-01 Sec.00 FONDO SOCIAL` | `\b(\d{4})-(\d{2})\s+SEC` |
| **Fallback** | Nombre de archivo | `_01-2026_` | `_(\d{2})-(\d{4})_` |

### Formatos de Montos y Vencimientos

| Concepto | Formato | Campos extraídos |
|---|---|---|
| **FAECYS** | `Fecha Primer Vto. : DD/MM/YYYY $ X.XXX,XX` | monto_1 + vto_1, monto_2 + vto_2 |
| **INACAP** | `VENCIMIENTO: DD/MM/YYYY` + `Monto Total: $ X.XXX,XX` | Vencimiento único |
| **POLICIA** | `VENCIMIENTO: DD/MM/YYYY` + `TOTAL A PAGAR $ X.XXX,XX` | Vencimiento único |
| **SEC** | `Fecha 1er Vto: DD/MM/YYYY` + pares fecha/importe en tabla | Doble vencimiento |

---

## 🏛️ Schema SQL (`pagos`) — v5.4

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Auto-incremental |
| `categoria` | TEXT | SINDICALES / SERVICIOS / IMPUESTOS |
| `concepto` | TEXT | SEC / FAECYS / INACAP / POLICIA / ... |
| `periodo_mes` | TEXT | MM (ej: "01") |
| `periodo_anio` | TEXT | YYYY (ej: "2026") |
| `monto` | REAL | Monto del 1er vencimiento |
| `fecha_vencimiento` | TEXT | ISO: YYYY-MM-DD — 1er vencimiento |
| `monto_2` | REAL | Monto del 2do vencimiento (0 si no aplica) |
| `fecha_vencimiento_2` | TEXT | ISO: YYYY-MM-DD — 2do vto (NULL si no aplica) |
| `estado` | TEXT | PENDIENTE / PAGADO |
| `path_boleta` | TEXT | Ruta **relativa** con `/` — se llena al ingestar la boleta |
| `path_comprobante` | TEXT | Ruta **relativa** con `/` — se llena al vincular el comprobante |
| `hash_boleta` | TEXT | SHA256 para idempotencia |
| `meta_json` | TEXT | JSON con `full_text` del PDF y montos extraídos intermedios |

> [!IMPORTANT]
> Las rutas en `path_boleta` y `path_comprobante` son **RELATIVAS** al workspace (sin prefijo de disco `C:\`). Formato: `modulo_pagos/archivos_pagos/SINDICALES/SEC/2026/01/Boleta_SEC_01_2026.pdf`

### Estados del Dato

- **PENDIENTE**: Boleta cargada, sin comprobante de pago vinculado.
- **PAGADO**: Comprobante vinculado (`path_comprobante` poblado).

El estado se determina automáticamente en `storage_pagos.save_pago()`:
```python
estado = 'PAGADO' if path_comprobante else 'PENDIENTE'
```

---

## 📁 Jerarquía de Archivos (Bóveda)

```
modulo_pagos/
├── inbox_pagos/          ← Drop aquí. Se limpia tras procesar.
├── archivos_pagos/       ← Bóveda permanente
│   └── [CATEGORIA]/      ← SINDICALES / SERVICIOS / IMPUESTOS
│       └── [CONCEPTO]/   ← SEC / FAECYS / INACAP / POLICIA
│           └── [YYYY]/
│               └── [MM]/
│                   ├── Boleta_[CONCEPTO]_[MM]_[YYYY].pdf
│                   └── Comprobante_[CONCEPTO]_[MM]_[YYYY].pdf
├── logic_pagos.py        ← Orquestador de ingesta
├── parser_pagos.py       ← Motor de extracción PDF (Inteligencia)
└── storage_pagos.py      ← Única puerta a la DB (Patrón Repositorio)
```

> [!TIP]
> Si aparece un nuevo tipo de boleta (ej: Servicoop, AFIP, IIBB), agregar en `parser_pagos.py`:
> 1. Identificación del concepto en la sección "IDENTIFICAR CONCEPTO"
> 2. Regex específico de periodo en sección "EXTRAER PERIODO"
> 3. Regex de montos/vencimientos en sección correspondiente al formato
> 4. Documentar el formato en `pagos_recurrentes.md` y en esta neurona.
