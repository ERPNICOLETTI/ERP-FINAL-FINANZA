# 🧠 Cerebro ERP - Manual de Arquitectura y Operación "Ladrillo por Ladrillo"

Este documento contiene la lógica maestra, el flujo de trabajo y las instrucciones técnicas del **Cerebro ERP**. Está diseñado para que cualquier IA o desarrollador entienda cómo opera el sistema desde cero.

---

## 🏛️ 1. Filosofía de Diseño: Modularidad Total
El sistema se rige por la separación absoluta de responsabilidades. Nada está "pegado", todo se enchufa.

### Arquitectura de 3 Capas:
1.  **Capa 0: El Motor (Core)** - Ubicado en `/core/`. Aquí reside la inteligencia pura. `tarjetas.py` sabe calcular, `ingesta.py` sabe guardar. No saben de dónde vienen los datos, solo saben procesarlos.
2.  **Capa 1: El Servicio (API)** - `erp_api.py`. Expone la inteligencia al mundo (o a la red local). Nadie toca la base de datos directamente excepto la API (vía el Core).
3.  **Capa 2: La Interfaz (Cerebro CLI)** - `cerebro.py`. Es la consola de comandos. Su única tarea es recibir tus órdenes, hablar con la API y mostrarte los resultados de forma linda.

---

## 🌲 2. Estructura de Carpetas
```text
/
├── cerebro.py          # Consola central (Comandos)
├── erp_api.py          # Servidor de Inteligencia (Puerto 5005)
├── erp_master.py       # Maestro de Esquema y Auditoría Global
├── erp_nicoletti.db    # La Base de Datos (Único Punto de Verdad)
├── core/               # INTELIGENCIA MODULAR
│   ├── ingesta.py      # "El Ladrillero" (Guarda en DB de forma limpia)
│   ├── tarjetas.py     # Motor de conciliación de plásticos
│   └── facturas.py     # Motor de análisis fiscal ARCA/AFIP
└── parsers/            # HERRAMIENTAS DE EXTRACCIÓN
    ├── parser_payway_liq.py    # Lector de CSV Prisma
    └── parser_patagonia.py    # Lector de PDF Patagonia 365
```

---

## 🏗️ 3. El Flujo de Ingesta (Cómo entra un dato)
Para mantener el orden, cada vez que entra un archivo nuevo (PDF de Patagonia, CSV de Payway, etc.), sigue este camino:

1.  **EXTRACCIÓN**: El **Parser** correspondiente abre el archivo y extrae los datos crudos, convirtiéndolos en un diccionario de Python estándar.
2.  **NORMALIZACIÓN**: El Parser le pasa ese diccionario a `core/ingesta.py` (El Ladrillero).
3.  **PERSISTENCIA**: El Ladrillero limpia los formatos (puntos, comas, fechas) y ejecuta un `INSERT OR IGNORE`. Si el dato ya existía, no hace nada. Si es nuevo, coloca el "ladrillo".

---

## 🛠️ 4. Manual de Comandos (Cómo opero el sistema)

### 🎫 Área: Tarjetas (Conciliación Financiera)
*   **Ver resumen del año**: `python cerebro.py tarjetas resumen 2026`
    *   *Qué hace*: Te muestra una tabla consolidada de Payway, Patagonia y Naranja con Bruto, Neto y Gastos.
*   **Importar datos nuevos**: `python cerebro.py tarjetas importar <FUENTE> <RUTA_ARCHIVO>`
    *   *Fuentes Soportadas*: `PAYWAY`, `PATAGONIA365`.
*   **Auditoría de Fugas**: `python cerebro.py tarjetas audit`
    *   *Qué hace*: Cruza ticket por ticket contra los depósitos diarios para ver si Payway te debe plata.

### 🧾 Área: Facturas (Auditoría Fiscal)
*   **Buscar cualquier cosa**: `python cerebro.py facturas buscar "Nombre Proveedor"`
*   **Resumen de IVA**: `python cerebro.py facturas resumen 2026`
*   **Alertas Rojas**: `python cerebro.py facturas discrepancias`
    *   *Qué hace*: Te avisa qué facturas de la AFIP no se subieron al sistema contable (CALIM).

---

## 🧩 5. Cómo expandir el sistema (Instrucciones para el futuro)
Si querés agregar una nueva fuente (Ejemplo: **Naranja**):

1.  **Crear el Lector**: Crear `parsers/parser_naranja.py`. Su única misión es devolver un diccionario con los campos: `total_bruto`, `total_neto`, `fecha`, etc.
2.  **Llamar al Ladrillero**: Al final del parser, importar `core.ingesta` y llamar a `persistir_liquidacion(data)`.
3.  **Actualizar API**: Agregar la opción "NARANJA" en el endpoint `/tarjetas/importar` de `erp_api.py`.
4.  **Actualizar Cerebro**: ¡Nada! Cerebro ya está preparado para mostrar cualquier fuente que aparezca en la tabla unificada.

---

> [!IMPORTANT]
> **ORDEN ABSOLUTO**: Nunca escribas código de base de datos fuera de `/core/`. Nunca escribas lógica de cálculo dentro de `cerebro.py`. Mantener las capas separadas es lo que hace que el sistema sea eterno.
