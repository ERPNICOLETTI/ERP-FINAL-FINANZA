# 🧠 Cerebro ERP - Manual de Arquitectura y Operación "Ladrillo por Ladrillo"

Este documento contiene la lógica maestra, el flujo de trabajo y las instrucciones técnicas del **Cerebro ERP**. Está diseñado para que cualquier IA o desarrollador entienda cómo opera el sistema desde cero.

---

## 🏛️ 1. Filosofía de Diseño: Modularidad Total
El sistema se rige por la separación absoluta de responsabilidades. Nada está "pegado", todo se enchufa.

### Arquitectura de 3 Capas:
1.  **Capa 0: El Motor (Core)** - Ubicado en `/core/`. Aquí reside la inteligencia pura. `tarjetas.py` sabe calcular, `ingesta.py` sabe guardar. No saben de dónde vienen los datos, solo saben procesarlos.
2.  **Capa 1: El Servicio (API)** - `erp_api.py`. Expone la inteligencia al mundo. Nadie toca la base de datos directamente excepto la API (vía el Core). **Separación por Áreas**: La API organiza las rutas (`/tarjetas/`, `/facturas/`) para mantener los dominios de datos aislados.
3.  **Capa 2: La Interfaz (Cerebro CLI)** - `cerebro.py`. Es la consola de comandos. Su única tarea es recibir tus órdenes, hablar con la API y mostrarte los resultados de forma linda.

### 🧩 Flujo de Orden (Cómo se organiza la información)
El sistema mantiene un orden jerárquico estricto para evitar confusión entre fuentes:
- **Identidad de Fuente**: Todos los datos se etiquetan con su `fuente` original (`PAYWAY`, `PATAGONIA365`, `NARANJA`).
- **Consolidación Inteligente**: En la base de datos, las liquidaciones de diferentes orígenes conviven en la misma tabla maestra para permitir sumas globales, pero mantienen sus metadatos específicos en campos JSON.
- **Rutas Propias**: Cada fuente tiene su propio Parser dedicado en `/parsers/`, asegurando que un cambio en el formato de Patagonia no afecte a Payway.
- **Auditoría 360**: El motor de auditoría cruza las ventas (fuente POSNET) contra las liquidaciones (fuente BANCO/TARJETA) usando la `fecha_presentacion` como puente de unión.

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
    ├── parser_patagonia.py     # Lector de PDF Patagonia 365
    └── parser_naranja_xlsx.py  # Lector de Excel Naranja

---

## 🏗️ 3. El Flujo de Ingesta (Digitalización Bit a Bit)
Para que no se pierda ni un centavo, cada archivo (PDF, CSV, XLSX) se digitaliza en dos capas:

1.  **CAPA DE CABECERA (Header)**: Se guardan los totales generales en `liquidaciones_tarjetas`.
2.  **CAPA ATÓMICA (Detalle)**: Se guarda **cada línea** del archivo original en `liquidaciones_detalles`. 

**Reglas de Oro del Ladrillero (`core/ingesta.py`):**
*   **Normalización Robusta**: El motor limpia automáticamente caracteres basura (como letras pegadas a números) para asegurar que los montos sean siempre correctos.
*   **Update Inteligente (`INSERT OR REPLACE`)**: Si vuelves a importar el mismo archivo con correcciones, el sistema sobreescribe la información anterior para que siempre tengas el dato más puro disponible.
*   **Búsqueda Nuclear**: Al estar todo digitalizado, puedes buscar "Resoluciones", "Nros de Certificado" o "Ingresos Brutos" directamente con una consulta a la tabla de detalles.

**Camino del dato**:
`Archivo Raw` -> `Parser` (Limpia y extrae) -> `Ladrillero` (Persiste) -> `DB (Header + Detalles)`

---

## 🛠️ 4. Manual de Comandos (Cómo opero el sistema)

### 🎫 Área: Tarjetas (Conciliación Financiera)
*   **Resumen Anual**: `python cerebro.py tarjetas resumen 2026`
*   **Importar Patagonia**: `python cerebro.py tarjetas importar PATAGONIA365 "RUTA_AL_PDF"`
*   **Importar Payway**: `python cerebro.py tarjetas importar PAYWAY "RUTA_AL_CSV"`
*   **Importar Naranja**: `python cerebro.py tarjetas importar NARANJA "RUTA_AL_XLSX"`


### 🧾 Área: Facturas y Búsquedas
*   **Búsqueda 360**: El sistema indexa automáticamente cada bit de información. Puedes buscar por cualquier término y el ERP te dirá en qué factura, liquidación o detalle aparece.

---

## 🧩 5. Instrucciones para la IA (Mantenimiento de 0)
Si eres una nueva IA tomando el control:
1.  **Mira el Esquema**: `erp_master.py` define la arquitectura de tablas.
2.  **Sigue la Normalización**: Usa siempre `normalizar_importe` de los parsers existentes. No intentes inventar reglas de limpieza de números nuevas.
3.  **Digitaliza TODO**: Al crear un nuevo parser, asegúrate de loopiar cada línea/celda del archivo y guardarla en `liquidaciones_detalles`.

---

> [!IMPORTANT]
> **ORDEN ABSOLUTO**: Nunca escribas código de base de datos fuera de `/core/`. Nunca escribas lógica de cálculo dentro de `cerebro.py`. La API (`erp_api.py`) es el único puente oficial entre la interfaz y los datos.
