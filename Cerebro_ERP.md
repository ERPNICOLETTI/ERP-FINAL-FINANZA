# 🧠 Cerebro ERP - Tronco Cerebral (Índice Maestro) 🦾🏗️🧬
# Versión 4.0 - Ingesta Autónoma y Cumplimiento Legal

Este documento es el **punto de entrada definitivo** para entender la arquitectura y operación del ERP. Cualquier desarrollador o IA que trabaje en este proyecto **DEBE** seguir las reglas maestras aquí descritas.

---

## 🏛️ 1. Arquitectura: Monolito Modular (Vertical Slicing)
El sistema se organiza en dominios autónomos (Tarjetas, Compras, Bancos). Zero acoplamiento directo entre bases de datos de distintos módulos.

---

## ⚖️ 2. Reglas de Oro Arquitectónicas (Inquebrantables)

### 🛡️ Aislamiento de Dominios (Patrón Repositorio)
> [!IMPORTANT]
> **Prohibición de SQL Directo**: Ninguna "Neurona" de lógica puede importar `sqlite3`. Toda persistencia debe realizarse a través de las funciones del archivo `storage_*.py` de su propio módulo.

### 📥 Flujo "Soltar e Ingerir" (Inbox Universal)
El sistema ha migrado de carpetas "crudos" locales a un **Inbox Centralizado**:
1.  **Entrada**: El usuario deposita cualquier archivo (PDF, CSV, XLSX) en la carpeta `/inbox/`.
2.  **Orquestación**: `erp_master.py` escanea el inbox y despacha al parser correcto basándose en la firma del archivo.
3.  **Parsers Híbridos**: Los parsers extraen datos y devuelven un objeto estandarizado `(success, info)`.
4.  **Archivado Legal**: `core_sistema/archiver_service.py` mueve el archivo a su ubicación permanente en `static/archivadas/` con una jerarquía legal, aplicando micro-hashes para evitar colisiones.

---

## 🧬 3. Mapa de Neuronas (Donde vive el conocimiento)

Consulta el manual específico de cada dominio antes de realizar cambios:

### 💳 Tarjetas (Recaudación)
Reglas de Payway, Naranja, Patagonia, aranceles y cruce de cupones.
👉 **Manual**: [modulo_tarjetas/NEURONA.md](modulo_tarjetas/NEURONA.md)

### 🏦 Bancos (Tesorería)
Extractos de Chubut, Credicoop, Hipotecario (Pesos/USD) y conciliación.
👉 **Manual**: [modulo_bancos/NEURONA.md](modulo_bancos/NEURONA.md)

### 🧾 Compras (Fiscal)
ARCA/AFIP, plataforma CALIM, Libro IVA y digitalización híbrida.
👉 **Manual**: [modulo_compras/NEURONA.md](modulo_compras/NEURONA.md)

### ⚙️ Core e Infraestructura
Motor de búsqueda 360, Archivador Legal y esquema global.
👉 **Manual**: [DB_ARCHITECTURE.md](DB_ARCHITECTURE.md)

---

## ⚙️ 4. API de Parsers (Interface Estándar)
Todos los parsers deben implementar la función:
`procesar_archivo(filepath) -> (bool, dict)`

El diccionario de retorno `info` **debe** contener:
- `modulo`: 'TARJETAS' | 'COMPRAS' | 'BANCOS'
- `entidad`: Nombre del proveedor/banco (ej: 'PAYWAY').
- `anio` / `mes`: Para la jerarquía de archivado.
- `db_table`: Nombre de la tabla de destino.
- `id_insertado`: El ID generado para actualizar la ruta del archivo.
