# -*- coding: utf-8 -*-
"""Lienzo: el estudio del pintor sin modelo — operar con imágenes reales, con Pillow + numpy
(+ OpenCV si está, solo para ruido/arañazos/inpainting rápido; todo funciona sin él, más lento
o con menos pasos, y lo dice). Ningún prompt sale de la máquina; ningún verbo llama a un
proveedor de imagen (`imagen.py`) salvo `borrar --metodo taller`, que habla con la máquina que
TÚ pongas en `taller_url` (`<memoria>/imagen_config.json`) — por defecto vacía, y entonces ese
método falla con "sin dato" en vez de asumir localhost (nada garantiza en el código que sea tu
propia máquina: el aviso "nunca sale de casa" es responsabilidad de cómo configures `taller_url`,
no una promesa que este módulo compruebe).

    python lienzo.py fundir <a> <b> [--modo mezcla|multiplicar|pantalla|superponer|luz_suave]
                     [--alfa 0.5] [--mascara degradado_h|degradado_v|radial|<png>] [--salida f.png]
    python lienzo.py doble <a> <b> [--alfa 0.5] [--salida f.png]
    python lienzo.py collage <img1> <img2> ... [--columnas N] [--ancho 1920] [--margen 12]
                     [--fondo #111111] [--salida f.png]
    python lienzo.py degradado <img> [--direccion abajo|arriba|izq|der|radial] [--color #000000]
                     [--desde 0.6] [--salida f.png]
    python lienzo.py restaurar <foto> [--salida f.png] [--sin-aranazos] [--nitidez 1.0]
                     [--color auto|no]
    python lienzo.py numeros <foto> [--colores 12] [--ancho 1400] [--min-zona N] [--salida base]
                     # sin --min-zona: 0,05% del área ya redimensionada (suelo 20 px)
    python lienzo.py borrar <img> (--caja x,y,w,h | --mascara m.png | --color #rrggbb[,tolerancia])
                     [--metodo telea|ns|taller] [--salida f.png]
    python lienzo.py cubista <foto> [--facetas 220] [--desplazamiento 0.07] [--giro 7]
                     [--sin-contorno] [--difuminado-fondo N] [--semilla 7]
                     [--pasos N --pasos-dir DIR] [--salida f.png]
    python lienzo.py surrealista <foto> [--fuerza 26] [--escala 90] [--viraje 42] [--semilla 7]
                     [--pasos N --pasos-dir DIR] [--salida f.png]

`fundir`: `b` se redimensiona al tamaño de `a` (LANCZOS) y se combina con un modo de mezcla
clásico (`mezcla` = normal; `multiplicar`, `pantalla`, `superponer`, `luz_suave` = fórmulas
estándar de edición de imagen sobre canales 0-1). `--alfa` es la opacidad global de la mezcla
(0 = sale `a` tal cual, 1 = sale el resultado de la mezcla entera — con `--modo mezcla`, eso es
`b` tal cual, píxel a píxel); `--mascara` sustituye ese único número por un mapa por píxel
(dos degradados y un radial generados aquí, o la ruta a un PNG en gris que hace de máscara),
multiplicado igualmente por `--alfa`.

`doble`: la exposición doble reparte, según la LUMINANCIA de `a` (más "pantalla" donde `a` ya es
brillante — así se transparenta como una sobreexposición real —, más mezcla lineal donde `a` es
oscura). Es una heurística declarada, no una simulación óptica de una doble exposición de
película.

`collage`: con `--columnas N`, rejilla estricta de celdas cuadradas (cada imagen se recorta
centrada para llenar su celda, sin bandas vacías). Sin `--columnas`, mosaico "justificado" por
filas: cada fila se llena hasta `--ancho` y luego se reescala esa fila entera a una altura común
(el mismo método que usan las galerías de fotos "a la Flickr"); la última fila puede quedar más
corta que el resto si no hay bastantes imágenes para llenarla del todo.

`degradado`: funde la foto hacia `--color` en un borde, empezando en la fracción `--desde` del
recorrido (0 = desde el propio centro/borde opuesto, 1 = solo el borde extremo). Para cabeceras
y portadas: pon el texto donde ya no queda foto, solo color.

`restaurar`: reduce ruido PRIMERO, antes de tocar niveles (estirar el contraste de una foto sin
quitarle antes el grano amplifica el grano tanto como el contraste), con fuerza proporcional al
ruido medido a la entrada (`cv2.fastNlMeansDenoisingColored` si hay OpenCV, con `h` derivado de
esa medida — sin OpenCV, mediana 3×3 de Pillow, dos pasadas si el ruido de entrada es alto),
niveles automáticos por percentil 1-99 de cada canal (estira el contraste sin saturar por un
pico o un valle aislado), corrección de dominante de color (lleva la media de los tres canales a
un gris medio común — corrige un viraje amarillento/azulado uniforme, NO un balance de blancos
con luces mixtas, y NO recupera el tono original de la foto: solo la lleva a neutro), arañazos
opcionales con `cv2.inpaint` sobre una máscara heurística (líneas finas cuyo valor se aparta
mucho de una mediana local — sin OpenCV, `--sin-aranazos` avisa y se salta ese paso), y una
pasada final de nitidez por máscara de desenfoque (`--nitidez`, 0 = ninguna). Imprime SIEMPRE
antes/después: contraste (desviación típica de la luminancia) y ruido estimado con una vara que
NO cambia de escala con el contraste (percentil 20 de la desviación típica LOCAL en bloques
fijos de 8×8 px sobre luminancia 0-255 — el percentil bajo aísla los bloques sin apenas detalle,
donde cualquier variación que quede es ruido, no textura de la escena; un bloque fijo, a
diferencia de un umbral de gradiente, no se corre cuando el contraste cambia, así que
antes/después son comparables). Si el ruido medido no baja, lo dice ("ruido no reducido") en vez
de imprimir la subida como si fuera un logro (JSON: `ruido_reducido`): `--nitidez` (por defecto
1.0) afila amplificando cualquier detalle fino que quede tras el denoise, ruido incluido, y en
fotos con poco margen puede devolverlo por encima de la entrada; es un efecto DISTINTO del que
arregla el orden ruido-antes-que-niveles, y el aviso existe justo para decirlo cuando pasa, no
para ocultarlo. Límite declarado y no sorteado aquí: esto NO reconstruye caras ni detalle que la
foto ya perdió — eso pide un modelo generativo, y esta pieza no tiene ninguno.

`numeros` ("pintar por números"): cuantiza a `--colores` tonos (Pillow `quantize`, corte de
mediana, sobre la foto ya suavizada con una mediana 3×3); ANTES de agrupar en zonas, un segundo
filtro de MODA (radio proporcional al ancho, `ancho/150`: cada píxel pasa al tono más frecuente
de su vecindad) limpia el ruido sal-y-pimienta y los píxeles sueltos que deja la cuantización —
sin este paso, cada mota de ruido nace como su propia zona, y un libro de pintar por números de
verdad tiene decenas o cientos de zonas, no miles. Agrupa en zonas conexas de un mismo tono (con
`cv2.connectedComponents` si hay OpenCV — rápido —; si no, unión-búsqueda propia en Python puro
— MUCHO más lenta en fotos grandes); cada zona de menos de `--min-zona` píxeles se FUNDE con la
zona vecina con la que comparte más frontera, repitiendo hasta que no quede ninguna; el recuento
de `zonas` que devuelve es el de DESPUÉS de fundir. `--min-zona`, si no se da, sale proporcional
al área ya redimensionada (0,05 % del lienzo, con un suelo de 20 px) en vez de un número fijo,
para que el umbral escale con el tamaño de la foto en vez de ser una cifra arbitraria. Dibuja el
contorno entre zonas y numera con la cifra de su color las zonas que quedan, y añade al pie del
PNG-plantilla la paleta numerada. Escribe dos ficheros: sin `--salida`,
`<foto>_numeros_plantilla.png` y `<foto>_numeros_color.png` (junto a la foto de entrada); con
`--salida <base>`, `<base>_plantilla.png` y `<base>_color.png` (el `<base>` tal cual, sin
`_numeros` de más). Límite: el número de entradas de la paleta es el de tonos que de verdad
aparecen en la imagen cuantizada — puede ser menor que `--colores` si la foto tiene menos
variedad de la pedida.

`borrar`: rellena la zona marcada (`--caja x,y,w,h`, o una `--mascara` en gris ya recortada por
ti, o un `--color` con tolerancia opcional en unidades de distancia RGB, 30 por defecto) con
`cv2.inpaint` (`--metodo telea`/`ns` por defecto: se prueban LOS DOS —Telea 2004 y Navier-Stokes
de Bertalmío 2001— y se usa el que deje menos discontinuidad de borde, la diferencia de
luminancia entre el interior rellenado y su anillo de fondo inmediato; el JSON dice cuál se pidió
y cuál se usó — sin OpenCV, "sin dato: pip install opencv-python", código 2) o, con `--metodo
taller`, mandando la imagen y la máscara a un servidor local que hable `POST /sdapi/v1/img2img`
con máscara (estilo A1111 — por ejemplo, `taller.py` con esa ruta añadida, o un A1111/Forge real)
— la URL sale de `taller_url` en `<memoria>/imagen_config.json` (NUNCA en el código; plantilla en
`plantillas/imagen_config.json`); sin esa clave, "sin dato". Límite declarado: el relleno clásico
(`telea`/`ns`) funciona bien sobre objetos FINOS (postes, cables, una mancha) o fondos casi
uniformes; sobre objetos grandes o fondos con estructura deja un borrón visible — ahí hace falta
`--metodo taller`. Antes de rellenar, mide el
área de la máscara frente al área de la imagen y la textura del anillo de 20 px de fondo
alrededor de ella (contra la mediana de desviación local de toda la imagen): si el área supera el
1 % de la imagen o el anillo tiene más textura que esa mediana, imprime un aviso ("borrón
probable…") y lo deja en el JSON (`aviso`, `None` si no aplica) — con `--metodo taller` no avisa
(ya es el método recomendado para esos casos).

`cubista`/`surrealista`: la pregunta de fondo no era qué parámetros pintar, sino DÓNDE viven — `pintor.py` es un motor de PINCELADAS
(Hertzmann 1998: por cada radio, difuminar, medir error por celdas, poner una pincelada
perpendicular al gradiente); sus seis estilos son el MISMO bucle con otro dict de radios/
umbral/alfa (ver el docstring de `pintor.py`). Cubismo y surrealismo no son eso: no son una
pincelada más fina o más gorda, son otra COMPOSICIÓN de la imagen ENTERA — llamarlos "otro
estilo de pintor.py" habría sido mentir con el nombre (un radio de pincel distinto no es una
faceta ni un derretido). Por eso viven aquí, como dos verbos más de `lienzo.py`, que ya opera
sobre la foto entera de una vez (como `collage`/`degradado`), no pincelada a pincelada.

`cubista` (analítico): puntos semilla sobre los bordes REALES de la foto (`cv2.Canny`) más un
relleno aleatorio y un marco (para cubrir el lienzo entero) -> triangulación de Delaunay de esos
puntos (`cv2.Subdiv2D` — ya dependencia opcional del paquete, sin necesitar scipy; sin OpenCV,
una rejilla triangular con jitter, declarada como lo que es: NO una Delaunay real) -> cada
triángulo se aplana a su color medio (medido sobre la foto ORIGINAL) -> se desplaza y gira un
poco alrededor de su propio centro, de MAYOR a MENOR área, sobre un fondo difuminado y con el
color atenuado (para que el hueco que deja una faceta movida enseñe un eco de la escena, no un
vacío) -> un contorno más oscuro remata cada faceta para que la junta se vea — eso ES lo que
hace el cubismo analítico: descomponer en planos y enseñar varios a la vez.

`surrealista`: dos campos de ruido de BAJA frecuencia (rejilla gruesa remuestreada a tamaño
completo — la propia interpolación bicúbica hace de paso-bajo) como mapa de desplazamiento
(x,y), que remuestrea la foto entera (`cv2.remap`, o un bilineal propio sin OpenCV) — las formas
se derriten sin romperse, porque el desplazamiento cambia suave de un píxel a su vecino — más un
viraje de tono (canal H de HSV) para el color onírico.

Los dos ENSEÑAN EL PROCESO en vídeo (como `video_pintura.py` con las pinceladas, pero aquí no
hay pinceladas que filmar: el efecto es una sola pasada por foto): con `--pasos N --pasos-dir
DIR` escriben N fotogramas de progreso — `cubista` revelando facetas de mayor a menor área,
`surrealista` interpolando el campo de deformación y el viraje de 0 a su fuerza completa — que
`video_composicion.py` (hermano de `video_pintura.py` para composiciones que no son pinceladas)
convierte en `.mp4`.

Qué sale de la máquina: NADA salvo `borrar --metodo taller`, y eso solo llega a la máquina que
TÚ configures en `taller_url` (por defecto, ninguna — sin configurar, ese método falla con "sin
dato"). El resto de verbos no toca `mem`, no resuelve un proyecto de Claude Code: cada verbo lee
los ficheros que le des y escribe el PNG que le pidas, nada más — no hay registro ni memoria
propia de `lienzo.py`.
"""
import io
import json
import math
import os
import sys
import urllib.error
import urllib.request

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
except ImportError as _e:
    sys.stderr.write(f'lienzo.py necesita Pillow y numpy (pip install Pillow numpy) [{_e.name}]\n')
    sys.exit(2)

try:
    import cv2
except ImportError:
    cv2 = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MODOS_FUNDIR = ('mezcla', 'multiplicar', 'pantalla', 'superponer', 'luz_suave')
DIRECCIONES_DEGRADADO = ('abajo', 'arriba', 'izq', 'der', 'radial')
METODOS_BORRAR = ('telea', 'ns', 'taller')


# ───────────────────────── utilidades comunes ─────────────────────────

def _cargar_rgb(ruta):
    return Image.open(ruta).convert('RGB')


def _redimensionar_a(img, tamano):
    return img if img.size == tuple(tamano) else img.resize(tuple(tamano), Image.LANCZOS)


def _nombre_salida(ruta, sufijo, ext='.png'):
    base = os.path.splitext(os.path.abspath(ruta))[0]
    return f'{base}_{sufijo}{ext}'


def _hex_a_rgb(hexcolor):
    h = hexcolor.strip().lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f'color no reconocido: "{hexcolor}" (usa #rrggbb)')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _a01(img):
    return np.asarray(img).astype(np.float32) / 255.0


def _de01(arr):
    return np.clip(np.round(arr * 255.0), 0, 255).astype(np.uint8)


def _suma_ventana(arr, radio):
    """Suma de una ventana cuadrada de lado `2*radio+1` centrada en cada píxel de
    `arr` (2D), con borde replicado — tabla de sumas de área (dos `cumsum`), sin
    depender de OpenCV. Con `arr` ya booleano/0-1 da un recuento de vecinos; con
    `arr**2` da la suma de cuadrados (para varianza local)."""
    pad = np.pad(arr.astype(np.float64), radio, mode='edge')
    sat = np.cumsum(np.cumsum(pad, axis=0), axis=1)
    sat = np.pad(sat, ((1, 0), (1, 0)), mode='constant')
    alto, ancho = arr.shape
    k = 2 * radio + 1
    return (sat[k:k + alto, k:k + ancho] - sat[0:alto, k:k + ancho]
            - sat[k:k + alto, 0:ancho] + sat[0:alto, 0:ancho])


def _media_ventana(arr, radio):
    return _suma_ventana(arr, radio) / float((2 * radio + 1) ** 2)


def _mapa_desviacion_local(lum, radio=4):
    """Desviación típica LOCAL de `lum` (2D, escala 0-255) en una ventana de lado
    `2*radio+1` alrededor de cada píxel — con OpenCV, `boxFilter`; sin él, la
    misma tabla de sumas de área que `_suma_ventana`. Sirve para comparar la
    textura de una región contra la del resto, con la MISMA vara en toda la imagen."""
    lum = lum.astype(np.float32)
    if cv2 is not None:
        k = 2 * radio + 1
        media = cv2.boxFilter(lum, ddepth=-1, ksize=(k, k), borderType=cv2.BORDER_REPLICATE)
        media2 = cv2.boxFilter(lum * lum, ddepth=-1, ksize=(k, k), borderType=cv2.BORDER_REPLICATE)
    else:
        media = _media_ventana(lum, radio).astype(np.float32)
        media2 = _media_ventana(lum * lum, radio).astype(np.float32)
    varianza = np.clip(media2 - media ** 2, 0, None)
    return np.sqrt(varianza)


# ───────────────────────── fundir ─────────────────────────

def _blend_pixels(a, b, modo):
    """`a`/`b`: arrays float32 en [0,1]. Fórmulas estándar de mezcla (no dependen del
    canal alfa: eso lo aplica quien llama, por separado, con `--alfa`/la máscara)."""
    if modo == 'mezcla':
        return b
    if modo == 'multiplicar':
        return a * b
    if modo == 'pantalla':
        return 1 - (1 - a) * (1 - b)
    if modo == 'superponer':
        return np.where(a < 0.5, 2 * a * b, 1 - 2 * (1 - a) * (1 - b))
    if modo == 'luz_suave':
        d = np.where(a <= 0.25, ((16 * a - 12) * a + 4) * a, np.sqrt(np.maximum(a, 0)))
        return np.where(b <= 0.5, a - (1 - 2 * b) * a * (1 - a), a + (2 * b - 1) * (d - a))
    raise ValueError(f'modo de mezcla desconocido: "{modo}" (usa {", ".join(MODOS_FUNDIR)})')


def _mascara_valor(nombre, ancho, alto):
    """Un mapa 0..1 por píxel: `degradado_h`/`degradado_v`/`radial` generados aquí, o la
    ruta a un PNG en escala de grises (0=negro, 1=blanco) redimensionado a `(ancho, alto)`."""
    if nombre == 'degradado_h':
        return np.tile(np.linspace(0, 1, ancho, dtype=np.float32), (alto, 1))
    if nombre == 'degradado_v':
        return np.tile(np.linspace(0, 1, alto, dtype=np.float32).reshape(-1, 1), (1, ancho))
    if nombre == 'radial':
        yy, xx = np.mgrid[0:alto, 0:ancho].astype(np.float32)
        cx, cy = ancho / 2.0, alto / 2.0
        r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        r = r / (r.max() or 1.0)
        return np.clip(1 - r, 0, 1)
    img = Image.open(nombre).convert('L').resize((ancho, alto), Image.LANCZOS)
    return _a01(img)


def fundir(ruta_a, ruta_b, modo='mezcla', alfa=0.5, mascara=None, salida=None):
    if modo not in MODOS_FUNDIR:
        raise ValueError(f'modo de mezcla desconocido: "{modo}" (usa {", ".join(MODOS_FUNDIR)})')
    a_img = _cargar_rgb(ruta_a)
    b_img = _redimensionar_a(_cargar_rgb(ruta_b), a_img.size)
    ancho, alto = a_img.size
    a, b = _a01(a_img), _a01(b_img)
    if mascara:
        m = _mascara_valor(mascara, ancho, alto)[..., None] * float(alfa)
    else:
        m = np.full((alto, ancho, 1), float(alfa), dtype=np.float32)
    mezclado = _blend_pixels(a, b, modo)
    resultado = a * (1 - m) + mezclado * m
    salida = salida or _nombre_salida(ruta_a, 'fundida')
    Image.fromarray(_de01(resultado), 'RGB').save(salida)
    return salida


# ───────────────────────── doble exposición ─────────────────────────

def doble(ruta_a, ruta_b, alfa=0.5, salida=None):
    a_img = _cargar_rgb(ruta_a)
    b_img = _redimensionar_a(_cargar_rgb(ruta_b), a_img.size)
    a, b = _a01(a_img), _a01(b_img)
    luminancia = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2])[..., None]
    pantalla = 1 - (1 - a) * (1 - b)
    lineal = a * (1 - float(alfa)) + b * float(alfa)
    resultado = luminancia * pantalla + (1 - luminancia) * lineal
    salida = salida or _nombre_salida(ruta_a, 'doble')
    Image.fromarray(_de01(resultado), 'RGB').save(salida)
    return salida


# ───────────────────────── collage ─────────────────────────

def _ajustar_cubrir(img, w, h):
    escala = max(w / img.width, h / img.height)
    nw, nh = max(1, round(img.width * escala)), max(1, round(img.height * escala))
    redim = img.resize((nw, nh), Image.LANCZOS)
    x0, y0 = (nw - w) // 2, (nh - h) // 2
    return redim.crop((x0, y0, x0 + w, y0 + h))


def _justificar_filas(imagenes, ancho, margen, h0=420):
    """Agrupa `imagenes` en filas: cada fila acumula anchuras (a una altura de referencia
    `h0`) hasta que la siguiente imagen ya no cabría en `ancho`; la altura FINAL de cada fila
    se decide después (`collage()`), reescalándola para que ocupe `ancho` exacto."""
    filas, fila_actual, ancho_actual = [], [], margen
    for img in imagenes:
        w0 = img.width * h0 / img.height
        if fila_actual and ancho_actual + w0 + margen > ancho:
            filas.append(fila_actual)
            fila_actual, ancho_actual = [], margen
        fila_actual.append((img, w0))
        ancho_actual += w0 + margen
    if fila_actual:
        filas.append(fila_actual)
    return filas


def collage(rutas, columnas=None, ancho=1920, margen=12, fondo='#111111', salida=None):
    imagenes = [_cargar_rgb(r) for r in rutas]
    if not imagenes:
        raise ValueError('no hay imágenes que montar')
    color_fondo = _hex_a_rgb(fondo)
    salida = salida or _nombre_salida(rutas[0], 'collage')

    if columnas:
        n = int(columnas)
        if n < 1:
            raise ValueError('--columnas debe ser al menos 1')
        cell_w = max(1, int((ancho - margen * (n + 1)) / n))
        cell_h = cell_w
        filas_n = math.ceil(len(imagenes) / n)
        alto_total = margen + filas_n * (cell_h + margen)
        lienzo = Image.new('RGB', (int(ancho), int(alto_total)), color_fondo)
        for idx, img in enumerate(imagenes):
            fila, col = divmod(idx, n)
            recortada = _ajustar_cubrir(img, cell_w, cell_h)
            x, y = margen + col * (cell_w + margen), margen + fila * (cell_h + margen)
            lienzo.paste(recortada, (x, y))
        lienzo.save(salida)
        return salida

    filas = _justificar_filas(imagenes, ancho, margen)
    alturas = []
    for fila in filas:
        suma_w = sum(w for _, w in fila)
        factor = (ancho - margen * (len(fila) + 1)) / suma_w if suma_w else 1.0
        alturas.append(max(1.0, 420 * factor))
    alto_total = margen + sum(int(h) + margen for h in alturas)
    lienzo = Image.new('RGB', (int(ancho), int(alto_total)), color_fondo)
    y = margen
    for fila, h in zip(filas, alturas):
        x = margen
        for img, _ in fila:
            wf = max(1, round(img.width * h / img.height))
            redim = img.resize((wf, max(1, round(h))), Image.LANCZOS)
            lienzo.paste(redim, (x, y))
            x += wf + margen
        y += int(h) + margen
    lienzo.save(salida)
    return salida


# ───────────────────────── degradado ─────────────────────────

def degradado(ruta, direccion='abajo', color='#000000', desde=0.6, salida=None):
    if direccion not in DIRECCIONES_DEGRADADO:
        raise ValueError(f'dirección desconocida: "{direccion}" (usa {", ".join(DIRECCIONES_DEGRADADO)})')
    img = _cargar_rgb(ruta)
    ancho, alto = img.size
    arr = _a01(img)
    rgb_color = np.array(_hex_a_rgb(color), dtype=np.float32) / 255.0
    tramo = max(1e-6, 1.0 - float(desde))

    if direccion in ('abajo', 'arriba'):
        eje = np.linspace(0, 1, alto, dtype=np.float32)
        if direccion == 'arriba':
            eje = eje[::-1]
        m = np.tile(np.clip((eje - desde) / tramo, 0, 1).reshape(-1, 1), (1, ancho))
    elif direccion in ('der', 'izq'):
        eje = np.linspace(0, 1, ancho, dtype=np.float32)
        if direccion == 'izq':
            eje = eje[::-1]
        m = np.tile(np.clip((eje - desde) / tramo, 0, 1).reshape(1, -1), (alto, 1))
    else:  # radial
        yy, xx = np.mgrid[0:alto, 0:ancho].astype(np.float32)
        cx, cy = ancho / 2.0, alto / 2.0
        r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        r = r / (r.max() or 1.0)
        m = np.clip((r - desde) / tramo, 0, 1)

    m = m[..., None]
    resultado = arr * (1 - m) + rgb_color * m
    salida = salida or _nombre_salida(ruta, 'degradado')
    Image.fromarray(_de01(resultado), 'RGB').save(salida)
    return salida


# ───────────────────────── restaurar ─────────────────────────

def _luminancia(arr):
    return 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]


def _ruido_zonas_planas(lum, bloque=8):
    """Ruido en zonas planas medido con una vara que NO cambia de escala con el
    contraste: se parte `lum` (0-255) en bloques FIJOS de `bloque` px, se mide la
    desviación típica dentro de cada bloque, y se toma el percentil 20 de esas
    desviaciones — el percentil bajo aísla los bloques sin apenas detalle (donde
    lo que quede de variación es ruido, no textura de la escena). Con un bloque
    fijo, la rejilla no se mueve aunque cambie el contraste: antes y después usan
    exactamente los mismos bloques, así que la medida sigue siendo comparable (a
    diferencia de un umbral basado en el gradiente, que se corre al estirar
    niveles)."""
    alto, ancho = lum.shape
    ah, aw = (alto // bloque) * bloque, (ancho // bloque) * bloque
    if ah == 0 or aw == 0:
        return float(lum.std())
    recorte = lum[:ah, :aw]
    bloques = (recorte.reshape(ah // bloque, bloque, aw // bloque, bloque)
               .swapaxes(1, 2).reshape(-1, bloque * bloque))
    return float(np.percentile(bloques.std(axis=1), 20))


def _medir(arr_u8):
    lum = _luminancia(arr_u8.astype(np.float32))
    contraste = float(lum.std())
    ruido = _ruido_zonas_planas(lum)
    return contraste, ruido


def _niveles_automaticos(arr01):
    salida = np.empty_like(arr01)
    for c in range(3):
        canal = arr01[..., c]
        p1, p99 = np.percentile(canal, 1), np.percentile(canal, 99)
        salida[..., c] = canal if p99 <= p1 else np.clip((canal - p1) / (p99 - p1), 0, 1)
    return salida


def _correccion_dominante(arr01):
    medias = arr01.reshape(-1, 3).mean(axis=0)
    gris = float(medias.mean())
    factores = gris / np.clip(medias, 1e-6, None)
    return np.clip(arr01 * factores, 0, 1)


def _reducir_ruido(arr01, ruido_medido=None):
    """Reduce ruido con fuerza PROPORCIONAL al ruido medido a la entrada (`ruido_medido`,
    en la misma escala que `_ruido_zonas_planas`) Y a la ganancia de contraste que
    `_niveles_automaticos` va a aplicar DESPUÉS (mismo percentil 1-99 por canal): una
    foto muy "lavada" (poco contraste de entrada) recibe un estirón grande, así que su
    ruido necesita una pasada más fuerte para no acabar amplificado igual. Con OpenCV,
    `fastNlMeansDenoisingColored` (mejor que el `bilateralFilter` viejo para ruido de
    grano, no solo de borde); sin OpenCV, mediana 3×3 de Pillow, y una SEGUNDA pasada
    si el ruido de entrada es alto (una sola mediana 3×3 no basta con ruido gaussiano
    fuerte)."""
    img_u8 = _de01(arr01)
    ruido = 15.0 if ruido_medido is None else float(ruido_medido)
    if cv2 is not None:
        ganancia_niveles = 1.0
        for c in range(3):
            canal = arr01[..., c]
            p1, p99 = np.percentile(canal, 1), np.percentile(canal, 99)
            ganancia_niveles = max(ganancia_niveles, 1.0 / max(p99 - p1, 1e-6))
        bgr = img_u8[..., ::-1]
        h = float(np.clip(ruido * ganancia_niveles * 1.1, 3.0, 45.0))
        suavizado = cv2.fastNlMeansDenoisingColored(bgr, None, h=h, hColor=h,
                                                      templateWindowSize=7, searchWindowSize=21)
        return suavizado[..., ::-1].astype(np.float32) / 255.0
    pasadas = 2 if ruido > 25.0 else 1
    img_pil = Image.fromarray(img_u8, 'RGB')
    for _ in range(pasadas):
        img_pil = img_pil.filter(ImageFilter.MedianFilter(size=3))
    return _a01(img_pil)


def _quitar_aranazos(arr01):
    """Heurística declarada: una raya de arañazo es una línea fina cuyo valor se aparta
    mucho de la mediana local (`cv2.medianBlur`); no distingue un arañazo real de un
    detalle fino de verdad (una rama, un cable) — con fotos que tengan mucho detalle
    fino, esto puede borrar cosas que no eran daño."""
    if cv2 is None:
        return arr01, False
    img_u8 = _de01(arr01)
    gris = cv2.cvtColor(img_u8, cv2.COLOR_RGB2GRAY)
    blur = cv2.medianBlur(gris, 5)
    dif = cv2.absdiff(gris, blur)
    _, mascara = cv2.threshold(dif, 18, 255, cv2.THRESH_BINARY)
    mascara = cv2.dilate(mascara, np.ones((3, 3), np.uint8), iterations=1)
    bgr = img_u8[..., ::-1]
    reparado = cv2.inpaint(bgr, mascara, 3, cv2.INPAINT_TELEA)
    return reparado[..., ::-1].astype(np.float32) / 255.0, True


def _nitidez(arr01, cantidad):
    if cantidad <= 0:
        return arr01
    img_u8 = Image.fromarray(_de01(arr01), 'RGB')
    desenfoque = np.asarray(img_u8.filter(ImageFilter.GaussianBlur(radius=2))).astype(np.float32)
    a = np.asarray(img_u8).astype(np.float32)
    realzado = a + (a - desenfoque) * float(cantidad)
    return np.clip(realzado, 0, 255) / 255.0


def restaurar(ruta, salida=None, sin_aranazos=False, nitidez=1.0, color='auto', avisar=print):
    img = _cargar_rgb(ruta)
    contraste0, ruido0 = _medir(np.asarray(img))
    arr = _a01(img)
    # el ruido se reduce ANTES de estirar niveles: estirar el contraste de una foto
    # sin quitarle antes el grano amplifica el grano tanto como el contraste (fallo
    # MEDIDO 7-sep: con el orden viejo — niveles, dominante, ruido — el ruido de una
    # foto real subía de 43.69 a 83.88, casi el doble).
    arr = _reducir_ruido(arr, ruido_medido=ruido0)
    arr = _niveles_automaticos(arr)
    if color == 'auto':
        arr = _correccion_dominante(arr)  # lleva la media a gris neutro; NO recupera el tono original
    hizo_aranazos = False
    if sin_aranazos:
        arr, hizo_aranazos = _quitar_aranazos(arr)
        if not hizo_aranazos:
            avisar('sin arañazos: falta OpenCV (pip install opencv-python); se sigue sin esa pasada')
    arr = _nitidez(arr, nitidez)
    final_u8 = _de01(arr)
    contraste1, ruido1 = _medir(final_u8)
    ruido_reducido = ruido1 < ruido0
    salida = salida or _nombre_salida(ruta, 'restaurada')
    Image.fromarray(final_u8, 'RGB').save(salida)
    etiqueta_ruido = (f'ruido en zonas planas {ruido0:.2f} -> {ruido1:.2f}' if ruido_reducido
                       else f'ruido no reducido ({ruido0:.2f} -> {ruido1:.2f})')
    avisar(f'contraste {contraste0:.1f} -> {contraste1:.1f} · {etiqueta_ruido} · {salida}')
    return {"salida": salida, "contraste_antes": round(contraste0, 2), "contraste_despues": round(contraste1, 2),
            "ruido_antes": round(ruido0, 2), "ruido_despues": round(ruido1, 2),
            "ruido_reducido": ruido_reducido, "aranazos_reparados": hizo_aranazos}


# ───────────────────────── numeros (pintar por números) ─────────────────────────

def _etiquetar_conexas(indices):
    """`(etiquetas, num_zonas)`: una zona por cada grupo de píxeles contiguos (4-conexión)
    con el MISMO índice de color. Rápido con OpenCV (`connectedComponents` por cada color);
    sin él, unión-búsqueda en Python puro — declarado más lento, sin medir a escala real."""
    if cv2 is not None:
        etiquetas = np.zeros(indices.shape, dtype=np.int32)
        siguiente = 1
        for valor in np.unique(indices):
            mascara = (indices == valor).astype(np.uint8)
            n, comp = cv2.connectedComponents(mascara, connectivity=4)
            for c in range(1, n):
                etiquetas[comp == c] = siguiente
                siguiente += 1
        return etiquetas, siguiente - 1
    return _etiquetar_conexas_puro(indices)


def _etiquetar_conexas_puro(indices):
    alto, ancho = indices.shape
    etiquetas = np.zeros((alto, ancho), dtype=np.int32)
    padre = [0]

    def encontrar(x):
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    def unir(a, b):
        ra, rb = encontrar(a), encontrar(b)
        if ra != rb:
            padre[max(ra, rb)] = min(ra, rb)

    siguiente = 1
    for y in range(alto):
        for x in range(ancho):
            v = indices[y, x]
            vecinos = []
            if x > 0 and indices[y, x - 1] == v:
                vecinos.append(int(etiquetas[y, x - 1]))
            if y > 0 and indices[y - 1, x] == v:
                vecinos.append(int(etiquetas[y - 1, x]))
            if not vecinos:
                etiquetas[y, x] = siguiente
                padre.append(siguiente)
                siguiente += 1
            else:
                m = min(vecinos)
                etiquetas[y, x] = m
                for et in vecinos:
                    unir(et, m)

    raices = np.array([encontrar(int(e)) for e in etiquetas.ravel()], dtype=np.int32)
    unicos = np.unique(raices)
    mapa = {int(r): i + 1 for i, r in enumerate(unicos)}
    renumerado = np.array([mapa[int(r)] for r in raices], dtype=np.int32).reshape(etiquetas.shape)
    return renumerado, len(unicos)


def _dibujar_contornos(draw, etiquetas, color=(160, 160, 160)):
    ys, xs = np.nonzero(etiquetas[:, 1:] != etiquetas[:, :-1])
    for y, x in zip(ys.tolist(), xs.tolist()):
        draw.point((x, y), fill=color)
    ys, xs = np.nonzero(etiquetas[1:, :] != etiquetas[:-1, :])
    for y, x in zip(ys.tolist(), xs.tolist()):
        draw.point((x, y), fill=color)


def _suavizar_indices_moda(indices, radio):
    """Filtro de MODA por ventana `2*radio+1`: cada píxel pasa al índice de color más
    frecuente en su vecindad. Aplicado ANTES de etiquetar zonas conexas, limpia el
    ruido sal-y-pimienta y los píxeles sueltos de la cuantización — sin él, cada mota
    de ruido nace como su propia zona de 1 píxel. Para cada color se cuenta cuántas
    veces aparece en la ventana de cada píxel (`_suma_ventana` sobre su máscara
    binaria — con OpenCV, `boxFilter`) y se toma el color con más votos."""
    if radio <= 0:
        return indices
    mejor_cuenta = np.full(indices.shape, -1.0, dtype=np.float32)
    mejor_indice = indices.copy()
    k = 2 * radio + 1
    for valor in np.unique(indices):
        mascara = (indices == valor).astype(np.float32)
        if cv2 is not None:
            cuenta = cv2.boxFilter(mascara, ddepth=-1, ksize=(k, k), normalize=False,
                                    borderType=cv2.BORDER_REPLICATE)
        else:
            cuenta = _suma_ventana(mascara, radio).astype(np.float32)
        mejor = cuenta > mejor_cuenta
        mejor_indice[mejor] = valor
        mejor_cuenta[mejor] = cuenta[mejor]
    return mejor_indice


def _vecino_dominante(etiquetas, zona_id):
    """La zona vecina con la que `zona_id` comparte más frontera (4-conexión) —
    acotado a su propio recuadro (+1 px por lado, donde cabe cualquier vecino
    posible), así que es barato aunque la imagen entera sea grande."""
    ys, xs = np.nonzero(etiquetas == zona_id)
    if ys.size == 0:
        return None
    y0, y1 = max(0, ys.min() - 1), min(etiquetas.shape[0], ys.max() + 2)
    x0, x1 = max(0, xs.min() - 1), min(etiquetas.shape[1], xs.max() + 2)
    sub = etiquetas[y0:y1, x0:x1]
    mascara = sub == zona_id
    borde = np.zeros_like(mascara)
    borde[1:, :] |= mascara[:-1, :]
    borde[:-1, :] |= mascara[1:, :]
    borde[:, 1:] |= mascara[:, :-1]
    borde[:, :-1] |= mascara[:, 1:]
    borde &= ~mascara
    vecinos = sub[borde]
    vecinos = vecinos[vecinos != zona_id]
    if vecinos.size == 0:
        return None
    valores, cuentas = np.unique(vecinos, return_counts=True)
    return int(valores[np.argmax(cuentas)])


def _renumerar_consecutivo(etiquetas):
    unicos = np.unique(etiquetas)
    unicos = unicos[unicos != 0]
    if unicos.size == 0:
        return etiquetas, 0
    mapa = np.zeros(int(etiquetas.max()) + 1, dtype=np.int32)
    mapa[unicos] = np.arange(1, unicos.size + 1)
    return mapa[etiquetas], int(unicos.size)


def _fusionar_zonas_pequenas(etiquetas, num_zonas, min_zona):
    """Funde cada zona con área < `min_zona` en la zona vecina con la que comparte
    más frontera, repitiendo hasta que no quede ninguna. Una zona sin ningún vecino
    (toda la imagen es una única zona diminuta) se deja tal cual: no hay con qué
    fundirla."""
    etiquetas = etiquetas.copy()
    for _ in range(int(num_zonas) + 1):
        tamanos = np.bincount(etiquetas.ravel())
        pequenas = [z for z in range(1, len(tamanos)) if 0 < tamanos[z] < min_zona]
        if not pequenas:
            break
        pequenas.sort(key=lambda z: tamanos[z])
        hubo_fusion = False
        for z in pequenas:
            if not (etiquetas == z).any():
                continue  # ya se fundió en esta misma pasada
            vecino = _vecino_dominante(etiquetas, z)
            if vecino is None or vecino == z:
                continue
            etiquetas[etiquetas == z] = vecino
            hubo_fusion = True
        if not hubo_fusion:
            break
    return _renumerar_consecutivo(etiquetas)


def numeros(ruta, colores=12, ancho=1400, min_zona=None, salida=None):
    n_colores = int(colores)
    img = _cargar_rgb(ruta)
    if img.width != int(ancho):
        alto_nuevo = max(2, round(img.height * int(ancho) / img.width))
        img = img.resize((int(ancho), alto_nuevo), Image.LANCZOS)
    ancho_img, alto_img = img.size
    if min_zona is None:
        min_zona = max(20, round(ancho_img * alto_img * 0.0005))  # 0,05% del lienzo, suelo 20 px
    else:
        min_zona = int(min_zona)

    suave = img.filter(ImageFilter.MedianFilter(size=3))
    cuantizada = suave.quantize(colors=n_colores, method=Image.Quantize.MEDIANCUT)
    paleta_plana = cuantizada.getpalette() or []

    # filtro de moda ANTES de etiquetar: limpia el ruido sal-y-pimienta y los píxeles
    # sueltos de la cuantización (si no, cada uno nace como su propia zona de 1 px).
    radio_moda = max(1, round(ancho_img / 150))
    indices = _suavizar_indices_moda(np.asarray(cuantizada), radio_moda)

    usados = sorted(int(v) for v in np.unique(indices))
    paleta = {idx: tuple(paleta_plana[idx * 3:idx * 3 + 3]) for idx in usados}
    numero_de_indice = {idx: i + 1 for i, idx in enumerate(usados)}

    etiquetas, num_zonas = _etiquetar_conexas(indices)
    etiquetas, num_zonas = _fusionar_zonas_pequenas(etiquetas, num_zonas, min_zona)
    tamanos = np.bincount(etiquetas.ravel()) if num_zonas else np.zeros(1, dtype=np.int64)

    plantilla = Image.new('RGB', (ancho_img, alto_img), (255, 255, 255))
    d = ImageDraw.Draw(plantilla)
    _dibujar_contornos(d, etiquetas)
    for zona_id in range(1, num_zonas + 1):
        if tamanos[zona_id] < min_zona:
            continue  # solo puede pasar si no tenía ningún vecino con quien fundirse
        mascara_zona = etiquetas == zona_id
        ys, xs = np.nonzero(mascara_zona)
        idx_color = int(np.bincount(indices[mascara_zona], minlength=len(paleta_plana) // 3 or 1).argmax())
        cy, cx = int(round(ys.mean())), int(round(xs.mean()))
        try:
            d.text((cx, cy), str(numero_de_indice[idx_color]), fill=(0, 0, 0), anchor='mm')
        except (TypeError, ValueError):  # Pillow sin soporte de anchor en la fuente por defecto
            d.text((cx - 3, cy - 5), str(numero_de_indice[idx_color]), fill=(0, 0, 0))

    arr_color = np.zeros((alto_img, ancho_img, 3), dtype=np.uint8)
    for idx, col in paleta.items():
        arr_color[indices == idx] = col
    coloreado = Image.fromarray(arr_color, 'RGB')

    pie_alto = 40
    plantilla_final = Image.new('RGB', (ancho_img, alto_img + pie_alto), (255, 255, 255))
    plantilla_final.paste(plantilla, (0, 0))
    dp = ImageDraw.Draw(plantilla_final)
    x = 8
    for idx in usados:
        dp.rectangle([x, alto_img + 8, x + 22, alto_img + 30], fill=paleta[idx], outline=(0, 0, 0))
        dp.text((x + 26, alto_img + 10), str(numero_de_indice[idx]), fill=(0, 0, 0))
        x += 60

    base = salida or _nombre_salida(ruta, 'numeros', ext='')
    if base.lower().endswith('.png'):
        base = base[:-4]
    ruta_plantilla, ruta_color = base + '_plantilla.png', base + '_color.png'
    plantilla_final.save(ruta_plantilla)
    coloreado.save(ruta_color)
    return {"plantilla": ruta_plantilla, "color": ruta_color, "colores": len(usados), "zonas": int(num_zonas)}


# ───────────────────────── borrar ─────────────────────────

def _mascara_de_caja(ancho, alto, caja_txt):
    try:
        x, y, w, h = (int(v) for v in caja_txt.split(','))
    except ValueError:
        raise ValueError('--caja necesita "x,y,w,h" (cuatro enteros separados por comas)')
    m = np.zeros((alto, ancho), dtype=np.uint8)
    m[max(0, y):y + h, max(0, x):x + w] = 255
    return m


def _mascara_de_fichero(ruta, ancho, alto):
    m = Image.open(ruta).convert('L')
    if m.size != (ancho, alto):
        raise ValueError(f'la máscara mide {m.size}, la imagen {(ancho, alto)}: deben coincidir')
    return np.where(np.asarray(m) > 127, 255, 0).astype(np.uint8)


def _mascara_de_color(img_rgb_arr, color_txt):
    partes = color_txt.split(',')
    rgb = np.array(_hex_a_rgb(partes[0]), dtype=np.float32)
    tolerancia = float(partes[1]) if len(partes) > 1 else 30.0
    dif = np.sqrt(((img_rgb_arr.astype(np.float32) - rgb) ** 2).sum(axis=2))
    return np.where(dif <= tolerancia, 255, 0).astype(np.uint8)


def _mascara_anillo(m_bool, ancho_anillo=20):
    """Anillo de fondo de `ancho_anillo` px alrededor de `m_bool`: dilata la máscara
    (con la misma tabla de sumas de área que `_suma_ventana`, sin depender de OpenCV)
    y le resta la propia máscara — el fondo INMEDIATO, no la zona que se va a rellenar."""
    dilatada = _suma_ventana(m_bool.astype(np.float32), ancho_anillo) > 0
    return dilatada & ~m_bool


def _evaluar_aviso_borron(arr_rgb, m_bool):
    """Mide ANTES de rellenar, para avisar de un borrón probable en vez de dejar que
    aparezca sin más: (1) el área de la máscara frente al área total de la imagen —
    un objeto grande relativo al lienzo deja un borrón visible; (2) la textura del
    anillo de 20 px de fondo alrededor de la máscara, contra la mediana de la
    desviación local de TODA la imagen — un fondo con estructura (matorral, un
    edificio) no se rellena bien con `cv2.inpaint`, uno casi uniforme sí. Umbrales:
    área > 1 % de la imagen, o desviación del anillo por encima de esa mediana."""
    alto, ancho = m_bool.shape
    area_fraccion = float(m_bool.sum()) / float(alto * ancho)
    lum = _luminancia(arr_rgb.astype(np.float32))
    mapa_dev = _mapa_desviacion_local(lum)
    anillo = _mascara_anillo(m_bool, ancho_anillo=20)
    textura_anillo = float(np.median(mapa_dev[anillo])) if anillo.any() else 0.0
    textura_mediana_imagen = float(np.median(mapa_dev))
    area_grande = area_fraccion > 0.01
    textura_alta = textura_anillo > textura_mediana_imagen
    medida = {"area_fraccion": round(area_fraccion, 4), "textura_anillo": round(textura_anillo, 2),
              "textura_mediana_imagen": round(textura_mediana_imagen, 2)}
    if not (area_grande or textura_alta):
        return None, medida
    motivos = []
    if area_grande:
        motivos.append(f'área {area_fraccion * 100:.1f}% de la imagen')
    if textura_alta:
        motivos.append(f'anillo con textura {textura_anillo:.1f} > mediana {textura_mediana_imagen:.1f}')
    aviso = ('borrón probable (' + '; '.join(motivos) + '): objeto grande o fondo con '
             'textura; usa --metodo taller')
    return aviso, medida


def _discontinuidad_borde(resultado_rgb, m_bool, ancho_borde=5):
    """Diferencia de luminancia entre el interior ya rellenado y su anillo de fondo
    inmediato (`ancho_borde` px) — cuanto más alta, más se nota la costura entre el
    relleno y lo que lo rodea. Sirve para elegir entre `telea` y `ns` sin decretarlo:
    se calculan los dos y se deja el que dé menos discontinuidad."""
    if not m_bool.any():
        return 0.0
    lum = _luminancia(resultado_rgb.astype(np.float32))
    anillo = _mascara_anillo(m_bool, ancho_anillo=ancho_borde)
    if not anillo.any():
        return 0.0
    return float(abs(lum[m_bool].mean() - lum[anillo].mean()))


def _cfg_imagen(mem):
    try:
        with open(os.path.join(mem, 'imagen_config.json'), encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return {}


def _borrar_via_taller(img, mascara_u8, mem):
    """Manda `img` (RGB) y `mascara_u8` (blanco = repintar) a `POST <taller_url>/sdapi/v1/
    img2img`, estilo A1111. `taller_url` vive en `<memoria>/imagen_config.json`; sin esa
    clave, RuntimeError("sin dato: ...") — nunca se inventa una URL."""
    import base64
    c = _cfg_imagen(mem)
    url = (c.get('taller_url') or '').rstrip('/')
    if not url:
        raise RuntimeError('sin dato: falta "taller_url" en imagen_config.json (arranca taller.py y apunta ahí)')

    def _png_b64(imagen):
        buf = io.BytesIO()
        imagen.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode('ascii')

    carga = {
        "init_images": [_png_b64(img)],
        "mask": _png_b64(Image.fromarray(mascara_u8, 'L')),
        "denoising_strength": float(c.get('taller_denoise', 0.75)),
        "steps": int(c.get('taller_pasos', 20)),
        "inpainting_fill": 1,
        "prompt": "",
    }
    req = urllib.request.Request(url + '/sdapi/v1/img2img', data=json.dumps(carga).encode('utf-8'),
                                  headers={"Content-Type": "application/json"}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            cuerpo = r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'taller: HTTP {e.code}')
    d = json.loads(cuerpo)
    datos = base64.b64decode(d['images'][0])
    return Image.open(io.BytesIO(datos)).convert('RGB')


def borrar(ruta, caja=None, mascara=None, color=None, metodo='telea', salida=None, mem=None, avisar=print):
    if sum(bool(v) for v in (caja, mascara, color)) != 1:
        raise ValueError('pasa exactamente una de --caja / --mascara / --color')
    if metodo not in METODOS_BORRAR:
        raise ValueError(f'método desconocido: "{metodo}" (usa {", ".join(METODOS_BORRAR)})')
    img = _cargar_rgb(ruta)
    ancho, alto = img.size
    arr = np.asarray(img)
    if caja:
        m = _mascara_de_caja(ancho, alto, caja)
    elif mascara:
        m = _mascara_de_fichero(mascara, ancho, alto)
    else:
        m = _mascara_de_color(arr, color)
    m_bool = m > 0

    aviso, medida = (None, {})
    if metodo != 'taller':  # con taller ya se está usando el método recomendado: no hace falta avisar
        aviso, medida = _evaluar_aviso_borron(arr, m_bool)

    metodo_usado, discontinuidad = metodo, None
    if metodo == 'taller':
        resultado = _borrar_via_taller(img, m, mem)
    else:
        if cv2 is None:
            raise RuntimeError('sin dato: pip install opencv-python (lienzo.py borrar --metodo telea|ns)')
        # se prueban los dos métodos clásicos y se deja el de menos discontinuidad de
        # borde (diciéndolo): un fondo puede favorecer a Telea o a Navier-Stokes según
        # su textura, y decretar uno de antemano deja el otro caso peor de lo que podría.
        bgr = arr[..., ::-1].copy()
        candidatos = {}
        for candidato, bandera in (('telea', cv2.INPAINT_TELEA), ('ns', cv2.INPAINT_NS)):
            reparado_rgb = cv2.inpaint(bgr, m, 3, bandera)[..., ::-1]
            candidatos[candidato] = (reparado_rgb, _discontinuidad_borde(reparado_rgb, m_bool))
        metodo_usado = min(candidatos, key=lambda k: candidatos[k][1])
        resultado_rgb, discontinuidad = candidatos[metodo_usado]
        resultado = Image.fromarray(resultado_rgb, 'RGB')

    salida = salida or _nombre_salida(ruta, 'borrada')
    resultado.save(salida)

    partes_msg = []
    if discontinuidad is not None:
        etiqueta = metodo_usado if metodo_usado == metodo else f'{metodo_usado} (pedido {metodo}, más discontinuidad)'
        partes_msg.append(f'método {etiqueta} · discontinuidad de borde {discontinuidad:.2f}')
    if aviso:
        partes_msg.append(aviso)
    partes_msg.append(salida)
    avisar(' · '.join(partes_msg))

    r = {"salida": salida, "metodo_pedido": metodo, "metodo_usado": metodo_usado, "aviso": aviso}
    r.update(medida)
    if discontinuidad is not None:
        r["discontinuidad_borde"] = round(discontinuidad, 2)
    return r


# ───────────────────────── cubista (facetas analíticas de verdad) ─────────────────────────
#
# Ver el docstring del módulo para el POR QUÉ vive aquí y no como un "estilo" más de
# pintor.py: no es una pincelada, es otra composición de la imagen entera.

def _color_medio_poligono(arr_rgb, pts):
    """Media de color de `arr_rgb` (H,W,3 uint8) dentro del polígono `pts`, recortando
    primero a su caja delimitadora — no la imagen entera: con cientos de facetas por
    cuadro, enmascarar la imagen COMPLETA cada vez sería O(facetas × píxeles_totales);
    la caja lo deja en O(facetas × píxeles_de_su_propia_caja), que es lo que hace
    falta de verdad. `None` si la faceta cae fuera del lienzo o es tan fina que ningún
    píxel entero queda dentro (triángulo casi colineal de la triangulación)."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = max(0, int(math.floor(min(xs)))), min(arr_rgb.shape[1], int(math.ceil(max(xs))) + 1)
    y0, y1 = max(0, int(math.floor(min(ys)))), min(arr_rgb.shape[0], int(math.ceil(max(ys))) + 1)
    if x1 <= x0 or y1 <= y0:
        return None
    m = Image.new('L', (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(m).polygon([(px - x0, py - y0) for px, py in pts], fill=255)
    mascara = np.asarray(m) > 0
    if not mascara.any():
        return None
    color = arr_rgb[y0:y1, x0:x1][mascara].mean(axis=0)
    return tuple(int(round(c)) for c in color)


def _area_triangulo(pts):
    (x1, y1), (x2, y2), (x3, y3) = pts
    return abs(x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)) / 2.0


def _puntos_de_bordes(gris_u8, n, rnd):
    """`n` puntos MUESTREADOS de los bordes reales de `gris_u8` (`cv2.Canny`; sin OpenCV,
    gradiente de Sobel propio sobre su percentil 90 — más lento y menos limpio, declarado,
    no medido a escala real). El cubismo analítico rompe la figura por donde YA hay un
    borde en la escena, no por una rejilla arbitraria: sin este paso, las facetas caerían
    donde caiga la rejilla y ninguna seguiría el contorno de nada."""
    if cv2 is not None:
        bordes = cv2.Canny(gris_u8, 60, 160)
    else:
        gy, gx = np.gradient(gris_u8.astype(np.float32))
        mag = np.hypot(gx, gy)
        bordes = (mag > np.percentile(mag, 90)).astype(np.uint8) * 255
    ys, xs = np.nonzero(bordes)
    if ys.size == 0:
        return np.empty((0, 2), dtype=np.float64)
    n = min(int(n), ys.size)
    idx = rnd.choice(ys.size, size=n, replace=False)
    return np.stack([xs[idx], ys[idx]], axis=1).astype(np.float64)


def _puntos_de_marco(ancho, alto, por_lado):
    """Puntos a lo largo de los cuatro bordes del lienzo: sin ellos, la triangulación de
    Delaunay se para donde caiga el punto semilla más externo y deja un borde de imagen
    sin ninguna faceta que lo cubra (fondo asomando por fuera, no por un hueco a propósito)."""
    lin = np.linspace(0, 1, max(2, int(por_lado)))
    arriba = np.stack([lin * (ancho - 1), np.zeros_like(lin)], axis=1)
    abajo = np.stack([lin * (ancho - 1), np.full_like(lin, alto - 1)], axis=1)
    izq = np.stack([np.zeros_like(lin), lin * (alto - 1)], axis=1)
    der = np.stack([np.full_like(lin, ancho - 1), lin * (alto - 1)], axis=1)
    return np.concatenate([arriba, abajo, izq, der], axis=0)


def _triangular_rejilla(ancho, alto, n_deseado):
    """Fallback SIN OpenCV: NO es una Delaunay real (declarado, no se hace pasar por una)
    — una rejilla regular de celdas partidas en dos triángulos por su diagonal, con el
    tamaño de celda elegido para acercarse a `n_deseado` facetas (cada celda da 2). Sigue
    cubriendo el lienzo entero y sigue dando polígonos con los que trabajar; lo que pierde
    es que las facetas ya no nacen de los bordes reales de la foto."""
    celdas = max(1, round(n_deseado / 2))
    cols = max(1, round(math.sqrt(celdas * ancho / max(1, alto))))
    filas = max(1, round(celdas / cols))
    xs = np.linspace(0, ancho - 1, cols + 1)
    ys = np.linspace(0, alto - 1, filas + 1)
    triangulos = []
    for j in range(filas):
        for i in range(cols):
            a, b = (xs[i], ys[j]), (xs[i + 1], ys[j])
            c, d = (xs[i], ys[j + 1]), (xs[i + 1], ys[j + 1])
            triangulos.append([a, b, c])
            triangulos.append([b, d, c])
    return triangulos


def _triangular_delaunay(ancho, alto, puntos, n_deseado):
    """Triangulación de Delaunay de `puntos` (`cv2.Subdiv2D` — ya dependencia opcional del
    paquete: no hace falta scipy) recortada al rectángulo del lienzo: `Subdiv2D` también
    genera triángulos de un "punto en el infinito" propio de su algoritmo incremental; se
    descartan quedándose solo con los que caen ENTEROS dentro de `(0,0,ancho,alto)`. Sin
    OpenCV, cae a `_triangular_rejilla` (declarado ahí lo que pierde)."""
    if cv2 is None:
        return _triangular_rejilla(ancho, alto, n_deseado)
    subdiv = cv2.Subdiv2D((0, 0, int(ancho), int(alto)))
    for x, y in puntos:
        x = min(max(float(x), 0.0), ancho - 1.0)
        y = min(max(float(y), 0.0), alto - 1.0)
        try:
            subdiv.insert((x, y))
        except cv2.error:
            continue  # punto duplicado o degenerado: se salta, no revienta el cuadro entero
    triangulos = []
    for t in subdiv.getTriangleList():
        pts = [(float(t[0]), float(t[1])), (float(t[2]), float(t[3])), (float(t[4]), float(t[5]))]
        if all(0 <= px <= ancho - 1 and 0 <= py <= alto - 1 for px, py in pts):
            triangulos.append(pts)
    return triangulos


def _rotar_y_mover(pts, angulo, dx, dy):
    cx = sum(p[0] for p in pts) / 3.0
    cy = sum(p[1] for p in pts) / 3.0
    ca, sa = math.cos(angulo), math.sin(angulo)
    out = []
    for px, py in pts:
        rx, ry = px - cx, py - cy
        out.append((cx + rx * ca - ry * sa + dx, cy + rx * sa + ry * ca + dy))
    return out


def _fondo_atenuado(img, radio):
    """Fondo del cuadro cubista: la foto difuminada y con el color atenuado hacia su propia
    luminancia (NO gris puro: solo atenuado) — para que el hueco que deja una faceta
    desplazada enseñe un eco borroso de la escena, no un vacío ni un color ajeno a la foto.
    `radio` grande de más aplana el eco hasta volverlo irreconocible; pequeño de más deja
    ver una foto nítida por las rendijas, que compite con las facetas en vez de quedarse
    detrás — el valor por defecto de `cubista()` (ancho/45) es una elección declarada,
    medida solo en que no revienta, no una ley de proporción."""
    difuso = img.filter(ImageFilter.GaussianBlur(radio))
    arr = _a01(difuso)
    luminancia = (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2])[..., None]
    atenuado = arr * 0.45 + luminancia * 0.55
    return Image.fromarray(_de01(atenuado), 'RGB')


def _escribir_pasos(pasos_dir, generar_frame, pasos):
    """Escribe `pasos` fotogramas PNG numerados (`paso_000.png`, ...) en `pasos_dir` —
    `generar_frame(k)` devuelve la imagen PIL del paso `k` (0-indexado; `k == pasos - 1`
    es el cuadro acabado, igual al PNG final). Mismo propósito que el `.json.gz` de
    pinceladas de `pintor.py`/`video_pintura.py`, pero aquí el "trazo" de cada paso ya es
    una imagen entera compuesta por `cubista()`/`surrealista()` — no hay pinceladas que
    guardar, así que el formato natural es una carpeta de fotogramas, no otro `.json.gz`."""
    os.makedirs(pasos_dir, exist_ok=True)
    ancho_indice = max(3, len(str(pasos - 1)))
    rutas = []
    for k in range(pasos):
        ruta = os.path.join(pasos_dir, f'paso_{k:0{ancho_indice}d}.png')
        generar_frame(k).save(ruta)
        rutas.append(ruta)
    return rutas


def cubista(ruta, facetas=220, desplazamiento=0.07, giro=7.0, contorno=True, difuminado_fondo=None,
            semilla=7, salida=None, pasos=None, pasos_dir=None):
    """Cubismo ANALÍTICO de verdad (ver el docstring del módulo: no es una pincelada más
    gorda) — descompone `ruta` en facetas poligonales sembradas en sus bordes reales,
    aplana cada una a su color medio y la desplaza/gira un poco sobre un fondo atenuado,
    de MAYOR a MENOR área.

    `facetas`: cuántos puntos semilla se piden (bordes + relleno); el número REAL de
    triángulos que salen de la triangulación se mide y se devuelve en `"facetas"` — no
    tiene por qué coincidir. `desplazamiento`: cuánto se mueve cada faceta, como fracción
    de su propio "radio" (raíz del área) — así una faceta grande se mueve más píxeles que
    una diminuta sin que ninguna de las dos pierda su forma. `giro`: rotación máxima en
    GRADOS alrededor de su propio centro. `contorno=False`: sin la línea oscura que remata
    cada faceta (junta visible). `pasos`+`pasos_dir`: además del PNG final, escribe esa
    cantidad de fotogramas de progreso (facetas reveladas de MAYOR a MENOR área) en ese
    directorio, para `video_composicion.py` — sin `pasos_dir` no se escribe ninguno.

    Devuelve {"salida", "facetas", "cobertura_facetas" (fracción del lienzo que ACABA bajo
    alguna faceta; el resto es fondo asomando por los huecos — medido, no una ley),
    "pasos" (lista de rutas, o None sin `pasos_dir`)}."""
    img = _cargar_rgb(ruta)
    ancho, alto = img.size
    arr = np.asarray(img)
    gris = np.asarray(img.convert('L'))
    rnd = np.random.RandomState(int(semilla))

    n_borde = max(8, round(facetas * 0.7))
    n_relleno = max(4, int(facetas) - n_borde)
    puntos = np.concatenate([
        _puntos_de_bordes(gris, n_borde, rnd),
        np.stack([rnd.uniform(0, ancho - 1, n_relleno), rnd.uniform(0, alto - 1, n_relleno)], axis=1),
        _puntos_de_marco(ancho, alto, max(3, round(math.sqrt(max(1, facetas))))),
    ], axis=0)

    triangulos_pts = _triangular_delaunay(ancho, alto, puntos, int(facetas))
    facetas_calc = []  # [(area, color, pts_originales)], luego ordenado de mayor a menor
    for pts in triangulos_pts:
        area = _area_triangulo(pts)
        if area < 3.0:
            continue  # esquirla degenerada de la triangulación (casi colineal): sin color fiable
        color = _color_medio_poligono(arr, pts)
        if color is None:
            continue
        facetas_calc.append((area, color, pts))
    facetas_calc.sort(key=lambda f: f[0], reverse=True)

    # El jitter (giro + desplazamiento) de cada faceta se decide UNA sola vez aquí, con el
    # mismo generador ya usado arriba para las semillas: así el cuadro FINAL no cambia según
    # se pidan pasos de vídeo o no. Si el jitter se calculase dentro de la función que dibuja
    # cada fotograma, se consumirían números aleatorios distintos según cuántas veces se
    # llame, y el último paso dejaría de coincidir con el PNG final.
    jitters = []
    for area, _color, _pts in facetas_calc:
        radio = math.sqrt(area)
        angulo = math.radians(rnd.uniform(-giro, giro))
        rumbo = rnd.uniform(0, 2 * math.pi)
        dist = desplazamiento * radio
        jitters.append((angulo, math.cos(rumbo) * dist, math.sin(rumbo) * dist))

    radio_fondo = float(difuminado_fondo) if difuminado_fondo is not None else max(4, round(ancho / 45))
    fondo_img = _fondo_atenuado(img, radio_fondo)
    grosor_contorno = max(1, round(ancho / 700))

    def _dibujar(hasta):
        lienzo = fondo_img.copy()
        d = ImageDraw.Draw(lienzo)
        for (area, color, pts), (angulo, dx, dy) in list(zip(facetas_calc, jitters))[:hasta]:
            pts_mov = _rotar_y_mover(pts, angulo, dx, dy)
            d.polygon(pts_mov, fill=color)
            if contorno:
                oscuro = tuple(max(0, int(c * 0.55)) for c in color)
                d.line(pts_mov + [pts_mov[0]], fill=oscuro, width=grosor_contorno)
        return lienzo

    total = len(facetas_calc)
    final = _dibujar(total)
    salida = salida or _nombre_salida(ruta, 'cubista')
    final.save(salida)

    cobertura = float(np.mean(np.any(np.asarray(final) != np.asarray(fondo_img), axis=-1))) if total else 0.0

    rutas_pasos = None
    if pasos and pasos_dir:
        n_pasos = max(1, int(pasos))

        def _frame(k):
            hasta = max(1, round((k + 1) * total / n_pasos)) if total else 0
            return _dibujar(hasta)

        rutas_pasos = _escribir_pasos(pasos_dir, _frame, n_pasos)

    return {"salida": salida, "facetas": total, "cobertura_facetas": round(cobertura, 4), "pasos": rutas_pasos}


# ───────────────────────── surrealista (deformación de dominio) ─────────────────────────
#
# Ver el docstring del módulo para el POR QUÉ vive aquí y no como un "estilo" más de
# pintor.py: es la imagen ENTERA remuestreada por un campo, no una pincelada.

def _campo_desplazamiento(ancho, alto, escala, rnd):
    """Dos campos (dx, dy) de ruido de baja frecuencia, en [-1,1] antes de escalar por la
    fuerza pedida: una rejilla GRUESA (`escala` px por celda) de números aleatorios,
    remuestreada a tamaño completo con `Image.resize(..., BICUBIC)` — esa interpolación
    hace de filtro paso-bajo (una rejilla FINA daría arrugas de alta frecuencia, no el
    derretido de formas anchas que pide un paisaje onírico)."""
    gh, gw = max(2, round(alto / escala)), max(2, round(ancho / escala))
    campos = []
    for _ in range(2):
        rejilla = rnd.uniform(-1.0, 1.0, (gh, gw)).astype(np.float32)
        campo = np.asarray(Image.fromarray(rejilla, mode='F').resize((ancho, alto), Image.BICUBIC))
        campos.append(np.clip(campo, -1.2, 1.2))  # la bicúbica puede rebasar un poco [-1,1]
    return campos[0], campos[1]


def _remuestrear_bilineal(arr, sx, sy):
    """Remuestreo bilineal manual (sin OpenCV): para cada píxel de salida, mezcla de los
    cuatro vecinos de `arr` en la posición fraccionaria `(sx, sy)` — mismo resultado que
    `cv2.remap(..., INTER_LINEAR)`, más lento (Python+numpy en vez del C de OpenCV) pero
    sin depender de él, como el resto de `lienzo.py` declara para sus pasos opcionales."""
    alto, ancho = arr.shape[:2]
    x0 = np.clip(np.floor(sx).astype(np.int32), 0, ancho - 1)
    y0 = np.clip(np.floor(sy).astype(np.int32), 0, alto - 1)
    x1 = np.clip(x0 + 1, 0, ancho - 1)
    y1 = np.clip(y0 + 1, 0, alto - 1)
    wx = (sx - x0)[..., None]
    wy = (sy - y0)[..., None]
    sup = arr[y0, x0] * (1 - wx) + arr[y0, x1] * wx
    inf = arr[y1, x0] * (1 - wx) + arr[y1, x1] * wx
    return sup * (1 - wy) + inf * wy


def _derretir(arr01, dx, dy, t):
    """Remuestrea `arr01` (H,W,3 en [0,1]) con el campo `(dx, dy)` (ya en píxeles, a fuerza
    completa) escalado por `t` — `t=0` deja la imagen intacta, `t=1` la fuerza completa;
    un `t` intermedio es justo lo que necesita el vídeo de progreso para enseñar el
    derretido EN MARCHA, no como un corte entre dos fotogramas."""
    alto, ancho = arr01.shape[:2]
    yy, xx = np.mgrid[0:alto, 0:ancho].astype(np.float32)
    sx = np.clip(xx + dx * t, 0, ancho - 1)
    sy = np.clip(yy + dy * t, 0, alto - 1)
    if cv2 is not None:
        return cv2.remap(arr01, sx, sy, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return _remuestrear_bilineal(arr01, sx, sy)


def _virar_tono(img_rgb, grados):
    """Gira el canal H de HSV `grados` (0-360, aunque Pillow lo guarde en 0-255) — un
    viraje de color parejo en toda la imagen, no un balance de blancos ni una corrección:
    es justo el efecto "onírico" que pide el encargo, declarado como lo que es."""
    if not grados:
        return img_rgb
    hsv = np.asarray(img_rgb.convert('HSV')).astype(np.int16)
    desplazamiento = int(round(grados / 360.0 * 255))
    hsv[..., 0] = (hsv[..., 0] + desplazamiento) % 256
    return Image.fromarray(hsv.astype(np.uint8), 'HSV').convert('RGB')


def surrealista(ruta, fuerza=26.0, escala=90.0, viraje=42.0, semilla=7, salida=None,
                pasos=None, pasos_dir=None):
    """Deformación de dominio de baja frecuencia + viraje de tono — ver el docstring del
    módulo (no es una pincelada: es la imagen entera remuestreada por un campo, más un
    giro de HSV).

    `fuerza`: desplazamiento MÁXIMO, en píxeles, del campo. `escala`: tamaño en píxeles de
    cada celda de la rejilla de ruido ANTES de suavizarla a tamaño completo — mayor
    escala, formas más anchas y suaves; menor, más arrugas. `viraje`: grados de giro del
    tono (HSV). `pasos`+`pasos_dir`: fotogramas de progreso interpolando el campo y el
    viraje de 0 a su fuerza completa (0 = foto intacta, último paso = igual al PNG final)
    — para `video_composicion.py`; sin `pasos_dir` no se escribe ninguno.

    Devuelve {"salida", "fuerza", "escala", "viraje", "desplazamiento_medido" (media de
    `hypot(dx,dy)` en píxeles sobre TODO el lienzo, a fuerza completa — comprueba que el
    campo de verdad mueve algo, no promete cuánto se "ve" el derretido), "pasos"}."""
    img = _cargar_rgb(ruta)
    ancho, alto = img.size
    rnd = np.random.RandomState(int(semilla))
    dx01, dy01 = _campo_desplazamiento(ancho, alto, float(escala), rnd)
    dx, dy = dx01 * float(fuerza), dy01 * float(fuerza)
    desplazamiento_medio = float(np.hypot(dx, dy).mean())

    arr01 = _a01(img)

    def _render(t):
        derretida = _derretir(arr01, dx, dy, t)
        base = Image.fromarray(_de01(derretida), 'RGB')
        return _virar_tono(base, float(viraje) * t)

    final = _render(1.0)
    salida = salida or _nombre_salida(ruta, 'surrealista')
    final.save(salida)

    rutas_pasos = None
    if pasos and pasos_dir:
        n_pasos = max(1, int(pasos))

        def _frame(k):
            t = (k + 1) / n_pasos  # el ÚLTIMO paso (t=1.0) es igual al PNG final
            return _render(t)

        rutas_pasos = _escribir_pasos(pasos_dir, _frame, n_pasos)

    return {"salida": salida, "fuerza": float(fuerza), "escala": float(escala), "viraje": float(viraje),
            "desplazamiento_medido": round(desplazamiento_medio, 2), "pasos": rutas_pasos}


# ───────────────────────── CLI ─────────────────────────

def _valor_de(argv, i, banderas_bool=()):
    """`True` si `argv[i+1]` existe y no es otra bandera conocida — la misma guarda que
    usa `imagen.py`/`pintor.py` para no tragarse `--x --y` como si `--y` fuera el valor
    de `--x`."""
    return i + 1 < len(argv) and not (argv[i + 1].startswith('--') and argv[i + 1] not in banderas_bool)


def _cli(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 1
    verbo, resto = argv[0], list(argv[1:])

    if verbo == 'fundir':
        return _cli_fundir(resto)
    if verbo == 'doble':
        return _cli_doble(resto)
    if verbo == 'collage':
        return _cli_collage(resto)
    if verbo == 'degradado':
        return _cli_degradado(resto)
    if verbo == 'restaurar':
        return _cli_restaurar(resto)
    if verbo == 'numeros':
        return _cli_numeros(resto)
    if verbo == 'borrar':
        return _cli_borrar(resto)
    if verbo == 'cubista':
        return _cli_cubista(resto)
    if verbo == 'surrealista':
        return _cli_surrealista(resto)
    print(f'verbo desconocido: "{verbo}" (usa fundir/doble/collage/degradado/restaurar/numeros/'
          'borrar/cubista/surrealista)')
    return 1


def _parse_generico(resto, con_valor, con_bandera=()):
    """Parser común: `con_valor` es {bandera: clave} para las que llevan un valor detrás;
    `con_bandera` son banderas sueltas (True/False). Los posicionales (lo que no empieza
    por `--`) se acumulan y se devuelven aparte. Cualquier otra cosa es un error claro."""
    posicionales, opts = [], {}
    i = 0
    while i < len(resto):
        a = resto[i]
        if a in con_valor and _valor_de(resto, i):
            i += 1
            opts[con_valor[a]] = resto[i]
        elif a in con_bandera:
            opts[a[2:].replace('-', '_')] = True
        elif not a.startswith('--'):
            posicionales.append(a)
        else:
            return None, None, f'argumento no reconocido: {a}'
        i += 1
    return posicionales, opts, None


def _cli_fundir(resto):
    pos, opts, err = _parse_generico(resto, {'--modo': 'modo', '--alfa': 'alfa',
                                              '--mascara': 'mascara', '--salida': 'salida'})
    if err:
        print(err)
        return 1
    if len(pos) != 2:
        print('fundir necesita dos imágenes: <a> <b>')
        return 1
    try:
        salida = fundir(pos[0], pos[1], modo=opts.get('modo', 'mezcla'),
                         alfa=float(opts.get('alfa', 0.5)), mascara=opts.get('mascara'),
                         salida=opts.get('salida'))
    except Exception as e:
        print(f'sin lienzo: {type(e).__name__} {e}')
        return 2
    print(salida)
    return 0


def _cli_doble(resto):
    pos, opts, err = _parse_generico(resto, {'--alfa': 'alfa', '--salida': 'salida'})
    if err:
        print(err)
        return 1
    if len(pos) != 2:
        print('doble necesita dos imágenes: <a> <b>')
        return 1
    try:
        salida = doble(pos[0], pos[1], alfa=float(opts.get('alfa', 0.5)), salida=opts.get('salida'))
    except Exception as e:
        print(f'sin lienzo: {type(e).__name__} {e}')
        return 2
    print(salida)
    return 0


def _cli_collage(resto):
    pos, opts, err = _parse_generico(resto, {'--columnas': 'columnas', '--ancho': 'ancho',
                                              '--margen': 'margen', '--fondo': 'fondo', '--salida': 'salida'})
    if err:
        print(err)
        return 1
    if len(pos) < 1:
        print('collage necesita al menos una imagen')
        return 1
    try:
        salida = collage(pos, columnas=int(opts['columnas']) if 'columnas' in opts else None,
                          ancho=int(opts.get('ancho', 1920)), margen=int(opts.get('margen', 12)),
                          fondo=opts.get('fondo', '#111111'), salida=opts.get('salida'))
    except Exception as e:
        print(f'sin lienzo: {type(e).__name__} {e}')
        return 2
    print(salida)
    return 0


def _cli_degradado(resto):
    pos, opts, err = _parse_generico(resto, {'--direccion': 'direccion', '--color': 'color',
                                              '--desde': 'desde', '--salida': 'salida'})
    if err:
        print(err)
        return 1
    if len(pos) != 1:
        print('degradado necesita una imagen')
        return 1
    try:
        salida = degradado(pos[0], direccion=opts.get('direccion', 'abajo'),
                            color=opts.get('color', '#000000'), desde=float(opts.get('desde', 0.6)),
                            salida=opts.get('salida'))
    except Exception as e:
        print(f'sin lienzo: {type(e).__name__} {e}')
        return 2
    print(salida)
    return 0


def _cli_restaurar(resto):
    pos, opts, err = _parse_generico(
        resto, {'--nitidez': 'nitidez', '--color': 'color', '--salida': 'salida'}, {'--sin-aranazos'})
    if err:
        print(err)
        return 1
    if len(pos) != 1:
        print('restaurar necesita una foto')
        return 1
    try:
        r = restaurar(pos[0], salida=opts.get('salida'), sin_aranazos=bool(opts.get('sin_aranazos')),
                      nitidez=float(opts.get('nitidez', 1.0)), color=opts.get('color', 'auto'))
    except Exception as e:
        print(f'sin lienzo: {type(e).__name__} {e}')
        return 2
    print(json.dumps(r, ensure_ascii=False))
    return 0


def _cli_numeros(resto):
    pos, opts, err = _parse_generico(resto, {'--colores': 'colores', '--ancho': 'ancho',
                                              '--min-zona': 'min_zona', '--salida': 'salida'})
    if err:
        print(err)
        return 1
    if len(pos) != 1:
        print('numeros necesita una foto')
        return 1
    try:
        r = numeros(pos[0], colores=int(opts.get('colores', 12)), ancho=int(opts.get('ancho', 1400)),
                    min_zona=int(opts['min_zona']) if 'min_zona' in opts else None, salida=opts.get('salida'))
    except Exception as e:
        print(f'sin lienzo: {type(e).__name__} {e}')
        return 2
    print(json.dumps(r, ensure_ascii=False))
    return 0


def _cli_borrar(resto):
    pos, opts, err = _parse_generico(resto, {'--caja': 'caja', '--mascara': 'mascara',
                                              '--color': 'color', '--metodo': 'metodo', '--salida': 'salida'})
    if err:
        print(err)
        return 1
    if len(pos) != 1:
        print('borrar necesita una imagen')
        return 1
    if sum(k in opts for k in ('caja', 'mascara', 'color')) != 1:
        print('pasa exactamente una de --caja / --mascara / --color')
        return 1
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import rutas
        mem = None
        if opts.get('metodo', 'telea') == 'taller':
            _, mem = rutas.resolver(resto, {})
        r = borrar(pos[0], caja=opts.get('caja'), mascara=opts.get('mascara'), color=opts.get('color'),
                   metodo=opts.get('metodo', 'telea'), salida=opts.get('salida'), mem=mem)
    except Exception as e:
        print(f'sin lienzo: {type(e).__name__} {e}')
        return 2
    print(json.dumps(r, ensure_ascii=False))
    return 0


def _cli_cubista(resto):
    pos, opts, err = _parse_generico(
        resto, {'--facetas': 'facetas', '--desplazamiento': 'desplazamiento', '--giro': 'giro',
                 '--difuminado-fondo': 'difuminado_fondo', '--semilla': 'semilla',
                 '--pasos': 'pasos', '--pasos-dir': 'pasos_dir', '--salida': 'salida'},
        {'--sin-contorno'})
    if err:
        print(err)
        return 1
    if len(pos) != 1:
        print('cubista necesita una foto')
        return 1
    try:
        r = cubista(pos[0], facetas=int(opts.get('facetas', 220)),
                    desplazamiento=float(opts.get('desplazamiento', 0.07)),
                    giro=float(opts.get('giro', 7.0)), contorno=not opts.get('sin_contorno'),
                    difuminado_fondo=float(opts['difuminado_fondo']) if 'difuminado_fondo' in opts else None,
                    semilla=int(opts.get('semilla', 7)), salida=opts.get('salida'),
                    pasos=int(opts['pasos']) if 'pasos' in opts else None,
                    pasos_dir=opts.get('pasos_dir'))
    except Exception as e:
        print(f'sin lienzo: {type(e).__name__} {e}')
        return 2
    print(json.dumps(r, ensure_ascii=False))
    return 0


def _cli_surrealista(resto):
    pos, opts, err = _parse_generico(
        resto, {'--fuerza': 'fuerza', '--escala': 'escala', '--viraje': 'viraje',
                 '--semilla': 'semilla', '--pasos': 'pasos', '--pasos-dir': 'pasos_dir',
                 '--salida': 'salida'})
    if err:
        print(err)
        return 1
    if len(pos) != 1:
        print('surrealista necesita una foto')
        return 1
    try:
        r = surrealista(pos[0], fuerza=float(opts.get('fuerza', 26.0)), escala=float(opts.get('escala', 90.0)),
                         viraje=float(opts.get('viraje', 42.0)), semilla=int(opts.get('semilla', 7)),
                         salida=opts.get('salida'), pasos=int(opts['pasos']) if 'pasos' in opts else None,
                         pasos_dir=opts.get('pasos_dir'))
    except Exception as e:
        print(f'sin lienzo: {type(e).__name__} {e}')
        return 2
    print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    try:                       # la consola de Windows y la salida tienen que hablar
        from . import consola  # el mismo idioma: ver abyss/consola.py
    except ImportError:
        import consola
    consola.preparar()
    sys.exit(_cli(sys.argv[1:]))
