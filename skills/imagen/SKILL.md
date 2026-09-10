---
name: imagen
description: >
  Generar una imagen por texto (cascada de proveedores), pintar una foto como un
  cuadro de pinceladas totalmente local con varios estilos (óleo, impresionista,
  acuarela, pastel, carbón, tinta), animar esas pinceladas en vídeo, buscar una
  imagen ya hecha con licencia libre o un motivo del mundo real (museos, Street
  View, webcams), renderizar una escena o modelo 3D con vista explosionada, u
  operar con imágenes reales (fundir, collage, restaurar, pintar por números,
  borrar un objeto) sin ningún modelo. Actívala con: "crea una imagen de…",
  "genera una foto de…", "pinta esta foto", "haz un cuadro de esta imagen",
  "píntalo como acuarela", "más pastel", "con pinceles gordos y pocas
  pinceladas", "hazlo a carboncillo", "anímalo en vídeo", "busca una imagen
  libre de…", "busca un motivo del mundo real de…", "fusiona estas fotos",
  "haz un collage con estas imágenes", "doble exposición de estas dos fotos",
  "restaura esta foto vieja", "pintar por números", "borra este objeto de la
  foto", "haz un render 3D de…", "vista explosionada de…", "renderiza este
  modelo", "create an image of…", "generate a picture of…", "paint this
  photo", "turn this into a painting", "paint it as watercolor", "more
  pastel-like", "thick brushes, few strokes", "make it charcoal", "animate the
  brushstrokes into a video", "find a freely-licensed image of…", "find a
  real-world subject of…", "blend these photos", "make a collage", "restore
  this old photo", "paint by numbers", "remove this object from the photo",
  "render this model", "exploded view", "render this 3D scene". Solo a
  petición explícita del usuario — ningún gancho la dispara.
allowed-tools: Bash
---

# imagen

Seis verbos en `imagen.py` (`crear`, `pintar`, `video`, `buscar`, `render`,
`mundo`), más `pintor.py`/`video_pintura.py`/`render3d.py`/`mundo.py` por
debajo, y `lienzo.py`/`taller.py` al lado para operar con imágenes reales sin
ningún modelo generativo.

## `crear`: texto → imagen, por cascada de proveedores

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/imagen.py" crear "lo que quieres ver" [salida.png] \
    [--ancho N] [--alto N] [--semilla N] [--via local|pollinations|cloudflare|together|huggingface|horde] \
    --proyecto "$(pwd)"
python "${CLAUDE_PLUGIN_ROOT}/abyss/imagen.py" vias --proyecto "$(pwd)"   # qué proveedores están configurados
```

`crear` recorre esta cascada y se queda con el **primer** proveedor que
devuelva una imagen:

1. **`local`**: tu propio servidor de imagen (A1111/Forge/SD.Next, o
   compatible con la API de imágenes de OpenAI — p. ej. `stable-diffusion.cpp`).
   Es la **única** vía en la que el prompt no sale de tu máquina.
2. Proveedores con clave propia, en el orden que fijes en
   `memory/imagen_config.json` (nunca en el código ni en el repo):
   `pollinations` (gen.pollinations.ai — exige clave desde 2026, ya no es
   anónimo), `cloudflare` (Workers AI, FLUX.1-schnell), `together`
   (FLUX.1-schnell-Free), `huggingface` (router de Hugging Face,
   FLUX.1-schnell).
3. **`horde`**: AI Horde (aihorde.net) con la clave anónima pública, sin
   registro. **Si no configuras ninguna clave, esta es la única vía que
   funciona**: cola de voluntarios con prioridad mínima, el prompt se procesa
   en una máquina de un tercero, y la imagen final se descarga de un host de
   almacenamiento que en algunas redes queda bloqueado (la generación puede
   completarse y aun así fallar la descarga).

Con cualquier vía que no sea `local`, el texto del prompt viaja a un servidor
ajeno; ningún proveedor de la lista documenta en una página legible cuánto
tiempo guarda ese prompt. Cada intento se apunta en `memory/imagen.log`
(cuándo, vía, bytes, ruta, prompt recortado — nunca la clave usada). Las
imágenes van a `memory/imagenes/` salvo que se indique una salida.

## `buscar`: encontrar una imagen ya hecha, con licencia libre

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/imagen.py" buscar "texto" [--n 5] \
    [--fuente openverse|commons|ambas] [--descargar] --proyecto "$(pwd)"
```

Busca en Openverse y Wikimedia Commons (sin clave; medido 6-sep: ambas
responden 200 en ~0,6 s) e imprime, por resultado, título, autor, licencia y
URL. Con `--descargar` guarda la PRIMERA en `memory/imagenes/` junto a un
`.txt` con la atribución completa (título, autor, licencia, fuente, página de
origen, URL de la imagen).

**Decisión del usuario (7-sep): `buscar` SOLO busca y trae con atribución —
NO monta, NO compone ni entiende la escena.** Si quien pregunta quiere una
escena con varios elementos ("un pájaro azul sobre una rama al atardecer"),
`buscar` no es la herramienta: eso es lo que hace `crear`, con su propia
cascada de proveedores. `buscar` sirve para "tráeme UNA foto libre de X", no
para montar una composición — para montar varias imágenes ya encontradas,
está `lienzo.py collage` (recorta y sobreimprime, no entiende la escena).

El TEXTO de la búsqueda viaja a Openverse/Wikimedia Commons (nunca a los
proveedores de `crear`); con `--descargar`, además se descarga la imagen
elegida desde el host que indique cada banco.

## `pintar`: foto → cuadro de pinceladas, 100% local

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/imagen.py" pintar <foto> [salida_dir] \
    [--ancho N] [--alta] [--suave [2]] [--acabado] [--html] \
    [--estilo oleo|impresionista|acuarela|pastel|carbon|tinta] \
    [--radios a,b,c] [--umbral a,b,c] [--longitud a,b,c] [--alfa N] \
    [--jitter-color N] [--jitter-rumbo N] [--papel #rrggbb] \
    [--saturacion N] [--luz N] [--mezcla-blanco N] --proyecto "$(pwd)"
```

Delega en `pintor.py` (método Hertzmann simplificado: capas de pincel grueso a
fino, cada una difumina la referencia a ese radio, mide el error contra el
lienzo y pinta donde el error supera el umbral de la capa, perpendicular al
gradiente). Nada sale de la máquina: depende solo de Pillow + numpy
(`ModuleNotFoundError` si faltan — sin fallback silencioso), dependencias
**opcionales** del paquete.

**`--estilo`** (motor único: el mismo bucle de siempre con otro dict de
parámetros, no un algoritmo distinto) — "más pinceladas gordas", "más vivo",
"a carboncillo" son pedidos de estilo, no de código nuevo:

| estilo (petición típica) | pinceladas frente a óleo | rasgo |
|---|---|---|
| `oleo` (por defecto) | — | opaco, papel oscuro de fábrica |
| `impresionista` ("pinceladas sueltas y vivas") | menos, más grandes | jitter de color y rumbo, saturación alta |
| `acuarela` ("como una acuarela", "más transparente") | bastantes menos | capas por alfa (transparencia real), papel claro |
| `pastel` ("más suave, tonos pastel") | menos | mezcla con blanco, saturación baja |
| `carbon` ("a carboncillo", "el David a carbón") | pincel muy fino | sin color (gris), tramado a 45° + esfumino final |
| `tinta` ("a tinta", "blanco y negro con trazo") | pocas, solo 2 radios | sin color, deja blanco puro donde no hay trazo |

Cualquier bandera suelta (`--radios`, `--umbral`, `--longitud`, `--alfa`,
`--jitter-color`, `--jitter-rumbo`, `--papel`, `--saturacion`, `--luz`,
`--mezcla-blanco`) pisa SOLO esa clave del estilo elegido — "más pinceles
gordos y pocas pinceladas" es `--estilo oleo --radios 40,24,14 --umbral
70,55,42`, no un estilo aparte. El `.json.gz` de trazos guarda el estilo, el
papel y el alfa, así que `video` reproduce el mismo cuadro (mismo fondo, misma
composición por capas).

Escribe siempre tres ficheros:
- `<base>_pintada.png` — el cuadro.
- `<base>_trazos.json.gz` — todas las pinceladas (de aquí sale el vídeo).
- con `--html`: `<base>_pintor.html` — repinta las pinceladas en el navegador
  con control de velocidad (solo pinceles ≥2 px para que pese poco).

Coste de las opciones, medido:
- **`--alta`**: resolución nativa (tope 3000 px) y pincel de 1 px — tarda
  minutos y el `.json.gz` puede pasar de 10 MB. Sin ella: 1400 px, pincel
  mínimo de 2 px, menos de un minuto.
- **`--suave [N]`**: pinta a N veces el tamaño (2 por defecto) y reduce al
  final — sin dientes de sierra, pero cuesta del orden de N² más en el dibujo.
- **`--acabado`**: capa final de 1 px con umbral más bajo que repasa lo que
  quedó sin cubrir.

Si la foto no existe o no se puede leer, la CLI imprime `sin cuadro: <motivo>`
y sale con código 2 — nunca una traza cruda.

## `video`: anima esas pinceladas

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/imagen.py" video <trazos.json.gz> <salida.mp4> \
    [--segundos 9] [--ancho 1080] [--fps 30] [--foco x,y[;x,y]] [--retrato] [--suave [2]] \
    --proyecto "$(pwd)"
```

Ritmo variable: despacio al principio (pinceles gruesos, se ve nacer la
imagen), rápido en el relleno, despacio al final (detalles). `--foco` decide
qué puntos se pintan los últimos en la capa fina; `--retrato` es un atajo para
dos ojos centrados. Depende de Pillow + `imageio-ffmpeg` (opcional); sin ella,
`sin video: <motivo>` con código 2, nunca una traza.

## `render`: escena o modelo 3D → página con three.js, y de ahí al pintor

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/imagen.py" render <modelo.glb|.gltf|.obj|.stl|escena.json> \
    [--html [salida.html]] [--png [salida.png]] [--explosion N] \
    [--camara x,y,z] [--mirar x,y,z] [--fondo #rrggbb] [--luz calida|fria|neutra] \
    [--ancho N] [--alto N] \
    [--pintar [--estilo oleo|impresionista|acuarela|pastel|carbon|tinta] [--alta] [--acabado] [--suave [2]]] \
    --proyecto "$(pwd)"
```

Actívalo con "haz un render 3D de…", "vista explosionada de…", "renderiza
este modelo", "render this model", "exploded view". Delega en
`render3d.renderizar()`: escribe SIEMPRE una página autocontenida con
three.js **embebido** (`abyss/vendor/three.min.js`, MIT, sin red para verla) —
órbita, luces, rejilla y alambre opcionales, planos de corte, y un deslizador
de **vista explosionada** (cada malla se aleja del centro de la escena según
su centroide y su grupo). Acepta `escena.json` (piezas declaradas: caja,
cilindro, esfera, texto, plano — para diagramas sin CAD) o un modelo real
(`.glb`/`.gltf`/`.obj`/`.stl`).

- **`--png`**: además de la página, una captura con un navegador sin cabeza
  (Edge o Chrome en Windows; `google-chrome`/`chromium` en Linux/macOS). Sin
  uno encontrado: `sin dato: no hay navegador sin cabeza`, código 2 — la
  página HTML se ha escrito de todas formas.
- **`--pintar`**: encadena render → PNG → `pintor.pintar(..., estilo=…)` (fuerza
  `--png` aunque no se pida, porque hace falta una imagen de la que partir).
  Las banderas de estilo son las mismas que en `pintar` (ver arriba). Las DOS
  salidas (el render y el cuadro) quedan apuntadas en `memory/imagen.log`.
- **Límites honestos**: visor y editor de vistas, **no un modelador** (no
  repara mallas, no simplifica, no exporta). La explosión exige piezas YA
  separadas en el fichero de entrada — un `.stl` de una sola malla no tiene de
  qué separarse. La página pesa lo que pesa three.js embebido más la
  geometría de la entrada.

## `mundo`: motivos DEL MUNDO REAL para pintar (museos, calle, cámaras en vivo)

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/imagen.py" mundo "<motivo>" \
    [--fuente met|artic|commons|streetview|mapillary|webcam|todas] [--n 5] [--descargar] \
    [--lugar lat,lon --rumbo N --inclinacion N --campo N] --proyecto "$(pwd)"
```

Actívalo con "busca un motivo del mundo real de…", "encuentra una vista a pie
de calle de…", "find a real-world subject of…". Delega ENTERO en `mundo.py`:
seis fuentes, tres sin clave y tres con clave/token propios en
`imagen_config.json`:

| fuente | qué da | clave |
|---|---|---|
| `met` | obras del Metropolitan, dominio público | ninguna |
| `artic` | obras del Art Institute of Chicago, dominio público | ninguna |
| `commons` | la obra o el LUGAR en alta resolución, con licencia | ninguna |
| `streetview` | vista a pie de calle (Google Street View) | `google_maps_key` |
| `mapillary` | vista a pie de calle, CC BY-SA | `mapillary_token` |
| `webcam` | una cámara pública EN DIRECTO (Windy) | `windy_key` |

Sin la clave/token de una fuente, esa fuente **nunca toca la red**: avisa
`sin clave: …` (nunca una traza) y sencillamente no aporta candidatos — igual
que los proveedores sin configurar de `crear`. `--lugar lat,lon` fija el
punto para `streetview`/`mapillary`/`webcam`; si no se da, `mundo.py` intenta
derivarlo de Wikidata + Wikipedia a partir del propio `motivo` (si el motivo
es un lugar reconocible) — y si tampoco eso trae coordenadas, esa fuente se
avisa `sin lugar: …` sin inventar un punto. Con `--descargar` guarda la
PRIMERA en `memory/imagenes/` junto a un `.txt` de atribución completa (mismo
patrón que `buscar`). **Sin combinar ni componer** (igual que `buscar`): el
motivo se pinta tal cual llega, o se esboza en el taller y se pinta.

## `lienzo.py`: el estudio del pintor sin modelo

Operar con imágenes REALES — nunca genera nada nuevo, nunca entiende la
escena — con Pillow + numpy (OpenCV opcional, solo para ruido/arañazos/relleno/
zonas conexas: todo funciona sin él, más lento o con menos pasos, y lo dice).
Ningún prompt: son operaciones deterministas sobre los píxeles que se le den.

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/lienzo.py" fundir <a> <b> \
    [--modo mezcla|multiplicar|pantalla|superponer|luz_suave] [--alfa 0.5] \
    [--mascara degradado_h|degradado_v|radial|<png>] [--salida f.png]
python "${CLAUDE_PLUGIN_ROOT}/abyss/lienzo.py" doble <a> <b> [--alfa 0.5] [--salida f.png]
python "${CLAUDE_PLUGIN_ROOT}/abyss/lienzo.py" collage <img1> <img2> ... \
    [--columnas N] [--ancho 1920] [--margen 12] [--fondo #111111] [--salida f.png]
python "${CLAUDE_PLUGIN_ROOT}/abyss/lienzo.py" degradado <img> \
    [--direccion abajo|arriba|izq|der|radial] [--color #000000] [--desde 0.6] [--salida f.png]
python "${CLAUDE_PLUGIN_ROOT}/abyss/lienzo.py" restaurar <foto> \
    [--salida f.png] [--sin-aranazos] [--nitidez 1.0] [--color auto|no]
python "${CLAUDE_PLUGIN_ROOT}/abyss/lienzo.py" numeros <foto> \
    [--colores 12] [--ancho 1400] [--min-zona N] [--salida base]
python "${CLAUDE_PLUGIN_ROOT}/abyss/lienzo.py" borrar <img> \
    (--caja x,y,w,h | --mascara m.png | --color #rrggbb[,tolerancia]) \
    [--metodo telea|ns|taller] [--salida f.png]
python "${CLAUDE_PLUGIN_ROOT}/abyss/lienzo.py" cubista <foto> \
    [--facetas 220] [--desplazamiento 0.07] [--giro 7] [--sin-contorno] \
    [--pasos N --pasos-dir DIR] [--salida f.png]
python "${CLAUDE_PLUGIN_ROOT}/abyss/lienzo.py" surrealista <foto> \
    [--fuerza 26] [--escala 90] [--viraje 42] [--pasos N --pasos-dir DIR] [--salida f.png]
```

- **`fundir`**: `b` al tamaño de `a`, combinada con un modo de mezcla clásico;
  `--mascara` sustituye el `--alfa` global por un mapa por píxel (dos
  degradados y un radial generados aquí, o un PNG en gris propio).
- **`doble`**: exposición doble real (reparte pantalla/mezcla según la
  luminancia de `a`) — heurística declarada, no una simulación óptica.
- **`collage`**: rejilla estricta con `--columnas`, o mosaico "a la Flickr"
  justificado por filas sin `--columnas`.
- **`degradado`**: funde la foto hacia un color en un borde — para cabeceras y
  portadas donde el texto va sobre el degradado, no sobre la foto.
- **`restaurar`**: reduce ruido PRIMERO (con fuerza proporcional al ruido
  medido a la entrada — antes de estirar niveles, que si no amplifica el
  grano tanto como el contraste: fallo MEDIDO 7-sep, el ruido de una foto real
  subía de 43.69 a 83.88 con el orden viejo), niveles automáticos por
  percentil, corrección de dominante de color (lleva la media a gris neutro,
  **no** recupera el tono original), arañazos (`cv2.inpaint` sobre una
  máscara heurística de líneas finas — sin OpenCV, `--sin-aranazos` avisa y
  se salta ese paso), nitidez por máscara de desenfoque. Imprime contraste y
  ruido antes/después con una vara que no cambia de escala con el contraste
  (percentil 20 de la desviación local en bloques fijos de 8 px); si el
  ruido no baja, lo dice («ruido no reducido») en vez de imprimir la subida
  como un logro. **No reconstruye caras ni detalle perdido** — eso pide un
  modelo generativo, y esta pieza no tiene ninguno.
- **`numeros`** ("pintar por números"): cuantiza a `--colores` tonos, limpia
  el ruido con un filtro de moda ANTES de agrupar en zonas conexas (si no,
  cada mota de ruido nace como su propia zona — fallo MEDIDO 7-sep: una foto
  real de 768×768 daba 24157 zonas), funde cada zona menor que `--min-zona`
  con la vecina con la que comparte más frontera hasta que no queda ninguna
  chica, numera las que quedan y escribe la paleta al pie. Sin `--min-zona`,
  el umbral sale proporcional al área (0,05 % del lienzo) en vez de un número
  fijo — con esa foto real, 208 zonas, bien por debajo de las mil. Dos
  ficheros, y el nombre depende de si se da `--salida`: sin ella,
  `<foto>_numeros_plantilla.png` (para pintar) y `<foto>_numeros_color.png`
  (referencia coloreada); con `--salida <base>`, `<base>_plantilla.png` y
  `<base>_color.png` (sin el `_numeros` de más).
- **`borrar`** (petición del usuario, 6-sep: borrar objetos): rellena la zona
  marcada con `cv2.inpaint`, probando `telea` y `ns` y quedándose con el que
  deje menos discontinuidad de borde (lo dice: `metodo_usado` en el JSON
  puede no ser el `--metodo` pedido) — sin OpenCV, «sin dato: pip install
  opencv-python». **Límite medido**: vale para objetos FINOS sobre fondo con
  textura regular (postes, cables, manchas) o fondos casi uniformes — sobre
  objetos grandes o fondos con estructura deja un borrón visible. Antes de
  rellenar mide el área de la máscara y la textura del anillo de fondo
  alrededor de ella; si el área supera el 1 % de la imagen o el anillo tiene
  más textura que el resto, avisa («borrón probable…», y lo deja en el JSON
  como `aviso`) y hace falta `--metodo taller` (ver abajo) — con `--metodo
  taller` no avisa, porque ya es el recomendado.
- **`cubista`/`surrealista`** (petición del usuario, 9-sep: "dos estilos
  pictóricos nuevos" — cubismo y surrealismo NO son otra pincelada de
  `pintor.py`, son otra COMPOSICIÓN de la imagen entera; ver el docstring de
  `lienzo.py` para el porqué viven aquí y no ahí). `cubista`: triangulación
  de Delaunay sembrada en los bordes reales de la foto (`cv2.Canny` +
  `cv2.Subdiv2D`), cada faceta aplanada a su color medio y desplazada/girada
  un poco alrededor de su centro, de mayor a menor área, sobre un fondo
  difuminado (sin OpenCV, cae a una rejilla triangular con jitter — declarado
  como lo que es, no una Delaunay real). `surrealista`: campo de
  deformación de baja frecuencia (deshace las formas sin romperlas) más un
  viraje de tono HSV. Los dos aceptan `--pasos N --pasos-dir DIR` para
  escribir una progresión de fotogramas (facetas reveladas de mayor a menor,
  o el campo/viraje interpolado de 0 a su fuerza completa) que
  `video_composicion.py` convierte en `.mp4` — ver más abajo.

`lienzo.py` no toca `memory/` ni resuelve un proyecto para `fundir`/`doble`/
`collage`/`degradado`/`restaurar`/`numeros`/`borrar --metodo telea|ns`/
`cubista`/`surrealista`: nada sale de la máquina. Solo `borrar --metodo
taller` lee `taller_url` de `memory/imagen_config.json` y manda
imagen+máscara a esa URL (local: no sale de la máquina) — sin esa clave
configurada, «sin dato».

### `video_composicion.py`: el vídeo del proceso de `cubista`/`surrealista`

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/video_composicion.py" <pasos_dir> <salida.mp4> \
    [--segundos 8] [--fps 30] [--hold-ini 0.6] [--hold-fin 1.6] [--ancho N]
```

Hermano de `video_pintura.py` (que hace lo mismo para los trazos de
`pintor.py`) pero para las carpetas de `paso_*.png` que escriben `lienzo.py
cubista`/`surrealista --pasos`: como cada paso ya es una imagen entera (no
una pincelada con un radio que pesar), el ritmo es sencillo — reparto igual
entre pasos, con un `hold` fijo al principio y al final. Depende de
`imageio_ffmpeg` (la misma dependencia opcional que ya necesita
`video_pintura.py`); sin ella, o sin ningún `paso_*.png` en `pasos_dir`,
«sin video: ...» y código 2.

## `taller.py`: un servidor local de texto→imagen (opcional, pesado)

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/taller.py" [--puerto 7860] [--modelo Lykon/dreamshaper-8] \
    [--cache-dir <ruta>] [--dispositivo auto|cuda|mps|cpu] [--pasos 20]
```

Un servidor mínimo (`http.server` de la biblioteca estándar, sin FastAPI) que
sirve `GET /health` y `POST /sdapi/v1/txt2img` con la misma forma que un
A1111/Forge real — es exactamente lo que `imagen.py crear --via local` espera
encontrar, y lo que `lienzo.py borrar --metodo taller` necesita para objetos
grandes (aunque el `img2img` con máscara que ese verbo pide **no está
implementado aquí todavía** — hace falta un A1111/Forge real, o ampliar este
mismo servidor). Necesita `diffusers` + `torch` (no vienen con el paquete: el
propio guion imprime el `pip install` exacto si faltan, y sale con código 2 —
nunca instala nada por su cuenta). El modelo se descarga de Hugging Face al
PRIMER uso; en CPU, cada imagen tarda MINUTOS, no segundos. VRAM: no medida
en la máquina de desarrollo (sin GPU CUDA ahí) — no se afirma una cifra sin
haberla medido de verdad.

Este servidor nunca se arranca solo: es el usuario quien lo levanta a mano
cuando quiere una vía local de verdad, en su propia máquina.

## Ojo aparte

`ojo.py` (webcam) es una pieza distinta — ver la skill `ojo` — y nunca se
dispara desde aquí ni por gancho: solo a petición explícita en ese turno.

## Límites honestos

- Ninguna vía de `crear` que no sea `local` mantiene el prompt en la máquina.
- AI Horde puede completar la generación y aun así fallar la descarga final en
  redes que bloquean su host de almacenamiento.
- `buscar` no monta ni compone: para una escena con varios elementos concretos
  usa `crear`, no `buscar` + collage a mano.
- `lienzo.py restaurar` no reconstruye caras ni detalle que la foto ya perdió;
  la corrección de dominante lleva la foto a gris neutro, no a su color
  original.
- `lienzo.py borrar` sin `--metodo taller` deja un borrón visible en objetos
  grandes o fondos con estructura (medido, no solo declarado) — por eso avisa
  («borrón probable…») cuando el área o la textura del fondo lo sugieren, en
  vez de dejar que el borrón aparezca sin más.
- `taller.py` no implementa `img2img` con máscara todavía: sirve para la vía
  `local` de `crear` (`txt2img`), pero no completa por sí solo
  `lienzo.py borrar --metodo taller` sin un A1111/Forge real detrás.
- `render` es un visor y editor de vistas, **no un modelador**: no repara
  mallas, no simplifica, no exporta. La vista explosionada exige piezas YA
  separadas en el fichero de entrada — un `.stl` de una sola malla no
  explosiona nada, porque no hay de qué separarlo.
- `render --png` (y por tanto `render --pintar`, que lo fuerza) necesita un
  navegador sin cabeza (Edge/Chrome en Windows, `google-chrome`/`chromium` en
  Linux/macOS) — **dependencia opcional del sistema**, no de pip: sin uno,
  `sin dato: no hay navegador sin cabeza` y código 2; la página HTML se
  escribe de todas formas, con o sin navegador.
- `mundo` no monta ni compone (igual que `buscar`): trae el motivo tal cual
  llega de la fuente elegida. Las tres fuentes con clave (`streetview`,
  `mapillary`, `webcam`) **nunca tocan la red** sin su clave/token propios en
  `imagen_config.json` — avisan `sin clave: …`, nunca una traza.

## Reglas SGICP de esta pieza

- **Fail-closed, nunca inventar**: si ninguna vía de la cascada responde,
  `crear` falla con el motivo de cada intento — nunca entrega una imagen
  degradada o simulada como si fuera un resultado real. `buscar` y `mundo`
  hacen lo mismo: si ninguna fuente responde, lo dicen con el motivo de cada
  una; `render` que necesita `--png` y no encuentra navegador dice «sin dato»
  en vez de fingir una captura.
- **Medir, no decretar**: el coste de `--alta`/`--suave`/`--acabado` en
  `pintar` está dicho arriba porque se midió, no porque "suene razonable"; el
  límite de `lienzo.py borrar` (objetos pequeños sí, grandes no sin taller)
  también está medido en la prueba de este paquete, no solo declarado; los
  tiempos de `render --png` y el umbral de PNG "en blanco" están medidos en
  `render3d.py`, no supuestos.
