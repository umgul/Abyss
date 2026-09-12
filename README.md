# Abyss

*[English version](README.en.md)*

Abyss es un conjunto de *skills* y ganchos para Claude Code que un asistente usa
sobre su propia memoria, su propio comportamiento y su propio entorno: sentidos
hacia fuera, memoria entre hilos, un vigía contra la confabulación, y un par de
manos para generar y pintar imágenes. Nada de estado guardado a ojo — todo lo
que dice cada pieza sale de medir algo real o de aplicar una regla fija.

**El camino corto, si tienes Claude Code**: clona este repositorio, abre Claude
Code en esa carpeta y dile «instálamelo». Hay un [`CLAUDE.md`](CLAUDE.md) en la
raíz escrito PARA Claude, no para ti: le dice que esto es un paquete de skills
que se instala (no un proyecto que se desarrolla), le enseña `python
instalar.py --listar` antes de tocar nada, y las tres cosas que no puede hacer
sin preguntarte primero. Sigue leyendo si prefieres instalarlo tú mismo, a
mano — todo lo de abajo es exactamente lo mismo que `CLAUDE.md` resume para
Claude, con el detalle completo.

## Filosofía, en cinco líneas

1. **Ley o medida, nunca estado**: cada pieza mide algo del transcript o aplica
   una regla fija; nada se decreta a ojo ("hoy estoy cansado").
2. **Cortes por cuantiles, nunca umbrales fijos**: lo que cuenta como
   "destacado" sale de la propia distribución acumulada hasta ese momento, y
   rota con ella.
3. **El nulo como suelo**: antes de decir "esto se parece", hay que saber
   cuánto vale el ruido de fondo, medido contra frases que no tienen nada que
   ver con el proyecto.
4. **Cazar lo que no salió de ninguna parte**: un vigía contrasta cada
   respuesta con la evidencia real de la sesión (lo dicho por el usuario, lo
   devuelto por herramientas) y bloquea una vez lo que no tiene fuente.
5. **Fail-closed, nunca inventar**: sin proyecto no hay datos, sin sesiones
   suficientes no hay percentil, sin red no hay lugar ni meteo — la respuesta
   siempre es "sin dato" o "sin vara todavía", jamás un valor puesto a mano.

Este resumen no es una lista 1:1: `docs/leyes.md` destila SEIS leyes (añade "una
vara sin varianza no mide" y "falsar antes de fiarse"), y el detalle completo de
cada una está ahí: [`docs/leyes.md`](docs/leyes.md).

## Las piezas de esta tanda

Cada pieza tiene su propia `skills/<nombre>/SKILL.md` con el comando exacto,
qué devuelve, qué sale de la máquina y sus límites honestos — esto es solo el
mapa.

**Memoria y continuidad**
- [`continuidad`](skills/continuidad/SKILL.md) — guarda cada sesión, mide su
  reloj de esfuerzo y despierta sesiones pasadas parecidas al mensaje actual.
- [`propiocepcion`](skills/propiocepcion/SKILL.md) — mide una sesión desde su
  transcript (horas, turnos, herramientas, tokens, correcciones) y da su
  percentil contra las demás.
- [`varas`](skills/varas/SKILL.md) — recalcula el peso de uso ◆/◆◆/◆◆◆ de cada
  ficha de `MEMORY.md` por cuantiles de citas y lecturas.
- [`modelo`](skills/modelo/SKILL.md) — detecta si se está respondiendo fuera
  del modelo preferido y marca los turnos a revisar al volver.
- [`parentesis`](skills/parentesis/SKILL.md) — marca un tramo (o una sesión
  entera) para que no entre en memoria futura, y recorta el transcript local
  ya cerrado si el usuario lo pide.

**Honestidad**
- [`vigia`](skills/vigia/SKILL.md) — caza números, rutas y citas de la propia
  respuesta que no salieron de ninguna parte, y bloquea el cierre del turno
  una vez.
- [`huella`](skills/huella/SKILL.md) — registra qué ficheros, procesos y
  puertos toca un hilo fuera de su propia carpeta, para poder decir al cerrar
  qué queda vivo y limpiarlo. **APAGADO por defecto** (ver "Límites honestos").
- [`esceptico`](skills/esceptico/SKILL.md) — la ley "ningún plan sin
  escéptico" como comando: lanza un revisor con model Opus a buscar lo que
  tumba un plan antes de ejecutarlo, con veredicto por gravedad y evidencia.
  `--paquete <ruta>` corre `auditar.py` sobre un paquete y le da el informe a
  ese mismo Opus para que lea por encima lo que el automatismo no ve.
- `abyss/plantillas/gestos_comun.js` — **la copia que manda** del vocabulario de la mano
  (sin espejo, lento a propósito, un puño frena y dos paran). `kinetica.html` la importa
  y `gestos.py` es su espejo en Python, mantenido a mano; hasta el 8-sep-2026 la misma
  gramática estaba escrita tres veces y las tres habían divergido.
- `auditar.py` — las cinco comprobaciones sobre un paquete ANTES de
  instalarlo (procedencia, comandos, permisos, qué sale de la máquina,
  dominio), con evidencia fichero:línea; nunca ejecuta el código auditado.
  Sin *skill* propia — se usa directo o desde `esceptico --paquete`.

**Sentidos**
- [`exterocepcion`](skills/exterocepcion/SKILL.md) — lugar (por IP y por lo
  dicho), meteo del lugar, y canal de entrada del último mensaje.
- [`noticias`](skills/noticias/SKILL.md) — portada y titulares por tema al
  arrancar, con una lista de temas automáticos autocurada.
- [`ojo`](skills/ojo/SKILL.md) — ocho verbos, todos a petición explícita,
  ninguno por gancho: `mirar` (un fotograma de la webcam), `texto`/
  `fotocopia`/`tarjeta`/`manual` (OCR por el motor de Windows o `tesseract`,
  delega en `lectura_visual.py`), `despiece`/`prompt3d` (despiece por capas
  2,5D y prompt de diseño 3D medido de la foto, delega en `volumen.py`), y
  `gestos` (MediaPipe + vocabulario propio: sirve por HTTP, solo en
  `127.0.0.1`, el estado de la mano ya traducido — capa aislada, apertura de
  explosión, órbita, escala, gesto de captura — pero nada lo consume
  todavía, delega en `gestos.py`).
- [`kinetica`](skills/kinetica/SKILL.md) — separa los COMPONENTES REALES de
  UNA foto de un objeto compuesto (regiones puestas a mano + `cv2.grabCut`,
  nunca capas de nitidez; sin regiones, separación automática por
  componentes conexos, avisada como peor y sin nombre real) y los despieza en
  3D dentro de un cubo invisible con three.js, manejados por la mano a través
  de la cámara — las manos de verdad necesitan `python instalar.py --manos`
  (MediaPipe Tasks Vision, ~27 MB, no va en el repositorio); sin eso, el
  visor se sirve igual, solo sin manos, con aviso en pantalla. Sustituye en
  calidad al viejo despiece 2,5D de `ojo despiece`/`volumen.py`; la cámara del
  visor solo se enciende a petición, nunca por gancho. En el visor, la mano
  abierta y quieta 3 s abre un holograma del producto montado SOBRE TU PROPIA
  PALMA, con fondo transparente y anclado a tres puntos de la mano (la pantalla
  dice que es un montaje sobre el vídeo, no una medida del espacio) y, dentro de él, cerrar la mano abre el sitio oficial del producto,
  pero solo si la ficha trae un reconocimiento con evidencia leída o vista EN
  LA FOTO; sin eso no hay enlace, y el visor escribe el motivo.
- [`kinetico`](skills/kinetico/SKILL.md) — recorre con la mano un CONJUNTO de
  cosas que se relacionan entre sí — una carpeta del disco (`arbol`: fichero =
  esfera, carpeta = cubo, la planta es la profundidad) o un grafo genérico de
  nodos (`datos <nodos.json>`, un adaptador por fuente) — como un edificio 3D:
  un puño abre la ficha de lo que tienes delante y un segundo puño sobre esa
  misma cosa entra en la carpeta o abre el fichero. Se distingue de `kinetica`
  (que despieza UNA foto de un objeto): aquí no hay ninguna foto, hay un
  conjunto. Su servidor (`kinetico_servidor.py`) solo actúa sobre lo que ya
  está en la escena montada, sin salir de la carpeta con la que se abrió. Sin
  cámara sigue siendo usable con el ratón; con cámara, las manos de verdad
  piden el mismo `python instalar.py --manos` que `kinetica`.
- `fondo.py` — sin *skill* propia (mismo caso que `auditar.py`): quita el
  fondo de una foto en local, con tres motores que siempre dicen quién es
  (`sistema`, la biblioteca Vision de macOS 14+ y sin descargas, ESCRITO PERO
  NO PROBADO porque este paquete se ha medido en Windows; `modelo`, una red
  pequeña ONNX de 4.574.861 bytes MEDIDOS con `onnxruntime`; y `grabcut`,
  tosco y avisado). Existe porque `kinetica.py --quitar-fondo` recorta mucho
  mejor con él: con el fondo quitado la silueta se MIDE en vez de estimarse
  (MEDIDO con la misma foto en sus dos versiones: 78.947 píxeles inventados
  por relleno con fondo, 55 sin él).
- [`cuerpo`](skills/cuerpo/SKILL.md) — el cuerpo de la máquina (cpu, ram,
  disco, vram, temperatura de GPU, batería) con su propia normal por
  cuantiles; nunca ordena nada, solo mide.

**Manos**
- [`imagen`](skills/imagen/SKILL.md) — crear una imagen por cascada de
  proveedores, pintar una foto como cuadro de pinceladas 100% local en varios
  estilos (óleo, impresionista, acuarela, pastel, carbón, tinta), animar esas
  pinceladas en vídeo, renderizar una escena o modelo 3D con three.js (vista
  explosionada, `render3d.py`) y encadenarlo con el pintor, buscar una imagen
  libre ya hecha (Openverse/Wikimedia Commons) o un motivo del mundo real
  (museos, Street View, webcams — `mundo.py`), y operar con imágenes reales
  sin ningún modelo (`lienzo.py`: fundir, collage, restaurar, pintar por
  números, borrar un objeto) — con un taller local opcional (`taller.py`)
  para quien quiera esa vía.
- [`lector_pdf`](skills/lector_pdf/SKILL.md) — indexa un PDF por página y
  sección, busca por TF-IDF y lee solo la parte que toca en vez del documento
  entero.
- [`mapa_codigo`](skills/mapa_codigo/SKILL.md) — el índice greppable de un
  repo Python con `ast`: módulos, clases, funciones e imports, cada uno con
  su línea.
- [`infografia`](skills/infografia/SKILL.md) — de un CSV o JSON a un SVG
  limpio (barras, líneas, tabla), biblioteca estándar sin dependencias.
- `presenta.py` — sin *skill* propia (mismo caso que `auditar.py`): genera,
  invocando de verdad las piezas de arriba, el vídeo corto que las enseña
  (`--salida <ruta.mp4> --idioma es|en --segundos N --ancho N`). Cada bloque
  es una demostración REAL hecha en el momento — memoria (`varas.py
  --index`), honestidad (`vigia.py --probar`), auditoría (`auditar.py` sobre
  el propio paquete), sentidos (`cuerpo.py` + `exterocepcion.py`), el pintor
  y sus cuatro estilos, un motivo del mundo, el ojo (OCR y fotocopia) y una
  escena 3D con su holograma — nunca una captura vieja: si una pieza falta en
  esta máquina, su bloque se salta y el propio vídeo lo dice al final ("se
  hizo con lo que había").

Por debajo de todas ellas, `abyss/rutas.py` es la única pieza que decide dónde
viven el código y dónde viven los datos — ninguna otra pieza calcula esa ruta
por su cuenta (ver "Dónde viven los datos" más abajo).

## Instalación

### Como plugin de Claude Code

```
/plugin marketplace add umgul/Abyss
/plugin install abyss@abyss
```

(la ruta del repositorio es la prevista para su publicación; ajústala si
`umgul/Abyss` cambia). Esto instala solo los *skills* de `skills/`. El plugin
no declara ningún gancho: Claude Code cargaría por sí solo un
`hooks/hooks.json` al instalarlo, y este paquete no lo lleva a propósito, para
que nada corra en cada sesión, en cada mensaje o tras cada herramienta sin que
el usuario lo haya elegido módulo a módulo.

**Los ganchos van por `instalar.py`**: `continuidad`, `huella`, `cuerpo` y
`vigia` se instalan módulo a módulo con `python instalar.py --instalar …`, que
detecta el intérprete real (`sys.executable`, o `--python <exe>`), dice qué
toca cada módulo y apunta la firma de cada gancho para poder quitarlo después.
Cada gancho resuelve la carpeta de datos del proyecto a partir del JSON que
Claude Code manda por stdin (`transcript_path`/`cwd`), vía `abyss/rutas.py`,
así que funciona en cualquier proyecto sin configurar rutas.

Lo que el plugin tampoco trae, porque necesita datos que solo puede dar una
persona: el módulo **telegram** (pide un token de bot y un chat id) y el
sembrado de plantillas de configuración (`modelo_preferido.json`,
`temas_noticias.json`, `imagen_config.json`). Para eso está `instalar.py`.

### Con `instalar.py`

```
python instalar.py --listar                       # qué módulos hay y si están instalados
python instalar.py                                 # ventana Tk: casilla por módulo + Instalar/Desinstalar/Cerrar
python instalar.py --instalar continuidad,vigia    # instala solo esos módulos, sin ventana

# Los cuatro que vienen APAGADOS por defecto, con su comando para encenderlos.
# Ninguno se enciende solo: cada uno cuesta algo y esa decisión es de quien instala.
python instalar.py --instalar huella      # apunta lo que el hilo toca fuera de su carpeta (peaje: PostToolUse en cada herramienta)
python instalar.py --instalar taller      # servidor local de texto→imagen (pesado)
python instalar.py --instalar telegram    # aviso por Telegram cuando termina algo
python instalar.py --instalar permisos    # ajustes de permisos de herramientas
python instalar.py --desinstalar vigia             # desinstala un módulo
python instalar.py --sin-ventana                   # fuerza el modo CLI aunque haya Tk disponible
```

El instalador:
- detecta el intérprete de Python (`sys.executable`, o `--python <exe>`) y lo
  usa en los ganchos que escribe, con la ruta absoluta del código tal como
  quedó instalado;
- **lee y fusiona** `~/.claude/settings.json` (o el que le indiques con
  `--settings <ruta>`): guarda antes una copia fechada
  (`settings.json.abyss-AAAAMMDD-HHMMSS.bak`), añade las entradas de Abyss a
  cada evento sin tocar las que ya hubiera de otros programas, y solo toca
  claves de preferencia (como `showThinkingSummaries`) si el módulo
  correspondiente está marcado;
- apunta todo lo que añade o cambia en `memory/abyss_manifiesto.json` del
  proyecto desde el que se instala, con el valor que tenía cada clave antes de
  tocarla — es lo que permite deshacerlo exacto, incluso si `abyss/` se mueve o
  se renombra después;
- no escribe nunca en el repo del usuario ni en la carpeta de memoria salvo lo
  que cada módulo declara guardar (ver la tabla de abajo); en la carpeta del
  código solo se escribe `abyss/config.json` (qué `python` se usó la última
  vez), nunca más.

El módulo **telegram** es distinto: `notify_telegram.ps1.plantilla` viaja con
los marcadores `<TELEGRAM_BOT_TOKEN>` y `<CHAT_ID>`; el instalador pide esos
dos valores (por consola o `--telegram-token`/`--telegram-chat`) y escribe la
copia rellena **fuera del repo**, en `memory/`, nunca en el código instalado.

Tres módulos vienen **apagados por defecto** (hay que marcarlos a propósito):
**permisos** (dar a Abyss permiso `Edit` sobre `settings.json`), **huella**
(su gancho `PostToolUse` corre tras cada herramienta, con el coste que eso
implica — ver su skill) y **taller** (deja lista la configuración de un
servidor local de imagen, pero no instala `diffusers`/`torch` ni lo arranca:
eso pesa GB y minutos, y es una decisión que toma quien lo instala, no el
instalador por su cuenta). El resto de módulos — incluido **preferencias**
(`showThinkingSummaries`) — vienen marcados de partida en la ventana Tk; basta
con desmarcarlos si no se quieren.

El módulo **esceptico** es distinto de los demás: no es un guion Python, es
una *skill* (`skills/esceptico/`) que el instalador COPIA a
`~/.claude/skills/esceptico/` (o a donde apunte `--skills-dir <ruta>`), con
una marca en su frontmatter (`abyss-managed: true`) para que el desinstalador
sepa que es la nuestra — una skill que el usuario ya tuviera puesta a mano con
el mismo nombre, sin esa marca, nunca se toca al desinstalar.

**Desinstalar**: `python instalar.py --desinstalar <módulo>` (o desmarcar la
casilla) hace lo inverso: lee `memory/abyss_manifiesto.json`, quita del
`settings.json` solo las entradas cuyo comando apunte a la carpeta donde está
instalado Abyss (o, para telegram, al `.ps1` que escribimos nosotros), y
restaura cada clave de preferencia al valor que tenía antes. Después pregunta
si además hay que borrar los datos generados en `memory/` — **por defecto NO**:
las sesiones guardadas y los relojes son memoria propia del usuario, no del
programa, y no se pierden solo porque se desinstale la herramienta que los
escribió (`--borrar-datos` fuerza el borrado sin preguntar).

**Límite honesto**: el desinstalador devuelve el mismo *contenido* de
`settings.json`, no el mismo texto — `_escribir_json` siempre reescribe con su
propio `indent=2` y siempre en LF (`newline='\n'`, a propósito: sin eso, en
Windows un `settings.json` de partida en LF volvía en CRLF), así que si el
fichero original tenía otro formato (por ejemplo `indent=4`, un orden de
claves distinto, o **CRLF** — el fin de línea habitual de Windows, del Bloc
de notas o de un editor con `files.eol` a CRLF), el JSON que queda tras
instalar y desinstalar es idéntico en lo que dice pero no byte a byte igual al
de antes: un `settings.json` en CRLF vuelve en LF. El formato original no se
pierde: queda en la copia fechada `settings.json.abyss-AAAAMMDD-HHMMSS.bak`
que se hace antes de tocar nada.

<details>
<summary>Apéndice secundario: cablear los ganchos A MANO (NO recomendado)</summary>

Solo si por lo que sea no se puede usar `instalar.py`: copiar el bloque de
[`docs/ganchos_settings_ejemplo.json`](docs/ganchos_settings_ejemplo.json)
dentro de `"hooks"` en `~/.claude/settings.json`, sustituyendo
`<RUTA_DEL_PAQUETE>` por la ruta real donde quedó `abyss/` y `<PYTHON>` por el
intérprete que se vaya a usar. Sin `instalar.py` no hay manifiesto ni registro
de qué se instaló, así que deshacerlo exige
recordar a mano qué se tocó.

</details>

### Lo que se descarga aparte, y por qué no viaja en el repositorio

Este repositorio no lleva binarios de terceros dentro, con una única excepción
declarada: [`abyss/vendor/three.min.js`](abyss/vendor/three.min.js) (three.js
r160, **669.884 bytes** MEDIDOS con `os.path.getsize`, licencia MIT). Se queda
porque ya estaba en la historia de este repositorio antes de esta regla —
quitarlo del índice ahora no lo quita del clon, para eso habría que reescribir
la historia— y porque sin él los tres visores 3D de este paquete
(`render3d.py`, y los visores que montan `kinetica`/`kinetico`) no arrancan
recién clonado: una skill sin código que mostrar no es una skill instalable.
Todo lo demás se baja aparte, con una orden explícita, después de clonar,
nunca al instalar y nunca en silencio:

```
python instalar.py --manos       # MediaPipe Tasks Vision, ~27 MB: manos por cámara en kinetica/kinetico/ojo gestos
python instalar.py --modelo      # U^2-Net p (u2netp.onnx), 4.574.861 bytes MEDIDOS: quitar el fondo de una foto
```

La razón no es una manía de peso: este mismo paquete ofrece `auditar.py` para
mirar un paquete ANTES de instalarlo, y esa promesa solo la sostiene un
repositorio que se puede LEER entero — un binario de terceros no se lee, se
confía en él. El detalle fichero a fichero de qué se baja, de dónde y por qué
el caso de `three.min.js` es distinto está en [`.gitignore`](.gitignore) y en
[`CLAUDE.md`](CLAUDE.md); la licencia de las tres obras de terceros —la de
three.js, que es la única que viaja dentro, y las de MediaPipe y U²-Net p, que
se bajan aparte— está en [`NOTICE.md`](NOTICE.md). Sin `--manos`, los visores cinéticos se sirven
igual, solo sin manos, con aviso en pantalla; sin `--modelo`, `fondo.py` usa
el recorte del sistema o `grabcut` y dice siempre con qué motor recortó.

## Dónde viven los datos

El código de Abyss se instala una vez (como plugin, o donde lo pongas con
`instalar.py`). Los datos (sesiones, relojes, bolsas, confabulaciones, lugar,
meteo, imágenes…) viven **por proyecto**, dentro de la memoria automática de
Claude Code para ese proyecto: `~/.claude/projects/<proyecto-saneado>/memory/`.
El único módulo que decide esa ruta es `abyss/rutas.py`; el resto la importa.
Como los ganchos de `settings.json` global disparan en todos los
proyectos, no solo en el que estaba abierto al instalar, cada uno resuelve su
propio proyecto en cada invocación por el `transcript_path`/`cwd` que le llega
— nunca se mezcla la memoria de un proyecto con la de otro.

| Pieza | Qué hace | Gancho | Datos que guarda (en `memory/`) |
|---|---|---|---|
| `rutas.py` | Resuelve dónde viven el código y los datos para todos los demás guiones. | Ninguno (librería que importan todos) | Solo crea `memory/` si no existe. |
| `continuidad.py` | Guarda cada sesión, mide su reloj, abre la sala de los relojes y lleva el latido de qué hilos siguen vivos. `--comprimir` gzipea sesiones viejas. | `SessionStart` (`--arranque`) · `SessionEnd` (`--cierre`) · `UserPromptSubmit` (`--despertar`) | `sesiones/*.jsonl(.gz)` · `relojes.jsonl` · `bolsas.json` · `.despertados/` · `.vivo/` · `sesiones/.omitir` · `varas.log` (avisos y fallos de `varas.py --index` tras cada cierre) |
| `vigia.py` | Contrasta la última respuesta contra la evidencia real de la sesión y bloquea el cierre del turno una vez si encuentra números, rutas o citas sin fuente. | `Stop` (`--verificar`) | `confabulaciones.jsonl` |
| `propiocepcion.py` | Mide cada sesión desde su transcript y da su percentil contra todas las medidas. | Ninguno propio — librería de `continuidad.py` y `varas.py`; también CLI a mano | `propiocepcion.json` |
| `varas.py` | Recalcula el peso ◆/◆◆/◆◆◆ de cada ficha por cuantiles de citas + lecturas, y reescribe esos glifos en el índice. Si `MEMORY.md` supera 24 KB solo **avisa** por stdout; el recorte real es a mano con `varas.py --index --recortar` (deja antes una copia fechada); nunca borra una línea entera. | Ninguno propio — lo llama `continuidad.py` tras cada cierre; también CLI a mano | Reescribe `MEMORY.md` · `MEMORY.md.abyss-AAAAMMDD-HHMMSS.bak` (una por cada recorte real) |
| `parentesis.py` | Marca un tramo o una sesión entera para que no entre en memoria futura; recorta el transcript local ya cerrado (`--recortar`/`--recortar-tramo`, con copia `.antes`). | Ninguno — uso manual | `parentesis.json` · `sesiones/.omitir` (reutilizado) |
| `exterocepcion.py` | Lugar (por IP y por lo dicho), meteo del lugar, y canal de entrada del último mensaje. | Ninguno propio — librería de `continuidad.py` | `lugar.json` · `meteo.json` |
| `modelo.py` | Detecta si se responde fuera del modelo preferido y marca los turnos a revisar al volver. | Ninguno propio — no existe un evento «PostModelSwitch»/«PreModelSwitch» en Claude Code; librería de `continuidad.py --despertar` | `modelo_preferido.json` · `.modelo_revisado/` |
| `noticias.py` | Portada y titulares por tema al arrancar; temas automáticos autocurados. | Ninguno propio — librería de `continuidad.py --arranque` | `noticias.json` · `temas_auto.json` · `temas_log.jsonl` · `temas_noticias.json` (editable a mano) · `temas_veto.json` |
| `ojo.py` | Ocho verbos, un solo punto de entrada, ninguno por gancho: `mirar` (un fotograma de la webcam, autónomo) y, delegando enteros en su módulo, `texto`/`fotocopia`/`tarjeta`/`manual` (→ `lectura_visual.py`), `despiece`/`prompt3d` (→ `volumen.py`) y `gestos` (→ `gestos.py`). | Ninguno — nunca por gancho | `ojo.log` (verbos `mirar`/`texto`/`fotocopia`/`tarjeta`/`manual`) + el fichero que pida cada verbo; `despiece`/`prompt3d`/`gestos` no tocan `memory/` |
| `lectura_visual.py` | OCR de una imagen por el motor de Windows (WinRT, sin instalar nada) o `tesseract` (segunda vía, PATH): `texto` (texto plano, opcionalmente al portapapeles), `fotocopia` (endereza/corrige iluminación una foto o un fotograma de cámara, PNG o PDF de varias páginas — el escáner WIA es una fuente OPCIONAL más, nunca el camino), `tarjeta` (patrones + heurística de posición → `.vcf` y `.png`), `manual` (ordena varias fotos, sin resumir). Usado por `ojo.py`. | Ninguno | `lectura_visual.log`; el fichero de salida que pida cada verbo (junto a la entrada, o en `memory/` si viene de `--camara`/`--escaner`) |
| `volumen.py` | `despiece`: separa el objeto del fondo (GrabCut) y lo reparte en capas 2,5D por nitidez+luminancia, para el deslizador de explosión de `render3d.py`. `prompt3d`: mide paleta (k-medias), proporción, horizonte y formas (circularidad de contorno) y escribe un prompt de diseño ES/EN para three.js. Usado por `ojo.py`. | Ninguno | Nada en `memory/`: no resuelve proyecto (guion de fichero a fichero, como `render3d.py`) — escribe donde se le pida |
| `gestos.py` | MediaPipe (21 puntos por mano) + vocabulario PROPIO del paquete: sirve por HTTP local, SOLO en `127.0.0.1`, el estado de la mano ya traducido a ese vocabulario (capa aislada por número de dedos, apertura de explosión por el pellizco, órbita por la pose de la palma, escala por la distancia entre dos manos, gesto de captura completado al abrir la mano y quedarse quieta 1 s), normalizado por percentiles de la propia sesión. Nada consume ese estado todavía: la página de `render3d.py` no lee `/estado` ni reacciona, y ningún PNG se captura por esta vía — conectar el servidor a una página sigue siendo trabajo pendiente, declarado, no hecho. Quien SÍ usa este vocabulario es el visor de `kinetica.py`, pero lo implementa por su cuenta DENTRO del navegador (MediaPipe Tasks Vision servido en local desde `mp/`), sin llamar a `gestos.py` ni a su `/estado` — y allí los dos ya han divergido: la palma quieta abre un holograma, no una captura. Usado por `ojo.py gestos`. | Ninguno | Nada en `memory/`: no resuelve proyecto (vive/sirve mientras corre, como `taller.py`) |
| `kinetica.py` | Convierte UNA foto de un objeto compuesto en un visor 3D manejado por la mano: separa sus componentes reales (`--regiones` a mano + `cv2.grabCut`, o automático y avisado como peor sin `--regiones`), monta un holograma del producto sobre la propia palma y, con `--reconocer`/`--reconocimiento`, anota de dónde salió cada marca reconocida (nunca del `titulo` dictado en `fichas.json`). `--quitar-fondo` delega en `fondo.py` antes de separar. | Ninguno — uso manual | Nada en `memory/`: monta una carpeta autocontenida junto a la foto (o en `--salida DIR`) y la sirve por HTTP SOLO en `127.0.0.1`; las manos de verdad piden `python instalar.py --manos` aparte |
| `kinetico.py` | Convierte un CONJUNTO de cosas — una carpeta del disco (`arbol`) o un contrato genérico de nodos (`datos <nodos.json>`, un adaptador por fuente) — en un edificio 3D navegable con la mano o el ratón; su servidor (`kinetico_servidor.py`) expone `entrar`/`abrir` SOLO sobre lo que la escena montada ya declara, sin salir de la carpeta con la que se abrió. | Ninguno — uso manual | Nada en `memory/`: LEE la carpeta o el fichero de nodos que se le pida y no escribe nada en ellos; monta una carpeta autocontenida (o en `--salida DIR`) y la sirve por HTTP SOLO en `127.0.0.1` |
| `fondo.py` | Quita el fondo de una foto en local, con tres motores que siempre dicen quién es: `sistema` (la biblioteca Vision del propio macOS 14+, sin descargas — ESCRITO PERO NO PROBADO: este paquete se ha medido en Windows), `modelo` (una red pequeña ONNX de 4.574.861 bytes MEDIDOS, en `abyss/vendor/modelos/`, que corre con `onnxruntime` igual en Windows, Linux y macOS) y `grabcut` (sin descargas, tosco, avisa cada vez). `auto` los prueba en ese orden y SIEMPRE imprime cuál usó. En Windows no se usa nada del sistema porque no se puede: el botón «Quitar fondo» de la aplicación Fotos no expone ninguna interfaz pública, y la segmentación del Windows App SDK está reservada a equipos con NPU. Lo llama `kinetica.py --quitar-fondo` antes de separar: con el fondo quitado, la silueta del objeto se MIDE en vez de estimarse, y cada píxel acaba en alguna pieza (MEDIDO con la misma foto en sus dos versiones: 78.947 píxeles inventados por relleno con fondo, 55 sin él). | Ninguno | Nada en `memory/`: escribe el recorte junto a la imagen de entrada (`<nombre>_sin_fondo.png`), o donde se le pida |
| `auditar.py` | Las cinco comprobaciones de un paquete ANTES de instalarlo: procedencia (manifiestos + `.git` local), comandos (ganchos que corren en cada mensaje o herramienta, sin declarar), permisos (qué escribe fuera de su carpeta), qué sale de la máquina (hosts del código sin nombrar en el README — la que ningún antivirus hace), y dominio (reunidos para lectura manual, sin veredicto). NUNCA ejecuta el código auditado. Usado directo o por `esceptico --paquete`. | Ninguno — uso manual | Nada en `memory/`: no resuelve proyecto (audita un paquete de terceros, no mide este hilo) |
| `huella.py` | Registra ficheros escritos, procesos y puertos que un hilo abre fuera de su carpeta; `--informe`/`--limpiar` dicen qué sigue vivo y lo cierran si se pide. `--limpiar --si` solo borra ficheros bajo el directorio temporal del sistema o bajo una subcarpeta que ESTE paquete genera en `mem` (`huella/`, `mapas/`, `pdf/`) — nunca `MEMORY.md`, una ficha `*.md`, ni nada suelto en la raíz de `mem`, aunque un `Write` de la sesión haya pasado por ahí. **Módulo apagado por defecto** (coste de `PostToolUse`). | `SessionStart` (`--arranque`) · `PostToolUse` (`--herramienta`) · `Stop` (`--fin`) | `huella/<sesión>.jsonl` (incluye el TEXTO de cada comando de Bash/PowerShell, recortado a 200 caracteres — si sueles pasar claves por línea de comandos, quedarán ahí en local) · `huella/<sesión>.snapshot.json` · `huella/_costes.json` |
| `cuerpo.py` | El cuerpo de la máquina (cpu, ram, disco, vram, temperatura de GPU, batería) con su propia normal por cuantiles; `UserPromptSubmit` calla si todo está dentro de lo suyo. Los seis canales se muestran en `SessionStart`; en `UserPromptSubmit` se vigilan cinco — la batería no, porque su propia oscilación normal (cargando/descargando) la sacaría de su p5 cada vez que se desenchufa el cargador. | `SessionStart` (`--arranque`) · `UserPromptSubmit` (`--despertar`) | `cuerpo.jsonl` |
| `lector_pdf.py` | Indexa un PDF por página y sección (PyMuPDF o pypdf), busca por TF-IDF y lee solo la sección o el rango de páginas que toca. | Ninguno — uso manual | `pdf/<sha1 del fichero>.json` |
| `mapa_codigo.py` | El índice greppable de un repo Python con `ast`: módulos, clases, funciones e imports con su línea; mide la proporción mapa/código. | Ninguno — uso manual | `mapas/<carpeta>.txt` (y `.json` con `--json`) |
| `esceptico` (skill) | La ley "ningún plan sin escéptico": lanza un `Task` con model Opus a tumbar un plan contra el código real; veredicto por gravedad (cae/grieta/fleco) con evidencia. `--paquete <ruta>` corre `auditar.py` primero y le da el informe a ese mismo Opus para que lea por encima lo que el regex no ve. No es Python: se COPIA a `~/.claude/skills/esceptico/` (o `--skills-dir`), con marca en su frontmatter. | Ninguno — se invoca con `/esceptico <plan>` o `/esceptico --paquete <ruta>` | `<plan>_veredicto_esceptico.md`, junto al propio plan (nunca en `memory/`); `--paquete` no escribe nada propio (el JSON de `auditar.py` va en la respuesta, o en `--markdown` si se pide) |
| `infografia.py` | De un CSV o JSON a un SVG limpio (barras, barras horizontales, líneas, tabla), biblioteca estándar. No resuelve proyecto: no escribe en `memory/`. | Ninguno — uso manual | Nada en `memory/`: solo el `.svg` pedido |
| `imagen.py` | `crear`: cascada de proveedores — tu propio servidor local (única vía que no saca el prompt de la máquina) → proveedores con clave, en el orden de `imagen_config.json` (Pollinations, Cloudflare Workers AI, Together, Hugging Face) → AI Horde anónimo. `pintar`: foto → cuadro de pinceladas, 100% local en varios estilos (delega en `pintor.py`). `video`: anima esas pinceladas a `.mp4` (delega en `video_pintura.py`). `buscar`: encuentra una imagen ya hecha con licencia libre (Openverse/Wikimedia Commons) — no monta ni compone. `render`: escena/modelo 3D → página con three.js, con `--pintar` encadena hacia `pintor.pintar` (delega en `render3d.py`). `mundo`: motivos del mundo real — museos, Street View, webcams (delega en `mundo.py`). `vias`: qué proveedores están configurados y si responden. | Ninguno — solo a petición | `imagenes/*.png` (y, con `buscar`/`mundo --descargar`, su `.txt` de atribución) · `imagen.log` (vía, bytes, ruta, prompt recortado en `crear`; entrada/salida en `render` y `render --pintar`) · `imagen_config.json` (claves de cada proveedor, todas opcionales) |
| `pintor.py` | Motor de pinceladas (Hertzmann simplificado) en varios estilos (óleo, impresionista, acuarela, pastel, carbón, tinta: mismo motor, otro dict de parámetros) que usa `imagen.py pintar`; también CLI suelta. | Ninguno | Nada propio: escribe donde le diga quien lo invoca |
| `video_pintura.py` | Anima los trazos de `pintor.py` a `.mp4` con ritmo variable, respetando el estilo y el papel del cuadro; usado por `imagen.py video`. | Ninguno | Nada propio |
| `render3d.py` | Escenas y modelos 3D (`escena.json`, `.glb`/`.gltf`/`.obj`/`.stl`) en una página autocontenida con three.js embebido (MIT), vista explosionada; `--acabado` elige entre `mate` (de serie — no le cambia el resultado a nadie que ya use este guion: material plano de siempre, tres luces planas) y `estudio` (metal con reflejos, un entorno de reflejo PROCEDURAL sin texturas cargadas de fuera, tono ACES, sombras suaves); `--png` la captura con un navegador sin cabeza. Usado por `imagen.py render`. | Ninguno | Nada en `memory/`: el HTML/PNG se escribe junto a la entrada, o donde se indique |
| `mundo.py` | Motivos DEL MUNDO REAL para pintar: The Met/Art Institute of Chicago/Wikimedia Commons sin clave, Street View/Mapillary/webcams de Windy con clave/token propios. `contexto()` deriva lat/lon de Wikidata+Wikipedia. Usado por `imagen.py mundo`. | Ninguno | `imagenes/*` (con `--descargar`, junto a su `.txt` de atribución); lee `imagen_config.json` (`google_maps_key`, `mapillary_token`, `windy_key`) |
| `lienzo.py` | Operar con imágenes reales sin ningún modelo: fundir, doble exposición, collage, degradado, restaurar, pintar por números, borrar un objeto (`cv2.inpaint`, o `--metodo taller` para objetos grandes). | Ninguno | Nada en `memory/` salvo `borrar --metodo taller`, que solo LEE `imagen_config.json` (`taller_url`) |
| `taller.py` | Servidor local mínimo de texto→imagen (boquilla A1111: `/health`, `/sdapi/v1/txt2img`) para la vía `local` de `crear`. No se arranca solo: lo levanta el usuario a mano. | Ninguno | Nada en `memory/`: el modelo se cachea en la carpeta de Hugging Face, no en el repo |
| `notify_telegram.ps1.plantilla` | Avisa por Telegram cuando Claude Code pide permiso o espera respuesta. Viaja como plantilla; el instalador la rellena y la guarda fuera del repo. | `Notification` (solo si se instala con `instalar.py`) | Nada propio: solo llama a la API de Telegram con el token y chat id configurados |

## Privacidad y qué sale de la máquina

- **`exterocepcion.py`**: la IP viaja a `ipinfo.io`; el nombre de lugar (dicho
  por el usuario, o cacheado por IP) viaja a `open-meteo.com` y, si hace
  falta, `nominatim.openstreetmap.org`.
- **`noticias.py`**: las consultas de portada y de tema (incluidos los nombres
  propios candidatos a tema automático) viajan a `news.google.com` (RSS, sin
  clave).
- **`imagen.py crear`**: con cualquier vía que no sea `local`, el texto del
  prompt viaja a un servidor ajeno (Pollinations, Cloudflare Workers AI,
  Together, Hugging Face, o AI Horde con su clave anónima pública si no hay
  ninguna configurada) — ningún proveedor documenta en una página legible
  cuánto tiempo guarda ese prompt. `pintar` y `video` son locales por
  completo: la foto y sus pinceladas nunca salen de la máquina.
- **`imagen.py buscar`**: el TEXTO de la búsqueda viaja a Openverse y
  Wikimedia Commons (sin clave); con `--descargar`, además se descarga la
  imagen elegida desde el host que indique cada banco. Nunca toca los
  proveedores de `crear`.
- **`imagen.py mundo`**: el TEXTO del motivo viaja a la fuente que se pida —
  The Met, Art Institute of Chicago y Wikimedia Commons sin clave; Street
  View, Mapillary y las webcams de Windy SOLO si hay clave/token propios en
  `imagen_config.json` (`google_maps_key`, `mapillary_token`, `windy_key`) —
  sin ella, esa fuente concreta no toca la red. `contexto()` (para derivar
  lat/lon cuando no se da `--lugar`) consulta Wikidata y Wikipedia, sin clave.
- **`imagen.py render`**: `--html` no toca la red (three.js va embebido);
  `--png` lanza un navegador sin cabeza LOCAL contra el propio HTML por
  `file://` — no sube ni descarga nada. Con `--pintar`, el PNG resultante se
  pinta en local, igual que `pintar`.
- **`ojo.py`**: ningún verbo sale por red. `mirar` deja el fotograma en disco
  local; `texto`/`fotocopia`/`tarjeta`/`manual` hacen OCR local (motor de
  Windows o `tesseract`, los dos en la propia máquina); `despiece`/`prompt3d`
  son cálculo local (GrabCut, k-medias) sobre el fichero de entrada; `gestos`
  sirve su estado por HTTP SOLO en `127.0.0.1` — nadie fuera de la máquina
  puede leerlo.
- **`kinetica.py`**: nada sale de la máquina al montar la carpeta (GrabCut,
  inpaint y el recorte de `fondo.py`, cálculo local sobre el fichero de
  entrada); el servidor solo escucha en `127.0.0.1`. Única excepción: cerrar
  la mano dentro del holograma abre en una pestaña nueva el sitio oficial de
  la marca o el modelo reconocido — una visita web normal, y solo si la ficha
  trae `reconocimiento` con `url`.
- **`kinetico.py`**: nada sale de la máquina — lee la carpeta o el fichero de
  nodos que se le da y sirve el resultado por HTTP SOLO en `127.0.0.1`; sus
  dos verbos (`entrar`/`abrir`) nunca actúan fuera de la escena montada ni de
  la carpeta con la que se abrió.
- **`lienzo.py`**: nada sale de la máquina salvo `borrar --metodo taller`, que
  manda imagen y máscara a la URL que TÚ configures en `imagen_config.json`
  (`taller_url`) — por defecto vacía, así que sin configurarla ese método
  falla con "sin dato" en vez de mandar nada a ningún sitio.
- **`taller.py`**: el prompt que le mandes no sale de esta máquina (es
  precisamente la vía `local` de `imagen.py crear`); el modelo se descarga de
  Hugging Face la primera vez que se usa.
- **`huella.py`**, **`cuerpo.py`**, **`lector_pdf.py`**, **`mapa_codigo.py`**,
  **`infografia.py`**, **`parentesis.py`**: ninguna llamada de red — todo
  local, dentro de `memory/` o del fichero de salida que se les pida.
- **`auditar.py`**: ninguna llamada de red — solo lee ficheros de texto y, si
  hay `.git`, invoca `git log` LOCAL sobre el propio repo del paquete (nunca
  contra un remoto); nunca ejecuta el código que audita.
- **`esceptico`**: no añade una llamada de red propia; el plan (o, con
  `--paquete`, el informe de `auditar.py` y lo que el sub-agente decida leer
  del paquete) viaja al mismo servicio de modelo que el resto de la sesión,
  por el mecanismo normal de `Task`.
- `continuidad.py` no hace red POR SÍ MISMO, pero en `--arranque` y `--despertar`
  invoca a `exterocepcion.py`/`noticias.py` como librerías (con un presupuesto de
  tiempo compartido, ver "Límites honestos"), así que el proceso del gancho SÍ
  contacta con `ipinfo.io`, `open-meteo.com`, `nominatim.openstreetmap.org` y
  `news.google.com`. `vigia.py`, `propiocepcion.py`, `varas.py` y `modelo.py` no
  hacen ninguna llamada de red: solo leen y escriben dentro de `memory/`.
- El módulo **telegram** (solo vía `instalar.py`) llama a la API de Telegram
  con el token y chat id que se configuren, para avisar de permisos/esperas.
- **`presenta.py`**: toca la red por sí mismo en dos de los bloques del vídeo
  que genera — «sentidos» invoca a `exterocepcion.py` (los mismos
  `ipinfo.io`/`open-meteo.com` de arriba) y «mundo» invoca a
  `mundo.buscar()`/`descargar()` (The Met, Art Institute of Chicago,
  Wikimedia Commons); `ABYSS_SIN_RED=1` corta las dos ANTES de tocar la red
  — MEDIDO: con esa variable puesta y sin caché de lugar previa, «sentidos»
  cae al «sin dato» normal de `exterocepcion.py` en vez de llamar a la red,
  pero entonces «mundo» tampoco tiene motivo que buscar (la misma bandera
  apaga los dos bloques, no distingue cuál). Y esto es lo que importa a
  quien vaya a PUBLICAR el vídeo, no solo a quien lo genera: SIN esa
  variable, MEDIDO en el vídeo de demostración del propio paquete, el
  bloque «sentidos» deja grabado dentro del propio `.mp4` — visible en
  pantalla, no solo transmitido por red — el municipio de quien lo generó
  (por IP o por lo dicho, con la marca «(ES; por IP)»), su meteorología
  local (temperatura, humedad, viento, día/noche) y la telemetría de su
  máquina (cpu, RAM libre, disco libre, VRAM libre, temperatura de GPU). El
  bloque «auditoría», dos antes, sí anonimiza a mano la ruta absoluta del
  disco antes de dibujarla; «sentidos» todavía no tiene ningún resguardo
  parecido para el lugar y la meteo (ver "Límites honestos").

## Límites honestos

- Los ganchos corren en cada mensaje (`UserPromptSubmit`) y en cada cierre de
  turno (`Stop`): añaden latencia y gasto de proceso a cada turno, no solo al
  arrancar o cerrar la sesión.
- `sesiones/` guarda el transcript **entero** de cada sesión, en local, sin
  cifrar. Es la fuente de todo lo demás y crece sin límite salvo
  `--comprimir` (que solo gzipea, no borra).
- El vigía bloquea como mucho una vez por turno; si insiste tras el primer
  bloqueo, lo deja pasar y solo lo apunta como "reincidente".
- Con menos de 8 sesiones medidas no hay vara: `propiocepcion.py`, `varas.py`
  y la sala de relojes de `continuidad.py` dicen "sin vara todavía" en vez de
  comparar contra un puñado de puntos que no significan nada.
- "Leída" solo ve lecturas explícitas (`Read`/`cat`): lo que Claude Code
  inyecta como memoria automática no deja huella, así que el uso medido de las
  fichas subestima el real.
- La sala de los relojes compara bolsas de palabras (TF-IDF), no ideas: puede
  despertar una sesión por vocabulario compartido sin que el tema sea
  realmente el mismo, y al revés.
- No hay vuelta automática al modelo preferido: `modelo.py` solo detecta y
  avisa; el regreso lo teclea la persona con `/model`, porque ninguna API
  expone hoy una forma de hacerlo desde un gancho.
- El lugar por IP puede equivocarse de ciudad (VPN, redes móviles) y solo se
  refresca al arrancar una sesión; "lo dicho" depende de que el mensaje use
  una fórmula reconocida, no cualquier forma de decir dónde se está.
- Los titulares y candidatos a tema son texto ajeno: dato para leer, nunca
  instrucción a seguir, pero siguen siendo contenido descargado sin revisar.
- En `imagen.py crear`, solo la vía `local` mantiene el prompt en la máquina;
  AI Horde puede completar la generación y aun así fallar la descarga final en
  redes que bloquean su host de almacenamiento.
- `pintar`/`video` dependen de dependencias opcionales (ver abajo): sin
  ellas, fallan con un mensaje claro (`sin cuadro: ...` / `sin video: ...`),
  nunca con una traza cruda.
- La parte de red de `--arranque` (ipinfo + noticias) y de `--despertar` (lugar
  dicho + meteo) va acotada por un presupuesto de tiempo compartido (por defecto
  4 s y 2,5 s; `ABYSS_PRESUPUESTO_ARRANQUE`/`ABYSS_PRESUPUESTO_DESPERTAR`): con la
  red caída o muy lenta, se corta antes de comerse el timeout del propio gancho —
  el precio es que un "casi lento" también se corta, no solo el que está muerto
  del todo.
- **`huella.py`** APAGADO por defecto: su gancho `PostToolUse` corre tras CADA
  herramienta, y la foto de puertos/procesos cuesta (medido: ~950 ms por
  PowerShell combinado en Windows) hasta que el propio guion, midiendo su
  propio coste, pasa a fotografiar solo tras comandos que parecen persistentes
  (heurística declarada, no una ley).
- **`cuerpo.py`** nunca ordena nada: no cierra procesos, no baja de modelo, no
  sugiere nada — mide, y la decisión de qué hacer con esa medida es de quien
  la lea, nunca del propio guion.
- **`presenta.py`**: el bloque «sentidos» del vídeo que genera no anonimiza el
  lugar ni la meteo, a diferencia del bloque «auditoría» con la ruta del
  disco — publicar el vídeo por defecto publica también el municipio y la
  meteo de quien lo generó. `ABYSS_SIN_RED=1` corta esa fuga (el bloque cae a
  «sin dato»), pero de paso apaga también el bloque «mundo» entero: hoy no
  hay forma de pedir solo una de las dos cosas.
- **`imagen.py buscar`** no monta ni compone: para una escena con varios
  elementos concretos hace falta `crear`, no una búsqueda de una sola imagen.
- **`imagen.py mundo`** tampoco monta ni compone (mismo criterio que
  `buscar`): el motivo se pinta tal cual llega. `streetview`/`mapillary`/
  `webcam` necesitan lat/lon: si no se da `--lugar` y el motivo no es un
  lugar que Wikipedia reconozca con coordenadas, esa fuente se avisa
  "sin lugar: …" y no aporta candidatos — nunca se inventa un punto.
- **`imagen.py render --png`** (y por tanto `--pintar`, que lo fuerza)
  necesita un navegador sin cabeza instalado en la máquina (Edge/Chrome en
  Windows; `google-chrome`/`chromium` en Linux/macOS) — dependencia opcional
  del SISTEMA, no de `requirements.txt`; sin uno, "sin dato: no hay
  navegador sin cabeza" y código 2, aunque la página HTML ya se haya
  escrito. Es un visor y editor de vistas, no un modelador: no repara
  mallas, no simplifica, no exporta, y la vista explosionada exige piezas
  YA separadas en el fichero de entrada (un `.stl` de una sola malla no
  explosiona nada).
- **`lienzo.py borrar`** sin `--metodo taller` deja un borrón visible en
  objetos grandes o fondos con estructura (medido en su prueba, no solo
  declarado) — por eso avisa ("borrón probable…") cuando el área o la
  textura del fondo lo sugieren, en vez de dejarlo aparecer sin más; y
  `--metodo taller` necesita un A1111/Forge real detrás — el `taller.py` de
  este paquete sirve `txt2img`, no el `img2img` con máscara que ese método
  pide.
- **`taller.py`** en CPU tarda MINUTOS por imagen, no segundos; su VRAM no está
  medida en la máquina de desarrollo (sin GPU CUDA ahí) — no se afirma una
  cifra sin haberla medido de verdad.
- **`esceptico`** depende de que el entorno deje fijar `model: opus` para el
  sub-agente; si no puede, la propia skill debe decirlo en la respuesta en vez
  de callarlo (mismo principio que el aviso `[modelo]` del resto del paquete).
  Con `--paquete`, `auditar.py` es texto y regex, no un parser ni un sandbox
  (una URL solo mencionada en un comentario cuenta igual que una llamada
  real) y el Opus que lee por encima tampoco ejecuta el paquete: lo que un
  README miente y ningún fichero desmiente puede seguir sin detectarse.
- **`ojo.py fotocopia`/`tarjeta`/`manual`** no reconstruyen lo que el motor
  de OCR no lee (campo vacío, nunca un valor inventado); `fotocopia --escaner`
  y `--camara` nunca se ejercen contra hardware real en la batería de
  pruebas del paquete — solo el cableado se prueba forzado. `manual` no
  resume: entrega el texto limpio y ordenado, resumirlo es cosa de quien lo
  pida, con el texto delante.
- **`ojo.py despiece`/`prompt3d`** no son reconstrucción 3D ni reconocimiento
  de objetos: miden geometría y color de la silueta 2D de una sola foto
  (heurística de composición fotográfica, nunca una medida de profundidad
  real) y dicen qué forma/color midieron, nunca qué es el objeto.
- **`ojo.py gestos`** hereda el `1,7` de la razón dedo-extendido de un post
  ajeno (técnica, no vocabulario) sin remedirlo todavía en esta máquina; el
  pellizco y la escala normalizan por percentiles de la PROPIA sesión y
  dicen «sin vara todavía» bajo 30 muestras en vez de fingir un corte. Se
  queda corriendo (servidor + bucle de cámara) hasta que se interrumpe: no
  es un verbo que "termina y devuelve un resultado" como los demás. Y nada
  consume ese estado todavía: la página que genera `render3d.py` no lee
  `/estado` ni reacciona a él, y ningún gesto llega a capturar un PNG —
  `gestos.py` sirve el JSON correcto y probado, con el vocabulario ya
  resuelto en cada campo, pero conectarlo a la página es trabajo pendiente,
  declarado, no prometido como hecho. El visor de `kinetica` sí mueve cosas
  con este vocabulario (piezas, órbita, holograma), pero NO pasa por
  `gestos.py`: lo reimplementa dentro del navegador, con su propia constante
  de quietud.
- **`kinetica.py`** no es reconstrucción 3D ni un escáner: sale de UNA foto
  2D, sin cámara estéreo ni sensor de profundidad; sin `--regiones` el
  resultado es automático y explícitamente peor (piezas sin nombre real,
  `auto_1`/`auto_2`…, avisado y no disimulado). `abyss/vendor/mp/` (las manos
  de verdad) no viene en el repositorio — sin `python instalar.py --manos`,
  el visor se sirve igual, solo sin manos, con aviso en pantalla.
- **`kinetico.py`** decreta la profundidad de carpeta a mostrar
  (`--hondura`), no la mide; el tamaño de una esfera (bytes) y el de un cubo
  (ficheros dentro) son unidades distintas que no se comparan entre sí; y el
  color por formato sale de la EXTENSIÓN del nombre, nunca de abrir el
  fichero para mirar dentro. Por encima de `--tope` una carpeta se colapsa en
  una sola bola que dice cuántos descendientes tiene, en vez de intentar
  mostrarlos todos.

## Dependencias

Python 3.12 o superior, biblioteca estándar para casi todo. La vía
recomendada para lo demás es dejar que el propio paquete lo resuelva
(quinta tanda) en vez de leer [`requirements.txt`](requirements.txt) a
mano:

```
python instalar.py --dependencias                        # qué falta, con tamaño aprox.
python instalar.py --instalar-dependencias [mod1,mod2]    # instala SOLO lo que de verdad falte
```

`--dependencias` mira, con un `import` real bajo el intérprete que se vaya a
usar (nunca una lista de paquetes fijada a mano), qué falta de cada pieza
opcional agrupada por módulo (`imagen`, `ojo`, `lector_pdf`, `gestos`) y lo
dice en una tabla con tamaño aproximado. `--instalar-dependencias` (con una
lista opcional de módulos; sin lista, todos) instala con `sys.executable -m
pip install <paquete>` UNA a una, enseñando el comando antes de correrlo y el
resultado después — nunca en silencio, nunca en el arranque, nunca dentro de
un gancho; si un paquete falla (sin pip, sin red, `pip install` con error) se
dice con su última línea de error y se sigue con el resto, sin reintentar
solo. No existe `--desinstalar-dependencias`: quitar paquetes de Python del
entorno de alguien es más arriesgado que ponerlos, y se deja a quien lo
instaló. Las dos banderas — y la casilla «Dependencias…» de la ventana Tk —
hablan en `--idioma es|en` (por defecto, el del sistema);
[`requirements.txt`](requirements.txt) lleva la misma lista, toda comentada,
para quien prefiera instalar a mano sin pasar por `instalar.py`.

### Lo que SÍ se puede instalar con `pip`

- **Pillow + numpy** — para `pintor.py` (y el verbo `imagen.py pintar`, que lo
  usa) y para `lienzo.py` (fundir, doble, collage, degradado, restaurar,
  numeros, borrar). Import de nivel de módulo: sin ellas, falla con
  `ModuleNotFoundError` al importar, no con un dict de error silencioso.
- **imageio-ffmpeg** (trae su propio binario de ffmpeg) — para
  `video_pintura.py` (`imagen.py video`) y, con el mismo binario, para
  `presenta.py` (ver su propio apartado, más abajo).
- **opencv-python** (`cv2`), opcional — para `ojo.py mirar` (sin ella, "sin
  cv2: no hay ojo"), para `ojo.py fotocopia/despiece/prompt3d` (delegados en
  `lectura_visual.py`/`volumen.py`, que necesitan además `numpy`), para
  `gestos.py` (junto con `mediapipe`, ver abajo), y para `lienzo.py`
  (reducción de ruido, arañazos, `borrar` y las zonas conexas y el filtro de
  moda de `numeros` — sin ella, cada uno de esos pasos usa un equivalente en
  Python puro: más lento, o directamente se salta con aviso, nunca falla en
  silencio).
- **`mediapipe`**, opcional y solo para `ojo.py gestos`/`gestos.py` (control
  de la escena por gestos de la mano) — junto con `opencv-python` para leer
  la cámara. Sin ella, el mensaje dice exactamente qué instalar y sale con
  código 2; nunca se instala nada por su cuenta.
- **PyMuPDF (`fitz`) o pypdf**, opcional (basta una de las dos) — para
  `lector_pdf.py`. `fitz` da secciones por tamaño de letra real; sin ninguna
  de las dos, «sin dato: pip install pymupdf».

### Lo que NO se puede instalar con `pip` (hace falta el gestor del sistema)

`--dependencias` también lo dice, con el comando EXACTO para el sistema
operativo de la máquina donde se corre — nunca uno genérico fingiendo que
vale para cualquiera:

- **Motor OCR fuera de Windows**: en Windows, el motor de reconocimiento de
  texto viene con el sistema (WinRT, `Windows.Media.Ocr`) — **no hace falta
  instalar nada**. En Linux, el binario se instala con
  `sudo apt install tesseract-ocr tesseract-ocr-spa` (u homólogo del gestor
  de la distro); en macOS, con Homebrew: `brew install tesseract
  tesseract-lang`. El código llama siempre al binario `tesseract` por PATH
  (`subprocess`), nunca a `pytesseract` — instalar ese paquete de pip no
  activaría nada, así que ni `instalar.py` ni `requirements.txt` lo ofrecen.
  Sin ninguna de las dos vías, `ojo.py texto/fotocopia/tarjeta/manual` dice
  «sin dato: no hay motor OCR» y sale con código 2.
- **`taller.py` (torch + diffusers)**: pesan gigas y `torch` depende de la
  tarjeta. `--dependencias` detecta si hay GPU NVIDIA (`nvidia-smi`) y
  escribe el comando exacto — con GPU, `pip install torch --index-url
  https://download.pytorch.org/whl/cu121`; sin ella, `pip install torch` a
  secas — más `pip install diffusers` aparte; pero no instala nada de esto
  por su cuenta (ver "Taller local" abajo).
- **Navegador sin cabeza** (Edge/Chrome en Windows; `google-chrome`/
  `chromium` en Linux/macOS), opcional y del SISTEMA, no de
  `requirements.txt` — para `render3d.py`/`imagen.py render --png` (y
  `--pintar`, que lo fuerza; y los bloques «3D»/«holograma» de `presenta.py`).
  Se busca en las rutas habituales; sin él, la página HTML se escribe igual y
  solo falla la captura ("sin dato: no hay navegador sin cabeza", código 2).
  `render3d.py` no depende de nada más: three.js va embebido en
  `abyss/vendor/`.
- **Escáner WIA**, del propio sistema y opcional — una fuente MÁS de
  `ojo.py fotocopia --escaner` (nunca el camino: sin uno conectado, «sin
  escáner: uso la cámara o un fichero» y sigue por la vía normal, sin error).

### `presenta.py`, sus dependencias

`presenta.py` no tiene fila propia en `--dependencias` (no es uno de los
módulos que instala `instalar.py`), pero importa `pintor.py` y
`video_pintura.py` como librería, así que hereda sus dependencias
OBLIGATORIAS — no opcionales para él —: **Pillow, numpy e imageio-ffmpeg**
(el mismo grupo `imagen` de arriba). Sin cualquiera de las tres,
`python presenta.py` falla al IMPORTAR, antes de llegar a generar nada. El
resto es opcional bloque a bloque, exactamente igual que en la pieza que cada
uno invoca: `opencv-python` + un motor OCR para el bloque «el ojo», un
navegador sin cabeza para «3D»/«holograma», y red para «mundo» y «sentidos»
(este último vía `exterocepcion.py`; `ABYSS_SIN_RED=1` corta las dos ANTES de
tocarla — ver "Privacidad y qué sale de la máquina" para lo que «sentidos»
deja grabado en el vídeo si esa variable no se pone). Sin alguna de ellas,
`presenta.py` no revienta: salta ese bloque y lo dice, por stdout y en el
propio vídeo — "se hizo con lo que había".

### Taller local (opcional, el coste dicho sin adornos)

`taller.py` es un servidor mínimo que sirve texto→imagen en tu propia
máquina, con la misma forma que espera `imagen.py crear --via local`. Nada de
esto se instala ni se arranca por su cuenta — ni el módulo `taller` de
`instalar.py`, ni ninguna otra pieza de este paquete llama a `pip install` ni
lanza el servidor: hace falta que lo decida quien lo usa, a mano.

- **Dependencias**: `pip install diffusers` y, aparte, `torch` — con CUDA si
  hay una GPU NVIDIA (`python instalar.py --dependencias` ya calcula el
  comando exacto para ESTA máquina, por `nvidia-smi`; para lo que ese comando
  no cubra, sigue las instrucciones de
  [pytorch.org/get-started/locally](https://pytorch.org/get-started/locally/)
  para la combinación exacta de tu sistema). Instalar el `torch` equivocado
  es la forma más común de que esto no arranque. Sin GPU, la versión CPU
  funciona igual, solo que más despacio (ver abajo).
- **Descarga del modelo**: al PRIMER `POST /sdapi/v1/txt2img` (no al arrancar
  el servidor), `taller.py` descarga el modelo (`Lykon/dreamshaper-8` por
  defecto, unos GB) de Hugging Face a la caché que le digas con
  `--cache-dir` (por defecto, la caché propia de Hugging Face en tu perfil de
  usuario) — nunca dentro de este repositorio.
- **Velocidad**: en `cuda` o `mps`, segundos por imagen; en `cpu`, MINUTOS por
  imagen — el propio servidor lo avisa por stdout al arrancar si detecta que
  va a correr en `cpu`, antes de que llegue la primera petición.
- **VRAM**: no medida en la máquina de desarrollo (sin GPU CUDA disponible
  ahí) — este README no repite ninguna cifra de VRAM que no se haya medido de
  verdad en ese hardware.
- **Límite declarado**: `taller.py` solo sirve `txt2img`; el `img2img` con
  máscara que necesitaría `lienzo.py borrar --metodo taller` para objetos
  grandes no está implementado en este servidor — hace falta un A1111/Forge
  real, o ampliarlo.

---

Abyss no está afiliado a Anthropic; Claude y Claude Code son marcas de
Anthropic.

## Licencia

Apache License 2.0 — ver [`LICENSE`](LICENSE). Las tres obras de terceros que
sí viajan dentro del repositorio (three.js, MediaPipe Tasks Vision, U²-Net p)
conservan cada una la suya — el detalle, con dónde vive cada fichero y qué
tamaño mide, está en [`NOTICE.md`](NOTICE.md).

## Las claves opcionales

Casi todo funciona sin ninguna clave. Lo que hace falta clave lo dice y **no toca la red**:
sin `google_maps_key`, la fuente de Street View no intenta la llamada, avisa «sin clave» y
sigue.

```
python instalar.py --claves
```

O el botón **Claves…** de la ventana del instalador, que hace lo mismo y además deja
ponerlas: una fila por clave, con lo que desbloquea, dónde se saca y su aviso al lado. El
campo va tapado, un campo en blanco no borra nada, y al guardar dice cuántas ha escrito,
nunca cuáles.

Dice cuáles hay, cuáles tienes puestas —nunca su valor—, qué desbloquea cada una, qué pasa
sin ella y dónde se saca. Para ponerlas se edita `imagen_config.json` en tu carpeta de
memoria, que vive **fuera** de este repositorio.

**Ninguna clave viaja dentro del paquete, y no es una precaución: es que no se puede.**
Publicar una credencial bajo una licencia abierta concede a todo el mundo el derecho a
redistribuirla, y esa concesión no se retira: cada copia se la lleva. Además, las cuotas de
estos servicios son por cuenta, no por persona, así que una clave compartida es una cuota
compartida que agota el primero que la use en serio. Y una de ellas, la de Street View,
factura de verdad: pasadas las 10.000 llamadas gratis al mes cobra 7,00 $ por cada 1.000, sin
tope por defecto, al dueño de la clave.

La única excepción viaja porque su dueño la publicó: `horde_key` viene con `0000000000`, la
clave anónima que el propio proyecto de AI Horde ofrece a quien no quiere registrarse. Por eso
el paquete genera imágenes nada más instalarse, sin pedirte nada.

## A dónde llama este paquete, y desde dónde

El propio auditor de Abyss (`abyss/auditar.py`, comprobación 4) exige que **todo host que
el código use aparezca nombrado en un README**. Un host que el código llama y la
documentación calla es un hallazgo de gravedad «rompe», y con razón: es lo que un paquete
hostil nunca escribiría. Aquí están todos, con quién los llama y cuándo.

Nada de esto ocurre solo: cada llamada nace de una habilidad que tú invocas en ese turno.

**Sitio y meteo** (skill `exterocepcion`, en cada prompt si la instalas)
`api.open-meteo.com`, `geocoding-api.open-meteo.com` — el tiempo y las coordenadas de un
nombre de lugar. Sin clave.

**Titulares** (skill `noticias`, al arrancar la sesión)
Google News RSS. Sin clave.

**Crear imágenes** (skill `imagen`, verbo `crear`, solo si lo pides)
`gen.pollinations.ai`, `api.cloudflare.com`, `api.together.xyz`, `router.huggingface.co`,
`aihorde.net` — proveedores en cascada; los cuatro primeros solo si les pones clave en
`imagen_config.json`, el último de forma anónima.

**Buscar imágenes con licencia** (skill `imagen`, verbo `buscar`)
`api.openverse.org`, `commons.wikimedia.org`.


**Enlaces que aparecen en el código y que este paquete NUNCA llama**
Estos cinco hosts salen en el texto del código, y el auditor los señala por eso —
su regla es que todo host que aparezca se nombre donde alguien lo lea. Ninguno se
consulta: no hay ninguna petición de red hacia ellos.

- `enter.pollinations.ai`, `developers.cloudflare.com`, `docs.together.ai`,
  `developers.google.com` — en el bloque de ayuda de
  [`plantillas/imagen_config.json`](plantillas/imagen_config.json): son la página
  donde CADA proveedor explica cómo sacar su clave. Están ahí para que no tengas
  que buscarla.
- `www.audi.com` — en la tabla `MARCAS` de [`abyss/kinetica.py`](abyss/kinetica.py):
  el sitio oficial de una marca, que el visor OFRECE como enlace si reconoce esa
  marca. Lo abre tu navegador si tú cierras la mano, no este paquete.

**Museos y calle** (skill `imagen`, verbo `mundo`)
`collectionapi.metmuseum.org` (Metropolitan) y `api.artic.edu` / `artic.edu` (Art Institute
of Chicago), sin clave. `maps.googleapis.com` (Street View), `graph.mapillary.com` /
`mapillary.com` y `api.windy.com` / `windy.com` **solo con clave**: sin ella, esa fuente no
toca la red. `es.wikipedia.org` y `wikidata.org`, para el pie de foto de una obra.

**La web oficial de un producto reconocido** (skill `kinetica`)
`vivo.com`, `zeiss.com`, `leica-camera.com`, `hasselblad.com`, `sony.com`, `global.canon`,
`nikon.com`, `fujifilm.com` — nunca se llaman: son la lista de destinos a los que el visor
puede ABRIR el navegador si reconoce esa marca **en la propia foto**.

**Descargas del instalador** (`instalar.py`, solo con la bandera que las pide)
`storage.googleapis.com` (el modelo de manos de MediaPipe, con `--manos`),
`cdn.jsdelivr.net` y `apache.org` — ninguna se descarga sola.

**Texto en documentos, nunca una llamada**
`github.com` (`fondo.py`: de dónde bajar el modelo de recorte), `threejs.org` y
`discourse.threejs.org` (`render3d.py`: la fuente de una técnica), `w3.org`
(`infografia.py`: el espacio de nombres de SVG) y `copia.ejemplo.com` (`vigia.py`: un
ejemplo de dominio falso dentro de un comentario).

**Y lo que NO sale de tu máquina, pase lo que pase**: la memoria, los transcripts, las
medidas de sesión, los PDF que lees, las fotos que pintas y todo lo que escribe el paquete
en `mem/`.
