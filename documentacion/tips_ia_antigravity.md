# 🧠 Guía de Supervivencia: Límites, Tips y Atajos de Antigravity (IA)

Este documento detalla cómo funciona la mente de tu asistente de IA (Antigravity/Gemini), cuáles son sus límites técnicos y cómo podés interactuar con ella para trabajar al 100% de eficiencia y evitar olvidos o errores en tu ERP.

---

## ⚡ 1. Los Límites Técnicos de la IA (Cómo Pienso)

### A. La Trampa de la Truncación (Memoria de Corto Plazo)
*   **Cómo funciona:** Cada vez que me escribís, el sistema me pasa el historial del chat actual. Si el chat se vuelve muy largo, el sistema lo "recorta" (lo trunca) por detrás para ahorrar velocidad y recursos.
*   **Consecuencia:** Si definimos una regla muy importante charlando y seguimos conversando de otras cosas, después de 15 o 20 mensajes me voy a olvidar de esa regla porque quedó fuera de mi recorte de chat.
*   **Atajo:** Cada vez que acordemos una regla importante (ej: *"los PDFs van a MD en el raw"*), **debemos escribirla inmediatamente en un archivo `.md` del proyecto**. Los archivos físicos en tu carpeta son mi **memoria de largo plazo**.

### B. El Superpoder de `AGENTS.md` (Reglas Permanentes)
*   **La característica:** Antigravity busca de forma automática un archivo llamado `AGENTS.md` en la carpeta `.agents/` de tu proyecto (o en mi configuración global).
*   **Cómo usarlo:** Si hay cosas que querés que yo recuerde **SIEMPRE**, en cada mensaje de cada día sin excepción (ej: *"no modifiques nunca el CSS"* o *"usá siempre WAL en SQLite"*), las escribimos en ese archivo y yo las leeré obligatoriamente al arrancar cada turno.

---

## 🚀 2. Tips y Trucos para Trabajar con la IA

### 💡 Tip 1: "Refrescame la memoria"
Antes de empezar a programar una función nueva o hacer cambios en una base de datos, siempre podés decirme:
> 🗣️ *"Leé el archivo `arquitectura.md` y el `neurona_pagos.md` y decime qué reglas tenemos que respetar antes de escribir código."*
Eso me obliga a leer el archivo completo en ese instante y evita que meta la pata con el diseño general.

### 💡 Tip 2: Un Archivo por Módulo (Neuronas)
No juntes toda la documentación en un solo archivo inmenso. Dividir las reglas por módulo (`neurona_pagos.md`, `neurona_bancos.md`) me permite enfocarme únicamente en las reglas del módulo con el que estamos trabajando hoy, reduciendo mi margen de error a cero.

### 💡 Tip 3: Evitar el "Código Inflado" (Bloatware)
Intento no escribir scripts de Python de más de 300 o 400 líneas. Si un archivo se empieza a hacer muy largo, pedime:
> 🗣️ *"Refactorizá este código y separalo en módulos más chicos."*
A las IAs nos cuesta mucho procesar y mantener la precisión en archivos de código gigantescos.

---

## 🛠️ 3. Comandos Útiles de la Interfaz (Slash Commands)

En tu chat del ERP con la IA, podés recomendarme o usar estos atajos rápidos:
*   `/grill-me` ➡️ Usalo cuando no estés segura de cómo encarar una funcionalidad. Me activa un modo "entrevista" donde te hago preguntas clave para ponernos de acuerdo en un plan antes de tocar código.
*   `/goal` ➡️ Usalo si querés dejarme una tarea larga o compleja (por ejemplo, resolver un bug difícil) para que yo trabaje de fondo de forma extra minuciosa y no me detenga hasta lograrlo.
*   `/learn` ➡️ Si corregís un error mío o logramos configurar algo complejo que costó trabajo, podés usar este comando para que yo persista ese aprendizaje para futuras sesiones.

---

## 🏛️ 4. Recordatorio: El flujo de nuestro ERP (ELT)
Para que vos también lo tengas a mano de forma visual rápida:

```
📥 [PDF/Excel en Inbox] 
       │
       ▼ (Fase 1: Ingesta Raw)
📄 [conversores.py] ───► Convierte a Markdown/JSON
       │
       ▼
🗄️ [core_staging_raw] ──► Guarda el texto plano crudo e inmutable en la DB
       │
       ▼ (Fase 2: Transformación)
⚙️ [storage_*.py] ─────► Procesa los datos, los convierte a centavos y los inserta en producción
```
