# 🧬 NEURONA: MÓDULO BANCOS (Tesorería) 🏦🧠
# Versión 4.6 - Diseño Híbrido y Conciliación Multibanco

Esta neurona es la **"Cámara Acorazada"** del sistema, registrando cada extracto de Chubut, Credicoop e Hipotecario.

---

## 🏛️ Patrón Repositorio (Regla Inquebrantable)
> [!CAUTION]
> **Prohibición de SQL Directo**: Ningún parser bancario puede importar `sqlite3`. 
> El acceso a datos se realiza exclusivamente mediante `storage_bancos.py`.

### Ejemplo de Uso del Repositorio:
```python
from . import storage_bancos as storage

# Inyectar lote de movimientos con hash de archivo
agregados, last_id = storage.save_movimiento_banco(lista_movs, file_hash)

# Actualizar ruta tras archivado legal (Obligatorio)
storage.update_record_path(last_id, "/ruta/final/en/archivo/legal.xlsx")
```

---

## 🛰️ Flujo de Datos 4.6 (Ley de Localía)
1.  **Ingesta de 3 Capas (Visual -> Tránsito -> Archivo)**:
    - `inbox_bancos/`: Interfaz UI deposita el Excel aquí.
    - `crudos_bancos/`: La API lo mueve aquí automáticamente como sala de espera. Orquestador escanea *sólo* aquí.
2.  **Modularidad Híbrida**: Los parsers (`chubut`, `hipotecario`, `credicoop`) extraen columnas duras y guardan la fila original de Excel en el JSON de `meta_json`.
3.  **Detección de IVA**: Los parsers informan automáticamente al `modulo_compras` ante la detección de IVA bancario/mora.
4.  **Archivado Legal**: El archivo original se mueve usando la jerarquía obligatoria aislada: `/modulo_bancos/archivos_bancos/[Nombre_Entidad_Bancaria]/[Año]/[Mes]/` con trazabilidad por micro-hash.

---

## 🧱 Tablas Clave
- `bancos_movimientos`: Tabla unificada.
- **Idempotencia**: `UNIQUE(banco, cuenta, fecha, descripcion, tipo_movimiento, importe)` + `INSERT OR IGNORE`.

---

## 🛠️ Comandos de Neurona
- `get_sueldos [anio]`: Filtro inteligente para detectar pago de haberes.
- `procesar_archivo(path)`: Firma estándar para el orquestador global.
