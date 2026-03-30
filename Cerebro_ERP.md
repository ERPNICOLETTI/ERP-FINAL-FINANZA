# 🧠 Cerebro ERP - Manual de Arquitectura y Operación "Ladrillo por Ladrillo"

Este documento contiene la lógica maestra, el flujo de trabajo y las instrucciones técnicas del **Cerebro ERP**. Está diseñado para que cualquier IA o desarrollador entienda cómo opera el sistema desde cero.

---

## 🏛️ 1. Filosofía de Diseño: Modularidad Total
El sistema se rige por la separación absoluta de responsabilidades. Nada está "pegado", todo se enchufa.

### Arquitectura de 3 Capas:
1.  **Capa 0: El Motor (Core)** - Ubicado en `/core/`. Aquí reside la inteligencia pura. `tarjetas.py` sabe calcular, `ingesta.py` sabe guardar. No saben de dónde vienen los datos, solo saben procesarlos.
2.  **Capa 1: El Servicio (API)** - `erp_api.py`. Expone la inteligencia al mundo. Nadie toca la base de datos directamente excepto la API (vía el Core). **Separación por Áreas**: La API organiza las rutas (`/tarjetas/`, `/facturas/`) para mantener los dominios de datos aislados.
3.  **Capa 2: La Interfaz (Cerebro CLI)** - `cerebro.py`. Es la consola de comandos. Su única tarea es recibir tus órdenes, hablar con la API y mostrarte los resultados de forma linda.

### 🧩 Procedimiento de Orden por Áreas (API y DB)
El sistema mantiene un orden jerárquico estricto. Toda nueva integración debe respetar su área designada en la API (`erp_api.py`), la Consola (`cerebro.py`) y la Base de Datos (`core/ingesta.py`):
- **ÁREA TARJETAS (`/tarjetas`)**: Maneja liquidaciones (Payway, Patagonia 365, Naranja). Usa las tablas `liquidaciones_tarjetas` (Cabecera) y `liquidaciones_detalles` (Bit a Bit).
- **ÁREA FACTURAS (`/facturas`)**: Maneja comprobantes fiscales (ARCA/CALIM). Usa las tablas `facturas` y `libroiva`.
- **ÁREA BANCOS (`/bancos`)**: Maneja extractos de cuenta corriente y caja de ahorro (Ej: Chubut). Usa la tabla `bancos_movimientos`. Implementa **Auto-Detección de Cuenta** basada en la lectura del archivo original.

**Consolidación Inteligente**: En la base de datos, las liquidaciones de diferentes orígenes conviven en la misma tabla maestra para permitir sumas globales, pero mantienen sus metadatos específicos en campos JSON. Cada fuente tiene su propio Parser dedicado en `/parsers/`.

---

## 🌲 2. Estructura de Carpetas
```text
/
├── cerebro.py          # Consola central (Comandos)
├── erp_api.py          # Servidor de Inteligencia (Puerto 5005)
├── erp_master.py       # Maestro de Esquema y Auditoría Global
├── erp_nicoletti.db    # La Base de Datos (Único Punto de Verdad)
├── core/               # INTELIGENCIA MODULAR
│   ├── ingesta.py      # "El Ladrillero" (Guarda en DB con INSERT OR IGNORE / REPLACE)
│   ├── tarjetas.py     # Motor de conciliación de plásticos
│   └── facturas.py     # Motor de análisis fiscal ARCA/AFIP
└── parsers/            # HERRAMIENTAS DE EXTRACCIÓN
    ├── parser_payway_liq.py    # Lector de CSV Prisma
    ├── parser_patagonia.py     # Lector de PDF Patagonia 365
    ├── parser_naranja_xlsx.py  # Lector de Excel Naranja
    └── parser_chubut.py        # Lector de Excel Banco Chubut (Cuentas)
```

---

## 🏗️ 3. El Flujo de Ingesta (Digitalización Bit a Bit)
Para que no se pierda ni un centavo, cada archivo (PDF, CSV, XLSX) se digitaliza con el máximo nivel de detalle:

**Reglas de Oro del Ladrillero (`core/ingesta.py`):**
*   **Normalización Robusta**: El motor limpia automáticamente caracteres basura (como letras pegadas a números) para asegurar que los montos sean siempre correctos.
*   **Des-duplicación Inteligente**: 
    * En Tarjetas usa `INSERT OR REPLACE` (sobreescribe la info en caso de correcciones).
    * En Bancos usa una clave `UNIQUE(banco, cuenta, fecha, descripcion, codigo_movimiento, importe)` para permitir que el banco cobre impuestos con el mismo ID, anulando solo duplicados exactos.
*   **Búsqueda Nuclear**: Al estar todo digitalizado en FTS5 (Búsqueda 360), puedes buscar un CUIT, un número de cupón o un impuesto bancario, y el sistema buscará a través de todas las áreas a la vez.

**Camino del dato**:
`Archivo Raw` -> `Parser` -> `Ladrillero` -> `DB`

---

## 🛠️ 4. Manual de Comandos (Cómo opero el sistema)

### 💳 Área: Tarjetas (Conciliación Financiera)
*   **Resumen Anual**: `python cerebro.py tarjetas resumen 2026`
*   **Importar Patagonia**: `python cerebro.py tarjetas importar PATAGONIA365 "RUTA_AL_PDF"`
*   **Importar Payway**: `python cerebro.py tarjetas importar PAYWAY "RUTA_AL_CSV"`
*   **Importar Naranja**: `python cerebro.py tarjetas importar NARANJA "RUTA_AL_XLSX"`

### 🏦 Área: Bancos (Movimientos de Cuenta)
*   **Importar Extracto Chubut**: `python cerebro.py bancos importar CHUBUT "RUTA_AL_XLSX"`
    *(Nota: El parser detecta automáticamente si es Caja de Ahorro o Cuenta Corriente).*

### 🧾 Área: Facturas y Búsquedas
*   **Búsqueda 360**: `python cerebro.py facturas buscar "TERMINO"`

---

## 🧠 5. Reglas de Negocio Contable (El Motor de Conciliación)
El mayor valor del Cerebro ERP es su capacidad de entender las distorsiones del sistema financiero argentino. Al codificar el futuro **Conciliador Tarjetas vs Bancos**, se deben respetar las siguientes reglas descubiertas en producción:

1.  **Depositos Fraccionados por Marca**: 
    Las procesadoras (ej. Payway) reportan un "Neto a Cobrar" diario. El banco rara vez recibe un único depósito con ese número. 
    *   *Mastercard*: Suele depositarse limpio o agrupado.
    *   *Visa*: Suele partirse en múltiples acreditaciones (Débito y Crédito) más un ajuste de Débito (comisiones). **El ERP debe sumar los lote de Acreditaciones de un día y restar los Débitos de la procesadora para que el monto haga "Match" con el Neto teórico expedido.**
2.  **Impuesto al Cheque Diferido (Ley 25413)**:
    Si la cuenta no tiene fondos al ingresar plata y luego retirarse todo (o por cortes de día), el banco cobra este impuesto de forma rezagada o acumulativa a fin de mes. **El ERP NO debe buscar el impuesto el mismo día de la venta.** Debe sumarizar el impuesto en el período mensual (ej: "Carga Fiscal Real Enero") y contrastar contra la masa de facturación.
3.  **Adelanto de Cupones (Cobro Anticipado)**:
    Cuando se enciende el cobro al instante, las fechas teóricas de pago a 14/18 días de los cupones de crédito quedan obsoletas. **El ERP usa la `fecha_compra` o `fecha_presentacion` (+ margen de 24/48hs hábiles) para cruzar contra el banco**, y asume que cualquier débito extra de la procesadora esconde el "Costo Financiero" por habilitar esta ventaja, catalogándolo automáticamente como pérdida financiera.

---

## 🧩 5. Instrucciones para la IA (Mantenimiento de 0)
Si eres una nueva IA tomando el control:
1.  **Mira el Esquema**: `erp_master.py` define la arquitectura de tablas.
2.  **Sigue la Normalización**: Usa siempre `normalizar_importe` de los parsers existentes. No intentes inventar reglas de limpieza de números nuevas.
3.  **Digitaliza TODO**: Al crear un nuevo parser, asegúrate de loopiar cada línea/celda del archivo y guardarla en `liquidaciones_detalles`.

---

> [!IMPORTANT]
> **ORDEN ABSOLUTO**: Nunca escribas código de base de datos fuera de `/core/`. Nunca escribas lógica de cálculo dentro de `cerebro.py`. La API (`erp_api.py`) es el único puente oficial entre la interfaz y los datos.
