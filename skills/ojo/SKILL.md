---
name: ojo
description: >
  El órgano de visión de Abyss, con ocho verbos — todos a petición explícita del
  usuario en ese turno, ninguno por gancho. Actívala con: "mira por la webcam",
  "haz una foto con la cámara", "qué ves por la cámara ahora mismo" (`mirar`);
  "lee lo que hay en esta foto", "cópiame el texto de la imagen", "qué pone en
  esta foto", "pásalo al portapapeles" (`texto`); "fotocopia esto", "escanea este
  documento", "endereza y limpia esta foto de un papel" (`fotocopia`); "pásame
  los datos de esta tarjeta", "saca el contacto de esta tarjeta de visita"
  (`tarjeta`); "resume este manual", "ordena estas fotos de las instrucciones"
  (`manual`); "haz un despiece de esto", "sepárame esta foto en capas"
  (`despiece`); "un prompt de three.js a partir de esta foto", "qué formas y
  colores tiene esta imagen" (`prompt3d`); "controla el holograma con la mano",
  "arranca el control por gestos" (`gestos`). Y en inglés: "look through the
  webcam", "take a picture with the camera", "what do you see through the
  camera right now" (`mirar`); "read what's in this photo", "copy the text from
  the image", "what does this photo say", "copy it to the clipboard" (`texto`);
  "scan this document", "straighten and clean this photo of a paper" (`fotocopia`);
  "get me the contact info from this business card" (`tarjeta`); "summarize this
  manual", "order these instruction photos" (`manual`); "make an exploded view
  of this", "split this photo into layers" (`despiece`); "a three.js prompt from
  this photo", "what shapes and colors does this image have" (`prompt3d`);
  "control the hologram with my hand", "start hand-gesture control" (`gestos`).
  Ninguno se dispara por gancho ni por iniciativa propia del asistente — una
  cámara que se enciende sola no es un ojo, es vigilancia.
allowed-tools: Bash
---

# ojo

## Qué hace

Ocho verbos en `ojo.py`, un solo punto de entrada:

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/ojo.py" <verbo> [argumentos del verbo] --proyecto "$(pwd)"
```

Salvo `mirar` ("lo de hoy": un fotograma suelto, sin cambios desde antes de
esta tanda), cada verbo **delega entero** en el módulo que de verdad lo
implementa — `ojo.py` no repite ninguna lógica de visión propia, solo
encamina el mismo argv que recibiría ese módulo si se invocara directo:

| verbo | qué hace | delega en |
|---|---|---|
| `mirar` | un fotograma de la webcam (índice, por defecto 0) | — (autónomo, ver abajo) |
| `texto` | OCR: texto plano de una imagen, opcionalmente al portapapeles | `lectura_visual.py` |
| `fotocopia` | endereza/limpia un documento fotografiado o escaneado, guarda PNG o PDF | `lectura_visual.py` |
| `tarjeta` | OCR + patrones sobre una tarjeta de visita → `.vcf` + `.png` compuesta | `lectura_visual.py` |
| `manual` | OCR de varias fotos, ordenadas y limpias, en markdown (sin resumir) | `lectura_visual.py` |
| `despiece` | separa el objeto del fondo y lo reparte en capas (2,5D) para `render3d.py` | `volumen.py` |
| `prompt3d` | mide paleta/proporción/horizonte/formas y escribe un prompt three.js ES/EN | `volumen.py` |
| `gestos` | sirve dedos/pellizco/pose/escala por HTTP local — el estado de la mano, ya traducido. Es el ESPEJO en Python de `abyss/plantillas/gestos_comun.js`, que es la copia que manda; los visores kinéticos usan ese módulo en el navegador y **no** este servidor, que hoy no lo consume nadie | `gestos.py` |

## `mirar`: un fotograma de la webcam (autónomo, sin delegar)

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/ojo.py" mirar [ruta_salida.jpg] [indice_camara] --proyecto "$(pwd)"
```

Abre la cámara indicada (por defecto la 0), descarta los primeros fotogramas
(la exposición tarda en ajustarse) y guarda uno como `.jpg`. Requiere OpenCV
(`cv2`), dependencia **opcional** del paquete — sin ella, «sin cv2: no hay
ojo» y sale con código 1, sin hacer nada más. Sin `ruta_salida`, escribe en
`memory/ojo_AAAAMMDD_HHMMSS.jpg`. Tras guardar el fotograma, léelo con la
herramienta de lectura de imágenes para poder describir lo que muestra — este
verbo solo lo captura, no lo interpreta. Cada captura queda apuntada en
`memory/ojo.log` (cuándo, cámara, tamaño).

## `texto`, `fotocopia`, `tarjeta`, `manual`: lo que el ojo LEE (OCR)

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/ojo.py" texto <imagen> [--portapapeles] [--salida f.txt] --proyecto "$(pwd)"
python "${CLAUDE_PLUGIN_ROOT}/abyss/ojo.py" fotocopia (<imagen>|--camara [indice]) [--escaner] \
    [--salida f.png|f.pdf] [--color|--gris|--umbral] [--paginas n] --proyecto "$(pwd)"
python "${CLAUDE_PLUGIN_ROOT}/abyss/ojo.py" tarjeta <imagen> [--salida base] --proyecto "$(pwd)"
python "${CLAUDE_PLUGIN_ROOT}/abyss/ojo.py" manual <imagen...> [--salida f.md] --proyecto "$(pwd)"
```

Delegan enteros en `lectura_visual.py` (ver su propio docstring
para el detalle completo). Motor de OCR, en
este orden, nunca se instala nada: el de Windows por WinRT (viene ya
instalado con el paquete de idioma del perfil) y, si no, `tesseract` si está
en el PATH. Sin ninguno de los dos: «sin dato: no hay motor OCR» y código 2.

- **`texto`**: líneas en el orden que da el motor; `--portapapeles` lo copia
  ya (`Set-Clipboard` en Windows, `pbcopy`/`xclip` si están en macOS/Linux).
- **`fotocopia`**: **el escáner es el software, no un aparato.** La vía
  normal es una foto — un fichero o `--camara [índice]` (una de las dos,
  obligatoria) — que se endereza (contorno cuadrilátero mayor, o el ángulo
  dominante si no hay uno claro, sin fingir un recorte que no hizo) y corrige
  de iluminación; `--color`/`--gris`/`--umbral` deciden el acabado.
  `--escaner` es una fuente OPCIONAL más, intentada antes: sin escáner
  disponible, «sin escáner: uso la cámara o un fichero» y sigue por la vía
  normal, sin error. `--paginas n` (solo con `--camara`) junta `n` fotogramas
  en secuencia en un solo PDF.
- **`tarjeta`**: teléfono/correo/web por patrones, y nombre/cargo/empresa por
  una heurística de posición y tamaño de letra — lo que no reconoce queda
  vacío, nunca inventado. Escribe `<base>.vcf` (vCard 3.0) y `<base>.png`.
- **`manual`**: ordena por número de página si todas las fotos lo dan, une
  palabras partidas por guion de corte, y reescribe los pasos detectados como
  lista markdown. **No resume** — entrega el texto limpio y ordenado; resumir
  ese texto es cosa del asistente, con el texto delante.

## `despiece`, `prompt3d`: lo que el ojo VE en relieve

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/ojo.py" despiece <imagen> [--capas 4] [--salida escena.json] [--html]
python "${CLAUDE_PLUGIN_ROOT}/abyss/ojo.py" prompt3d <imagen> [--salida f.txt] [--escena f.json]
```

Delegan enteros en `volumen.py`. **No es
reconstrucción 3D**: todo sale de heurísticas declaradas sobre una sola foto
2D, nunca de una cámara estéreo ni de un sensor de profundidad.

- **`despiece`**: separa el objeto del fondo con GrabCut y reparte el primer
  plano en capas por una heurística de nitidez+luminancia (lo enfocado y
  luminoso suele estar delante en una foto bien compuesta — nunca una medida
  de distancia real); escribe una `escena.json` de planos texturizados que
  `render3d.py` abre con su deslizador de explosión. `--html` además escribe
  esa página, con un aviso fijo de que es 2,5D, no 3D. **Esto es lo VIEJO y lo
  PEOR**: separa por nitidez, no por componente real, así que dos piezas
  igual de enfocadas quedan en la misma capa aunque sean objetos distintos.
  Para separar los COMPONENTES REALES de una foto (regiones puestas a mano +
  GrabCut, sin adivinar por nitidez) y manejarlos en 3D con la mano por la
  cámara, ver la skill `kinetica` — no esta.
- **`prompt3d`**: mide paleta dominante (k-medias), proporción del objeto,
  horizonte (si hay uno claro) y formas dominantes por circularidad de
  contorno, y escribe un prompt de diseño ES/EN para three.js con esos
  números — nunca adivina qué es el objeto, dice qué midió.
- **DEPENDENCIA obligatoria**: OpenCV (`cv2`) y `numpy`. Sin ellas, «sin
  dato: pip install opencv-python numpy» y código 2 — nunca se instala nada.

## `gestos`: la mano manda en el holograma

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/ojo.py" gestos [--camara 0] [--puerto 8799] \
    [--escena f.json] [--holograma] [--vocabulario f.json]
```

Delega entero en `gestos.py`. MediaPipe lee
21 puntos por mano; el vocabulario es **propio de este paquete**, no el de
ningún tutorial ajeno: número de dedos aísla capas del despiece, pellizco
desliza la explosión, pose de la palma orbita la cámara, la palma abierta y
sin moverse durante `segundos_captura_quieta` (**1,0 s** por defecto,
cambiable con `--vocabulario`) marca `gesto_completado` = `"captura"`, dos
manos escalan. Ojo con la de la palma quieta: `gestos.py` **publica ese campo
en su JSON y nada más** — no escribe imagen alguna, y hoy ningún programa lee
ese estado (la página de `render3d.py` no lo sondea). Sirve el estado por HTTP
**SOLO en `127.0.0.1`** — nunca fuera de la máquina. **DEPENDENCIA**:
`mediapipe` (y `opencv-python` para la cámara); sin ellas, dice exactamente
qué instalar y sale con código 2. Este verbo se queda corriendo hasta que se
interrumpe (`Ctrl+C`): úsalo solo cuando el usuario quiera de verdad leer el
estado de su mano, no como paso intermedio de otra tarea.

**Dónde SÍ mueve algo este vocabulario**: en el visor de la skill `kinetica`,
que lo reimplementa aparte, dentro del navegador (MediaPipe Tasks Vision
servido en local), sin llamar a `gestos.py`. Allí los dos vocabularios ya han
divergido: la mano abierta y quieta 3 s abre un **holograma** del producto
montado sobre la propia palma, con fondo transparente y anclado a tres puntos
de la mano — la pantalla dice que es un montaje sobre el vídeo, no una medida
del espacio — y, dentro de él, cerrar la mano 0,6 s abre
el sitio oficial del producto **solo si la ficha trae reconocimiento con
evidencia**: sin reconocimiento no hay enlace, y el visor escribe el motivo.
Para eso, `kinetica`, no este verbo.

## Cómo se ejecuta

Ver el bloque de cada verbo arriba. `--proyecto "$(pwd)"` (o `ABYSS_PROYECTO`)
hace falta porque este guion se invoca siempre a mano — nunca hay stdin de un
gancho; si falta, `rutas.resolver()` avisa por stderr y sale.

## Qué devuelve

`mirar` imprime la ruta del `.jpg` (o el mensaje de error). Los demás verbos
imprimen exactamente lo que imprime su módulo delegado — el propio JSON o
mensaje de `lectura_visual.py`/`volumen.py`/`gestos.py`, y el mismo código de
salida: `ojo.py` no lo reformatea ni lo suaviza.

## Qué sale de la máquina

Nada por red, en ningún verbo. `mirar`/`texto`/`fotocopia`/`tarjeta`/`manual`/
`despiece`/`prompt3d` son locales de principio a fin (OCR por WinRT o
`tesseract`, ambos locales; GrabCut y k-medias son cálculo local). `gestos`
sirve HTTP solo en `127.0.0.1`: nadie fuera de la máquina puede leerlo.

## Límites honestos

- `mirar` depende de OpenCV, no incluido por defecto; sin él, no hace nada.
- El resto de verbos heredan EXACTAMENTE los límites de su módulo delegado —
  no se repiten aquí para no desincronizarse; ver `lectura_visual.py`,
  `volumen.py` y `gestos.py` (y sus skills, si hace falta más detalle).
- `despiece`/`prompt3d` no reconocen objetos: miden geometría y color de la
  silueta 2D, nunca dicen "esto es una taza".
- `despiece` separa por nitidez+luminancia, NO por componente real — es la
  vía vieja y peor para "quiero ver las piezas reales de esto"; esa tarea es
  de la skill `kinetica` (regiones puestas a mano + GrabCut + mano por la
  cámara), no de `ojo`.
- `manual` no resume: entrega texto limpio y ordenado, no una síntesis.
- `gestos` se queda corriendo (servidor HTTP + bucle de cámara) hasta que se
  interrumpe — no es un comando que "termina y devuelve un resultado" como
  los demás verbos.
- `gestos` sirve el estado, pero **nada lo consume**: la página de
  `render3d.py` no lee `/estado` ni reacciona, y `gestos.py` no escribe
  ninguna imagen — el campo `gesto_completado` es una etiqueta, no un efecto.
  El único sitio donde este vocabulario mueve algo de verdad hoy es el visor
  de la skill `kinetica`, que lo reimplementa en el navegador por su cuenta.

## Reglas SGICP de esta pieza

- **Nunca por gancho**: es la única familia de verbos del paquete para la que
  la ley no es "cómo medir" sino "cuándo no disparar". El consentimiento del
  turno actual es la condición, no una preferencia guardada ni un patrón
  detectado en el mensaje — ni para `mirar`, ni para `fotocopia --camara`, ni
  para `gestos`.
- **Delegar sin repetir**: `ojo.py` no reimplementa OCR, despiece ni gestos —
  cada verbo (salvo `mirar`) es un encaminador hacia el módulo que ya tiene
  su propia batería, con el mismo argv y el mismo código de salida.
