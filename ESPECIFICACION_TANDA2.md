# SEGUNDA TANDA · siete piezas nuevas
Abyss · 6-sep-2026 · complemento de `ESPECIFICACION.md` (§1 contrato, §2 correcciones, §4
instalador, §5 docs, §6 pruebas siguen valiendo para todo lo de aquí). Aprobada por el usuario
(«dale al pack completo»). Se construye SOBRE la primera tanda ya revisada: no se toca lo que
pasó la revisión salvo para registrar los módulos nuevos en el instalador, el README y `docs/leyes.md`.

Regla común a las siete: **miden, no decretan**. Cortes de la propia distribución (con menos de
8 muestras: «sin vara todavía (n=…)», nunca un número inventado); fail-closed (sin dato = «sin
dato», nunca un valor por defecto que parezca medido); cada pieza declara en su docstring qué
dependencias externas usa, qué sale de la máquina (por defecto NADA) y qué NO puede prometer.
Datos en `mem` (resuelto por `rutas.resolver`), nunca junto al código. Castellano. Biblioteca
estándar salvo donde se diga; lo opcional se importa dentro de un `try` y su ausencia se dice.

## T2.1 · `parentesis.py` — lo que no entra en memoria
Es el §8 de `ESPECIFICACION.md`, tal cual. Resumen operativo:
- `--abrir [motivo]` / `--cerrar`: tramo por sesión en `mem/parentesis.json` (session_id, inicio,
  fin, motivo opcional). Dentro del tramo NO viaja nada: `continuidad.guardar()` copia el transcript
  saltando esas líneas (por marca de tiempo `timestamp` de cada línea del jsonl); frases, bolsas,
  relojes, sala de relojes y propiocepción ignoran el tramo; el vigía no lo usa como evidencia.
- `--omitir-sesion [id]`: escribe en `mem/sesiones/.omitir` (ya existe en continuidad).
- `--recortar <jsonl> "<último mensaje del usuario que se conserva>"` y `--recortar-tramo <jsonl>
  <inicio_iso> <fin_iso>`: recortan el transcript LOCAL con copia `.antes`; se niegan si el hilo
  está vivo (`mem/.vivo/<id>` con latido de menos de 2 min) y lo dicen. `recortar_hilo.py` se
  funde aquí y desaparece como fichero suelto.
- Lo que no promete (docstring + README): lo ya enviado a la API ya viajó; esto gobierna la
  memoria local y lo que el asistente vuelve a leer.
- Sin gancho. El asistente lo llama cuando el usuario lo pide.
- Pruebas: transcript sintético con tramo marcado → la copia en `sesiones/` no lo contiene; las
  bolsas no llevan sus palabras; `--recortar` deja `.antes` y conserva hasta la respuesta al
  mensaje dado; `--recortar` sobre un hilo con latido reciente se niega.

## T2.2 · `huella.py` — todo lo que toco fuera de mi carpeta
Motivo: el 6-sep el asistente dejó un servidor escuchando en un puerto y tres clones de un
proyecto ajeno en Temp, y los cazó a mano. Un hilo debe poder decir al cerrar QUÉ tocó.
- Ganchos: `SessionStart` (foto inicial: puertos en escucha y PIDs con su hora de arranque),
  `PostToolUse` (por cada herramienta: si es `Write`/`Edit`/`NotebookEdit`, la ruta escrita; si es
  `Bash`/`PowerShell`, el comando y, tras él, la DIFERENCIA de puertos y procesos respecto a la
  foto anterior), `Stop` (resumen de una línea solo si hay algo vivo: «[huella] 1 proceso y 1 puerto
  abiertos por este hilo siguen vivos: `--informe`»).
- Registro: `mem/huella/<session_id>.jsonl` (una línea por evento: ts, tipo, ruta/pid/puerto,
  comando recortado a 200 caracteres). Fuera de `mem`, nada.
- `--informe [id]`: ficheros escritos (agrupados por raíz), procesos arrancados aún vivos (pid,
  nombre, hora), puertos abiertos aún en escucha. `--limpiar [id] [--si]`: mata SOLO procesos
  cuyo pid Y hora de arranque coincidan con lo registrado (un pid reutilizado no se toca) y borra
  SOLO ficheros registrados que estén bajo el directorio temporal del sistema o bajo
  `mem/`; todo lo demás se lista y no se toca. Sin `--si`, solo muestra lo que haría.
- Medida de puertos/procesos: Windows por PowerShell (`Get-NetTCPConnection -State Listen`,
  `Get-Process` con `StartTime`); Linux/macOS por `ss -ltnp`/`lsof -iTCP -sTCP:LISTEN` y `ps -o
  pid,lstart`; si el comando no existe: «sin dato» y el gancho calla. Coste: la foto de puertos y
  procesos tras CADA Bash cuesta; medirlo (ms) y apuntarlo en el propio registro; si la mediana
  supera 1,5 s, el gancho pasa a fotografiar solo tras comandos que contengan `start`, `Start-`,
  `python`, `node`, `serve`, `&`, `nohup` (dicho en el docstring como lo que es: heurística).
- Pruebas: con un JSON de PostToolUse falso de `Write` queda la ruta; con un `Bash` que arranca
  `python -c "import time; time.sleep(30)"` aparece el pid en `--informe` y `--limpiar --si` lo
  mata y lo dice; un pid registrado cuya hora de arranque no coincide NO se mata.

## T2.3 · `cuerpo.py` — el cuerpo de la máquina, con normal propia
- Canales: cpu (% uso), ram_libre (MB), disco_libre (GB, del disco de `mem`), vram_libre (MiB,
  `nvidia-smi --query-gpu=memory.used,memory.total,temperature.gpu --format=csv,noheader`),
  temp_gpu, bateria (% y si carga). Windows: RAM por `ctypes` (`GlobalMemoryStatusEx`), CPU por
  PowerShell (`Get-CimInstance Win32_Processor | Measure LoadPercentage`) o `wmic`, batería por
  `Win32_Battery`; Linux/macOS: `/proc/meminfo`, `/proc/loadavg`, `/sys/class/power_supply`,
  `vm_stat`/`sysctl`. Sin instrumento: «sin dato», jamás cero.
- Normal propia: cada medida se apunta en `mem/cuerpo.jsonl` (ts, canales). Con ≥ 8 medidas,
  cada canal se lee contra sus cuantiles (p5, p50, p95) del propio historial; con menos, «sin
  vara todavía (n=…)».
- Ganchos: `SessionStart` una línea `[cuerpo] cpu 12% · ram libre 9,8 GB · vram libre 11,7 GiB
  (p50 tuyo 8,1) · disco 210 GB · batería 87% cargando`; `UserPromptSubmit` SOLO si algún canal
  sale de su p5–p95 propio («[cuerpo] vram libre 1,2 GiB: por debajo de tu p5 (3,4)»), si no,
  silencio. Nunca ordena nada (no cierra procesos, no baja modelos): mide, y quien lea decide.
- CLI: `cuerpo.py` (imprime la línea), `--historial [n]`, `--json`.
- Pruebas: con instrumentos simulados (monkeypatch de las funciones de lectura) y 0/3/8 medidas
  previas, comprueba «sin vara», la aparición de cuantiles y el silencio del gancho de prompt
  cuando todo está dentro de lo suyo.

## T2.4 · `lector_pdf.py` — leer solo lo que toca
- `--indexar <pdf>`: texto por página con PyMuPDF (`fitz`) si está; si no, `pypdf`; si ninguno,
  «sin dato: pip install pymupdf». Secciones por tamaño de fuente (fitz: spans con `size` ≥ p90 de
  la página y línea corta) o, sin fitz, por líneas en mayúsculas/numeradas (heurística, dicho).
  Índice en `mem/pdf/<sha1 del fichero>.json` (páginas, secciones con página de inicio, título).
- `--secciones <pdf>`: lista numerada. `--buscar <pdf> "consulta" [k=5]`: TF-IDF de biblioteca
  estándar sobre páginas (tokens en minúscula sin acentos, stopwords castellano+inglés cortas),
  devuelve páginas y sección con la puntuación. `--leer <pdf> <sección|p1-p2>`: imprime el texto.
- `--ahorro <pdf> "consulta"`: caracteres que se leerían con `--buscar` (k páginas) frente al PDF
  entero; se imprime como proporción y con la advertencia de que es ahorro de LECTURA, no de
  calidad de respuesta: eso solo lo mide un A/B con preguntas y respuestas, y no está hecho.
- Sin gancho. Nada sale de la máquina.
- Pruebas: PDF sintético de 6 páginas hecho con fitz (o saltado con motivo si no está) con dos
  títulos grandes → 2 secciones; `--buscar` de una palabra que solo está en la página 5 la devuelve
  la primera; `--ahorro` da proporción < 1.

## T2.5 · `mapa_codigo.py` — el índice de un repo, con `ast`
- `mapa_codigo.py <carpeta> [--salida fichero] [--json]`: recorre `.py` (excluye `.git`, `venv`,
  `.venv`, `node_modules`, `__pycache__`, `site-packages`), y por fichero lista módulo (docstring
  primera línea, líneas totales), clases (línea inicio-fin, bases) y funciones/métodos (línea
  inicio-fin, firma con argumentos, decoradores, primera línea del docstring) e imports. Un fichero
  con error de sintaxis se lista con «(no parsea: <error>)» y no tumba el resto.
- Salida por defecto: texto greppable `mem/mapas/<nombre de la carpeta>.txt` con una línea por
  símbolo: `ruta:linea_ini-linea_fin  clase.metodo(args)  — docstring`. `--buscar <nombre>` sobre el
  último mapa. `--json` escribe además el `.json`.
- Medida: tamaño del mapa frente al código (líneas) para saber qué se ahorra al leer el mapa en vez
  del código; se imprime, sin adjetivos.
- Sin gancho. Pruebas: carpeta sintética con 2 módulos, una clase con 2 métodos, un decorador y
  un fichero roto → mapa con las líneas correctas y el roto señalado.

## T2.6 · `esceptico` — la ley «ningún plan sin escéptico» en un comando
- No es Python: es una skill de Claude Code. Carpeta `skills/esceptico/SKILL.md` en el repo, que
  el instalador copia a `~/.claude/skills/esceptico/` (módulo «esceptico»; el desinstalador la
  borra si es la nuestra: comprueba una marca en el frontmatter).
- Frontmatter: `name: esceptico`, `description:` («Lanza un revisor Opus a tumbar un plan o
  diseño antes de ejecutarlo: veredicto por gravedad con evidencia. Usar cuando el usuario diga
  /esceptico <fichero>, "tumba este plan", "revisa antes de construir".»).
- Cuerpo (en castellano): (1) lee el fichero del plan; (2) lanza UN Agent con `model: opus` y
  este encargo: leer el plan y el código al que apunte, y devolver un veredicto con tres niveles,
  «cae» (el plan no puede cumplir lo que promete: con la línea del código o la medida que lo
  prueba), «grieta» (funciona pero deja un agujero concreto) y «fleco» (menor); por cada punto:
  qué afirma el plan, qué se ha mirado, qué se ha encontrado, qué mediría antes de fiarse; sin
  elogios, sin resumen del plan; si no encuentra nada que lo tumbe, decirlo y decir QUÉ miró; (3)
  escribe `<plan>_veredicto_esceptico.md` junto al plan y muestra el veredicto; (4) no toca el plan.
- Prueba: la skill no se ejecuta sin Claude Code; la prueba comprueba que el instalador la copia,
  que el frontmatter parsea y que el desinstalador la retira solo si lleva nuestra marca.

## T2.7 · `infografia.py` — de CSV o JSON a SVG limpio
- `infografia.py <datos.csv|.json> --tipo barras|barras_h|lineas|tabla [--x col] [--y col[,col2]]
  [--titulo "…"] [--subtitulo "…"] [--fuente "…"] [--salida f.svg] [--ancho 1200] [--alto 675]`.
- Biblioteca estándar (`csv`, `json`, `xml.sax.saxutils.escape`). Paleta sobria fija (5 tonos
  sobre fondo blanco o, con `--oscuro`, sobre `#0f0e0e`), tipografía `system-ui` con fallback,
  márgenes, ejes con ticks «bonitos» (1-2-5), etiquetas de valor, leyenda si hay más de una serie,
  pie con la fuente. Texto escapado; números con coma decimal si `--es` (por defecto sí).
- Sin PNG: el SVG se abre en el navegador; lo dice el docstring. Nada sale de la máquina.
- Pruebas: CSV de 5 filas → SVG que parsea con `xml.etree`, contiene tantas `<rect>` como filas
  (barras) o una `<polyline>` por serie (líneas), y el título escapado (`<` → `&lt;`).

## Instalador, README, docs, pruebas
- Módulos nuevos en `instalar.py` y en la ventana: parentesis · huella (ganchos SessionStart,
  PostToolUse, Stop) · cuerpo (SessionStart, UserPromptSubmit) · lector_pdf · mapa_codigo ·
  esceptico (copia de skill) · infografia. Cada uno con su línea, qué toca, y APAGADO por defecto
  el que añade ganchos que corren tras cada herramienta (huella), con aviso de coste.
- README: los dieciséis en cuatro grupos (memoria y continuidad · honestidad · sentidos · manos)
  y la lista de dependencias opcionales (Pillow+numpy, imageio-ffmpeg, OpenCV, PyMuPDF/pypdf).
- `docs/leyes.md`: qué mide cada pieza nueva y qué no promete.
- `pruebas/`: un fichero por pieza; `python -m unittest discover -s pruebas` sigue en verde con lo
  anterior. Ninguna prueba toca `~/.claude/` real ni red: todo en directorios temporales y con
  `ABYSS_PROYECTO`.

## T2.8 · `lienzo.py` — el estudio del pintor: operar con imágenes reales, sin modelo
Petición del usuario (6-sep 20:04): el pintor debe poder fusionar imágenes, montar diseños con varias,
fundidos, sobreexposiciones, recuperar fotos viejas, y (idea suya) un «libro de pintar por números».
Todo con Pillow + numpy (+ OpenCV si está, para ruido y arañazos). Ningún prompt sale de la máquina.
- `lienzo.py fundir <a> <b> [--modo mezcla|multiplicar|pantalla|superponer|luz_suave] [--alfa 0.5]
  [--mascara degradado_h|degradado_v|radial|<png>] [--salida f.png]`: dos imágenes al tamaño de la
  primera; modos de mezcla clásicos; máscara opcional.
- `lienzo.py doble <a> <b> [--alfa] [--salida]`: doble exposición (pantalla + mezcla ponderada por
  luminancia de la primera).
- `lienzo.py collage <img1> <img2> ... [--columnas N] [--ancho 1920] [--margen 12] [--fondo #111]
  [--salida]`: rejilla o mosaico por filas (alturas iguales), con márgenes.
- `lienzo.py degradado <img> [--direccion abajo|arriba|izq|der|radial] [--color #000] [--desde 0.6]
  [--salida]`: fundido a color en un borde (para cabeceras, portadas).
- `lienzo.py restaurar <foto> [--salida] [--sin-arañazos] [--nitidez 1.0] [--color auto|no]`: niveles
  automáticos por percentiles (p1/p99 por canal), corrección de dominante (gris medio), reducción de
  ruido (median/bilateral con OpenCV; sin OpenCV, filtro mediana de Pillow), arañazos con
  `cv2.inpaint` sobre una máscara de líneas finas muy claras/oscuras (dicho como heurística), nitidez
  por máscara de desenfoque. Imprime antes/después: contraste (desviación típica de luminancia) y
  ruido estimado (desviación en zonas planas). Límite declarado: no reconstruye caras ni detalle
  perdido; eso necesita modelo y no está aquí.
- `lienzo.py numeros <foto> [--colores 12] [--ancho 1400] [--min-zona 80] [--salida]`: pintar por
  números: cuantiza a N colores (Pillow `quantize` con mediana de corte), suaviza, extrae zonas
  conexas ≥ min-zona píxeles, dibuja contornos finos, numera cada zona en su centro (etiqueta del
  color), y escribe la paleta numerada al pie. Salida PNG (plantilla) + PNG coloreado de referencia.
- `imagen.py buscar "texto" [--n 5] [--fuente openverse|commons|ambas] [--descargar]`: busca
  imágenes con licencia libre en Openverse (`api.openverse.org/v1/images/?q=…&license_type=commercial`)
  y Wikimedia Commons (API `action=query&generator=search&gsrnamespace=6&prop=imageinfo&iiprop=url|
  extmetadata`), sin clave (medido 6-sep: ambas 200 en 0,6 s). Devuelve título, autor, licencia,
  URL; con `--descargar` guarda la primera en `mem/imagenes/` junto a un `.txt` con la atribución.
  La búsqueda sale a esos dos servicios; se dice. Solo busca y trae con atribución: NO combina.
  DECISIÓN del usuario (7-sep 00:00): fuera el montaje automático de imágenes buscadas y el compositor
  de escenas; medido el 6-sep, solo recortan y sobreimprimen (collages), sin entender la escena.
- SKILL.md de imagen amplía los activadores: «fusiona estas fotos», «haz un collage», «doble
  exposición», «restaura esta foto vieja», «pintar por números», «busca una imagen libre de…».
- Pruebas: imágenes sintéticas; `fundir` con alfa 0 devuelve la primera y con alfa 1 la segunda
  (píxel a píxel); `collage` de 4 → ancho pedido y 4 zonas no negras; `restaurar` sube el contraste
  de una imagen lavada (medido, no afirmado); `numeros` produce exactamente N entradas de paleta;
  `buscar` se prueba contra una respuesta JSON guardada (sin red en la suite).
- `lienzo.py borrar <img> (--caja x,y,w,h | --mascara m.png | --color #rrggbb[,tolerancia]) [--metodo telea|ns|taller] [--salida]`
  (petición del usuario, 6-sep 22:24: borrar objetos): rellena la zona marcada con `cv2.inpaint`
  (Telea o Navier-Stokes; sin OpenCV, «sin dato: pip install opencv-python»); la máscara la da
  el asistente tras MIRAR la imagen (caja o polígono), o un rango de color. Con `--metodo taller`
  y un taller local encendido que soporte inpainting (POST /sdapi/v1/img2img con máscara, estilo
  A1111), manda imagen+máscara al taller (local: no sale de la máquina) para objetos grandes.
  Límite declarado y medido en la prueba: el relleno clásico vale para objetos pequeños sobre
  fondo con textura regular (postes, cables, manchas, personas lejanas); en objetos grandes o
  con fondo estructurado deja un borrón, y entonces solo el taller sirve. Prueba: imagen sintética
  con textura y un rectángulo negro de 30×30 → tras borrar, el error medio en la zona frente a la
  textura original baja por debajo de la mitad del error inicial (medido, no afirmado).

## TERCERA TANDA (idea del usuario, 7-sep 00:01; NO en esta construcción)
- **T3.1 `render3d.py <modelo.glb|.obj|.stl|escena.json> --html [--png] [--explosion 0.5]`**: página
  autocontenida con three.js (versión fijada; embebida para funcionar sin red) con órbita, luces,
  rejilla, alambre, planos de corte, captura a PNG, y vista explosionada por deslizador (cada malla
  se desplaza desde el centro del conjunto según su centroide). `escena.json`: primitivas (caja,
  cilindro, esfera, texto) con posición, tamaño, color y nombre de pieza, para diagramas sin CAD.
  `--png`: render sin navegador visible con Chrome/Edge headless si existe. Fallback: renderizador
  SVG por CPU de three.js sin aceleración; PNG estático sin navegador. Límites: visor y editor de
  vistas, no modelador; la explosión exige piezas separadas (un STL de una malla no se explosiona);
  la página pesa lo que pesa la librería embebida.
