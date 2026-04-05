# 🧬 NEURONA: MÓDULO TARJETAS (Recaudación) 💳🧠
# Versión 4.0 - Diseño Híbrido y Persistencia Blindada

Esta neurona es responsable de la **ingesta, normalización y auditoría** de transacciones con tarjeta.

---

## 🏛️ Patrón Repositorio (Regla Inquebrantable)
> [!CAUTION]
> **Prohibición de SQL Directo**: Está terminantemente prohibido importar `sqlite3` o ejecutar SQL en cualquier archivo de lógica o parsing.
> Toda la persistencia debe delegarse exclusivamente a `storage_tarjetas.py`.

### Ejemplo de Uso del Repositorio:
```python
from . import storage_tarjetas as storage

# Guardar una liquidación con metadata híbrida
liq_id = storage.save_liquidacion({
    "fuente": "PAYWAY",
    "total_bruto": 1500.50,
    "meta_json": meta_json_dict  # Diseño Híbrido
})
```

---

## 🛰️ Flujo de Datos 4.0
1.  **Ingesta (Regla Inbox)**: Los archivos PDF/Excel se reciben estrictamente en `/modulo_tarjetas/inbox_tarjetas/`.
2.  **Parsing Híbrido**: El parser extrae las "Columnas Duras" (monto, fecha) y empaqueta el resto en un JSON para la columna `meta_json`.
3.  **Firma Estándar**: El parser retorna `(True, info_dict)` al orquestador para gatillar el archivado legal.
4.  **Archivado Legal**: El destino final responde a la jerarquía obligatoria `/static/archivadas/tarjetas/[Nombre_Entidad_o_Marca]/[Año]/[Mes]/`.
5.  **Auditoría 360**: Cruce de `payway_records` (POS) vs `liquidaciones_tarjetas` (Banco).

---

## 🧱 Estructura de Datos
- `payway_records`: Cupones individuales. **Clave Unique**: `(fecha_compra, cupon, lote, marca, monto_bruto)`.
- `liquidaciones_tarjetas`: Resumen bancario. Indexado en **FTS5** vía `meta_json`.

---

## 🛠️ Comandos y Herramientas
- `resumen [anio]`: Visión gerencial de ingresos por marca.
- `audit`: El detective que busca dinero no depositado.
- `procesar_archivo(path)`: Punto de entrada para el orquestador global.
