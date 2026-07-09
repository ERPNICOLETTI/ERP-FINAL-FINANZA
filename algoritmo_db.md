# Plan de Implementación: Nuevo Paradigma de Ingesta Raw (ELT)
**Nombre del Algoritmo/Diseño: algoritmo_db**

Este documento detalla el rediseño del flujo de ingesta de datos del ERP, pasando de un modelo ETL directo (donde los archivos modifican la base de datos final de inmediato) a un modelo **ELT (Extract, Load, Transform)** utilizando una tabla unificada de Staging en la base de datos.

---

## 🏛️ Objetivos de Diseño
1. **Separación de Responsabilidades:** El cargador de archivos (`erp_master.py`) solo lee archivos del inbox, los convierte a texto estructurado (Markdown, JSON o CSV) y los guarda en la base de datos raw. La lógica de negocio y validación financiera se traslada por completo a procesos de transformación específicos de cada módulo.
2. **Preservación Inmutable:** El estado crudo de cada documento ingresado queda guardado permanentemente en la base de datos.
3. **Idempotencia y Trazabilidad:** Evitamos duplicación de archivos usando hashes SHA-256 e incluimos linaje de datos (`raw_ingesta_id`) en las tablas definitivas para auditoría rápida.
4. **Transaccionalidad Atómica (ACID):** Los procesos de transformación se ejecutan bajo transacciones SQL para asegurar la consistencia.

---

## 🗄️ 1. Cambios en la Base de Datos

### ⚡ Configuración de Concurrencia (SQLite WAL)
Para habilitar lecturas concurrentes concurrentes (por ejemplo, desde el dashboard del frontend/Streamlit) mientras se realizan escrituras de ingesta en disco, se exige forzar la inicialización de la conexión de SQLite en modo **Write-Ahead Logging (WAL)** y sincronía normal. En Python/SQLAlchemy se implementa mediante el siguiente hook:

```python
from sqlalchemy import event

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.close()
```

### Nueva Tabla: `core_staging_raw`
Esta tabla actuará como el Data Lakehouse / Staging unificado para todas las fuentes del ERP.

```sql
CREATE TABLE IF NOT EXISTS core_staging_raw (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_archivo  TEXT NOT NULL,
    hash_sha256     TEXT UNIQUE NOT NULL,      -- Para rechazo inmediato de duplicados
    modulo          TEXT NOT NULL,             -- 'compras', 'tarjetas', 'bancos', 'pagos'
    tipo_fuente     TEXT NOT NULL,             -- 'CREDICOOP', 'CHUBUT', 'PAYWAY', 'CALIM', etc.
    formato_raw     TEXT NOT NULL,             -- 'MD' (para PDFs), 'JSON' (para Excels), 'CSV' (para CSVs)
    parser_version  TEXT NOT NULL,             -- Versión del parser de ingesta
    contenido_raw   TEXT NOT NULL,             -- Documento completo serializado
    filas_leidas    INTEGER DEFAULT 0,         -- Cantidad de registros encontrados en el archivo
    fecha_ingesta   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_procesado TIMESTAMP,                 -- Cuándo se ejecutó la transformación exitosamente
    estado          TEXT DEFAULT 'PENDIENTE',  -- 'PENDIENTE', 'PROCESADO', 'ERROR'
    mensaje_error   TEXT
);

-- Índices para búsquedas y filtros ultra-rápidos
CREATE INDEX IF NOT EXISTS idx_staging_modulo_estado ON core_staging_raw(modulo, estado);
-- Nota técnica de SQLite: NO creamos un índice explícito sobre hash_sha256 ya que SQLite crea automáticamente
-- un índice implícito al estar definido como UNIQUE NOT NULL.
```

> [!NOTE]
> **Gestión de Fechas en SQLite:** Aunque definimos `TIMESTAMP` en el esquema, SQLite carece de un tipo de dato nativo para fechas y almacena timestamps como texto plano (ISO-8601 string `YYYY-MM-DD HH:MM:SS`). El código de Python/SQLAlchemy se encargará de mapear y serializar estos valores como objetos `datetime` de forma transparente.

### Modificación de Tablas Definitivas (Linaje de Datos, Unicidad Compuesta y Centavos)
Para evitar pérdidas de transacciones duplicadas legítimas al aplicar `INSERT OR IGNORE`, documentar la escala monetaria a nivel de base de datos y optimizar el borrado de reprocesamiento, se realizarán las siguientes modificaciones:

1.  **Columna `raw_ingesta_id` (INTEGER):** Se agrega a todas las tablas definitivas de producción (`bancos_movimientos`, `tarjetas_liquidaciones`, `tarjetas_payway`, `compras_facturas`) para auditoría y linaje.
2.  **Índices del Linaje (Optimización de Reprocesamiento):** Para evitar escaneos completos de tabla (`Full Table Scan`) al ejecutar el borrado selectivo durante el reprocesamiento, se crearán índices sobre la columna de linaje:
    ```sql
    CREATE INDEX IF NOT EXISTS idx_bancos_mov_raw_id ON bancos_movimientos(raw_ingesta_id);
    CREATE INDEX IF NOT EXISTS idx_tarjetas_liq_raw_id ON tarjetas_liquidaciones(raw_ingesta_id);
    CREATE INDEX IF NOT EXISTS idx_tarjetas_pw_raw_id ON tarjetas_payway(raw_ingesta_id);
    CREATE INDEX IF NOT EXISTS idx_compras_fact_raw_id ON compras_facturas(raw_ingesta_id);
    ```
3.  **Columna `numero_linea` (INTEGER):** Se agrega a todas las tablas definitivas para registrar la posición (1-indexed) del movimiento dentro del archivo de origen.
4.  **Renombrado a Centavos (`*_centavos`):** Para evitar insertar números flotantes por error en el futuro, las columnas monetarias de las tablas definitivas se renombran explícitamente a `importe_centavos`, `monto_ingreso_centavos`, `monto_egreso_centavos` o `total_centavos`.
5.  **Restricción de Unicidad Compuesta:** Se reemplazan o definen las restricciones de unicidad en las tablas de producción para incluir la línea:
    *   *Bancos y Tarjetas:* `UNIQUE(raw_ingesta_id, fecha, descripcion, importe_centavos, numero_linea)` o `UNIQUE(raw_ingesta_id, fecha, lote, cupon, numero_linea)`
    *   *Compras:* `UNIQUE(raw_ingesta_id, cuit_proveedor, tipo_comprobante, punto_venta, numero_comprobante, numero_linea)`
6.  **Columna `meta_json` (TEXT / JSON):** Se garantiza su existencia en las tablas definitivas para capturar metadatos complementarios y específicos del emisor (ej: CAE de AFIP, número de cuenta, medidor, etc.). 
    *   *Nota de Implementación:* En SQLAlchemy/SQLModel se definirá como `meta_json = Column(JSON, default=dict, nullable=False)`. Esto garantiza que la columna devuelva siempre un diccionario de Python vacío `{}` en lugar de un tipo `None` (NoneType), eliminando la necesidad de realizar validaciones defensivas en el código de lectura y permitiendo el uso seguro de `.get()`.

---

## 🛠️ 2. Convertidores de Formatos (Inbox ➡️ Raw)

Definiremos funciones utilitarias de conversión limpia en `core_sistema/conversores.py`:

1.  **PDF a Markdown (MD):**
    *   Usaremos `pdfplumber` (ya listado en `requirements.txt`) para extraer texto de forma ordenada.
    *   Para reportes con tablas (como Payway o resúmenes de tarjetas), formatearemos las filas detectadas en tablas de Markdown estándar (`| columna | columna |`).
2.  **Excel a JSON:**
    *   Usaremos `pandas` (`pd.read_excel`) para procesar las hojas de cálculo.
    *   Convertiremos los dataframes resultantes a JSON estructurado utilizando `df.to_json(orient='records')`.
3.  **CSV a Texto Plano:**
    *   Lectura simple del archivo como string de texto plano, conservando los saltos de línea y codificación UTF-8/ISO-8859-1 según corresponda.

---

## 🔄 3. Flujo de Trabajo en Detalle

### Fase 1: Ingesta Centralizada (`erp_master.py --ingest`)
```mermaid
graph TD
    Inbox[Archivo en Inbox] -->|Calcular SHA-256| Checksum{¿Existe en DB?}
    Checksum -->|Sí| Borrar[Eliminar de Inbox - Duplicado]
    Checksum -->|No| Convertir[Convertir a MD / JSON / CSV]
    Convertir -->|Insertar| Staging[Guardar en core_staging_raw como PENDIENTE]
    Staging -->|Mover Archivo| Historico[Archivar en crudos_[modulo]]
```

### Fase 2: Transformación Modular (`erp_master.py --transform` o por Módulo)
Cada storage modular (`storage_*.py`) tendrá una función del tipo `procesar_pendientes_raw()` estructurada así:
1.  Inicia transacción SQL (`BEGIN`).
2.  Consulta registros en `core_staging_raw` que correspondan a su módulo y estén con `estado = 'PENDIENTE'`.
3.  Para cada registro:
    *   Deserializa `contenido_raw` (según `formato_raw`).
    *   **Normalización de Importes (Firmas Financieras y Precisión Matemática):** La fase de transformación obligará a normalizar la columna de monto a una columna unificada `importe` (o `monto_total`), donde:
        *   **Tipo de Dato:** Para evitar errores de redondeo de punto flotante (`REAL`/`FLOAT`), los montos se almacenarán estrictamente como **Enteros en Centavos** (ej: `$1.500,50` se multiplicará por 100 y se guardará como `150050`).
        *   Los **egresos** (gastos, intereses pagados, comisiones) se guardarán estrictamente como **valores negativos**.
        *   Los **ingresos** (ventas, acreditaciones, intereses ganados) se guardarán estrictamente como **valores positivos**.
    *   Aplica lógica de negocio (asigna cuentas `LDK`, `JOA`, `JOR`, `COMUN`, detecta intereses, etc.).
    *   **Mitigación de Saltos de Auto-incremento en SQLite:** Para evitar que las inserciones fallidas por unicidad consuman el secuenciador automático de la clave primaria (`AUTOINCREMENT`), la lógica de Python realizará una verificación previa en memoria (o mediante consulta selectiva rápida) para filtrar registros duplicados *antes* de mandar el comando SQL a la base de datos, dejando el `ON CONFLICT DO NOTHING` como última línea de defensa técnica.
    *   Inserta en la tabla definitiva correspondiente guardando el ID del registro raw en `raw_ingesta_id` y el número de línea respectivo en `numero_linea` (1-indexed).
    *   Actualiza el estado del registro raw a `'PROCESADO'` y setea `fecha_procesado = CURRENT_TIMESTAMP`.
4.  **Consistencia de Transacciones:** Si todo es correcto, ejecuta `COMMIT`. Si ocurre un error, ejecuta `ROLLBACK` y marca el registro raw como `'ERROR'` con el detalle de la excepción en `mensaje_error`.

---

## ⚙️ 4. Diagnóstico, Reprocesamiento y Reset (Enterprise)

Para facilitar el desarrollo y el mantenimiento del ERP en producción, se implementarán herramientas CLI en el orquestador:

### A. Comando de Reprocesamiento Remoto
*   **Comando:** `erp_master.py --reprocess <id_raw>` o `--reprocess-all --modulo <nombre_modulo>`
*   **Funcionamiento:**
    1.  Inicia transacción.
    2.  Busca el registro en `core_staging_raw`.
    3.  **Elimina de forma selectiva** todos los registros en las tablas finales de producción cuyo campo `raw_ingesta_id` coincida con el ID de staging (limpieza limpia y sin residuos).
    4.  Vuelve a setear el registro de staging con `estado = 'PENDIENTE'`, `mensaje_error = NULL` y `fecha_procesado = NULL`.
    5.  Llama al transformador correspondiente para que vuelva a procesar la información.
    6.  Hace `COMMIT`.


---

## ⚖️ 5. Ventajas y Desventajas del Paradigma

### 🌟 Ventajas:
1.  **Auditoría y Linaje de Datos:** Trazabilidad de extremo a extremo. Podés reconstruir el camino desde cualquier transacción en tu libro diario hasta el byte original del archivo ingresado.
2.  **Reprocesamiento Rápido (Backfill):** Si detectás un error en cómo se asignó una categoría o se liquidó un interés, podés reprogramar el transformador y volver a correr la historia completa en segundos sin depender de archivos en disco.
3.  **Resiliencia Extrema:** Los cambios en las columnas de las tablas finales no rompen la ingesta. El dato crudo se guarda igual y el error se trata de forma controlada en la fase de transformación.
4.  **Separación de Código (I/O vs Lógica):** Desacopla la lectura física de archivos (propensa a bloqueos o codificaciones corruptas) de la matemática y categorización financiera.

### ⚠️ Desventajas / Mitigaciones:
1.  **Duplicación de Almacenamiento:** Los datos se guardan dos veces (crudo en JSON/MD y normalizado en SQL). 
    *   *Mitigación:* Para el tamaño actual de tu ERP (donde la base de datos entera pesa ~1MB), el costo en espacio de almacenamiento es despreciable (menos de unos pocos megabytes adicionales al año).
2.  **Procesamiento en Dos Fases:** El flujo requiere realizar dos escrituras en la base de datos en lugar de una.
    *   *Mitigación:* SQLite local es extremadamente rápido (menos de 1-2ms por query). Para tu volumen de transacciones, la diferencia de tiempo es imperceptible.
3.  **Políticas de Error (All-or-Nothing):** Si una sola fila del archivo raw está corrupta, se aborta la carga completa del archivo en producción.
    *   *Mitigación:* Esto es deseable en sistemas contables y ERPs, ya que evita que un extracto bancario quede subido "por la mitad" (lo que descuadraría el balance general).


---

## 🛠️ 6. Mitigaciones y Robustez (Diseño Avanzado)

Para resolver las desventajas identificadas (fragilidad de parseo, depuración compleja, crecimiento de DB y errores tardíos), se incorporan las siguientes especificaciones al diseño:

### A. Interfaz Unificada del Parser (List[Dict])
*   El módulo `core_sistema/conversores.py` ofrecerá funciones auxiliares para transformar las tablas Markdown (extraídas de PDFs) y los contenidos de texto plano (CSVs) a una estructura limpia de Python `List[Dict]` (idéntica a la salida de Excel).
*   **Beneficio:** Toda la lógica de transformación en producción consumirá exclusivamente listas de diccionarios, abstrayendo por completo el formato físico de origen y simplificando drásticamente el código de negocio.

### B. Firma Temprana (Pre-Validation y Desvío de Errores)
*   **Inspección de Archivos Vacíos:** Antes de intentar abrir o leer un archivo del `inbox`, el cargador verificará su tamaño físico en disco. Si el tamaño es igual a `0 bytes`, se considerará inmediatamente corrupto/inválido y se desviará de forma directa a la carpeta `/no_reconocidos/` sin intentar procesarlo ni iniciar lectores.
*   **Firma del Archivo:** Si el tamaño es válido, se ejecutará una comprobación ultra-liviana de la firma del archivo (ej. buscar palabras clave como "CUIT", "Banco Chubut", "Payway" o patrones numéricos).
*   **Gestión de Fallos:** Si el archivo no supera la validación de firma, el script no arrojará un error que detenga la ejecución. En su lugar, moverá el archivo físico de forma automática del `inbox` a la carpeta `/no_reconocidos/` dentro del módulo correspondiente, garantizando que el `inbox` quede limpio y no se generen bucles infinitos en el procesamiento.
*   **Beneficio:** Robustez en la ingesta continua y aislamiento inmediato de archivos inválidos o descargas a medias (0 bytes).

### C. Tabla de Auditoría Histórica (`core_staging_logs`)
*   Se creará una tabla de soporte para registrar los intentos de procesamiento de cada staging, utilizando una política `SET NULL` para preservar los metadatos si el archivo pesado se purga en el futuro:
    ```sql
    CREATE TABLE IF NOT EXISTS core_staging_logs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        staging_id      INTEGER DEFAULT NULL,     -- Permite SET NULL al purgar raw
        fecha_intento   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resultado       TEXT NOT NULL,            -- 'SUCCESS', 'FAILED'
        detalles        TEXT,                     -- Traceback completo del error (format_exc)
        FOREIGN KEY(staging_id) REFERENCES core_staging_raw(id) ON DELETE SET NULL
    );
    ```
*   **Captura de Excepciones:** Se exigirá el uso de `traceback.format_exc()` al capturar excepciones durante la fase de transformación, volcando el stacktrace completo (con el número de línea exacto del fallo en el script Python) en la columna `detalles`.
*   **Beneficio:** Permite diagnosticar e identificar bugs de parseo o expresiones regulares de forma inmediata desde cualquier visor sin necesidad de revisar la terminal del servidor.

### D. Purgado y Compactación (`--vacuum-staging`)
*   Se añadirá un comando CLI para archivar o eliminar registros raw que tengan estado `PROCESADO` y una antigüedad mayor a 12 meses, seguido de un comando `VACUUM` en SQLite.
*   **Beneficio:** Evita que el archivo `.db` crezca de manera descontrolada a lo largo de los años.

### E. Motor de Parseo Adaptativo y Metadata-Driven (Pragmatismo Operativo)
Para evitar caer en la trampa de programar un intérprete dinámico de JSON sumamente complejo desde cero y aprovechar el trabajo ya realizado, **no desecharemos los lectores específicos de cada banco y tarjeta (`lector_*.py`)** del ERP. En su lugar:

1.  **Adaptación de Lectores Existentes:** Se modificarán los lectores específicos actuales para que extraigan el texto desde el `contenido_raw` de la base de datos (Staging) en lugar del archivo físico en disco.
2.  **Configuraciones Locales de Parseo:** Los parámetros del parser se centralizarán en diccionarios de Python (o plantillas JSON si son dinámicos) que definirán las siguientes variables:
    *   **El "Ancla de Fin de Registro" (Filtro Anti-Basura):**
        *   *Mecanismo:* Definición de la propiedad `anclas_finalizacion: List[str]` en la plantilla. 
        *   *Lógica:* Cuando el bucle de procesamiento de líneas detecta una línea con términos como `"TOTAL DE DEBITOS"`, `"SALDO ACTUAL"`, etc., **frena la lectura del archivo de inmediato**, descartando el resto del pie de página y legales institucionales.
    *   **Sanitización Previa de Saltos de Página (Cortes de Hojas):**
        *   *Mecanismo:* Definición de la propiedad `encabezados_a_ignorar: List[str]`.
        *   *Lógica:* Antes del parseo, se filtran las líneas que correspondan exactamente a los logos o cabeceras repetitivas del PDF. Al hacerlo, **se deben conservar estrictamente los caracteres de salto de línea (`\n`)** (es decir, reemplazar la línea ignorada por un string vacío manteniendo el salto de línea, o realizar la depuración directamente mientras se itera línea por línea). Esto evita que el final del texto de la página 1 se fusione de forma deformada con el principio de la página 2.
    *   **Tolerancia Cero al "Falso Cero" en Importes:**
        *   *Mecanismo:* Ignorar transacciones con valor numérico nulo o nulo implícito.
        *   *Lógica:* Los guiones `"-"`, espacios en blanco o valores que matemáticamente resulten en exactamente `0.00` tras el formateo se descartan. Si una línea no contiene un importe real tanto para ingreso como para egreso, se ignora en la importación.

#### Ejemplo de Configuración de Plantilla Utilizada por el Lector:
```json
{
  "fuente_nombre": "CREDICOOP_CC",
  "config_json": {
    "patron_inicio_fila": "^\\d{2}/\\d{2}/\\d{4}", 
    "separador_columnas": "|",
    "indice_fecha": 0,          -- 0-indexed (primera columna)
    "indice_descripcion": 1,    -- 0-indexed (segunda columna)
    "indice_monto": 2,          -- 0-indexed (tercera columna)
    "encabezados_a_ignorar": [
      "Fecha | Detalle de Movimiento | Importe",
      "BANCO CREDICOOP COOPERATIVO LIMITADO"
    ],
    "anclas_finalizacion": [
      "SALDO ACTUAL",
      "TOTAL DE DEBITOS"
    ],
    "reemplazos_moneda": [
      {"original": ".", "reemplazo": ""},
      {"original": ",", "reemplazo": "."}
    ]
  }
}
```

---

## 🧪 7. Plan de Verificación y Mitigación

### Pruebas de Ingesta (Dry-Run)
*   **Paso 1:** Desarrollar scripts de prueba que tomen archivos de muestra reales y los conviertan a Markdown y JSON, validando que el texto resultante mantenga coherencia.
*   **Paso 2:** Simular la ingesta de un archivo duplicado para verificar que el hash SHA-256 impida la inserción doble.
*   **Paso 3:** Provocar un fallo intencional en la lógica de transformación en producción para verificar que la transacción haga `ROLLBACK` de manera segura y no queden datos corruptos a mitad de camino.
*   **Paso 4:** Correr un ciclo completo de ingesta, transformación, error intencional, y posterior ejecución de `--reprocess` para validar el linaje y restauración de datos.


