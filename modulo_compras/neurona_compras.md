# 🧬 NEURONA: MÓDULO COMPRAS (Facturación) 🧾🧠
# Versión 5.0.0 - Ecosistema Estable: Match CAE, Sala de Espera y Bóveda Blindada

Este documento es el manual de operaciones definitivo para el **Ecosistema de Compras**. Diseñado para ser portátil, rápido y a prueba de errores de codificación.

---

## 🏛️ Patrón Repositorio (Regla Inquebrantable)
> [!CAUTION]
> **Prohibición de SQL Directo**: Ningún archivo de este módulo (parsers o lógica) puede importar `sqlite3`.
> Toda la persistencia debe pasar por `storage_compras.py` para garantizar la integridad de los metadatos JSON.

---

## 🛰️ Ecosistema de Ingesta Unificado (v5.0)

### 1. Match Atómico Inteligente (Búsqueda 360) 🔍
- **Input Único**: El formulario usa un solo buscador inteligente.
- **Detección CAE**: Si se ingresa el número de CAE, el sistema busca dentro del `meta_json` (AFIP/CALIM) y lo asocia instantáneamente al archivo.
- **Limpieza de Ceros**: El sistema ignora ceros a la izquierda y guiones para que el match sea siempre exitoso.

### 2. Flujo de Ingesta (El "Mazo de Cartas")
1. **Drop & HD Visor**: Se suelta el archivo en el panel. El visor permite Zoom dinámico y Paneo (arrastrar con mouse) para leer tickets pequeños.
2. **Match o Sala de Espera**:
   - **Match**: Si existe en la base, se vincula y archiva.
   - **Sala de Espera (Cuarentena CALIM)**: Si el ticket no es encontrado (no está en AFIP ni CALIM), se usa el botón **"Archivar como Pendiente CALIM"**. 
   - El archivo se mueve a la carpeta `00000000000 - PENDIENTES CALIM` y el registro queda marcado en **AMARILLO** con el texto **⏳ PENDIENTE**.

### 3. Archivador Nominal y Engrapadora Virtual 📎
Al confirmar, el Motor Orquestador (`archiver_service.py`):
- **Normalización de Slashes**: Todas las rutas se guardan con diagonales frontales (`/`) para evitar errores de escape en Windows.
- **Engrapadora PDF**: Si la factura ya tenía una foto, el sistema **las fusiona en un solo PDF multi-página** en tiempo real.
- **Bóveda Jerárquica**: `/modulo_compras/archivos_compras/Facturas/[CUIT] - [PROVEEDOR]/[YYYY]/[MM]/`.
- **Rutas a Prueba de Balas**: Se permiten puntos (`.`) en nombres de proveedores para evitar 404s en la visualización.

---

## 👁️ Visor de Bóveda (UX)
- **Cero Zeros**: La tabla muestra números de factura compactos (ej: `3-839` en vez de `00003-00000839`).
- **No-Wrap**: Las fechas y números nunca se cortan en dos líneas.
- **Link Inteligente**: El botón "VER" es capaz de recortar rutas absolutas de Windows para abrir el PDF sin importar dónde esté instalado el ERP.

---

## 🛠️ Herramientas de Mantenimiento
- `sync_dots.py`: (Uso interno) Sincroniza nombres de carpetas físicas con la base de datos.
- `sanar_db.py`: (Uso interno) Repara rutas corruptas por codificaciones viejas.
- `storage.smart_search_invoice(q)`: El corazón de la búsqueda elástica.

---
*Documentación actualizada para v5.0.0 - 05/04/2026*
