# 🗄️ Arquitectura de Base de Datos - ERP FINAL

Este documento detalla la estructura lógica de `erp_nicoletti.db`. Cualquier modificación al esquema debe reflejarse aquí.

## 🏛️ Áreas de Datos Consolidadas

### 💳 1. Área Tarjetas (Cruce Financiero)
*   **`liquidaciones_tarjetas`**: Cabecera de liquidación (Payway, Patagonia 365, Naranja).
    *   *Campos clave*: `fuente`, `tipo`, `fecha_liquidacion`, `total_neto`.
*   **`liquidaciones_detalles`**: Detalle línea por línea (Bit a Bit) de cada liquidación vinculada por `liquidacion_id`.
    *   *Uso*: Permite auditoría granular de impuestos y aranceles.
*   **`payway_records`**: Registro de cupones individuales presentados (Ventas brutas del Posnet).
    *   *Uso*: Cruce diario contra el banco para detectar faltantes de acreditación.

### 🧾 2. Área Facturación (Fiscal ARCA/AFIP)
*   **`facturas`**: Tabla maestra de comprobantes (Ventas y Compras).
    *   *Campos clave*: `numero_completo`, `proveedor`, `monto_total`.
*   **`facturas_calim`**: Espejo de datos importados de la plataforma CALIM.
    *   *Uso*: Detección de discrepancias entre lo que tiene el contador y lo que dice el sistema.
*   **`libroiva`**: Resúmenes mensuales de declaraciones juradas (F.2051).

### 🏦 3. Área Bancos (Cuenta Corriente)
*   **`bancos_movimientos`**: Extractos bancarios digitalizados.
    *   *Lógica*: Clave UNIQUE por `(banco, cuenta, fecha, descripcion, codigo_movimiento, importe)` para evitar duplicados en cobranzas automatizadas.

### 🔍 4. Área Inteligencia (FTS5)
*   **`search_index`**: Tabla virtual de búsqueda rápida estilo Google. Unifica todas las áreas en un solo motor de búsqueda textual.

---

## 🛠️ Flujo de Integridad (Business Logic)
1.  **Detección de Duplicados**: Se usa `INSERT OR IGNORE` o `INSERT OR REPLACE` basado en la unicidad de los datos brutos.
2.  **Normalización**: Todos los montos se expresan en `REAL` (Float) tras limpiar caracteres basura en los parsers.
3.  **Persistencia Centralizada**: Nada escribe en la DB fuera de `core/ingesta.py`.
4.  **Desacoplamiento**: Los parsers solo extraen datos; el motor de ingesta decide si el dato es nuevo o repetido.
