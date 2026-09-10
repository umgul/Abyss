---
name: kinetica
description: >
  Ver por dentro un objeto fotografiado: separa sus COMPONENTES REALES a partir
  de UNA foto (nunca capas de nitidez), los despieza en 3D dentro de un cubo
  invisible con three.js y deja que la mano los maneje mirando la cámara. El
  usuario solo pone la foto: mirarla, escribir las regiones de cada pieza,
  quitar el fondo y buscar en la web los datos de cada parte con su fuente lo
  hace esta skill.
  Actívala con: "haz un despiece de verdad de esto", "sepárame las piezas
  reales de este objeto y déjame moverlas con la mano", "quiero ver por dentro
  esta foto", "abre esta foto como un despiece en 3D que pueda mover con la
  mano", "mira cada pieza una a una con la cámara". Y en inglés: "take this
  photo apart into its real components", "let me handle the real parts of this
  with my hand", "show me what's inside this photo", "open this as a
  hand-controlled 3D exploded view", "look at each piece one by one with my
  hand". Se distingue de `ojo despiece` (heurística de nitidez, 2,5D, sin
  cámara ni mano) y de `imagen render --explosion` (una escena o modelo YA
  separado en piezas; aquí las piezas salen de reconocer una foto real). Nunca
  adivina qué es el objeto ni mide profundidad real: solo si se pide, y solo
  con lo que se lee o se ve EN LA FOTO, anota un reconocimiento con su
  evidencia. La cámara para manejarlo solo se enciende a petición explícita de
  este turno — nunca por gancho.
allowed-tools: Bash
---

# kinetica

## Qué hace

Coge UNA foto de un objeto compuesto (una herramienta con su mango y su
cabezal, un aparato con su carcasa y su pieza interior…) y la convierte en una
carpeta lista para un visor 3D que la mano maneja por la cámara — separando
sus **componentes reales**, no capas de nitidez como el viejo `ojo
despiece`/`volumen.py`. Una sola llamada monta la carpeta y, salvo que se pida
lo contrario, arranca el visor:

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/kinetica.py" <foto> [--regiones f.json] [--fichas f.json] \
    [--salida DIR] [--puerto 8811] [--sin-abrir] [--solo-montar] [--rellenar] \
    [--quitar-fondo] [--reconocer [--permitir-nombre-fichero] | --reconocimiento f.json]
```

De dónde sale cada cosa, sin adornos:

- **Con `--regiones f.json`** (recomendado, y **lo escribes tú**: ver «La
  receta entera» más arriba): QUÉ pieza hay y DÓNDE está lo decide quien mira
  la foto — reconocimiento asistido, declarado como tal, nunca un detector
  entrenado. Es texto legible:
  se puede leer y discutir antes de correr el guion. El **borde** de cada
  pieza sí es medido: `cv2.grabCut` sembrado con la máscara de ese polígono
  (su interior erosionado = "primer plano seguro", fuera de una holgura =
  "fondo seguro", el resto = "probable"; el núcleo y la holgura escalan al
  18% y al 6% del lado corto de CADA región, no son constantes fijas). Los
  **solapes** se resuelven por `prioridad`, con las MÁSCARAS reales ya
  calculadas por GrabCut — nunca con los polígonos crudos: una pieza puede
  declararse con un polígono generoso (su silueta entera, aunque otra la
  tape) y solo pierde los píxeles que esa otra ocupa DE VERDAD.
- **Sin `--regiones`**: separación AUTOMÁTICA por componentes conexos del
  primer plano (GrabCut con un rectángulo + `connectedComponents`, quedándose
  con los mayores que superen el 1% del área de la foto). El guion lo avisa
  por pantalla y en `piezas.json` (`procedencia.modo`): las piezas se llaman
  `auto_1`, `auto_2`… y su título dice explícitamente "sin nombre real" — este
  camino **nunca finge** haber reconocido el objeto, y el resultado es peor
  que dando regiones a mano. El rumbo de cada pieza automática es solo el
  vector del centro de la foto a su centroide (heurística de "hacia fuera",
  no un eje de montaje real).
- **`--rellenar`** (solo tiene efecto con `--regiones`): los píxeles que una
  pieza tenía tapados por otra de más prioridad se reconstruyen con
  `cv2.inpaint` (Telea) — son píxeles INVENTADOS, no fotografiados; la cuenta
  queda en `relleno_px` de cada pieza. Sin ella, esos huecos quedan
  transparentes (alfa 0). En modo automático no aplica (los componentes
  conexos no se solapan entre sí) y, si se pide de todas formas, se avisa y se
  ignora.
- **`--quitar-fondo`**: quita el fondo de la foto ANTES de separar, en local,
  con `abyss/fondo.py` — y así la silueta del objeto no se estima, se MIDE.
  Ver el apartado "El fondo" más abajo: es, con diferencia, lo que más cambia
  el resultado.
- **`--reconocer` / `--reconocimiento f.json`**: intenta averiguar QUÉ producto
  hay en la foto, para poder ofrecer un enlace al sitio oficial desde el
  visor. Por defecto, solo con lo que se lee o se ve EN LA FOTO; con
  `--permitir-nombre-fichero` (opt-in, solo tiene efecto junto a `--reconocer`)
  se mira TAMBIÉN el nombre del fichero cuando la foto no dio marca, y se
  declara como tal, nunca como si se hubiera leído. Ver el apartado
  "Reconocer el producto, o decir que no".

## La receta entera: de una foto suelta a un despiece, sin que nadie dibuje nada

Esto es lo que TÚ, Claude, tienes que hacer cuando alguien te da una foto de un
objeto y te pide verlo por dentro. No le pidas que escriba ficheros: los
escribes tú, y declaras de dónde salió cada cosa.

**Sin esto, la foto de un objeto compacto da UNA sola pieza.** El modo
automático separa componentes conexos, y un coche, una herramienta o un
electrodoméstico son una silueta conexa: la carrocería, las ruedas y la
parrilla son todo lo mismo para ese algoritmo. Si entregas eso, el usuario verá
una pieza y pensará que la herramienta no funciona.

### 1. Mira la foto

Ábrela y míra la de verdad. Necesitas saber qué objeto es y qué partes tiene,
porque los dos ficheros que vas a escribir salen de eso.

### 2. Escribe el fichero de regiones

Un polígono por parte, en píxeles de ESA foto (mira sus dimensiones antes:
las coordenadas son absolutas, no fracciones). El formato exacto está más
abajo, en «Ejemplo de fichero de regiones». Cuatro consejos que salen de
haberlo hecho:

- **Un polígono holgado vale**: el borde fino no lo decides tú, lo decide
  `cv2.grabCut` sembrado desde tu polígono. Tu trabajo es decir *dónde está* la
  pieza, no recortarla al píxel.
- **`prioridad` resuelve los solapes**: la pieza que va delante en la foto lleva
  el número más alto.
- **`rumbo`** es hacia dónde sale esa pieza al separarse; piensa cómo se
  desmontaría de verdad.
- Empieza por las partes GRANDES y evidentes. Ocho piezas bien puestas valen
  más que veinte adivinadas.

Y lo que no es negociable: esto es **reconocimiento asistido, no un detector
entrenado**, y `piezas.json` lo dirá con esas palabras. Tú has mirado una foto
y has dicho dónde te parece que está cada cosa. Eso es honesto y es útil; lo
deshonesto sería presentarlo como una medida.

### 3. El fondo se quita solo

**No pases `--quitar-fondo` por costumbre.** El módulo mide si las esquinas son
de un solo color y, si no lo son y hay motor disponible, lo quita él y lo dice
en la procedencia. Un fondo liso hace la silueta exacta, así que esto mejora el
despiece, no solo el aspecto. Si la foto ya venía con el fondo quitado —con
canal alfa— esa máscara ES la silueta y no se estima nada.

Solo pasa `--fondo-tal-cual` si el usuario quiere la foto como vino.

### 4. Busca los datos, y que cada cifra traiga su fuente

Las fichas son lo que convierte un despiece bonito en algo que se lee. Busca en
la web las características del objeto y repártelas por pieza, de modo que cada
cartel diga algo que corresponda a lo que se está mirando: la medida del
neumático en la rueda, el motor en la parrilla, las dimensiones en la
carrocería.

Reglas que aquí pesan más que la completitud:

- **Cada dato lleva su URL.** El campo `fuente` de cada pieza no es un adorno:
  es lo que permite comprobarlo. Un dato sin URL no se escribe.
- **Donde no hay fuente se escribe «sin dato con fuente»**, y el visor lo pinta
  en su propio color. Un cartel que dice eso es un cartel honesto; uno que
  rellena el hueco con algo verosímil es una mentira con formato de dato.
- **Si el objeto tiene varias versiones** —generaciones de un coche, modelos de
  una herramienta—, di de cuál son tus datos y por qué elegiste esa. Si no
  puedes saber cuál es el de la foto, DILO en la propia ficha.

### 5. La marca, solo si de verdad se sabe de dónde sale

`--reconocer` lee lo que hay EN LA FOTO con el OCR, y si no lee nada no hay
enlace. Un logotipo suele ser un dibujo que ningún OCR lee, así que casi
siempre no habrá.

Con `--permitir-nombre-fichero` se mira TAMBIÉN el nombre del fichero. Úsalo
cuando el nombre lo diga claramente, y no te preocupes por disimularlo: el
`como` que queda escrito será `nombre_fichero` y el porqué dirá sin adornos que
la marca salió del nombre y no de haberla leído en la foto.

### 6. Monta

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/kinetica.py" <foto>     --regiones <el que escribiste> --fichas <el que escribiste>     --reconocer --permitir-nombre-fichero
```

Y cuando lo entregues, di las dos cosas que el usuario tiene derecho a saber:
que las regiones las pusiste tú mirando la foto, y qué carteles se quedaron sin
dato con fuente.

## La carpeta que monta

Por defecto, `<carpeta de la foto>/<nombre sin extensión>_kinetica/`
(`--salida DIR` para elegir otra). Queda AUTOCONTENIDA — todo lo que espera
`abyss/plantillas/kinetica.html` (leída, nunca modificada por esta skill):

```
piezas/piezas.json    # ancho, alto, original, procedencia, piezas[] (clave/titulo/
                      # orden/caja_px/centro/tam_frac/rumbo/png/area_px/relleno_px)
                      # + reconocimiento (como/texto_leido/url/por_que)
piezas/<clave>.png    # cada componente recortado, con canal alfa (ruta = su clave "png")
original.jpg          # copia de la foto de entrada; si no era JPEG, se recodifica
three.min.js          # copiado de abyss/vendor/three.min.js (ya viene con el paquete)
index.html            # abyss/plantillas/kinetica.html tal cual, renombrada
fichas.json           # opcional: copia de --fichas f.json, si se dio
mp/                   # MediaPipe Tasks Vision — ver el aparte de abajo
```

Sin `--fichas`, cada cartel de especificaciones dice «sin dato con fuente»
(lo decide la propia plantilla, no este guion).

### `mp/`: manos reales si están, nunca fingidas si no

`abyss/vendor/mp/` (MediaPipe Tasks Vision: `vision_bundle.mjs`, `wasm/`,
`hand_landmarker.task`, unos 27 MB) **no viene en el repositorio** — solo
`three.min.js`, que pesa cientos de KB, se commitea; los seis ficheros de
`mp/` se bajan aparte, una vez, con `python instalar.py --manos` (jsdelivr
para el JS+wasm, el modelo de manos de Google Storage; sin red, un aviso
limpio y para ahí, nunca una traza). Si esa carpeta YA existe en la
instalación, `kinetica.py` la copia entera y las manos funcionan de verdad.
**Si no existe**, `kinetica.py` NUNCA la inventa ni descarga nada por su
cuenta: escribe un `mp/vision_bundle.mjs` SUSTITUTO (código propio, unas
pocas líneas) que deja cargar la página entera con normalidad y solo lanza un
error claro en el momento en que de verdad se intenta usar — la propia
plantilla ya captura ese error y lo muestra en pantalla («sin camara:
MediaPipe no está instalado en este servidor…») al pulsar "Encender cámara",
nunca antes. El aviso de qué falta y cómo conseguirlo sale por stdout al
montar la carpeta.

## El fondo: quitarlo antes de separar (`--quitar-fondo`)

Con el fondo puesto, el borde de cada pieza hay que ESTIMARLO (GrabCut sembrado
desde el polígono), y lo que GrabCut se deja fuera se pierde. Con el fondo
quitado, la silueta del objeto se MIDE — se resta el color del fondo — y
entonces cada píxel del objeto acaba en ALGUNA pieza, así que no queda casi
nada tapado que reconstruir. `kinetica.py` detecta solo el fondo liso y lo dice
en pantalla: `silueta: fondo liso (…), … % del cuadro -> exacta, sin GrabCut`.

MEDIDO con la misma foto en sus dos versiones: **con** fondo, el relleno
inventado por `cv2.inpaint` en el cuerpo del aparato fue de **78.947 píxeles**;
**sin** fondo, **55**.

Quien quita el fondo es `abyss/fondo.py` (también se puede usar suelto:
`python abyss/fondo.py <imagen> [--motor auto|sistema|modelo|grabcut]
[--sobre blanco|negro|alfa] [--listar-motores]`). Tres motores, y **siempre
dice cuál usó** — un recorte tosco presentado como si fuera del sistema sería
justo el engaño que este paquete persigue:

- **`sistema`** — la biblioteca Vision del propio macOS 14+
  (`VNGenerateForegroundInstanceMaskRequest`, vía PyObjC), el mismo recorte que
  hacen Vista Previa y Fotos. No baja ningún modelo: ya viene con el sistema.
  ⚠ **ESCRITO PERO NO PROBADO**: este paquete se ha escrito y medido en
  Windows. El camino está completo y falla con un mensaje claro si falta
  PyObjC o el sistema es anterior, pero nadie lo ha visto funcionar todavía;
  está declarado así a propósito y no se presenta como medido.
- **`modelo`** — una red pequeña en ONNX (U^2-Net «p», **4.574.861 bytes**
  MEDIDOS, en `abyss/vendor/modelos/u2netp.onnx`) que corre con `onnxruntime`
  sobre la CPU. Funciona igual en Windows, Linux y macOS, y es el único camino
  bueno en Windows. **Por qué en Windows no se usa nada del sistema**: el
  botón «Quitar fondo» de la aplicación Fotos no expone ninguna interfaz
  pública, y la segmentación que sí trae el Windows App SDK está reservada a
  equipos con NPU. Así que aquí no se usa el sistema: se usa este modelo, y se
  dice.
- **`grabcut`** — sin descargas y sin modelo, solo OpenCV. Notablemente peor
  (se come los bordes finos, se escapa por los reflejos); está para que la
  herramienta nunca se quede sin respuesta, y **avisa cada vez** de que el
  recorte es tosco.

`auto` prueba `sistema`, luego `modelo`, luego `grabcut`, y SIEMPRE imprime
cuál usó. Con `--quitar-fondo`, `kinetica.py` deja el recorte junto a la foto
de entrada, como `<nombre>_sin_fondo.png`, y sigue el despiece con ÉL; si el
recorte se queda con menos del 3% del cuadro, avisa y sigue con la foto
ORIGINAL en vez de despiezar un cuadro vacío.

## Reconocer el producto, o decir que no

El visor puede ofrecer un enlace al **sitio oficial** de lo que hay en la foto.
La regla por defecto es dura y no se negocia:

> El enlace solo puede salir de lo que se LEE o se VE **en la foto**. Nunca del
> `titulo` que una persona escribió en `fichas.json`: un enlace apoyado en un
> dato dictado sería presentarlo como hallazgo.
> **Sin reconocimiento no hay enlace**, y el visor dice por qué.
> Y si solo se reconoce la MARCA y no el modelo, el enlace es el sitio de la
> marca, jamás una página de producto.

9-sep: un logotipo puede ser un dibujo (un anillo, un escudo) que ningún OCR
lee, sin que la marca sea ningún misterio para quien nombró el fichero al
guardarlo. `--permitir-nombre-fichero` (junto a `--reconocer`, APAGADO por
defecto) deja mirar TAMBIÉN el nombre del fichero cuando la foto no dio nada
— pero eso NO es leer la foto, y nunca se disfraza de tal: el `como` que
queda escrito es `nombre_fichero`, y el `por_que` dice sin adornos que la
marca (y el modelo, si el resto del nombre lo trae) salieron del NOMBRE DEL
FICHERO, no de la foto. Si el nombre tampoco trae ninguna marca conocida,
sigue sin haber enlace.

Cuatro vías — más el `ninguno` honesto cuando no hay ninguna —, todas escritas
en `piezas.json` bajo la clave `reconocimiento`, con `como`, la evidencia
(`texto_leido`), la `url` (o `null`) y el `por_que`:

| `como` | de dónde salió |
|---|---|
| `ocr` | `--reconocer`: OCR (`lectura_visual.py`) sobre las piezas ya recortadas; se leyó una marca conocida y el enlace es el sitio de esa marca |
| `ocr_sin_marca` | `--reconocer`: se leyó texto, pero ninguna marca conocida — se guarda el texto y NO se enlaza a nada adivinado |
| `nombre_fichero` | `--reconocer --permitir-nombre-fichero`, solo cuando la foto no dio marca: la marca (y el modelo, si el resto del nombre lo trae) salen del NOMBRE DEL FICHERO — un dato dictado por quien lo guardó, no leído en la foto, y el `por_que` lo dice así |
| `asistente` | `--reconocimiento f.json`: lo reconoció el asistente MIRANDO la foto, con su evidencia declarada y su confianza |
| `ninguno` | no se pidió reconocer, no hay motor de OCR, o el OCR no leyó nada (y, con `--permitir-nombre-fichero`, el nombre del fichero tampoco traía marca) — y se dice cuál |

El fichero de `--reconocimiento` **rechaza con error** (código 2, «sin dato:
…») cualquier fichero cuyo `visto` esté vacío: sin evidencia no hay
reconocimiento. Con `modelo` a `null`, se guarda igual pero anotando que el
modelo NO se leyó en la imagen y que el enlace es de marca.

Un ejemplo honesto de por qué esto no se puede automatizar: MEDIDO con una foto
de un teléfono con dos accesorios, el motor de OCR de Windows estaba
disponible y aun así leyó **0 líneas en las tres piezas** — incluso recortando
los logotipos y ampliándolos 8 veces con el contraste forzado. Un logotipo
estilizado no es texto para un OCR; ahí el camino honesto es `--reconocimiento`
(alguien mira la foto y firma lo que ve), no fingir una lectura.

## El vocabulario de la mano (en el propio visor, dentro del navegador)

El vocabulario de `abyss/gestos.py`, pero **implementado aparte**: directo en
`kinetica.html`, con MediaPipe Tasks Vision leído en el navegador desde el
`mp/` servido en local. No depende de que el servidor HTTP de `gestos.py` esté
corriendo — de hecho no lo llama nunca —, así que los dos vocabularios ya no
son idénticos y un cambio en uno no llega solo al otro: `gestos.py` sigue
declarando su gesto de quietud a 1,0 s (`segundos_captura_quieta`), y aquí son
`SEG_QUIETA` segundos y abren el holograma.

| gesto | efecto |
|---|---|
| dedos extendidos (0..N) | 0 = ver todas las piezas; 1..N = aísla la pieza de ese `orden` |
| pellizco (pulgar-índice) | abre/cierra la explosión de las piezas |
| pose de la palma | gira e inclina la cámara alrededor del cubo |
| dos manos | acerca/aleja (escala) |
| mano abierta y quieta 3 s | abre el HOLOGRAMA del producto montado, sobre tu propia palma |
| cerrar la mano (cero dedos extendidos) 0,6 s, ya dentro del holograma | abre el sitio oficial, si la ficha trae reconocimiento con evidencia; si no, el propio holograma escribe por qué no hay enlace |

**El holograma va SOBRE LA MANO**: el producto entero, montado, flotando sobre
la palma dentro de la imagen de la cámara y con fondo transparente. Se ancla a
tres puntos de la mano y cada anclaje sale de una medida de la propia mano:
**dónde**, el promedio de muñeca, nudillo del índice y nudillo del meñique (tres
puntos y no uno, porque un punto solo tiembla); **cuánto de grande**, el ancho de
palma en pantalla, que no depende de lo lejos que esté la mano, así que el objeto
mide tantas palmas y no un tamaño fijo; **cómo está girado**, la base ortonormal
de la palma, sin `solvePnP` y sin calibrar la cámara. Si la mano sale del cuadro,
el objeto se desvanece en aproximadamente un segundo en vez de saltar.
Las piezas son planos y de canto se verían como cartón, así que se les da grosor
apilando `CAPAS_GROSOR` copias cada vez más oscuras y se limita el giro con
`TOPE_GIRO`, mezclando la orientación de la palma con la de frente. **Ninguna de
las dos cosas es volumen medido**: son un remedio declarado a que la foto es
plana, y **la propia pantalla dice que es un montaje sobre el vídeo y no una
medida del espacio**. Se sale con `Esc` o con un clic. Los segundos
que hay que aguantar la mano quieta son la constante `SEG_QUIETA` de
`abyss/plantillas/kinetica.html`, y la prueba
`pruebas/test_kinetica_documentacion.py` comprueba que este texto y esa
constante digan lo mismo.

La captura a PNG **sigue existiendo, pero solo desde el botón «Captura»** de la
página (descarga local del navegador): ningún gesto la dispara.

Pellizco y escala se normalizan por percentiles 10/90 de la sesión ACTUAL del
navegador (no del proyecto, no de otras sesiones); con menos de 30 lecturas no
hay vara todavía, y en vez de fingir un valor medio el visor se queda mostrando
la foto entera sin despiezar. La razón `1,7` para "dedo extendido" hereda la
misma cita de un tercero que declara `gestos.py` (técnica, no vocabulario),
sin remedir en esta máquina. El botón "Grabar" del visor graba un `.webm`
local (composición en un `<canvas>`, `MediaRecorder` del propio navegador) —
nada de esto pasa por `kinetica.py`, es la plantilla ya probada.

## El servidor

Salvo `--solo-montar` (deja la carpeta lista y no abre nada — para revisarla,
o para servirla luego a mano en otra máquina), el guion sirve esa carpeta con
`http.server` de la biblioteca estándar, **SOLO en `127.0.0.1`** (nunca
`0.0.0.0`), con las cabeceras `Cross-Origin-Opener-Policy: same-origin` y
`Cross-Origin-Embedder-Policy: require-corp` que el `.wasm` de MediaPipe
necesita para cargar como módulo ES — es la razón real por la que la
plantilla no se puede abrir con `file://` ni con un `http.server` genérico sin
esas dos cabeceras, no un simple bloqueo de CORS. Abre el navegador salvo
`--sin-abrir`; se queda corriendo hasta que se interrumpe (`Ctrl+C`) — con
`--solo-montar`, en cambio, el guion termina y devuelve un resultado, como
`separar` en el resto del paquete.

## Qué devuelve

Por stdout: los avisos de procedencia (motor del fondo si se pidió, silueta
exacta o estimada, regiones/automático, relleno, reconocimiento, `mp/`), luego
una línea JSON con `{destino, modo, piezas, mp}` (`modo` es `"manual"` o
`"automatico"`), y — si no se pidió `--solo-montar` — la URL local donde
quedó sirviendo (`http://127.0.0.1:<puerto>/`). Cualquier fallo (foto
ilegible, fichero de regiones mal formado, polígono con menos de 3 puntos,
fichero de reconocimiento sin `visto`…) se imprime como «sin dato: …» con
código de salida 2, nunca como una traza cruda de Python.

## Qué sale de la máquina

Nada, al montar: es cálculo local (GrabCut, inpaint, y el recorte de fondo de
`fondo.py`, que corre entero en la CPU de la máquina) sobre los ficheros que se
le dan — ni siquiera toca la red para avisar de qué falta en `mp/`, solo lo
imprime. El servidor solo escucha en `127.0.0.1` — nadie fuera de la máquina
puede abrir el visor —; con `mp/` real, MediaPipe procesa los fotogramas de la
cámara DENTRO del navegador, sin mandarlos a ningún sitio. Dos excepciones,
las dos declaradas: `python instalar.py --manos` es un paso APARTE y explícito
(fuera de esta skill) que baja `mp/` una vez; y **cerrar la mano dentro del
holograma abre el sitio oficial en una pestaña nueva** — eso es una visita web
normal, con lo que cualquier visita web lleva, y solo ocurre si la ficha trae
`reconocimiento` con `url`.

## Límites honestos

- No es reconstrucción 3D ni un escáner: sale de UNA foto 2D, sin cámara
  estéreo ni sensor de profundidad — el cubo invisible del visor, el rumbo de
  cada pieza y su prioridad de solape son geometría y decisión declaradas,
  nunca una medida real de profundidad.
- Sin `--regiones`, el resultado es automático y explícitamente peor: piezas
  sin nombre real (`auto_N`), separadas por contraste con el fondo, no por
  reconocer el objeto — el propio guion lo avisa, no lo disimula.
- Con `--regiones`, si esas regiones están mal puestas, el recorte sale mal:
  GrabCut solo puede afinar el borde partiendo de un polígono razonable, no
  corregir una región puesta en el sitio equivocado.
- El relleno de lo tapado (`--rellenar`) es SIEMPRE píxel inventado, nunca
  fotografiado, y `relleno_px` lo cuenta por pieza; no tiene efecto en modo
  automático (se avisa y se ignora si se pide de todas formas).
- Los carteles de `fichas.json` solo muestran cifras con fuente declarada;
  sin fichero o sin esa clave, «sin dato con fuente» — nunca un valor
  plausible puesto para rellenar el cartel.
- El vocabulario de la mano vive DUPLICADO (una vez en `gestos.py`, otra en
  `kinetica.html`) porque el visor no depende del servidor de `gestos.py` —
  un ajuste al vocabulario de uno no llega solo al otro, y de hecho ya han
  divergido: la quietud de la palma vale 1,0 s y se llama «captura» en
  `gestos.py`, y `SEG_QUIETA` segundos y abre el holograma en `kinetica.html`.
- `abyss/vendor/mp/` (las manos de verdad) NO viene en el repositorio por su
  peso (~27 MB) — hace falta `python instalar.py --manos` una vez, con red.
  Sin ella, el visor se sirve igual, pero cualquier intento de "Encender
  cámara" falla con un aviso claro en pantalla, nunca con la página rota ni
  con una mano fingida.
- Depende de OpenCV, numpy y Pillow; sin alguna, dice EXACTAMENTE qué
  instalar y sale con código 2, antes de tocar la foto. El motor `modelo` de
  `fondo.py` necesita además `onnxruntime`; sin él, `auto` cae a `grabcut` y
  lo dice.
- El "holograma" del visor NO es un holograma ni realidad aumentada medida: es
  el objeto montado sobre el vídeo, anclado a la palma, con grosor fingido por
  copias apiladas y el giro limitado. La propia pantalla lo declara.
- El motor `sistema` de `fondo.py` (macOS 14+) está ESCRITO PERO NO PROBADO:
  el paquete se ha medido en Windows. No se presenta como medido.
- `--reconocer` corre el OCR de verdad (arreglado el 8-sep: usaba un nombre
  que el módulo no definía y su propio `except` lo devolvía como
  `como: ninguno`, es decir, fallaba callando). MEDIDO con una foto de un
  producto: el motor estaba disponible y aun así leyó 0 líneas — un
  logotipo estilizado no es texto para un OCR, y sin texto no hay enlace.
- `--permitir-nombre-fichero` (9-sep, opt-in, APAGADO por defecto) es la
  única grieta en la regla dura: deja mirar el nombre del fichero cuando la
  foto no dio marca. Sigue sin fingir una lectura — el `como` que queda
  escrito es `nombre_fichero`, no `ocr`, y el `por_que` dice siempre que la
  marca (y el modelo, si lo hay) vinieron del nombre, no de la foto.
- Con `--quitar-fondo`, el recorte se escribe junto a la foto de entrada
  (`<nombre>_sin_fondo.png`) — un fichero de más en esa carpeta, no en la
  carpeta de salida.
- La cámara del visor solo se enciende al pulsar "Encender cámara" en la
  propia página — nunca sola al montar o servir, y nunca por un gancho de
  este paquete.

## Reglas SGICP de esta pieza

- **Procedencia declarada, no disfrazada**: con regiones, es reconocimiento
  asistido y lo dice; sin ellas, es automático y lo dice — ninguno de los dos
  se presenta como si un detector entrenado hubiera decidido QUÉ hay en la
  foto.
- **Fail-closed, nunca inventar**: `relleno_px` cuenta el píxel inventado en
  vez de esconderlo; sin fuente, «sin dato con fuente» en los carteles; sin
  `mp/` real, un aviso en pantalla en vez de una mano fingida; cualquier
  fallo sale como «sin dato: …» con código 2, nunca una traza cruda.
- **Nunca por gancho**: igual que el resto de la familia que enciende la
  cámara (`ojo`, `gestos`), este visor solo se enciende a petición explícita
  del usuario en ese turno.
- **Un enlace es un hallazgo, no un dato dictado**: el sitio oficial solo sale
  de lo leído o visto EN LA FOTO; el `titulo` de `fichas.json` lo escribió una
  persona y no vale para enlazar. Sin reconocimiento no hay enlace, y el
  holograma escribe el motivo en vez de callarse.

## Ejemplo de fichero de regiones (`--regiones`)

Una lista JSON de piezas — `poligono` en píxeles de ESA foto (mínimo 3
puntos), `rumbo` es el vector (x, y, z) del eje de montaje. `titulo` (por
defecto, la propia `clave`), `rumbo` (por defecto `[0, 0, 0.3]`, hacia el
espectador), `orden` (por defecto, la posición en la lista) y `prioridad`
(por defecto 0, gana el solape la más alta) son opcionales. `orden` solo
ORDENA las piezas entre sí — se puede numerar 1, 2, 3… o dejar huecos, que
`kinetica.py` reasigna la posición final tras ordenar (0, 1, 2…) antes de
escribir `piezas.json`, porque el visor lo usa como índice denso (cuántos
dedos aíslan cada pieza):

```json
[
  {
    "clave": "cuerpo",
    "titulo": "Cuerpo principal",
    "poligono": [[140, 260], [420, 230], [460, 520], [160, 560]],
    "rumbo": [0.0, 0.0, 0.0],
    "orden": 0,
    "prioridad": 0
  },
  {
    "clave": "tapa",
    "titulo": "Tapa desmontable",
    "poligono": [[170, 190], [400, 175], [415, 260], [180, 270]],
    "rumbo": [0.0, -1.0, 0.2],
    "orden": 1,
    "prioridad": 1
  }
]
```

## Ejemplo de fichero de fichas (`--fichas`)

```json
{
  "cuerpo": {
    "titulo": "Cuerpo principal",
    "datos": [
      {"etiqueta": "material", "valor": "aluminio anodizado"},
      {"etiqueta": "peso", "valor": "210 g"}
    ],
    "fuente": "ficha técnica del fabricante, hoja 2"
  },
  "tapa": {}
}
```

Una clave sin `datos` ni `fuente` (como `tapa` arriba) es exactamente lo mismo
que no aparecer en el fichero: el cartel de esa pieza dice «sin dato con
fuente».

## Ejemplo de fichero de reconocimiento (`--reconocimiento`)

Lo que el asistente vio MIRANDO la foto, firmado como tal. `visto` es la
evidencia y es obligatorio (con la lista vacía, el guion rechaza el fichero);
`modelo` a `null` significa que el modelo concreto no se leyó, así que la `url`
tiene que ser la del sitio de la marca, nunca la de una página de producto:

```json
{
  "visto": [
    "logotipo de la marca grabado en la tapa, esquina inferior derecha",
    "el mismo logotipo, más pequeño, en el accesorio de la izquierda"
  ],
  "marca": "marca-de-ejemplo",
  "modelo": null,
  "url": "https://sitio-oficial-de-ejemplo.example",
  "confianza": "media"
}
```
