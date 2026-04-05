# 🧠 Cerebro ERP - Tronco Cerebral (Índice Maestro) 🦾🏗️🧬
# Versión 4.0 - Ingesta Autónoma y Cumplimiento Legal

Este documento es el **punto de entrada definitivo** para entender la arquitectura y operación del ERP. Cualquier desarrollador o IA que trabaje en este proyecto **DEBE** seguir las reglas maestras aquí descritas.

---

## 🏛️ 1. Arquitectura: Monolito Modular (Vertical Slicing)
El sistema se organiza en dominios autónomos (Tarjetas, Compras, Bancos). Zero acoplamiento directo entre bases de datos de distintos módulos.

---

## ⚖️ 2. Reglas de Oro Arquitectónicas (Inquebrantables)

### 🔄 Regla de Evolución Continua (Auto-Mantenimiento)
> [!IMPORTANT]
> **REGLA DE EVOLUCIÓN CONTINUA**: Siempre que surjan modificaciones críticas en el código, lógica, bases de datos o arquitectura que deban ser registradas, la IA DEBE modificar proactivamente los archivos instructivos `.md` (neuronas, cerebro, db_architecture) correspondientes para mantener el Zero-Shot Context actualizado para futuras sesiones.

### 🛡️ Aislamiento de Dominios (Patrón Repositorio)
> [!IMPORTANT]
> **Prohibición de SQL Directo**: Ninguna "Neurona" de lógica puede importar `sqlite3`. Toda persistencia debe realizarse a través de las funciones del archivo `storage_*.py` de su propio módulo.

### 📥 Flujo "Soltar e Ingerir" (Ley de Localía v4.6)
El sistema utiliza una arquitectura de **Aislamiento Físico Total** en tres estadios por módulo:
1.  **Entrada Visual (`inbox_[modulo]/`)**: Punto de entrada físico inicial desde la UI Frontend.
2.  **Depósito de Tránsito (`crudos_[modulo]/`)**: Sala de espera física donde la API almacena los documentos antes de ser ingeridos por el Orquestador.
3.  **Archivado Legal Permanente (`archivos_[modulo]/`)**: Bóveda final, recluida internamente en el módulo. Jerarquía obligatoria: `/modulo_[nombre]/archivos_[nombre]/[Entidad]/[Año]/[Mes]/`. **Queda extinto el uso de la carpeta genérica `/static/` para resguardo operativo**.

---

## 🧬 3. Mapa de Neuronas (Donde vive el conocimiento)

Consulta el manual específico de cada dominio antes de realizar cambios:

### 💳 Tarjetas (Recaudación)
Reglas de Payway, Naranja, Patagonia, aranceles y cruce de cupones.
👉 **Manual**: [modulo_tarjetas/neurona_tarjetas.md](modulo_tarjetas/neurona_tarjetas.md)

### 🏦 Bancos (Tesorería)
Extractos de Chubut, Credicoop, Hipotecario (Pesos/USD) y conciliación.
👉 **Manual**: [modulo_bancos/neurona_bancos.md](modulo_bancos/neurona_bancos.md)

### 🧾 Compras (Fiscal)
ARCA/AFIP, plataforma CALIM, Libro IVA y digitalización híbrida.
👉 **Manual**: [modulo_compras/neurona_compras.md](modulo_compras/neurona_compras.md)

### ⚙️ Core e Infraestructura
Motor de búsqueda 360, Archivador Legal y esquema global.
👉 **Manual**: [db_architecture.md](db_architecture.md)

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
