# 🧠 Cerebro ERP - Tronco Cerebral (Índice Maestro) 🦾🏗️🧬
# Versión 5.0.0 - Ecosistema Estable con Match CAE y Sala de Espera

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

### 📥 Ecosistema Unificado de Ingesta (v5.0.0)
El sistema utiliza una arquitectura de **Aislamiento Físico Total** con un flujo de "Limpieza Atómica de Origen" para evidencias:
1.  **Terminal de Ingesta HD**: Una única interfaz (Frontend) permite hacer Drop de PDFs/Imágenes y ofrece Zoom dinámico (Scroll/Pan) sin salir del módulo.
2.  **Match Atómico Omni-Direccional (CAE)**: El operario ingresa el número de factura o el **CAE** en un input único. El cerebro hace una búsqueda elástica en metadatos y asocia origen (AFIP/CALIM) en tiempo real.
3.  **Sala de Espera (Excepción)**: Si el comprobante no existe, se archiva en la carpeta unificada `PENDIENTES CALIM` para posterior conciliación.
4.  **Archivado Legal Nominal (`archivos_[modulo]/`)**: Tras vincular, el archivo temporal se "mueve" y desaparece (Limpieza de Origen). 
    - **Nomenclatura**: `YYYY-MM-DD_[Proveedor]_Factura_PV-NUM.pdf`.
    - **Normalización**: Rutas guardadas con `/` para máxima portabilidad y estabilidad en Windows (Anti-Corrupción).

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
