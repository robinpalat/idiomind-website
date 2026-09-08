# Changelog - Configuración del Sitio

Registro incremental de cambios en la configuración y diseño de idiomind.com

---

## [0.28.0] - 2026-09-06

### Nombres de Topics más Destacados

Los nombres de topics en las listas de categorías ahora tienen mayor tamaño, peso y contraste, con hover en el color de acento.

---

## [0.27.0] - 2026-09-06

### Scroll Invisible con Rueda Activa

Se ocultó visualmente la barra de scroll de las listas embebidas sin desactivar el desplazamiento con la rueda del mouse. Se mantiene una altura fija para no alterar el diseño del viewer.

---

## [0.26.0] - 2026-09-06

### Viewer sin Scroll Interno en Listas

Las listas largas de categorías ahora ajustan automáticamente la altura del viewer al contenido. El scroll pasa a ser el de la página principal, evitando un segundo scroll interno en la lista de topics.

---

## [0.25.0] - 2026-09-06

### Límite de Pinned

La Library ahora muestra como máximo 5 topics Pinned.

---

## [0.24.0] - 2026-09-06

### Eliminación de Línea Duplicada

Se eliminó la línea superior añadida por el contenedor del viewer para conservar una sola línea visual en la Library.

---

## [0.23.0] - 2026-09-06

### Labels de Flashcards con Borde

Los labels de resultado ahora tienen fondo blanco y bordes finos con los mismos colores de los botones inferiores: rojo para `I did not know it` y verde para `I knew it`.

---

## [0.22.0] - 2026-09-06

### Labels de Resultado sin Fondo

Los labels `I did not know it` e `I knew it` ahora usan fondo transparente, color semántico, peso tipográfico y una línea inferior sutil en lugar de cajas coloreadas.

---

## [0.21.0] - 2026-09-06

### Botones de Topic más Compactos

Se redujo ligeramente el tamaño de los botones Favorito y Flashcards, con una escala todavía más compacta en móviles.

---

## [0.20.0] - 2026-09-06

### Jerarquía Visual del Topic

Se amplió y destacó el nombre del topic. La información de nivel, estadísticas, traducciones, fecha, autor y descarga ahora tiene una jerarquía visual más clara y consistente, con adaptación para móviles.

---

## [0.19.0] - 2026-09-06

### Ajuste Vertical de Palabras y Oraciones

Se añadió separación superior a los bloques de palabra y oración del viewer para que respiren mejor y queden ligeramente más abajo, manteniendo intactos sus tamaños y los controles inferiores.

---

## [0.18.0] - 2026-09-06

### Flashcards más Legibles

Se aumentó el padding del encabezado de Flashcards y el tamaño de los textos `I did not know it` / `I knew it`. En móviles, los indicadores se adaptan y pueden pasar a varias líneas sin desbordarse.

---

## [0.17.0] - 2026-09-06

### Eliminación del Icono Back del Topic

Se ocultó el icono de regreso interno del visor de topics. La navegación ahora se realiza mediante `Back to library` en el viewer integrado.

---

## [0.16.0] - 2026-09-06

### Corrección de Scroll Inicial del Viewer

Se corrigió el overflow inicial causado por la pantalla de carga (`100vw/100vh` más márgenes). El viewer ahora usa el tamaño real del iframe, elimina el overflow horizontal innecesario y evita scrollbars durante la carga.

---

## [0.15.0] - 2026-09-06

### Categoría en el Viewer

La etiqueta del viewer integrado ahora muestra la categoría correspondiente (`Article`, `Grammar`, `At Home`, `Pinned`, etc.) en lugar de `Topic viewer`.

---

## [0.14.0] - 2026-09-06

### Categorías dentro del Viewer de Library

Los botones de categoría ahora se abren en el mismo viewer integrado que los topics. Los enlaces de topics dentro de cada categoría también se interceptan para evitar lightboxes anidados.

---

## [0.13.0] - 2026-09-06

### Viewer Integrado en Library

La Library dejó de abrir topics mediante Fancybox. Ahora carga el viewer dentro de la propia página, en un iframe contenido por la sección `library-viewer`, con navegación de regreso a la lista y soporte para Pinned.

---

## [0.12.0] - 2026-09-06

### Modal Relativo al Slide de Fancybox

Se eliminó el cálculo basado en `window.innerWidth/innerHeight`, que podía hacer que el modal pareciera tomar como referencia el monitor. Fancybox vuelve a calcular el tamaño relativo a su propio slide: `90%` de ancho y `86%` de alto, con comportamiento responsive para móviles.

---

## [0.11.0] - 2026-09-06

### Ajuste del Tamaño Real del Modal

Se eliminaron los mínimos inline de Fancybox (`min-width: 100%` y `min-height: 100%`) que impedían reducir el modal. Ahora respeta realmente el `90%` de ancho y `88%` de alto calculados sobre la ventana del navegador.

---

## [0.10.0] - 2026-09-06

### Modal con Tamaño no Completo

El lightbox ahora ocupa aproximadamente el `90%` del ancho y el `88%` del alto de la ventana del navegador, con límites máximos y márgenes visibles. Ya no aparenta ser una ventana a pantalla completa.

---

## [0.9.0] - 2026-09-06

### Lightbox basado en la ventana del navegador

El tamaño del iframe ahora se calcula con `window.innerWidth` y `window.innerHeight` del documento padre, incluyendo actualización al redimensionar la ventana. Esto evita que el lightbox tome dimensiones del monitor cuando el navegador no está maximizado.

---

## [0.8.0] - 2026-09-06

### Lightbox con Márgenes

El lightbox dejó de ocupar toda la pantalla. Ahora usa márgenes de `24px` en escritorio y `12px` en pantallas pequeñas, manteniendo un tamaño amplio y relativo a la ventana del navegador.

---

## [0.7.0] - 2026-09-06

### Carga de Topics Pinned

Los topics guardados ya resuelven su categoría real desde `search-index.json` antes de cargar el archivo `.idmnd`. Esto corrige las URLs antiguas con `c=fav`, que intentaban cargar rutas inexistentes como `/english/fav/Topic.idmnd`.

**Archivos modificados:**
- `js/view.js`, `js/view_mob.js` → versiones en `dist/`

---

## [0.6.0] - 2026-09-06

### Cierre del Topic desde Latest Published

El botón interno de volver/cerrar ahora cierra el Fancybox padre cuando el topic está abierto dentro del lightbox. Ya no navega a la lista de categorías dentro del iframe; la página vuelve directamente a la Library.

**Archivos modificados:**
- `js/view.js`, `js/view_mob.js` → versiones en `dist/`
- `library.html` → `dist/library.html`

---

## [0.5.0] - 2026-09-06

### Cierre del Lightbox

Se ocultó el botón de cierre generado por Fancybox únicamente en los iframes de topics (`view.html`), para evitar la superposición con su control interno. Las listas de categorías conservan su cruz blanca.

**Archivos modificados:**
- `js/fancybox/jquery.fancybox.css` → `dist/js/fancybox/jquery.fancybox.css`
- `js/fancybox/jquery.fancybox.js` → `dist/js/fancybox/jquery.fancybox.js`
- `library.html` → `dist/library.html`

---

## [0.4.0] - 2026-09-06

### Corrección del Lightbox y Flashcards

**Problemas corregidos:**
- El iframe del lightbox no ocupaba la ventana actual por el padding vertical de Fancybox.
- Flashcards fallaba al intentar parsear una respuesta XHR vacía.
- Los botones y la descripción no seguían el orden visual esperado.

**Solución:**
- El iframe ahora ocupa el viewport actual (`100%` del slide sin padding).
- El cargador de quiz espera `onload`, valida el estado HTTP y protege el parseo JSON.
- `TopicLanding` se mueve debajo del nombre del topic; la descripción queda debajo de los botones.
- Se añadieron versiones a las URLs de recursos para evitar caché antigua.

**Archivos modificados:**
- `js/fancybox/jquery.fancybox.css` → `dist/js/fancybox/jquery.fancybox.css`
- `js/view.js`, `js/view_mob.js` → `dist/js/view.js`, `dist/js/view_mob.js`
- `css/view.css`, `css/mobileview.css` → versiones en `dist/`
- `library.html`, `dist/library.html`
- Plantilla correspondiente en `build.py`

---

## [0.3.0] - 2026-09-06

### Fix: Cookie de idioma no se reconocía en Library

**Problema:** Al seleccionar un idioma (french, german, russian, etc.) y volver a library.html, el picker se mostraba de nuevo en lugar de recordar la selección.

**Causa:** `LIB_LANGS` solo contenía `["english","portuguese","spanish"]`. Si el usuario elegía french, german, u otro idioma, la cookie existía pero no era reconocida como "known".

**Solución:** Actualizar `LIB_LANGS` con todos los idiomas soportados.

**Archivos modificados:**
- `library.html`
- `dist/library.html`

---

## [0.2.0] - 2026-09-06

### Corrección de Layout - Library (Latest published)

**Problema:** El nombre del topic estaba separado de su información de publicación. La fecha aparecía debajo, pegada al siguiente topic.

**Solución:** Envolver cada item en un contenedor `.feed-item` con `display: flex` y `align-items: baseline` para alinear nombre y fecha en la misma línea.

**Archivos modificados:**
- `css/site.css` → `dist/css/site.css` (nueva clase `.feed-item`)
- `library.html` → `dist/library.html` (estructura HTML actualizada)

**CSS agregado:**
```css
.feed-item {
    display: flex;
    align-items: baseline;
    gap: 10px;
    margin: 0 0 10px;
}
```

---

## [0.1.0] - 2026-09-06

### Cambios de Color de Acento

**Archivos modificados:**
- `css/home.css` → `dist/css/home.css`
- `css/classic.css` → `dist/css/classic.css`
- `css/apphome.css` → `dist/css/apphome.css`
- `css/mobilehome.css` → `dist/css/mobilehome.css`
- `css/fonts.css` → `dist/css/fonts.css` (sobreescribía las variables)
- `js/fancybox/jquery.fancybox.css` → `dist/js/fancybox/jquery.fancybox.css` (colores hardcoded)

**Variables CSS actualizadas en `:root`:**

| Variable | Antes | Después | Uso |
|----------|-------|---------|-----|
| `--accent` | `#AE5B35` | `#866895` | Color principal (enlaces, botones, bordes activos) |
| `--accent-strong` | `#8C4525` | `#6B5276` | Variante oscura (hover, active states) |
| `--accent-soft` | `#F1E2D6` | `#E8E0ED` | Variante clara (focus rings, fondos sutiles) |

**Notas:**
- El color anterior era un tono terracota/naranja quemado (`#AE5B35`)
- El nuevo color es un tono púrpura/violeta (`#866895`)
- Los cambios aplican automáticamente a todos los componentes que usan estas variables
