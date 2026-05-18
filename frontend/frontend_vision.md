# 🎨 Visión del Frontend - ERP NICOLETTI 🚀💎

Este documento define la dirección estética y funcional de la interfaz de usuario (UI) para el ERP. Buscamos una experiencia **premium**, **oscura** y **altamente interactiva**.

---

## 🏛️ Concepto Core: "The Launchpad" (Lanzadera)

La pantalla inicial (`index.html`) debe dejar de ser un módulo específico (como Compras) para convertirse en un **Dashboard Maestro**. 

### 🎴 Diseño de Módulos (Cards)
Cada módulo del sistema se representará mediante una tarjeta (Card) con las siguientes características:
- **Glassmorphism**: Fondo translúcido con desenfoque (`backdrop-filter: blur`).
- **Glow-text**: Títulos que resaltan con sombras de neón sutiles.
- **Acciones Rápidas**: Cada card mostrará mini-estadísticas (ej: "3 vencimientos hoy") y un botón principal de acceso.
- **Micro-animaciones**: Hover effects que den sensación de profundidad y respuesta.

---

## 💰 Módulo: Pagos y Vencimientos

El objetivo es tener un control absoluto sobre el flujo de caja y las obligaciones sindicales/servicios.

### 🎯 Objetivos de la Pantalla de Pagos:
1.  **Semáforo de Prioridad**: 
    - 🔴 **Rojo**: Vencido.
    - 🟡 **Amarillo**: Vence hoy o mañana (1er vencimiento).
    - 🟠 **Naranja**: Segundo vencimiento aproximándose.
    - 🟢 **Verde**: Pagado (Comprobante vinculado).
2.  **Soporte Dual (v5.4)**: Visualización clara de `Monto 1 / Vto 1` y `Monto 2 / Vto 2`. Si el primer vencimiento pasó, resaltar automáticamente el segundo.
3.  **Vinculación Rápida**: Arrastrar un comprobante de pago sobre una fila para marcarla como **PAGADO** y archivar el archivo automáticamente.
4.  **Buscador Inteligente**: Filtrado instantáneo por concepto (SEC, FAECYS) o categoría (SINDICALES, SERVICIOS).

---

## 🛠️ Tecnologías y Estética
- **Framework**: HTMX + Jinja2 (Cero JavaScript pesado, lógica centralizada en FastAPI).
- **Estilos**: CSS Custom Properties (Vanilla CSS).
- **Iconografía**: Emojis potentes y modernos para feedback visual rápido.
- **Layout**: CSS Grid para el Dashboard maestro y Flexbox para componentes internos.
- **Tipografía**: 'Inter' (Google Fonts) para máxima legibilidad.

---

## 🗺️ Mapa de Navegación
- `/` -> **Dashboard / Launchpad**
- `/compras.html` -> Gestión de Facturas y Proveedores
- `/pagos.html` -> Vencimientos, Boletas y Comprobantes
- `/tarjetas.html` -> Resúmenes y Liquidaciones (Próximamente)
- `/bancos.html` -> Extractos y Sueldos (Próximamente)
