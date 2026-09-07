# TERCERA TANDA · render 3D con three.js y estilos del pintor
Abyss · 7-sep-2026 · complemento de `ESPECIFICACION.md` y `ESPECIFICACION_TANDA2.md` (mismas reglas:
ley o medida; fail-closed; dependencias opcionales dentro de `try`; datos en `mem`; castellano; nada
personal; cada cifra del docstring es una medida de una máquina, no una ley).

## T3.1 · `render3d.py`: escenas 3D con three.js, y de ahí al pintor
Petición del usuario (7-sep 07:44): «añade three.js al pintor, que pueda hacer renders en 3D pero que
también lo use para crear imágenes y después las pinte en HQ».

- `render3d.py <modelo.glb|.gltf|.obj|.stl|escena.json> --html [salida.html] [--explosion 0.5]
  [--camara x,y,z] [--mirar x,y,z] [--fondo #rrggbb] [--luz calida|fria|neutra] [--ancho 1600 --alto 900]`:
  escribe una página autocontenida con three.js EMBEBIDO (fichero `abyss/vendor/three.min.js`, versión
  fijada y anotada con su licencia MIT en `abyss/vendor/LICENSE-three.txt`; sin red para verla) con
  órbita (OrbitControls embebido igual), luces, rejilla opcional, alambre, planos de corte, y un
  deslizador de VISTA EXPLOSIONADA: cada malla se desplaza desde el centro del conjunto según su
  centroide, con la distancia del deslizador. Botón «Capturar PNG» que descarga el fotograma.
- `escena.json` (para diagramas sin CAD): `{"unidades": "m", "piezas": [{"nombre", "tipo":
  caja|cilindro|esfera|texto|plano, "pos": [x,y,z], "tam": [..], "color": "#..", "grupo": "..."}],
  "camara": {...}}`. `--explosion` agrupa por `grupo` si existe.
- `render3d.py ... --png salida.png`: render SIN navegador visible con Chrome o Edge sin cabeza
  (busca `msedge.exe`/`chrome.exe` en las rutas habituales de Windows, `google-chrome`/`chromium` en
  PATH en Linux/macOS; medido el 7-sep: `"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
  --headless --disable-gpu --window-size=W,H --screenshot=… file:///…` produce el PNG); sin navegador,
  «sin dato: no hay navegador sin cabeza» y código 2. Espera al evento de render (la página escribe
  `document.title = "listo"` cuando ha pintado el primer fotograma; el guion reintenta la captura
  hasta 3 veces con 1,5 s entre ellas y lo dice).
- Fallback declarado: three.js renderiza en WebGL; sin aceleración el navegador sin cabeza usa
  SwiftShader (software) y tarda más; no hay «fallback a WebGL» porque WebGL es el camino normal.
- `imagen.py render <modelo|escena.json> [--png] [--pintar [--estilo …] [--alta --acabado --suave]]`:
  encadena render → PNG → `pintor.pintar(...)`. Las dos salidas se apuntan en `mem/imagen.log`.
- Límites en el docstring y la skill: visor y editor de vistas, no modelador; la explosión exige
  piezas separadas (un STL de una sola malla no se explosiona); la página pesa lo que pesa three.js.
- Pruebas: `escena.json` sintética de 3 piezas → HTML que contiene las 3 por nombre y el deslizador;
  el HTML no referencia ninguna URL externa (grep de `http` fuera de comentarios de licencia); con
  navegador sin cabeza disponible, `--png` produce un PNG ≥ 10 KB de las dimensiones pedidas; sin él,
  código 2 y mensaje; `imagen.py render --pintar` deja PNG + trazos.

## T3.2 · Estilos del pintor (motor único, parámetros distintos)
Petición del usuario (7-sep 07:44) para un pintor de otro proyecto y, de paso, para Abyss: acuarela,
impresionista, pastel, tonos más o menos vivos, más o menos trazos, pinceles más o menos gordos.
Prototipado el 7-sep (`pintor_estilos.py`, sobre una imagen de 768×768 a 1200 px de ancho, 33 s
los seis cuadros): óleo 172.593 pinceladas · impresionista 76.358 · acuarela 39.972 · pastel 35.098 ·
pincel gordo con pocos trazos 4.235.

- `pintor.pintar(..., estilo="oleo|impresionista|acuarela|pastel", **ajustes)` y CLI `--estilo` más
  ajustes sueltos: `--radios 28,14,7,4,2` · `--umbral 60,45,32,24,18` · `--longitud 12,12,10,8,6` ·
  `--alfa 0.42` (opacidad por capa: la capa entera se compone con alfa, que es lo que da la
  acuarela por capas) · `--jitter-color 14` · `--jitter-rumbo 0.35` (radianes) · `--papel #f9f7f0` ·
  `--saturacion 1.18` · `--luz 1.05` · `--mezcla-blanco 0.28` (pastel). Cada estilo es un dict de
  esos parámetros (tabla en el docstring); un estilo no es un algoritmo distinto.
- El JSON de trazos guarda el estilo y los parámetros (`"estilo"`, `"papel"`, `"alfa"`) para que
  `video_pintura.py` reproduzca el cuadro igual (papel de fondo, alfa por capa).
- `--acabado` y `--suave` valen para todos los estilos.
- Pruebas: con una imagen sintética, cada estilo produce PNG y trazos; `acuarela` tiene menos
  pinceladas que `oleo` y su fondo es el papel donde no hay trazo; `--saturacion 0` da un cuadro en
  grises (medido: desviación entre canales < 2).

## Skills, instalador, README
- `skills/imagen/SKILL.md`: verbo `render` («haz un render 3D de…», «vista explosionada de…»,
  «render this model», «exploded view») y los estilos («píntalo como acuarela», «más pastel», «con
  pinceles gordos y pocas pinceladas»). Módulo «render3d» en `instalar.py` (declara: three.js
  embebido MIT; navegador sin cabeza para `--png`). README.md y README.en.md: pieza nueva en «Manos» y
  estilos en la fila de imagen; sección de dependencias: navegador sin cabeza (opcional).

### Estilos añadidos (7-sep 07:54, petición del usuario: «el David a carbón»)
- `carbon`: saturación 0, papel gris cálido claro, trazos finos (radios 6,3,2,1) con ruido de rumbo
  alto y dos direcciones (a lo largo del contorno y a 45°: tramado), opacidad 0,6 por capa para que
  el tramado oscurezca al superponerse, y un difuminado final suave (radio 1) que hace de esfumino.
- `tinta`: saturación 0, papel blanco, solo dos radios (3 y 1), umbral alto (deja blanco lo claro),
  opacidad 1, sin ruido de color.
- Pruebas: `carbon` y `tinta` dan desviación entre canales < 2 (gris de verdad); `tinta` deja más
  de la mitad del lienzo con el color del papel en una imagen sintética clara.

## T3.3 · `imagen.py mundo`: motivos del mundo real (medido 7-sep 07:54 desde la máquina del usuario)
Petición del usuario: la búsqueda de motivos «debe incluir Street View o Google Maps, webs museísticas,
de historia, de arte, no los repos de imágenes; tiene que plasmar cosas del mundo real».
- `imagen.py mundo "<motivo>" [--fuente met|artic|commons|streetview|mapillary|webcam|todas] [--n 5]
  [--descargar] [--lugar lat,lon --rumbo 270 --inclinacion 10 --campo 80]`:
  | fuente | qué da | clave | medido |
  |---|---|---|---|
  | The Met (collectionapi.metmuseum.org) | obras de la colección, dominio público con imagen original | ninguna | 200 en 0,5 s; «Last Supper» 67 resultados; objeto 437213 con `primaryImage` |
  | Art Institute of Chicago (api.artic.edu + IIIF) | obras, dominio público, `image_id` IIIF | ninguna | 200 en 0,7 s; «Michelangelo» 3 resultados de dominio público |
  | Wikimedia Commons (obras y lugares) | la obra o el lugar en alta resolución, con licencia | ninguna | La última cena de Leonardo: 9600×4800, dominio público |
  | Google Street View Static | la vista a pie de calle desde un punto, rumbo e inclinación | clave de Google Maps Platform (la pone el usuario) | 403 sin clave: «You must use an API key» |
  | Mapillary (a pie de calle, abierto) | vistas a pie de calle con licencia CC BY-SA | token OAuth de Mapillary | error 190 sin token |
  | Windy webcams | el mundo EN DIRECTO desde cámaras públicas cerca de un punto | clave de Windy | 403 sin clave |
  Contexto del motivo (qué es, dónde está, de quién): Wikidata `wbsearchentities` + Wikipedia REST
  (sin clave; 200 medido), para que el motivo lleve su historia y su lugar (lat, lon) y de ahí salga
  la vista a pie de calle.
- Devuelve candidatos con fuente, título, autor/lugar, licencia, tamaño y URL; con `--descargar`
  guarda con atribución. Las claves van en `imagen_config.json` (`google_maps_key`, `mapillary_token`,
  `windy_key`). El texto del motivo viaja a esas fuentes; se dice.
- Sin combinar ni componer: el motivo se pinta tal cual llega (o se esboza en el taller y se pinta).
- Pruebas contra respuestas JSON guardadas (sin red) por fuente; y que sin clave las fuentes con
  clave devuelven «sin clave: …» y no una traza.
