# 🎨 Visión del Frontend & UI (Premium Design) 🚀💎
**Versión 6.0.0 — Optimizado y Consolidado**

Este documento define la dirección de diseño y los componentes interactivos de la interfaz del ERP. Apuntamos a una experiencia premium, minimalista y ultra-reactiva.

---

## 🏛️ Componentes y Estructura
1.  **[index.html](index.html) (El "Launchpad")**: Panel de control general de la aplicación. Organiza los módulos en tarjetas adaptables (Cards).
2.  **[style.css](style.css)**: Sistema de diseño. Contiene variables CSS (`--accent-color`, `--success`, etc.) y clases de utilidad transversales.
3.  **[table_sort.js](table_sort.js)**: Script ligero en vanilla Javascript que añade capacidades de ordenamiento interactivo (numérico, alfabético y de fechas) a las cabeceras `<th>` de las tablas vía delegación de eventos.
4.  **Plantillas Jinja2**: Fragmentos dinámicos devueltos por la API para inyecciones específicas vía HTMX (ej: `tabla_pagos.html`, `gastos_list.html`).

---

## 🎨 Principios de Diseño Estético

### 🎴 Glassmorphism & Glow
Las tarjetas y paneles del sistema emplean fondos semi-translúcidos y bordes finos con colores difusos que transmiten profundidad:
```css
.glass {
    background: rgba(255, 255, 255, 0.75);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(0, 0, 0, 0.05);
}
```
Los títulos usan text-shadows sutiles para emular brillos LED (`glow-text`).

### ⚡ Interactividad Reactiva (HTMX & Micro-animaciones)
-   **Sin recarga completa de página:** El paso de datos, los envíos de formularios y los borrados se resuelven reemplazando fragmentos específicos del DOM (`hx-target`, `hx-swap`).
-   **Indicadores visuales ("Spinners"):** Toda operación asíncrona de procesamiento (sincronizar, procesar boletas) muestra una animación fluida (`.sync-spinner`) para notificar el progreso al usuario.
-   **Efectos Hover:** Las tarjetas y filas reaccionan de manera suave ante el puntero del ratón, mejorando la sensación de interactividad.

---

## ⚖️ Filosofía UX: Minimalismo Joaquín (Reglas de Oro)
-   **Cero datos inútiles:** Diseñado para uso personal y familiar. Se suprimen formularios corporativos burocráticos y campos innecesarios.
-   **Semáforo de Pagos:** El módulo de vencimientos se asiste de colores atómicos intuitivos (Rojo = Vencido | Amarillo = Vence Hoy | Naranja = 2do Vencimiento | Verde = Pagado).
-   **No-Wrap y Compactación:** Para evitar que la información se corte o desborde, los importes, fechas e identificadores numéricos se configuran con `white-space: nowrap` y se suprimen ceros innecesarios a la izquierda.
