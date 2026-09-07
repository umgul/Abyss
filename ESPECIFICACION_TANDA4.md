# CUARTA TANDA · el ojo deja de ser una foto, y el vigía mira lo que instalas
Abyss · 7-sep-2026 · complemento de `ESPECIFICACION.md`, `_TANDA2.md` y `_TANDA3.md` (mismas reglas:
ley o medida; fail-closed; dependencias opcionales dentro de `try` y declaradas; datos en `mem`;
castellano; nada personal; cada cifra de un docstring es una medida de UNA máquina, no una ley).

## 0 · Lo medido en la máquina de desarrollo el 7-sep, antes de prometer nada
| qué | resultado |
|---|---|
| OCR de Windows (WinRT, `Windows.Media.Ocr`) | **disponible sin instalar nada**, idioma `es-ES`; sobre una imagen sintética de 900×420 devolvió las 6 líneas correctas, con acentos y con `correo@ejemplo.es` y `Tel. +34 600 123 456` intactos, en 443 ms |
| `tesseract` | no está en PATH |
| `mediapipe` | **NO instalado** (lo necesita el control por gestos) |
| `cv2` 4.12.0 · `numpy` 2.3.5 · `PIL` 11.2.1 · `imageio_ffmpeg` 0.6.0 | instalados |
| cámara | «Trust 1080p Full HD Webcam» |
| escáner WIA | «HP DeskJet 3700 series», tipo 1 (escáner), respondiendo ahora |
| portapapeles | `clip.exe` y `Set-Clipboard` |
| `abyss/ojo.py` hoy | 66 líneas: abre la cámara, guarda un fotograma, lo apunta en `mem/ojo.log` |

Referencia del control por gestos (post de Jhon Jairo Torres, leído el 7-sep): MediaPipe da 21 puntos
por mano; un dedo cuenta como extendido si la distancia punta-muñeca supera 1,7 veces la de
nudillo-muñeca (razón invariante a la escala); la pose de la palma sale de `solvePnP` de OpenCV; el
temblor se quita con un filtro One Euro; la apertura del pellizco se normaliza con los percentiles 10
y 90 de cada grabación; y la regla de diseño es que nada en pantalla puede saber el futuro, o sea que
solo se muestran gestos ya completados. Corre en un portátil de 8 GB sin GPU.

## T4.1 · El vigía mira también dominios y comandos (dos tipos de caza más)
Motivo: el incidente que cuenta Yonathan Cohen (leído el 7-sep) es que a alguien lo comprometieron con
un comando que le dio su propia IA, apuntando a un dominio copia. El vigía ya juzga procedencia sobre
lo que sale de mi boca; esto es el mismo instrumento sobre otras dos formas.
- Tipos nuevos en `vigia.py`, junto a los actuales (`numero`, `ruta`, `cita`, `parafrasis`):
  - `dominio`: cualquier host o URL de mi respuesta que no aparezca en un resultado de herramienta ni
    en un mensaje del usuario en este turno. Se comparan hosts normalizados (minúsculas, sin `www.`,
    sin puerto ni ruta), no la URL entera.
  - `comando`: cualquier línea de mi respuesta con forma de instalación o ejecución remota
    (`curl`/`wget`/`iwr`/`irm` con tubería a `bash`/`sh`/`iex`; `pip install`, `npm i`, `winget`,
    `choco`, `Invoke-Expression`, `powershell -enc`) cuya fuente no esté en el turno.
- La bandera `--descargo` y `--precision` valen igual para los tipos nuevos.
- **Límite declarado, en el docstring y en la skill**: el vigía comprueba DE DÓNDE salió un dominio,
  no si es de fiar. Un dominio devuelto por una búsqueda tiene procedencia y puede seguir siendo una
  copia. Contra eso solo vale leerlo carácter a carácter, y eso lo hace quien lee, no el guion.
- Pruebas: un dominio inventado en la respuesta se caza y uno que aparece en un `tool_result` no;
  `curl … | bash` con URL no vista se caza; el mismo comando citado por el usuario en su mensaje, no;
  un descargo sobre una caza de tipo `dominio` baja la precisión aparente.

## T4.2 · `auditar.py`: las cinco comprobaciones sobre un paquete
Cinco dimensiones del post de Cohen, cada una con evidencia, nunca con una promesa:
`auditar.py <ruta_de_paquete> [--json] [--markdown salida.md]`
1. **Procedencia**: manifiesto (`.claude-plugin/plugin.json`, `package.json`, `pyproject.toml`):
   ¿hay autor con nombre real, repositorio, licencia? Un paquete sin autor ni historia no es gratis:
   es de nadie. Si hay `.git`, número de commits y fecha del primero.
2. **Comandos**: qué se ejecuta y cuándo. Lee `hooks/hooks.json` y `settings.json` si los hay, y lista
   cada evento con su comando; marca los que corren en CADA mensaje o tras CADA herramienta. Busca en
   el código llamadas a `subprocess`, `os.system`, `eval`, `exec`, y descargas ejecutables.
3. **Permisos**: qué toca fuera de su carpeta: escrituras a `~/.claude`, a `settings.json`, al
   registro, a rutas absolutas; y si declara un manifiesto para deshacerlo.
4. **Qué sale de la máquina**: extrae del código TODOS los hosts de red (regex de URL y de
   `urlopen`/`requests`/`fetch`), los agrupa, y **contrasta cada uno contra el README**: un host que el
   código usa y el README no nombra es un hallazgo, con fichero y línea. Esta es la comprobación que
   ningún antivirus hace y que aquí sí se puede medir.
5. **Dominio**: lista los dominios de instalación que aparecen en README y manifiestos para que quien
   lea los compare carácter a carácter; el guion NO dice si un dominio es legítimo, y lo declara.
Veredicto en tres niveles, como el escéptico: `rompe` (hace algo que no declara), `engaña` (declara
algo que no cumple), `roza`. Sin red: solo lee ficheros.
- `skills/esceptico/SKILL.md` amplía: `/esceptico <plan.md>` como hoy, y `/esceptico --paquete <ruta>`,
  que corre `auditar.py` y le da el resultado a un Opus para que lo lea y busque lo que el informe
  automático no ve.
- **Primer informe: Abyss sobre Abyss**, en `docs/AUDITORIA_DE_ABYSS.md`, con lo que salga, incluido lo
  que suspenda. Medido hoy: `plugin.json` no tiene autor y `marketplace.json` firma como «el usuario»;
  9 ganchos, 2 en cada mensaje y 1 tras cada herramienta; 10 servicios de red nombrados en el README.
- Pruebas: paquete sintético con un host en el código que el README no nombra → hallazgo; paquete
  sintético sin autor → hallazgo de procedencia; paquete limpio → veredicto sin hallazgos.

## T4.3 · `lectura_visual.py`: lo que el ojo LEE (OCR y sus tres usos)
Motor: el de Windows por WinRT mediante `abyss/ocr_win.ps1` (medido: 443 ms, `es-ES`, sin instalar).
Sin Windows o sin motor: «sin dato: no hay motor OCR» y código 2. `tesseract` se usa si está en PATH,
como segunda vía; nunca se instala nada.
- `texto <imagen> [--portapapeles] [--salida f.txt]`: texto plano, líneas en orden. Con
  `--portapapeles`, YA copiado (`clip.exe`; en Linux/macOS `xclip`/`pbcopy` si están, si no lo dice).
- `fotocopia <imagen|--camara> [--salida f.png|f.pdf] [--color|--gris|--umbral] [--paginas n]`:
  **el escáner es el software, no un aparato**. Toma una FOTO (fichero o webcam), endereza el papel
  (contorno cuadrilátero mayor con `cv2` y `getPerspectiveTransform`), recorta, corrige la
  iluminación desigual, umbraliza si se pide, y GUARDA el resultado en local como PNG o PDF de varias
  páginas. Sin cuadrilátero claro: lo dice y guarda la imagen enderezada por bordes, sin fingir el
  recorte. **Prohibido**: no imprime nada, no manda nada a ninguna impresora, y no da por hecho que
  quien lo use tenga escáner ni impresora. Un escáner WIA, si existe en la máquina, es una fuente
  OPCIONAL más (`--escaner`), nunca el camino: si no hay, se dice «sin escáner: uso la cámara o un
  fichero» y se sigue por la vía normal, sin error. La prueba de la suite usa una foto sintética de
  un folio torcido, jamás un aparato.
- `tarjeta <imagen> [--salida base]`: OCR + extracción por patrones (teléfono, correo, web, y el resto
  de líneas como nombre/empresa/cargo por posición y tamaño) → `.vcf` válido (vCard 3.0) y una tarjeta
  `.png` compuesta con Pillow. Lo que no reconozca queda vacío y se dice; no se inventa un cargo.
- `manual <imagen...> [--salida f.md]`: OCR de varias fotos o páginas, ordena por número de página si
  lo encuentra, limpia guiones de corte y saltos, y devuelve markdown con los pasos numerados que
  DETECTA (líneas que empiezan por número, «Paso», «Step», viñeta). **Honestidad**: el guion no
  resume; entrega el texto limpio y ordenado, y es el asistente quien resume, con el texto delante.
  La skill lo dice así.

## T4.4 · `volumen.py`: lo que el ojo VE en relieve (despiece y prompt de diseño)
- `despiece <imagen> [--capas 4] [--salida escena.json] [--html]`: separa el objeto del fondo con
  GrabCut (`cv2`, probado el 6-sep en este mismo paquete), estima capas por una heurística DECLARADA
  (nitidez local por laplaciano + luminancia: lo enfocado y cercano delante), recorta cada capa como
  textura y escribe una `escena.json` de planos texturizados a distintas profundidades, que
  `render3d.py` ya sabe abrir con su deslizador de explosión. **No es reconstrucción 3D**: es un
  despiece por capas (2,5 D) de lo que la cámara ve; se dice en el docstring, en la skill y en la
  propia página.
- `prompt3d <imagen> [--salida f.txt|--escena f.json]`: mide de la foto la paleta dominante (k-medias
  sobre los píxeles), las proporciones del objeto, el horizonte y las formas dominantes (rectángulos,
  cilindros o esferas por circularidad de contornos) y escribe (a) un prompt de diseño en castellano e
  inglés para three.js con esos números, y (b) opcionalmente una `escena.json` de primitivas ya
  colocadas. Nada de esto adivina el objeto: dice qué formas y colores midió.
- `render3d.py --holograma`: la misma escena en CUATRO CUADRANTES espejados (arriba, abajo, izquierda,
  derecha, cada uno girado 90°) sobre fondo negro, que es lo que pide la pirámide de metacrilato
  (Pepper's ghost). Sin dependencias nuevas: es una vista más de lo que ya hay.

## T4.5 · `gestos.py`: la mano manda, con vocabulario PROPIO
Del post ajeno se toman TÉCNICAS, no su diseño: nada de copiar su vocabulario (un dedo una flor, dos
un aguacate, tres una calavera). Lo que se hereda, declarado como heredado: los 21 puntos de MediaPipe;
la razón invariante a la escala para saber si un dedo está extendido (distancia punta-muñeca frente a
nudillo-muñeca, con el 1,7 del autor como listón heredado hasta medir el propio en esta máquina); la
normalización del pellizco por percentiles de la propia sesión, que además es la ley de cortes propios
de este paquete; el suavizado del temblor; y la regla de que nada en pantalla se adelanta a un gesto
sin terminar.
Requiere `mediapipe`, que NO está instalado (medido). Sin él: imprime exactamente qué instalar y sale
con código 2; no instala nada.
- **Vocabulario propio, y es el del paquete, no el de nadie**: la mano no invoca objetos, MANEJA la
  escena que ya hay (la de `render3d.py`, que puede venir de un modelo, de un `escena.json` o del
  despiece de una foto). Verbos de la mano:
  - **número de dedos = qué capa del despiece se aísla** (0 todas, 1 la primera, 2 las dos primeras…),
    que es exactamente la idea que al usuario le interesa, puesta al servicio de nuestra vista
    explosionada en vez de a un catálogo de figuritas;
  - **pellizco = deslizador de explosión** (cerrado, montado; abierto, despiezado), normalizado por
    los percentiles 10 y 90 de la propia sesión;
  - **pose de la palma = órbita de la cámara** (giro e inclinación), con `solvePnP`;
  - **mano abierta y quieta un segundo = capturar PNG** de lo que se está viendo;
  - **dos manos = escala** por la distancia entre ellas.
  Cada asignación va en una tabla del docstring, y se puede cambiar por fichero
  (`mem/gestos_vocabulario.json`), porque un vocabulario decretado que no se puede cambiar es un
  decreto, no una interfaz.
- `gestos.py [--camara 0] [--puerto 8799] [--escena f.json] [--holograma] [--vocabulario f.json]`:
  sirve el estado por HTTP local (`127.0.0.1`, JSON: dedos, pellizco, pose, gesto completado) y la
  página de `render3d.py` lo lee y reacciona. Con `--holograma`, la página sale en cuatro cuadrantes.
- **Calibración propia, no un número del diseñador**: al arrancar, 5 segundos de mano libre para medir
  SUS percentiles; mientras no haya 30 muestras, «sin vara todavía (n=…)» y se usa el listón heredado,
  declarado en pantalla.
- Pruebas: sin `mediapipe`, código 2 y el mensaje nombra el paquete; con un módulo falso inyectado que
  devuelve 21 puntos sintéticos, la razón de dedo extendido cuenta los dedos que toca, el pellizco
  normalizado da 0 y 1 en los extremos, un gesto a medias NO cambia la escena, y el vocabulario se
  puede sustituir por fichero; el servidor local responde JSON y no escucha fuera de 127.0.0.1.

## T4.6 · El ojo, ya como órgano, y las descripciones al día
- `ojo.py` pasa a tener verbos y a delegar: `mirar` (lo de hoy), `texto`, `fotocopia`, `tarjeta`,
  `manual`, `despiece`, `prompt3d`, `gestos`. Ninguno se dispara por gancho: la cámara solo se
  enciende cuando se pide, y eso sigue siendo ley.
- `skills/ojo/SKILL.md` reescrita con los ocho verbos y sus disparadores en castellano e inglés:
  «mira por la webcam», «lee lo que hay en esta foto»/«cópiame el texto de la imagen», «fotocopia
  esto», «pásame los datos de esta tarjeta», «resume este manual», «haz un despiece de esto», «un
  prompt de three.js a partir de esta foto», «controla el holograma con la mano», y sus equivalentes
  en inglés. El primero (`mirar`) es solo cámara en vivo; leer una foto que ya se tiene es `texto`
  (OCR), nunca dispara la webcam.
- `skills/vigia/SKILL.md`: los dos tipos de caza nuevos y el límite declarado.
- `skills/esceptico/SKILL.md`: `--paquete`.
- `README.md` y `README.en.md`: el ojo con sus verbos en «Sentidos», `auditar` en «Honestidad», y en
  dependencias opcionales: motor OCR de Windows (sin instalar), `mediapipe` (solo gestos), escáner WIA.
- `instalar.py`: módulos `auditar` y `gestos`; el de `ojo` con su línea nueva.
