# 🧠 Cerebro ERP - Tronco Cerebral (Índice Maestro) 🦾🏗️🧬

Este documento es el **punto de entrada definitivo** para entender la arquitectura y operación del ERP. Cualquier desarrollador o IA que trabaje en este proyecto **DEBE** seguir las reglas maestras aquí descritas.

---

## 🏛️ 1. Visión Global: Monolito Modular
El sistema está diseñado bajo una arquitectura de **Monolito Modular (Vertical Slicing)**. 
Cada dominio de negocio (Tarjetas, Compras, Bancos) es una unidad autónoma y autosuficiente. El sistema no es una maraña de cables, sino un conjunto de "cajas negras" bien definidas.

---

## ⚖️ 2. Reglas de Oro Arquitectónicas (Inquebrantables)

> [!IMPORTANT]
> **Aislamiento de Dominios**: Está terminantemente prohibido que un módulo acceda directamente a las tablas o archivos de persistencia de otro módulo. La comunicación entre dominios debe hacerse a través de interfaces de servicio (Funciones de Storage o API interna).

-   **Persistencia Local**: Cada módulo gestiona su propia base de datos lógica a través de su respectivo archivo `storage_*.py`. El dominio es el único dueño de su esquema SQL.
-   **Crudos Locales**: Cada módulo tiene su propia carpeta `crudos/`. Los archivos de origen (PDF, CSV, XLSX) deben depositarse en el módulo correspondiente. El Core solo orquesta la llamada, pero el módulo "manda" en sus archivos.
-   **Orquestación Central**: El `core_sistema` actúa como el "Hub". Su responsabilidad es coordinar la inicialización, la infraestructura y mantener el motor de búsqueda global **FTS5** (`search_index`). No debe contener lógica ni persistencia de negocio.

---

## 🧬 3. Mapa de Neuronas (Donde vive el conocimiento)

Para modificar o entender el comportamiento del sistema, consulta la **Neurona** correspondiente. **No modifiques código sin antes leer la documentación de su dominio.**

### 💳 Tarjetas (Recaudación)
Reglas de Payway, Naranja, liquidaciones, aranceles y cruce de cupones.
👉 **LEER OBLIGATORIAMENTE**: [modulo_tarjetas/NEURONA.md](file:///c:/Users/essao/OneDrive/Escritorio/ERP%20FINAL/modulo_tarjetas/NEURONA.md)

### 🏦 Bancos (Tesorería)
Reglas de conciliación bancaria, extractos de Chubut, Credicoop, Hipotecario y detección de cuentas.
👉 **LEER OBLIGATORIAMENTE**: [modulo_bancos/NEURONA.md](file:///c:/Users/essao/OneDrive/Escritorio/ERP%20FINAL/modulo_bancos/NEURONA.md)

### 🧾 Compras (Fiscal)
Reglas de ARCA/AFIP, plataforma CALIM, Libro IVA y digitalización de facturas.
👉 **LEER OBLIGATORIAMENTE**: [modulo_compras/NEURONA.md](file:///c:/Users/essao/OneDrive/Escritorio/ERP%20FINAL/modulo_compras/NEURONA.md)

### ⚙️ Core e Infraestructura
Para entender la orquestación del sistema, el motor de búsqueda 360 y el esquema global.
👉 **LEER OBLIGATORIAMENTE**: [DB_ARCHITECTURE.md](file:///c:/Users/essao/OneDrive/Escritorio/ERP%20FINAL/DB_ARCHITECTURE.md)
👉 **REVISAR**: `core_sistema/reset_database.py` (Script de reconstrucción total).

---

> [!CAUTION]
> **AVISO PARA IAs**: Si estás leyendo esto para realizar cambios, detente. Busca el archivo `NEURONA.md` del módulo que vas a modificar. Ignorar las reglas de aislamiento modular resultará en una degradación inaceptable de la arquitectura.
