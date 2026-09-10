/* ============================================================================
 * Idiomind - view.js
 * ----------------------------------------------------------------------------
 * ¿Cómo carga Idiomind un topic?
 *
 *   URL (.idmnd)
 *     -> TopicFile.load(url)
 *          - detecta si la respuesta es JSON "legacy" o un ZIP "modern"
 *          - legacy: JSON.parse directo
 *          - modern: JSZip abre el ZIP, extrae "topic.idmnd" y hace JSON.parse
 *          - en ambos casos devuelve el MISMO objeto `data` de siempre
 *            (mismo formato JSON, no se normaliza ni se cambia semántica)
 *          - además expone `data.resources` con getImage/getAudio/getNote
 *            para no acoplar Topic/Viewer/Quiz al hecho de que el topic
 *            venga de un ZIP o de un JSON suelto
 *     -> Topic / Viewer / Quiz consumen `data` exactamente igual que antes
 *
 * Formato legacy: "topic.idmnd" es directamente el JSON del topic.
 * Formato modern: "topic.idmnd" es un ZIP que contiene:
 *     topic.idmnd (el JSON real), audio/{shared,topic}/, images/{shared,topic}/,
 *     note.md
 *
 * NOTA IMPORTANTE:
 * - `window.myData` es la única fuente de verdad para la URL del topic
 *   actual. La declara view.html (`var myData = '/' + lang + ...`) antes
 *   de que este script reciba el evento 'load'. Este archivo nunca vuelve
 *   a declarar una copia local de `myData`; todas las referencias a
 *   `myData` (dentro y fuera de `window.addEventListener('load', ...)`)
 *   son el mismo global. `TopicFile.resolveFavoriteUrl()` puede
 *   reescribir `window.myData` al resolver un topic "favorito".
 * - `data.items[x]` se sigue tratando como un array posicional legacy
 *   (ver `parseItem`). No se ha cambiado el formato del JSON.
 * ==========================================================================*/

/* ---------------------------------------------------------------------------
 * 1. Carga de librerías externas (igual que antes: inyección dinámica de
 *    <script>, mismo mecanismo que ya usaba el archivo original).
 * -------------------------------------------------------------------------*/

function loadExternalScript(src) {
    var script = document.createElement('script');
    script.src = src;
    document.head.appendChild(script);
    return script;
}

loadExternalScript('/js/sweetalert.min.js');
loadExternalScript('/js/voicerss-tts.min.js');

// Necesaria para poder leer el nuevo formato .idmnd cuando es un ZIP.
// Se sirve localmente (no CDN). La inyección de <script> es asíncrona:
// el navegador sigue ejecutando el resto de este archivo (y el <script>
// inline de view.html que llama a Topic.loadData) sin esperar a que
// jszip.min.js termine de descargarse. Por eso NO basta con cambiar la
// URL: si un topic resulta ser un ZIP y `JSZip` todavía no existe en ese
// momento, la carga fallaba. `jsZipReady` es una promesa que se resuelve
// cuando el script ha terminado de cargar (o se rechaza si falla), y
// `TopicFile.load()` la espera justo antes de usar `JSZip`, únicamente
// cuando el topic descargado resulta ser un ZIP (los topics legacy en
// JSON no necesitan esperarla en absoluto).
var jsZipReady = new Promise(function (resolve, reject) {
    var script = loadExternalScript('/js/jszip.min.js');
    script.onload = function () { resolve(); };
    script.onerror = function () { reject(new Error('No se pudo cargar /js/jszip.min.js')); };
});


/* ---------------------------------------------------------------------------
 * 2. TTS (VoiceRSS) - comportamiento y clave preservados sin cambios.
 * -------------------------------------------------------------------------*/

var VOICERSS_API_KEY = '48118d3dbd84495482314170e8361839';

function speechtrgt(trgt) {
    if (typeof VoiceRSS === 'undefined') {
        console.error('VoiceRSS todavía no está cargado.');
        return;
    }
    VoiceRSS.speech({
        key: VOICERSS_API_KEY,
        src: trgt,
        hl: 'en-us',
        r: 0,
        c: 'ogg',
        f: '8khz_8bit_mono',
        ssml: false
    });
}

/* ---------------------------------------------------------------------------
 * 3. Utilidades generales
 * -------------------------------------------------------------------------*/

function percentage(num, per) {
    return (num * 100) / per;
}

/**
 * Redondea el porcentaje de aciertos igual que el código original
 * (`por.toFixed()`), centralizado para no repetirlo en Viewer/Quiz.
 */
function scorePercentageLabel(correct, total) {
    return percentage(correct, total).toFixed();
}

/* ---------------------------------------------------------------------------
 * 4. Capa de acceso al DOM
 * -------------------------------------------------------------------------
 * No se cambia ningún id ni ninguna estructura del DOM. Solo se centraliza
 * el acceso para: (a) evitar repetir document.getElementById/querySelector,
 * y (b) fallar de forma controlada si un elemento no existe, en vez de
 * lanzar "Cannot read properties of null".
 * -------------------------------------------------------------------------*/

var dom = {
    byId: function (id) {
        var el = document.getElementById(id);
        if (!el) {
            console.error('Elemento no encontrado: #' + id);
        }
        return el;
    },
    // Los templates de este proyecto usan el patrón "#id > primer hijo"
    // para el nodo donde realmente va el contenido. Se preserva tal cual.
    firstChildOf: function (selector) {
        var container = document.querySelector(selector);
        if (!container || !container.children || !container.children[0]) {
            console.error('No se encontró el hijo esperado de: ' + selector);
            return null;
        }
        return container.children[0];
    },
    setText: function (selector, value) {
        var el = dom.firstChildOf(selector);
        if (el) el.innerHTML = value;
        return el;
    },
    // Preserva EXACTAMENTE los mismos valores de `style` que usaba el
    // código original (incluyendo "DISPLAY: true;" / "DISPLAY: none;",
    // que no son CSS válido pero se mantienen sin modificar para no
    // arriesgar el comportamiento visual actual del sitio).
    setStyleText: function (id, cssText) {
        var el = document.getElementById(id);
        if (el) el.style = cssText;
    }
};

/* ---------------------------------------------------------------------------
 * 5. TopicFile: capa central de carga (legacy JSON / modern ZIP)
 * -------------------------------------------------------------------------*/

var TopicFile = (function () {

    function isZipResponse(arrayBuffer) {
        // Firma de cabecera de un ZIP: "PK\x03\x04" (o variantes vacías).
        var bytes = new Uint8Array(arrayBuffer.slice(0, 4));
        return bytes[0] === 0x50 && bytes[1] === 0x4b;
    }

    function parseLegacyJson(text) {
        try {
            return JSON.parse(text);
        } catch (error) {
            throw new Error('JSON de topic inválido: ' + error.message);
        }
    }

    /**
     * Crea el objeto `resources` que Topic/Viewer/Quiz pueden usar sin saber
     * si el topic viene de un ZIP o no. En modo legacy no hay recursos
     * empaquetados (todo se sirve por URL, como siempre), así que estos
     * métodos devuelven null y el llamador cae a la ruta legacy.
     */
    function createLegacyResources() {
        return {
            isPackaged: false,
            getImage: function () { return null; },
            getAudio: function () { return null; },
            getNote: function () { return null; }
        };
    }

    function createZipResources(zip) {
        var cache = {};

        function readAsUrl(path) {
            if (!zip.file(path)) return Promise.resolve(null);
            if (cache[path]) return cache[path];
            cache[path] = zip.file(path).async('blob').then(function (blob) {
                return URL.createObjectURL(blob);
            });
            return cache[path];
        }

        return {
            isPackaged: true,
            // Intenta primero el recurso específico del topic y luego el
            // compartido, siguiendo la estructura descrita para el nuevo
            // formato (images/topic/... , images/shared/...).
            getImage: function (fileName) {
                return readAsUrl('images/topic/' + fileName).then(function (url) {
                    return url || readAsUrl('images/shared/' + fileName);
                });
            },
            getAudio: function (fileName) {
                return readAsUrl('audio/topic/' + fileName).then(function (url) {
                    return url || readAsUrl('audio/shared/' + fileName);
                });
            },
            getNote: function () {
                if (!zip.file('note.md')) return Promise.resolve(null);
                return zip.file('note.md').async('text');
            }
        };
    }

    /**
     * Carga y devuelve el `data` del topic, igual que antes, más
     * `data.resources` (ver arriba). No modifica el JSON del topic.
     */
    function load(url) {
        return fetch(url).then(function (response) {
            if (!response.ok) {
                var error = new Error('HTTP ' + response.status);
                error.httpStatus = response.status;
                throw error;
            }
            return response.arrayBuffer();
        }).then(function (buffer) {
            if (isZipResponse(buffer)) {
                // Espera a que /js/jszip.min.js haya terminado de cargar
                // (ver comentario junto a `jsZipReady` al inicio del
                // archivo) antes de tocar el global `JSZip`.
                return jsZipReady.then(function () {
                    if (typeof JSZip === 'undefined') {
                        throw new Error('JSZip no está disponible para leer el formato .idmnd (ZIP).');
                    }
                    return JSZip.loadAsync(buffer).then(function (zip) {
                        var entry = zip.file('topic.idmnd');
                        if (!entry) {
                            throw new Error('El ZIP .idmnd no contiene "topic.idmnd".');
                        }
                        return entry.async('text').then(function (text) {
                            var data = parseLegacyJson(text);
                            data.resources = createZipResources(zip);
                            return data;
                        });
                    });
                });
            }

            var text = new TextDecoder('utf-8').decode(buffer);
            if (!text.trim()) {
                throw new Error('Respuesta vacía al cargar el topic.');
            }
            var data = parseLegacyJson(text);
            data.resources = createLegacyResources();
            return data;
        });
    }

    /**
     * Resuelve un topic "favorito" (`/lang/fav/nombre.idmnd`) contra
     * `/search-index.json`, igual que hacía Topic.load_data originalmente.
     * Solo Topic usaba esta ruta; se mantiene aislada aquí para no
     * cambiar el comportamiento de Viewer/Quiz, que nunca la usaron.
     * Devuelve la URL real a cargar, o null si `url` no es un favorito.
     */
    function resolveFavoriteUrl(url) {
        var favorite = url.match(/^\/([^/]+)\/fav\/(.+)\.idmnd$/);
        if (!favorite) {
            return Promise.resolve(null);
        }
        return fetch('/search-index.json').then(function (response) {
            if (!response.ok || !response.body) {
                return null;
            }
            return response.text();
        }).then(function (text) {
            if (!text || !text.trim()) return null;
            try {
                var entries = JSON.parse(text);
                var name = decodeURIComponent(favorite[2]);
                var match = entries.find(function (entry) {
                    return entry.lang && entry.lang.toLowerCase() === favorite[1].toLowerCase() && entry.name === name;
                });
                if (!match) return null;
                var resolved = new URL(match.viewUrl, window.location.origin);
                var resolvedUrl = '/' + resolved.searchParams.get('l') + '/' + resolved.searchParams.get('c') + '/' + resolved.searchParams.get('set') + '.idmnd';
                window.myData = resolvedUrl;
                return resolvedUrl;
            } catch (error) {
                console.error('No se pudo resolver el topic favorito', error);
                return null;
            }
        }).catch(function (error) {
            console.error('No se pudo resolver el topic favorito', error);
            return null;
        });
    }

    return {
        load: load,
        resolveFavoriteUrl: resolveFavoriteUrl
    };
})();

/* ---------------------------------------------------------------------------
 * 6. parseItem: sustituye la extracción manual por índice duplicada en
 *    Viewer y Quiz.
 * -------------------------------------------------------------------------
 * `data.items[key]` sigue siendo, como en el código original, un array
 * posicional legacy. Los índices y su significado se conservan idénticos
 * a los que usaba el archivo original (arr[0], arr[11], arr[15], arr[19],
 * arr[20], arr[23]).
 *
 * El código original, antes de leer esas posiciones, recorría las claves
 * del item convirtiendo cada valor con `new Date(...)` y luego hacía un
 * roundtrip `JSON.stringify` + `JSON.parse`. Para los valores primitivos
 * que aloja este array (strings/numbers), esa secuencia es, en la práctica,
 * una operación sin efecto (ver informe). Por seguridad se REPLICA aquí
 * exactamente el mismo procedimiento en vez de eliminarlo directamente,
 * para no arriesgar el comportamiento si algún topic tuviera un item con
 * forma distinta a la esperada.
 * -------------------------------------------------------------------------*/

var ITEM_FIELD_INDEX = {
    source: 0,
    example: 11,
    grammar: 15,
    imageId: 19,
    imageGroup: 20,
    type: 23
};

/**
 * Replica el bucle "clonar con Date + JSON roundtrip" del código original.
 * Ver comentario arriba: se mantiene por seguridad de comportamiento.
 */
function legacyCloneItemFields(item) {
    var cloned = [];
    for (var eventKey in item) {
        var value = item[eventKey];
        if (value !== null && typeof value === 'object') {
            var copy = {};
            for (var innerKey in value) {
                copy[innerKey] = new Date(value[innerKey]);
            }
            cloned.push(JSON.parse(JSON.stringify(copy)));
        } else {
            // Asignar una propiedad sobre un primitivo no lo modifica
            // (modo no estricto): el valor original se conserva tal cual,
            // igual que en el código legacy.
            cloned.push(value);
        }
    }
    return cloned;
}

/**
 * Extrae los campos de un item en un objeto con nombres claros.
 * Devuelve las mismas posiciones/valores que extraía el código original.
 */
function parseItem(item) {
    if (!item || typeof item !== 'object') {
        return {
            source: undefined,
            example: undefined,
            grammar: undefined,
            imageId: undefined,
            imageGroup: undefined,
            type: undefined
        };
    }

    return {
        source: item.srce,
        example: item.exmp,
        grammar: item.grmr,
        imageId: item.imag,
        imageGroup: item.imgr,
        type: item.type
    };
}

/**
 * Igual que el original: resalta en negrita el target (en su forma literal
 * y en minúsculas) dentro del texto de ejemplo.
 */
function highlightTargetInExample(example, trgt) {
    var lower = trgt.toLowerCase();
    var highlighted = example.replace(lower, '<b>' + lower + '</b>');
    highlighted = highlighted.replace(trgt, '<b>' + trgt + '</b>');
    return highlighted;
}

/* ---------------------------------------------------------------------------
 * 7. resolveImage: desacopla a Viewer/Quiz de dónde vive físicamente la
 *    imagen (legacy /share/images/... o recursos empaquetados del ZIP).
 * -------------------------------------------------------------------------*/

function hasImage(item) {
    return Number(item.type) === 1 && Number(item.imageId) !== 0;
}

function legacyImageUrl(item) {
    return '/share/images/' + item.imageGroup + '-' + item.imageId + '.jpg';
}

/**
 * Resuelve la imagen según el tipo de topic.
 *
 * Topic moderno (.idmnd):
 *   images/topic/<target>.jpg
 *   images/shared/<target>.jpg
 *
 * Topic legacy:
 *   /share/images/<imageGroup>-<imageId>.jpg
 */
function resolveImage(item, resources, trgt) {
    var legacyUrl = legacyImageUrl(item);

    // Topic legacy: no hay recursos empaquetados.
    if (!resources || !resources.isPackaged) {
        return Promise.resolve(legacyUrl);
    }

    // Topic moderno: el nombre de la imagen es el target.
    var fileName = String(trgt).toLowerCase().trim() + '.jpg';

    // IMPORTANTE:
    // No hacemos fallback a /share/images para topics empaquetados.
    return resources.getImage(fileName);
}

/* ---------------------------------------------------------------------------
 * 8. Tipografía dinámica compartida (antes duplicada entre Viewer y Quiz)
 * -------------------------------------------------------------------------*/

function sizeForLength(chars, table) {
    for (var i = 0; i < table.length; i++) {
        var row = table[i];
        if (chars >= row.min && chars < row.max) {
            return row;
        }
    }
    return table[table.length - 1];
}

var TITLE_SIZE_TABLE = [
    { min: 1, max: 20, fs: 68, vw: 4.30 },
    { min: 20, max: 40, fs: 50, vw: 4.10 },
    { min: 40, max: 80, fs: 55, vw: 3.80 },
    { min: 80, max: 100, fs: 45, vw: 3.60 },
    { min: 100, max: Infinity, fs: 35, vw: 3.50 }
];

var SOURCE_SIZE_TABLE = [
    { min: 1, max: 20, fs: 21, vw: 2.30 },
    { min: 20, max: 40, fs: 19, vw: 2.20 },
    { min: 40, max: 80, fs: 18, vw: 2.10 },
    { min: 80, max: 100, fs: 17, vw: 2.00 },
    { min: 100, max: Infinity, fs: 16, vw: 2.00 }
];

var EXAMPLE_SIZE_TABLE = [
    { min: 1, max: 20, fs: 11, vw: 1.70 },
    { min: 20, max: 40, fs: 10, vw: 1.60 },
    { min: 40, max: 80, fs: 9, vw: 1.40 },
    { min: 80, max: 100, fs: 9, vw: 1.20 },
    { min: 100, max: Infinity, fs: 8, vw: 1.20 }
];

/**
 * Calcula los mismos tamaños de fuente (título/fuente/ejemplo, en px y vw)
 * que calculaban, de forma duplicada, viewer_render_card y Quiz_render_card.
 */
function computeTypography(trgt, srce, exmp) {
    var title = sizeForLength(trgt.length, TITLE_SIZE_TABLE);
    var source = sizeForLength(srce.length, SOURCE_SIZE_TABLE);
    var example = sizeForLength(exmp.length, EXAMPLE_SIZE_TABLE);
    return {
        fs: title.fs, vw: title.vw,
        sfs: source.fs, svw: source.vw,
        efs: example.fs, evw: example.vw
    };
}

/**
 * Genera el CSS de la tarjeta (idéntico al original, incluida la media
 * query de dispositivos pequeños) y lo aplica reutilizando UNA sola hoja
 * de estilos dinámica, en vez de crear un <style> nuevo en cada render
 * (que es lo que hacía el código original y que iba acumulando etiquetas
 * <style> sin límite). El resultado visual final es el mismo: al ser CSS
 * con los mismos selectores, la última hoja aplicada siempre "gana"; ahora
 * simplemente reutilizamos la misma etiqueta en lugar de apilar muchas.
 */
var applyCardTypography = (function () {
    var styleTag = null;

    function ensureStyleTag() {
        if (styleTag && document.head.contains(styleTag)) {
            return styleTag;
        }
        styleTag = document.createElement('style');
        styleTag.type = 'text/css';
        styleTag.id = 'idiomind-card-typography';
        (document.head || document.getElementsByTagName('head')[0]).appendChild(styleTag);
        return styleTag;
    }

    return function (typography) {
        var mvw = 6, msvw = 5, mevw = 5;
        var css = 'h1 { font-size:' + typography.fs + 'px;font-size:' + typography.vw + 'vw;} ' +
            'h2 { font-size:' + typography.sfs + 'px;font-size:' + typography.svw + 'vw;}' +
            'p { font-size:' + typography.efs + 'px;font-size:' + typography.evw + 'vw;}' +
            '.pronounce {width:90%}' +
            '@media all and (max-device-width: 320px){' +
            'h1 { font-size:' + typography.fs + 'px;font-size:' + mvw + 'vw;}' +
            'h2 { font-size:' + typography.sfs + 'px;font-size:' + msvw + 'vw;}' +
            'p { font-size:' + typography.efs + 'px;font-size:' + mevw + 'vw;}' +
            '.pronounce {width:95%}}';
        var tag = ensureStyleTag();
        tag.textContent = css;
    };
})();

/* ---------------------------------------------------------------------------
 * 9. Topic
 * -------------------------------------------------------------------------*/

var Topic = (function () {

    function renderPage(data) {
        dom.setText('#name', data.name);

        var topicName = document.querySelector('#name');
        var topicLanding = document.querySelector('#TopicLanding');
        if (topicName && topicLanding && topicLanding.parentNode !== topicName.parentNode) {
            topicName.parentNode.insertBefore(topicLanding, topicName.nextSibling);
        }
        
        var infoNote = document.getElementById('info_note');

		if (data.info && data.info.trim()) {
			dom.setText('#info_note', data.info);
			infoNote.style.display = '';
		} else {
			infoNote.style.display = 'none';
		}
        dom.setText('#autr', data.autr);
        dom.setText('#nwrd', data.nwrd === 1 ? (data.nwrd + ' Word,') : (data.nwrd + ' Words,'));
        dom.setText('#nsnt', data.nsnt === 1 ? (data.nsnt + ' Sentence,') : (data.nsnt + ' Sentences,'));
        dom.setText('#nimg', data.nimg === 1 ? (data.nimg + ' Image.') : (data.nimg + ' Images.'));
        dom.setText('#naud', data.naud === 1 ? (data.naud + ' Audio file and') : (data.naud + ' Audio files and'));
        dom.setText('#dteu', data.dteu);
        dom.setText('#slng', data.slng);

		var level = Number(data.levl);

		var levelLabel;
		if (level === 0) {
			levelLabel = 'beginner';
		} else if (level === 1) {
			levelLabel = 'intermediate';
		} else if (level === 2) {
			levelLabel = 'advance';
		} else {
			levelLabel = '';
		}

		dom.setText('#levl', levelLabel);

        var first = Object.keys(data.items)[0];
        renderTopic(first, data.items[first]);
    }

    function renderTopic(trgt, dat) {
        document.body.style.backgroundColor = '#F0ECEB';
        dom.setStyleText('headA', 'DISPLAY: true;');
        dom.setStyleText('headB', 'DISPLAY: none;');
        dom.setStyleText('headC', 'DISPLAY: none;');
        dom.setStyleText('TopicLanding', 'DISPLAY: true;');
        dom.setStyleText('fscreen', 'DISPLAY: none;');
        dom.setStyleText('vscreen', 'DISPLAY: none;');
        dom.setStyleText('QuizButtons', 'DISPLAY: none;');
        dom.setStyleText('ViewerButtons', 'DISPLAY: none;');
        dom.setStyleText('slidecontainer', 'DISPLAY: none;');
    }

    function reportLoadError(error) {
        console.error('Error cargando el topic', error);
        if (error && error.httpStatus === 404) {
            if (typeof swal === 'function') {
                swal('This file is not yet on Server, try again later.', ' ', 'error');
            }
            document.write('<br><br><div align="center"><big>Exiting...</big></div>');
            if (typeof goBack === 'function') goBack();
            return;
        }
        if (typeof swal === 'function') {
            swal('Something went wrong loading this topic.', ' ', 'error');
        }
    }

    function loadData(file) {
        TopicFile.resolveFavoriteUrl(file).then(function (resolvedUrl) {
            var url = resolvedUrl || file;
            return TopicFile.load(url);
        }).then(function (data) {
            currentTopicData = data;
            renderPage(data);
        }).catch(reportLoadError);
    }

    return {
        renderTopic: renderTopic,
        renderPage: renderPage,
        loadData: loadData
    };
})();

/* ---------------------------------------------------------------------------
 * 10. Estado compartido entre Topic/Viewer/Quiz
 * -------------------------------------------------------------------------
 * El código original compartía una variable global implícita `data` entre
 * los tres módulos: quien cargaba último dejaba ahí los datos que los
 * demás leían. Ese acoplamiento se preserva tal cual (no se separa en
 * estados independientes, porque romperlo sin poder probar contra el HTML
 * real podría cambiar comportamiento), pero ahora es una única variable
 * explícita y documentada en vez de una fuga accidental a `window`.
 * -------------------------------------------------------------------------*/
var currentTopicData;

/* ---------------------------------------------------------------------------
 * 11. Viewer
 * -------------------------------------------------------------------------*/

var Viewer = (function () {
    // Estado propio de Viewer (antes: variables globales accidentales
    // `play_stts` y `myTimer`).
    var playState = 0;
    var playTimer = null;

    function bindStaticControls() {
        var nextBtn = dom.byId('Next');
        if (nextBtn) nextBtn.onclick = function () { Viewer.nextCard(); };

        var playBtn = dom.byId('Play');
        if (playBtn) playBtn.onclick = function () { Viewer.psplayer(); };

        var backBtn = dom.byId('Back');
        if (backBtn) backBtn.onclick = function () { Viewer.backCard(); };

        var slider = dom.byId('item_slider');
        if (slider) {
            slider.oninput = function () {
                // Se preserva el comportamiento original: el valor real
                // del slider no se usa todavía (había un TODO en el
                // código legacy), simplemente avanza a la siguiente
                // tarjeta. No se corrige aquí para no cambiar el
                // comportamiento actual del sitio.
                Viewer.nextCard();
            };
        }
    }
    bindStaticControls();

		function preloadImages(data) {
			Object.keys(data.items).forEach(function (key) {
				var item = parseItem(data.items[key]);

				if (hasImage(item)) {
					resolveImage(item, data.resources, key).then(function (url) {
						if (!url) return;

						var img = new Image();
						img.src = url;
					});
				}
			});
		}

    function renderPage(data) {
        var first = Object.keys(data.items)[0];
        var items = Object.keys(data.items);
        var count = items.length;
        var shaft = 0;

        preloadImages(data);

        document.body.style.backgroundColor = '#F0ECEB';
        dom.setStyleText('headA', 'DISPLAY: none;');
        dom.setStyleText('headB', 'DISPLAY: none;');
        dom.setStyleText('headC', 'DISPLAY: true;');
        dom.setStyleText('TopicLanding', 'DISPLAY: none;');
        dom.setStyleText('fscreen', 'DISPLAY: none;');
        dom.setStyleText('vscreen', 'DISPLAY: true;');
        dom.setStyleText('slidecontainer', 'DISPLAY: true;');
        dom.setStyleText('QuizButtons', 'DISPLAY: none;');
        dom.setStyleText('ViewerButtons', 'DISPLAY: true;');

        renderCard(first, data.items[first], count, shaft);
    }

    function renderCard(trgt, dat, count, shaft) {
        var item = parseItem(dat);
        var example = highlightTargetInExample(item.example, trgt);
        var typography = computeTypography(trgt, item.source, example);
        applyCardTypography(typography);

        window.pronounce = function () {
            speechtrgt(trgt);
        };

        var trgtElement = dom.firstChildOf('#v_trgt');
        var grmrElement = dom.firstChildOf('#grmr');
        var srceElement = dom.firstChildOf('#v_srce');
        var imgsElement = dom.firstChildOf('#v_imgs');
        var exmpElement = dom.firstChildOf('#v_exmp');
        var dotsElement = dom.firstChildOf('#dots');

        if (srceElement) srceElement.hidden = false;
        if (dotsElement) dotsElement.hidden = true;

        var countItems = dom.byId('item_slider');
        if (countItems) {
            countItems.value = 1;
            countItems.setAttribute('min', 1);
            countItems.setAttribute('max', count);
        }

        if (trgtElement) trgtElement.innerHTML = trgt;

        if (hasImage(item)) {
            if (grmrElement) grmrElement.innerHTML = trgt;
		resolveImage(item, currentTopicData && currentTopicData.resources, trgt).then(function (url) {
			if (imgsElement) {
				if (url) {
					imgsElement.innerHTML =
						'<img class="WordImage" src="' + url + '">';
				} else {
					imgsElement.innerHTML = '';
				}
			}
		});
        } else if (item.type === '1') {
            if (grmrElement) grmrElement.innerHTML = trgt;
            if (imgsElement) imgsElement.innerHTML = '';
        } else {
            var grammar = item.grammar.replace(/<span/g, '<font').replace(/<\/span>/g, '</font>');
            if (grmrElement) grmrElement.innerHTML = grammar;
            if (imgsElement) imgsElement.innerHTML = '<font "size=0"></font>';
        }

        var itemCounter = dom.firstChildOf('#item');
        if (itemCounter) itemCounter.innerHTML = shaft + 1;

        var totalCounter = dom.firstChildOf('#total');
        if (totalCounter) totalCounter.innerHTML = count;

        if (srceElement) srceElement.innerHTML = item.source;
        if (exmpElement) exmpElement.innerHTML = example;
    }

    function player() {
        var data = currentTopicData;
        if (!data) {
            console.error('Viewer.psplayer(): no hay topic cargado.');
            return;
        }

        if (playState === 0) {
            playState = 1;
            var playBtn = dom.byId('Play');
            if (playBtn) playBtn.src = '/images/stop.png';

            var trgtElement = dom.firstChildOf('#v_trgt');
            var trgt = trgtElement ? trgtElement.innerHTML : '';
            var items = Object.keys(data.items);
            var count = items.length;
            var shaft = items.indexOf(trgt);
            shaft = shaft + 1;

            var stop = function (cnt) {
                if (cnt >= count) {
                    clearInterval(playTimer);
                    if (playBtn) playBtn.src = '/images/play.png';
                    var countItems = dom.byId('item_slider');
                    if (countItems) countItems.value = 1;
                }
            };

            playTimer = setInterval(function () {
                stop(shaft);
                var slider = dom.byId('item_slider');
                if (slider && slider.offsetParent !== null) {
                    Viewer.nextCard();
                    slider.value = parseInt(shaft, 10);
                } else {
                    clearInterval(playTimer);
                    if (playBtn) playBtn.src = '/images/play.png';
                    var countItems2 = dom.byId('item_slider');
                    if (countItems2) countItems2.value = 1;
                }
                shaft++;
            }, 1 * 3500);
        } else {
            playState = 0;
            clearInterval(playTimer);
            var playBtnStop = dom.byId('Play');
            if (playBtnStop) playBtnStop.src = '/images/play.png';
        }
    }

    function nextCard() {
        var data = currentTopicData;
        var trgtElement = dom.firstChildOf('#v_trgt');
        var trgt = trgtElement ? trgtElement.innerHTML : '';
        var items = Object.keys(data.items);
        var count = items.length;
        var shaft = items.indexOf(trgt);
        shaft = shaft + 1;
        if (shaft === count) {
            shaft = 0;
        }

        var next = items[shaft];
        renderCard(next, data.items[next], count, shaft);

        var slider = dom.byId('item_slider');
        if (slider) slider.value = parseInt(shaft, 10);

        var imgsElement = dom.firstChildOf('#imgs');
        if (imgsElement) {
            var img = imgsElement.innerHTML;
            img.error = function () {
                var imgsContainer = dom.byId('imgs');
                if (imgsContainer) imgsContainer.style.display = 'none';
            };
        }
    }

    function backCard() {
        var data = currentTopicData;
        var trgtElement = dom.firstChildOf('#v_trgt');
        var trgt = trgtElement ? trgtElement.innerHTML : '';
        var items = Object.keys(data.items);
        var count = items.length;
        var shaft = items.indexOf(trgt);
        shaft = shaft - 1;

        if (shaft === count) {
            Topic.loadData(myData);
            shaft = 0;
        }

        var next = items[shaft];
        renderCard(next, data.items[next], count, shaft);

        var slider = dom.byId('item_slider');
        if (slider) slider.value = parseInt(shaft, 10);
    }

    function loadData(file) {
        TopicFile.load(file).then(function (data) {
            currentTopicData = data;
            renderPage(data);
        }).catch(function (error) {
            console.error('Error cargando el topic en el Viewer', error);
            if (typeof swal === 'function') {
                swal('Something went wrong loading this topic.', ' ', 'error');
            }
        });
    }

    return {
        renderCard: renderCard,
        renderPage: renderPage,
        nextCard: nextCard,
        backCard: backCard,
        psplayer: player,
        loadData: loadData
    };
})();

/* ---------------------------------------------------------------------------
 * 12. Quiz
 * -------------------------------------------------------------------------*/

var Quiz = (function () {
    // Estado propio de Quiz (antes: variables globales `scoreOk`/`scoreNo`,
    // que en la práctica ya vivían "de facto" en el DOM porque las
    // funciones de navegación las releían de ahí). Se mantiene aquí de
    // forma explícita, actualizando el DOM en el mismo orden que el
    // código original.
    var scoreOk = 0;
    var scoreNo = 0;

    function bindStaticControls() {
        var rightBtn = dom.byId('Right');
        if (rightBtn) rightBtn.onclick = function () { Quiz.nextCardOk(); };

        var wrongBtn = dom.byId('Wrong');
        if (wrongBtn) wrongBtn.onclick = function () { Quiz.nextCardNo(); };
    }
    bindStaticControls();

	function preloadImages(data) {
		Object.keys(data.items).forEach(function (key) {
			var item = parseItem(data.items[key]);

			if (hasImage(item)) {
				resolveImage(item, data.resources, key).then(function (url) {
					if (!url) return;

					var img = new Image();
					img.src = url;
				});
			}
		});
	}

    function renderPage(data) {
        preloadImages(data);

        document.body.style.backgroundColor = '#F0ECEB';
        dom.setStyleText('headA', 'DISPLAY: none;');
        dom.setStyleText('headC', 'DISPLAY: none;');
        dom.setStyleText('headB', 'DISPLAY: true;');
        dom.setStyleText('TopicLanding', 'DISPLAY: none;');
        dom.setStyleText('fscreen', 'DISPLAY: true;');
        dom.setStyleText('vscreen', 'DISPLAY: none;');
        dom.setStyleText('slidecontainer', 'DISPLAY: none;');
        dom.setStyleText('QuizButtons', 'DISPLAY: true;');
        dom.setStyleText('ViewerButtons', 'DISPLAY: none;');

        var rightBtn = dom.byId('Right');
        if (rightBtn) rightBtn.setAttribute('value', '0');
        var wrongBtn = dom.byId('Wrong');
        if (wrongBtn) wrongBtn.setAttribute('value', '0');

        scoreOk = 0;
        scoreNo = 0;

        var first = Object.keys(data.items)[0];
        renderCard(first, data.items[first], scoreOk, scoreNo);
    }

    function renderCard(trgt, dat, currentScoreOk, currentScoreNo) {
        var item = parseItem(dat);
        var example = highlightTargetInExample(item.example, trgt);
        var typography = computeTypography(trgt, item.source, example);
        applyCardTypography(typography);

        window.pronounce = function () {
            speechtrgt(trgt);
        };

        var trgtElement = dom.firstChildOf('#trgt');
        var srceElement = dom.firstChildOf('#srce');
        var dotsElement = dom.firstChildOf('#dots');
        var imgsElement = dom.firstChildOf('#imgs');
        var exmpElement = dom.firstChildOf('#exmp');
        var scoreOkElement = dom.firstChildOf('#score_ok');
        var scoreNoElement = dom.firstChildOf('#score_no');

        dom.setStyleText('Show', 'DISPLAY: true;');
        var rightBtn = dom.byId('Right');
        if (rightBtn) rightBtn.style.right = '5%';
        var wrongBtn = dom.byId('Wrong');
        if (wrongBtn) wrongBtn.style.left = '5%';

        if (srceElement) srceElement.hidden = true;
        if (dotsElement) dotsElement.hidden = false;

        if (trgtElement) trgtElement.innerHTML = trgt;

        if (hasImage(item)) {
			resolveImage(
				item,
				currentTopicData && currentTopicData.resources,
				trgt
			).then(function (url) {
				if (imgsElement) {
					if (url) {
						imgsElement.innerHTML =
							'<img class="WordImage" src="' + url + '">';
					} else {
						imgsElement.innerHTML = '';
					}
				}
			});
        } else if (imgsElement) {
            imgsElement.innerHTML = '<font "size=0"></font>';
        }

        if (srceElement) srceElement.innerHTML = item.source;
        if (dotsElement) dotsElement.innerHTML = '<img src="/images/eyelashes.svg"</img>';
        if (exmpElement) exmpElement.innerHTML = example;
        if (scoreNoElement) scoreNoElement.innerHTML = currentScoreNo;
        if (scoreOkElement) scoreOkElement.innerHTML = currentScoreOk;
    }

    function finishRoundIfNeeded(nextIndex, totalCount) {
        if (nextIndex !== totalCount) return false;

        var por = scorePercentageLabel(scoreOk, totalCount);

        if (typeof swal === 'function') {
            if (scoreOk === totalCount) {
                swal('Congratulations, you made a passing score!', 'Your score is: ' + por + '%', 'success');
            } else if (scoreOk > scoreNo) {
                swal('Good job!', 'Your score is: ' + por + '%', 'success');
            } else if (scoreOk < scoreNo) {
                swal("You've not passed", 'Your score is: ' + por + '%', 'error');
            } else if (scoreOk === scoreNo) {
                swal('Good job!', 'Your score is: ' + por + '%', 'warning');
            }
        }

        scoreOk = 0;
        scoreNo = 0;
        var rightBtn = dom.byId('Right');
        if (rightBtn) rightBtn.setAttribute('value', '0');
        var wrongBtn = dom.byId('Wrong');
        if (wrongBtn) wrongBtn.setAttribute('value', '0');

        return true;
    }

    function nextCardOk() {
        var data = currentTopicData;
        var trgtElement = dom.firstChildOf('#trgt');
        var trgt = trgtElement ? trgtElement.innerHTML : '';
        var keys = Object.keys(data.items);
        var current = keys.indexOf(trgt);
        var nextIndex = current + 1;

        scoreOk = scoreOk + 1;
        var rightBtn = dom.byId('Right');
        if (rightBtn) rightBtn.setAttribute('value', scoreOk);

        if (finishRoundIfNeeded(nextIndex, keys.length)) {
            nextIndex = 0;
        }

        var next = keys[nextIndex];
        renderCard(next, data.items[next], scoreOk, scoreNo);

        var imgsElement = dom.firstChildOf('#imgs');
        if (imgsElement) {
            var img = imgsElement.innerHTML;
            img.error = function () {
                var imgsContainer = dom.byId('imgs');
                if (imgsContainer) imgsContainer.style.display = 'none';
            };
        }
    }

    function nextCardNo() {
        var data = currentTopicData;
        var trgtElement = dom.firstChildOf('#trgt');
        var trgt = trgtElement ? trgtElement.innerHTML : '';
        var keys = Object.keys(data.items);
        var current = keys.indexOf(trgt);
        var nextIndex = current + 1;

        scoreNo = scoreNo + 1;
        var wrongBtn = dom.byId('Wrong');
        if (wrongBtn) wrongBtn.setAttribute('value', scoreNo);

        if (nextIndex === keys.length) {
            // Preservado exactamente igual que en el original: `myData`
            // no se declara en este archivo (ver nota al inicio del
            // archivo y el informe). Se asume variable global inyectada
            // por la página.
            Topic.loadData(myData);
        }

        if (finishRoundIfNeeded(nextIndex, keys.length)) {
            nextIndex = 0;
        }

        var next = keys[nextIndex];
        renderCard(next, data.items[next], scoreOk, scoreNo);
    }

    function loadData(file) {
        TopicFile.load(file).then(function (data) {
            currentTopicData = data;
            renderPage(data);
        }).catch(function (error) {
            console.error('Unable to read quiz data', error);
        });
    }

    return {
        renderCard: renderCard,
        renderPage: renderPage,
        nextCardOk: nextCardOk,
        nextCardNo: nextCardNo,
        loadData: loadData
    };
})();

/* ---------------------------------------------------------------------------
 * 13. Wiring de eventos globales de la página (igual que el original)
 * -------------------------------------------------------------------------*/

window.addEventListener('load', function () {
    // Fuente única de verdad para la URL del topic: `window.myData`.
    // view.html ya declara `var myData = '/' + lang + '/' + cat + '/' +
    // set + '.idmnd';` en el <script> inline que se ejecuta justo antes
    // de este listener (y antes de que se dispare 'load'), lo que la
    // convierte en una variable global real (`window.myData`). Antes,
    // este mismo bloque creaba una SEGUNDA copia local ('var myData = ...'
    // leída de #dom-target) que solo usaban los handlers definidos aquí
    // dentro (ToHomeB/ToHomeC/flashdef). Esa copia se quedaba obsoleta
    // cuando TopicFile.resolveFavoriteUrl() reescribía `window.myData`
    // tras resolver un topic "favorito", mientras que Viewer.backCard()
    // y Quiz.nextCardNo() (definidos fuera de este listener) sí leían la
    // versión ya actualizada. Para que todos lean siempre el mismo
    // valor, ya no se declara una copia local aquí: solo se reconstruye
    // `window.myData` desde #dom-target como reserva, por si este
    // archivo se cargara en un contexto donde no estuviera ya definida.
    if (typeof window.myData === 'undefined') {
        var div = document.getElementById('dom-target');
        window.myData = div ? div.textContent : '';
    }

    var el;
    el = document.getElementById('tts'); if (el) el.onclick = function () { if (window.pronounce) window.pronounce(); };
    el = document.getElementById('vtts'); if (el) el.onclick = function () { if (window.pronounce) window.pronounce(); };
    el = document.getElementById('ToHomeB'); if (el) el.onclick = function () { Topic.loadData(myData); };
    el = document.getElementById('ToHomeC'); if (el) el.onclick = function () { Topic.loadData(myData); };
    el = document.getElementById('goBack'); if (el) el.onclick = function (event) {
        event.preventDefault();
        if (window.parent !== window && window.parent.libCloseViewer) {
            window.parent.libCloseViewer();
        } else if (window.parent !== window && window.parent.jQuery && window.parent.jQuery.fancybox) {
            window.parent.jQuery.fancybox.close();
        } else if (el.href) {
            window.location.href = el.href;
        }
        return false;
    };
    el = document.getElementById('flashdef'); if (el) el.onclick = function () { Quiz.loadData(myData); };

    el = document.getElementById('Show'); if (el) el.onclick = function () {
        var srceElement = dom.firstChildOf('#srce');
        var dotsElement = dom.firstChildOf('#dots');
        if (srceElement) srceElement.hidden = false;
        if (dotsElement) dotsElement.hidden = true;
        dom.setStyleText('Show', 'DISPLAY: none;');
        var rightBtn = document.getElementById('Right');
        if (rightBtn) rightBtn.style.right = '25%';
        var wrongBtn = document.getElementById('Wrong');
        if (wrongBtn) wrongBtn.style.left = '25%';
    };
});
