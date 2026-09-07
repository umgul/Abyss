# -*- coding: utf-8 -*-
"""Presenta: el vídeo de un minuto que genera el propio paquete (T5.3).

    python presenta.py [--salida abyss_1min.mp4] [--idioma es|en] [--segundos 60] [--ancho 1920]

No es un vídeo montado a mano: cada bloque es una tarjeta de título + una demostración REAL,
generada en el momento invocando la propia pieza (`varas.py --index`, `vigia.py --probar`,
`auditar.py`, `cuerpo.py`/`exterocepcion.py`, `pintor.py`/`video_pintura.py`, `mundo.py`,
`lectura_visual.py` (verbos `texto`/`fotocopia` de `ojo.py`), `render3d.py`). Nada de lo que se
ve se inventa ni se recorta de una captura vieja: si una pieza cambia, este guion se vuelve a
correr y el vídeo sale distinto — esa es la garantía.

Bloques (en este orden; T5.3, ver ESPECIFICACION_TANDA5.md):
    apertura · memoria y continuidad (`varas --index`) · honestidad (`vigia --probar`) ·
    auditoría (`auditar.py`) · sentidos (`cuerpo` + `exterocepcion`) · pintor (`video_pintura.py`) ·
    estilos (`pintor.py`, cuatro estilos) · mundo (`mundo.py` + `pintor.py`) ·
    el ojo (`lectura_visual.texto`/`fotocopiar`) · 3D (`render3d.py --png`) ·
    holograma (`render3d.py --holograma`) · cierre.

Si una pieza no está disponible en ESTA máquina (sin OpenCV, sin motor OCR, sin navegador sin
cabeza para el 3D, sin red para `mundo`, o cualquier fallo real al generarla) su bloque se
SALTA — nunca revienta el vídeo entero — y al final, en una línea (en el propio vídeo y por
stdout), se dice cuáles: "se hizo con lo que había". Con TODAS las piezas ausentes, el vídeo
sale igual: solo apertura y cierre, diciéndolo.

Presupuesto de tiempo declarado (`--segundos`, 60 por defecto): cada bloque tiene una duración
"natural" (una tabla fija, calibrada para que TODOS los bloques disponibles quepan en un minuto
sin recortar). Si la suma de las duraciones naturales de los bloques disponibles no cabe en el
tiempo pedido, se recortan los tramos MÁS LARGOS (un techo común por bisección: todo bloque que
pase de ese techo se corta A ese techo; los bloques ya cortos no se tocan) — nunca se acelera
todo por igual hasta que no se entienda, y se DICE qué bloques se recortaron y cuánto (por
stdout). Ningún bloque baja de un suelo mínimo (`PISO_BLOQUE`): con un `--segundos` muy pequeño
y muchos bloques disponibles, el vídeo puede salir algo más largo que lo pedido — límite
declarado, no un fallo silencioso.

Tipografía y paleta: las MISMAS que `infografia.py` (`PALETA`, `colores(oscuro=True)`) — un
paquete, una sola paleta. Fuente `arial.ttf`/`arialbd.ttf` con reserva a la bitmap de Pillow
(mismo criterio que `lectura_visual._fuente`; no se reimplementa esa función porque es privada
de otro módulo, pero el criterio es idéntico a propósito). Sin música: quien lo publique le pone
la suya (T5.3). Texto en el idioma pedido (`--idioma es|en`; por defecto, el de la máquina).

1920×1080 a 30 fps con `imageio_ffmpeg`, igual que `video_pintura.py` (mismos parámetros de
`libx264`: `-crf 18 -preset medium -pix_fmt yuv420p -movflags +faststart`). El bloque «pintor»
reutiliza `pintor.pintar()` + `video_pintura.video()` tal cual (pinta a una anchura pequeña por
velocidad; `video_pintura.py` redibuja los trazos — vectoriales, no un píxel ampliado — a la
anchura final) y el clip resultante se vuelve a leer con el MISMO `ffmpeg` (decodificado a
`rawvideo`) para empalmarlo en el hilo del vídeo entero: no hay una segunda pasada de
codificación con otra herramienta, es el mismo binario en los dos sentidos.

Autosuficiente a propósito (T5.1, "no sabemos a qué máquina se va a instalar"): ninguna imagen ni
escena de ejemplo vive en `pruebas/datos/` (eso es del árbol de desarrollo, puede no viajar con
el paquete instalado) — la foto de demostración, el texto para OCR, la "hoja" para fotocopia y
la escena 3D se generan aquí mismo, con Pillow y un dict, en el momento.

Proyecto de ejemplo (bloques «memoria» y «sentidos»): un directorio temporal que hace de `proj`
(mismo patrón que `pruebas/ayudas.nuevo_proyecto()`, sin importarlo — este guion no depende de
`pruebas/`), con unas pocas fichas `.md`, un `MEMORY.md` que las enlaza, transcritos sintéticos
con lecturas (`Read`) reales de esas fichas, y `UMBRAL_FRIO` sesiones archivadas para que
`varas.py --index` recalcule pesos ◆ DE VERDAD en vez de decir «sin vara todavía» — ambas
salidas son honestas (con menos corpus, este guion enseñaría igualmente el aviso real).

Nada de esto sale de la máquina salvo el bloque «mundo» (que sí llama a `mundo.buscar()`/
`descargar()`, con la misma red que usaría cualquier persona a mano) y, si hay red,
`exterocepcion.py` del bloque «sentidos» — el resto es local. `ABYSS_SIN_RED=1` (la misma
bandera que ya usan `exterocepcion.py`/`noticias.py`) corta el intento de red del bloque
«mundo» ANTES de tocarla — `mundo.py` no mira esa variable por su cuenta, así que este guion la
comprueba él mismo — y deja intacto el «sin dato» normal de `exterocepcion.py` si tampoco hay
red para ese bloque.

Nunca ejecuta el código de ningún paquete de terceros: el bloque «auditoría» corre
`auditar.auditar()` (que en sí mismo NUNCA ejecuta lo que audita, ver su propio docstring)
sobre el propio repositorio de Abyss (la carpeta que contiene `abyss/`), en modo lectura.

`varas.py` y `vigia.py` NUNCA se importan en este proceso (los dos ejecutan código de resolución
de proyecto nada más importarse, `ESPECIFICACION.md` §1 / ver `pruebas/ayudas.py`): se invocan
por `subprocess`, exactamente como los invocaría un gancho o una persona por terminal, con
`ABYSS_PROYECTO` apuntando al proyecto de ejemplo y stdin vacío (para que `rutas.leer_stdin()`
no se quede esperando). `cuerpo.py`/`exterocepcion.py` se invocan igual, por simetría y para no
depender del estado que dejan en el propio proceso (`exterocepcion._CACHE`) si este guion se
llama más de una vez. `auditar.py`, `pintor.py`, `video_pintura.py`, `render3d.py`,
`lectura_visual.py` y `mundo.py` sí son seguros de importar (ninguno toca `rutas.resolver()` ni
stdin al importarse, solo dentro de funciones que este guion no llama) y se usan como librería,
más rápido que un subproceso por cada fotograma.

`ABYSS_PRESENTA_FORZAR_AUSENTE` (solo para pruebas, mismo patrón que `ABYSS_RENDER3D_NAVEGADOR`
de `render3d.py` o `ABYSS_SIN_RED` de `exterocepcion.py`): lista de ids de bloque separados por
comas (`memoria,honestidad,auditoria,sentidos,pintor,estilos,mundo,ojo,threed,holograma`) que se
tratan como ausentes SIN intentar generarlos — para los seis bloques que son el propio paquete
(memoria/honestidad/auditoría/sentidos/pintor/estilos) no hay ninguna forma "natural" de que
falten (no dependen de red, cámara ni navegador), así que la única manera de probar de verdad
"con TODAS las piezas ausentes, el vídeo no revienta" sin fingir que falta Pillow/numpy es esta.
"""
import json
import locale
import math
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # para que "import auditar" etc. resuelvan

import imageio_ffmpeg  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import auditar  # noqa: E402
import infografia  # noqa: E402
import lectura_visual  # noqa: E402
import mundo  # noqa: E402
import pintor  # noqa: E402
import render3d  # noqa: E402
import video_pintura  # noqa: E402

CODE = os.path.dirname(os.path.abspath(__file__))
RAIZ_PAQUETE = os.path.dirname(CODE)  # carpeta que contiene abyss/, docs/, README.md...

FPS = 30
PISO_BLOQUE = 0.6  # segundos: ningún bloque disponible baja de aquí, aunque el presupuesto apriete
COLORES = infografia.colores(oscuro=True)
PALETA = infografia.PALETA

# Escena 3D de ejemplo (T5.1: nada de `pruebas/datos/` — ver docstring del módulo). Misma forma
# que acepta `render3d._cargar_escena_json()`: un pedestal con remate, en dos grupos, para que
# la vista explosionada tenga algo de verdad que separar.
ESCENA_3D_DEMO = {
    "unidades": "m",
    "piezas": [
        {"nombre": "base", "tipo": "caja", "pos": [0, 0.2, 0], "tam": [2, 0.4, 2],
         "color": "#7a6b57", "grupo": "base"},
        {"nombre": "columna", "tipo": "cilindro", "pos": [0, 1.4, 0], "tam": [0.3, 0.3, 2],
         "color": "#c9c2b3", "grupo": "columna"},
        {"nombre": "remate", "tipo": "esfera", "pos": [0, 2.8, 0], "tam": [0.5],
         "color": "#d4af37", "grupo": "remate"},
    ],
    "camara": {"pos": [5.0, 3.5, 6.0], "mirar": [0, 1.2, 0], "fov": 50},
}

# Duración "natural" de cada bloque (T5.3: calibrada para sumar, con apertura+cierre, algo por
# debajo de 60 s cuando TODAS las piezas están disponibles — el minuto de sobra es margen para
# el bloque «pintor», que es una animación real y no un rótulo estático).
DURACION_NATURAL = {
    "memoria": 4.0, "honestidad": 4.0, "auditoria": 4.5, "sentidos": 4.0,
    "pintor": 8.0, "estilos": 5.0, "mundo": 5.0, "ojo": 5.5,
    "threed": 6.0, "holograma": 4.0,
}
ORDEN_BLOQUES = ["memoria", "honestidad", "auditoria", "sentidos", "pintor", "estilos",
                 "mundo", "ojo", "threed", "holograma"]


class PiezaNoDisponible(Exception):
    """La pieza que ilustra un bloque no está en esta máquina (o se forzó su ausencia para
    pruebas, ver `ABYSS_PRESENTA_FORZAR_AUSENTE` más abajo): motivo legible, nunca una traza."""


# ───────────────────────────── idioma y textos ─────────────────────────────

def _idioma_sistema():
    """`ABYSS_IDIOMA`/`LC_ALL`/`LANG`/`LANGUAGE` si alguna empieza por "es"; si no, la
    configuración regional de Python (`locale.getlocale()`, con `getdefaultlocale()` como
    respaldo — deprecado desde 3.11 pero aún presente; nunca revienta si falta). Sin ninguna
    pista, inglés (mismo criterio que T5.2 describe para `instalar.py`, sin depender de él)."""
    for var in ("ABYSS_IDIOMA", "LC_ALL", "LANG", "LANGUAGE"):
        v = os.environ.get(var)
        if v:
            return "es" if v.lower().startswith("es") else "en"
    cod = None
    try:
        cod = locale.getlocale()[0]
    except Exception:
        cod = None
    if not cod:
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                cod = locale.getdefaultlocale()[0]
        except Exception:
            cod = None
    return "es" if (cod or "").lower().startswith("es") else "en"


TEXTOS = {
    "es": {
        "apertura_titulo": "Abyss",
        "apertura_sub": "dieciséis piezas que miden en vez de decretar",
        "memoria_titulo": "Memoria y continuidad",
        "memoria_sub": "varas.py --index · pesos ◆ recalculados sobre un proyecto de ejemplo",
        "memoria_sin_datos": "sin vara todavía (proyecto de ejemplo con poco corpus)",
        "honestidad_titulo": "Honestidad",
        "honestidad_sub": "vigia.py --probar · el vigía cazando lo que no salió de ninguna parte",
        "honestidad_sin_caza": "esta respuesta de ejemplo no llevaba nada que cazar",
        "honestidad_numeros": "números sin fuente: {n}",
        "honestidad_rutas": "rutas sin fuente: {n}",
        "honestidad_dominios": "dominios sin fuente: {n}",
        "auditoria_titulo": "Auditoría",
        "auditoria_sub": "auditar.py · las cinco comprobaciones sobre el propio paquete",
        "auditoria_veredicto": "veredicto",
        "sentidos_titulo": "Sentidos",
        "sentidos_sub": "cuerpo.py + exterocepcion.py · lo de dentro y lo de fuera, medido",
        "pintor_titulo": "Pintor",
        "pintor_sub": "video_pintura.py · una foto convirtiéndose en cuadro, acelerado",
        "estilos_titulo": "Estilos",
        "estilos_sub": "pintor.py · la misma foto en óleo, acuarela, carbón y tinta",
        "mundo_titulo": "Mundo",
        "mundo_sub": "mundo.py + pintor.py · un motivo buscado y pintado",
        "mundo_sin_red": "sin red (ABYSS_SIN_RED=1 o sin conexión): este bloque necesita red de verdad",
        "mundo_sin_candidatos": "sin candidatos para este motivo ahora mismo",
        "ojo_titulo": "El ojo",
        "ojo_sub": "ojo.py texto / fotocopia · una foto se vuelve texto, un folio se endereza",
        "ojo_sin_motor": "sin motor OCR ni OpenCV en esta máquina",
        "threed_titulo": "3D",
        "threed_sub": "render3d.py --png · una escena girando y abriéndose en vista explosionada",
        "threed_sin_navegador": "sin navegador sin cabeza (Chrome/Edge) en esta máquina",
        "holograma_titulo": "Holograma",
        "holograma_sub": "render3d.py --holograma · los cuatro cuadrantes espejados",
        "holograma_sin_navegador": "sin navegador sin cabeza (Chrome/Edge) en esta máquina",
        "cierre_titulo": "Se instala en un paso",
        "cierre_sub": "python instalar.py — y cada pieza dice ella misma qué le falta",
        "omitidos_titulo": "Se hizo con lo que había",
        "omitidos_ninguno": "en esta máquina no había ninguna pieza disponible para enseñar",
        "recorte_log": "recorte de presupuesto (--segundos {seg}): \"{titulo}\" de {antes:.1f}s a {despues:.1f}s",
        "salta_log": "se salta \"{titulo}\": {motivo}",
    },
    "en": {
        "apertura_titulo": "Abyss",
        "apertura_sub": "sixteen pieces that measure instead of decree",
        "memoria_titulo": "Memory and continuity",
        "memoria_sub": "varas.py --index · ◆ weights recalculated over a sample project",
        "memoria_sin_datos": "no measure yet (sample project with too little history)",
        "honestidad_titulo": "Honesty",
        "honestidad_sub": "vigia.py --probar · the watcher catching what came from nowhere",
        "honestidad_sin_caza": "this sample response had nothing to catch",
        "honestidad_numeros": "numbers with no source: {n}",
        "honestidad_rutas": "paths with no source: {n}",
        "honestidad_dominios": "domains with no source: {n}",
        "auditoria_titulo": "Audit",
        "auditoria_sub": "auditar.py · the five checks, run on the package itself",
        "auditoria_veredicto": "verdict",
        "sentidos_titulo": "Senses",
        "sentidos_sub": "cuerpo.py + exterocepcion.py · the inside and the outside, measured",
        "pintor_titulo": "Painter",
        "pintor_sub": "video_pintura.py · a photo becoming a painting, sped up",
        "estilos_titulo": "Styles",
        "estilos_sub": "pintor.py · the same photo in oil, watercolor, charcoal and ink",
        "mundo_titulo": "World",
        "mundo_sub": "mundo.py + pintor.py · a subject searched for, and painted",
        "mundo_sin_red": "no network (ABYSS_SIN_RED=1 or offline): this block needs a real connection",
        "mundo_sin_candidatos": "no candidates for this subject right now",
        "ojo_titulo": "The eye",
        "ojo_sub": "ojo.py text / photocopy · a photo becomes text, a page gets straightened",
        "ojo_sin_motor": "no OCR engine and no OpenCV on this machine",
        "threed_titulo": "3D",
        "threed_sub": "render3d.py --png · a scene turning and opening into an exploded view",
        "threed_sin_navegador": "no headless browser (Chrome/Edge) on this machine",
        "holograma_titulo": "Hologram",
        "holograma_sub": "render3d.py --holograma · the four mirrored quadrants",
        "holograma_sin_navegador": "no headless browser (Chrome/Edge) on this machine",
        "cierre_titulo": "It installs in one step",
        "cierre_sub": "python instalar.py — and every piece says for itself what it's missing",
        "omitidos_titulo": "Made with what was here",
        "omitidos_ninguno": "this machine had no piece available to show",
        "recorte_log": 'budget trim (--segundos {seg}): "{titulo}" from {antes:.1f}s to {despues:.1f}s',
        "salta_log": 'skipping "{titulo}": {motivo}',
    },
}


# ───────────────────────────── tipografía y lienzo ─────────────────────────────

def _fuente(tam, negrita=False):
    """`arial.ttf`/`arialbd.ttf` si están (Windows los trae de serie); si no, la bitmap por
    defecto de Pillow. Mismo criterio que `lectura_visual._fuente` (privada de ese módulo, no
    se importa de ahí): es la aproximación más cercana a la pila `system-ui, ..., Segoe UI,
    Roboto, sans-serif` de `infografia.py` que la biblioteca estándar más Pillow permiten sin
    una fuente empaquetada aparte."""
    for nombre in (("arialbd.ttf", "Arial Bold.ttf") if negrita else ("arial.ttf", "Arial.ttf")):
        try:
            return ImageFont.truetype(nombre, tam)
        except Exception:
            continue
    return ImageFont.load_default()


def _fuente_mono(tam):
    for nombre in ("consola.ttf", "Consolas.ttf", "cour.ttf", "Courier New.ttf"):
        try:
            return ImageFont.truetype(nombre, tam)
        except Exception:
            continue
    return ImageFont.load_default()


def _lienzo(ancho, alto):
    return Image.new("RGB", (ancho, alto), COLORES["fondo"])


_SIMBOLOS_SIN_COBERTURA = set("★◆")  # varas.py: ni arial.ttf ni consola.ttf/cour.ttf los traen


def _fuente_simbolos(tam):
    try:
        return ImageFont.truetype("seguisym.ttf", tam)  # Segoe UI Symbol: sí los trae
    except Exception:
        return None


def _dibujar_texto(d, xy, texto, fuente, fill):
    """Como `d.text()`, pero los símbolos propios de la vara del paquete (★/◆, ver
    `varas.py`) que la fuente principal no trae (salen como un cuadro vacío: medido más
    arriba con `arial.ttf`/`consola.ttf`) se dibujan con `seguisym.ttf` en su lugar —
    mismo tamaño, el resto del texto no cambia de fuente."""
    x, y = xy
    if not any(ch in _SIMBOLOS_SIN_COBERTURA for ch in texto):
        d.text((x, y), texto, font=fuente, fill=fill)
        return
    f_simb = _fuente_simbolos(fuente.size)
    if f_simb is None:
        d.text((x, y), texto, font=fuente, fill=fill)
        return
    actual = ""
    for ch in texto:
        if ch in _SIMBOLOS_SIN_COBERTURA:
            if actual:
                d.text((x, y), actual, font=fuente, fill=fill)
                x += _ancho_texto(d, actual, fuente)
                actual = ""
            d.text((x, y), ch, font=f_simb, fill=fill)
            x += _ancho_texto(d, ch, f_simb)
        else:
            actual += ch
    if actual:
        d.text((x, y), actual, font=fuente, fill=fill)


def _ancho_texto(d, texto, fuente):
    try:
        return d.textlength(texto, font=fuente)
    except Exception:
        return len(texto) * fuente.size * 0.55


def _envolver(d, texto, fuente, max_ancho):
    palabras = texto.split()
    if not palabras:
        return [""]
    lineas, actual = [], ""
    for p in palabras:
        candidato = (actual + " " + p).strip()
        if not actual or _ancho_texto(d, candidato, fuente) <= max_ancho:
            actual = candidato
        else:
            lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    return lineas


def _texto_centrado(d, texto, ancho, y, fuente, color, max_ancho=None):
    max_ancho = max_ancho if max_ancho is not None else ancho * 0.86
    lineas = _envolver(d, texto, fuente, max_ancho)
    alto_linea = fuente.size * 1.3
    y0 = y - (len(lineas) - 1) * alto_linea / 2
    for i, ln in enumerate(lineas):
        w = _ancho_texto(d, ln, fuente)
        _dibujar_texto(d, ((ancho - w) / 2, y0 + i * alto_linea), ln, fuente, color)
    return len(lineas) * alto_linea


def _encajar(im, w, h):
    """Reencaja `im` a exactamente `(w, h)` recortando el sobrante tras escalar "a cubrir"
    (sin bandas ni deformar), para tejas de mosaico limpias sin depender de que la foto de
    origen tenga la proporción exacta del hueco."""
    w, h = max(1, int(w)), max(1, int(h))
    escala = max(w / im.width, h / im.height)
    nw, nh = max(1, round(im.width * escala)), max(1, round(im.height * escala))
    im2 = im.resize((nw, nh), Image.LANCZOS)
    x0, y0 = (nw - w) // 2, (nh - h) // 2
    return im2.crop((x0, y0, x0 + w, y0 + h))


def _repetir(imagen, duracion, fps=FPS):
    n = max(1, round(duracion * fps))
    return [imagen] * n


def _repartir(imagenes, duracion, fps=FPS):
    """Reparte `duracion` entre varias imágenes DISTINTAS (p. ej. los fotogramas del bloque
    3D): cada una se sostiene un número de fotogramas casi igual, el resto (por redondeo) se
    lo lleva la última."""
    if not imagenes:
        return []
    n = max(len(imagenes), round(duracion * fps))
    base, resto = divmod(n, len(imagenes))
    out = []
    for i, im in enumerate(imagenes):
        cuenta = base + (1 if i >= len(imagenes) - resto else 0)
        out += [im] * max(1, cuenta)
    return out


def _hex_a_ffmpeg(hexcolor):
    return "0x" + hexcolor.lstrip("#")


# ───────────────────────────── tarjetas y bloques de texto ─────────────────────────────

def _tarjeta(titulo, subtitulo, ancho, alto, indice=0, pie=None):
    img = _lienzo(ancho, alto)
    d = ImageDraw.Draw(img)
    acento = PALETA[indice % len(PALETA)]
    d.rectangle([0, 0, max(6, round(ancho * 0.006)), alto], fill=acento)
    f_tit = _fuente(round(alto * 0.075), negrita=True)
    f_sub = _fuente(round(alto * 0.032))
    _texto_centrado(d, titulo, ancho, alto * 0.44, f_tit, COLORES["texto"])
    if subtitulo:
        _texto_centrado(d, subtitulo, ancho, alto * 0.44 + alto * 0.09, f_sub, COLORES["atenuado"])
    if pie:
        f_pie = _fuente(round(alto * 0.022))
        _dibujar_texto(d, (ancho * 0.04, alto * 0.93), pie, f_pie, COLORES["atenuado"])
    return img


def _frame_bloque(titulo, subtitulo, lineas_reales, ancho, alto, indice, mono=True):
    """Un fotograma «de terminal»: título + subtítulo + la salida REAL (ya en texto) de la
    pieza que ilustra este bloque, recortada a lo que quepa sin solaparse."""
    img = _lienzo(ancho, alto)
    d = ImageDraw.Draw(img)
    acento = PALETA[indice % len(PALETA)]
    d.rectangle([0, 0, max(6, round(ancho * 0.006)), alto], fill=acento)
    x0 = ancho * 0.07
    f_tit = _fuente(round(alto * 0.05), negrita=True)
    _dibujar_texto(d, (x0, alto * 0.10), titulo, f_tit, COLORES["texto"])
    y = alto * 0.10 + f_tit.size * 1.5
    if subtitulo:
        f_sub = _fuente(round(alto * 0.024))
        for ln in _envolver(d, subtitulo, f_sub, ancho * 0.86):
            _dibujar_texto(d, (x0, y), ln, f_sub, COLORES["atenuado"])
            y += f_sub.size * 1.35
    y += alto * 0.035
    d.line([(x0, y), (ancho - x0, y)], fill=COLORES["rejilla"], width=2)
    y += alto * 0.03
    f_cont = _fuente_mono(round(alto * 0.024)) if mono else _fuente(round(alto * 0.026))
    max_y = alto * 0.90
    for ln in lineas_reales:
        for envuelta in _envolver(d, str(ln), f_cont, ancho * 0.86):
            if y > max_y:
                break
            _dibujar_texto(d, (x0, y), envuelta, f_cont, COLORES["texto"])
            y += f_cont.size * 1.4
        if y > max_y:
            break
    return img


def _cabecera_mosaico(titulo, ancho, alto, indice):
    """Para los bloques de mosaico (estilos/mundo/ojo): lienzo con una franja de cabecera YA
    reservada (acento + título) y el alto de esa franja, para que el contenido se pegue POR
    DEBAJO — nunca al revés, que taparía justo lo que se quiere enseñar (medido: pegar la
    cabecera al final tapaba las etiquetas del mosaico de arriba)."""
    img = _lienzo(ancho, alto)
    d = ImageDraw.Draw(img)
    acento = PALETA[indice % len(PALETA)]
    alto_cabecera = round(alto * 0.10)
    d.rectangle([0, 0, ancho, alto_cabecera], fill=(0, 0, 0))
    d.rectangle([0, 0, max(6, round(ancho * 0.006)), alto], fill=acento)
    f_tit = _fuente(round(alto * 0.036), negrita=True)
    _dibujar_texto(d, (ancho * 0.03, alto_cabecera * 0.28), titulo, f_tit, "#ffffff")
    return img, d, alto_cabecera


def _frame_omitidos(ausentes, T, ancho, alto):
    img = _lienzo(ancho, alto)
    d = ImageDraw.Draw(img)
    f_tit = _fuente(round(alto * 0.045), negrita=True)
    _dibujar_texto(d, (ancho * 0.07, alto * 0.30), T["omitidos_titulo"], f_tit, COLORES["texto"])
    y = alto * 0.30 + f_tit.size * 1.6
    f_ln = _fuente(round(alto * 0.026))
    if not ausentes:
        _dibujar_texto(d, (ancho * 0.07, y), T["omitidos_ninguno"], f_ln, COLORES["atenuado"])
    else:
        for r in ausentes:
            for envuelta in _envolver(d, f"· {r['titulo']}: {r['motivo']}", f_ln, ancho * 0.86):
                _dibujar_texto(d, (ancho * 0.07, y), envuelta, f_ln, COLORES["atenuado"])
                y += f_ln.size * 1.35
    return img


# ───────────────────────────── vídeo: escritura y (para «pintor») lectura ─────────────────────────────

class _EscritorVideo:
    """Un único proceso `ffmpeg` para todo el vídeo (mismos parámetros que `video_pintura.py`):
    cada bloque escribe sus fotogramas ya listos, en el orden en que deben salir."""

    def __init__(self, ruta_salida, ancho, alto, fps=FPS):
        try:
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as e:
            raise RuntimeError(f"falta imageio_ffmpeg (pip install imageio-ffmpeg): {e}")
        self.ancho, self.alto, self.fps = ancho, alto, fps
        self.frames = 0
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{ancho}x{alto}", "-r", str(fps), "-i", "-", "-c:v", "libx264",
               "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", "-movflags", "+faststart",
               os.path.abspath(ruta_salida)]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def escribir(self, imagen):
        if imagen.size != (self.ancho, self.alto):
            imagen = _encajar(imagen.convert("RGB"), self.ancho, self.alto)
        elif imagen.mode != "RGB":
            imagen = imagen.convert("RGB")
        self.proc.stdin.write(imagen.tobytes())
        self.frames += 1

    def escribir_todas(self, imagenes):
        for im in imagenes:
            self.escribir(im)

    def cerrar(self):
        self.proc.stdin.close()
        self.proc.wait()
        if self.proc.returncode != 0:
            raise RuntimeError(f"ffmpeg devolvió {self.proc.returncode}")


def _decodificar_mp4(ruta, ancho, alto, avisar=print):
    """Vuelve a leer un `.mp4` YA escrito (por `video_pintura.video()`) como fotogramas RGB
    de exactamente `ancho`×`alto`, con el MISMO `ffmpeg` que lo codificó — reencaja "a cubrir"
    con relleno del color de fondo si la proporción de origen no es 16:9 exacta, en vez de
    deformar la imagen."""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    color = _hex_a_ffmpeg(COLORES["fondo"])
    vf = (f"scale={ancho}:{alto}:force_original_aspect_ratio=decrease,"
          f"pad={ancho}:{alto}:(ow-iw)/2:(oh-ih)/2:color={color}")
    cmd = [ffmpeg, "-loglevel", "error", "-i", os.path.abspath(ruta), "-vf", vf,
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    datos = r.stdout
    tam = ancho * alto * 3
    if len(datos) < tam:
        raise RuntimeError(f"ffmpeg no devolvió ningún fotograma decodificando {ruta}")
    return [Image.frombytes("RGB", (ancho, alto), datos[i:i + tam])
            for i in range(0, len(datos) - tam + 1, tam)]


# ───────────────────────────── proyecto de ejemplo (memoria/sentidos/honestidad) ─────────────────────────────

def _construir_proyecto_ejemplo(tmp):
    """Un `proj` sintético completo (ver docstring del módulo): fichas + `MEMORY.md` +
    transcritos vivos con lecturas reales + `UMBRAL_FRIO` sesiones archivadas, para que
    `varas.py --index` recalcule ◆ de verdad. Nada de esto sale del directorio temporal."""
    proyecto = os.path.join(tmp, "proyecto_ejemplo")
    mem = os.path.join(proyecto, "memory")
    sesiones = os.path.join(mem, "sesiones")
    os.makedirs(sesiones, exist_ok=True)

    fichas = {
        "la_vara.md": "# La vara\n\nMide antes de decretar: esta ficha es la más citada del "
                      "proyecto de ejemplo.\n",
        "el_andamiaje.md": "# El andamiaje\n\nDe dónde sale cada dato. [[la_vara]] la sostiene.\n",
        "la_confeccion.md": "# La confección\n\nNotas sueltas que nadie más cita ni lee todavía, "
                             "para que el índice también enseñe lo que no pesa.\n",
    }
    for nombre, cuerpo in fichas.items():
        with open(os.path.join(mem, nombre), "w", encoding="utf-8") as fh:
            fh.write(cuerpo)
    with open(os.path.join(mem, "MEMORY.md"), "w", encoding="utf-8") as fh:
        fh.write("# Memoria de ejemplo\n\n"
                  "- [La vara](la_vara.md)\n- [El andamiaje](el_andamiaje.md)\n"
                  "- [La confección](la_confeccion.md)\n")

    for i in range(8):  # propiocepcion.UMBRAL_FRIO
        ruta = os.path.join(sesiones, f"sesion_{i:02d}.jsonl")
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "user", "message": {"content": f"turno de ejemplo {i}"},
                                  "timestamp": f"2026-08-{(i % 28) + 1:02d}T10:00:00Z"},
                                 ensure_ascii=False) + "\n")

    def _linea_read(ruta_ficha, ts):
        # Substrings LITERALES que `varas.py` busca: `'memory'` y `'"name":"Read"'` (sin
        # espacio, ver su docstring) — de ahí `separators=(',', ':')` aquí.
        d = {"type": "assistant", "timestamp": ts,
             "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": ruta_ficha}}]}}
        return json.dumps(d, ensure_ascii=False, separators=(",", ":"))

    with open(os.path.join(proyecto, "sesion_viva_0.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "user", "message": {"content": "hola"},
                              "timestamp": "2026-09-07T09:00:00Z"}, ensure_ascii=False) + "\n")
        fh.write(_linea_read(os.path.join(mem, "la_vara.md"), "2026-09-07T09:00:05Z") + "\n")
    with open(os.path.join(proyecto, "sesion_viva_1.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(_linea_read(os.path.join(mem, "el_andamiaje.md"), "2026-09-07T09:05:00Z") + "\n")

    return proyecto


def _transcript_honestidad(tmp):
    """Un transcrito sintético con una respuesta final que inventa un número que no sale de
    ninguna parte (ni del usuario, ni de ninguna herramienta) — lo que `vigia.py --probar`
    debe cazar como «número sin fuente»."""
    ruta = os.path.join(tmp, "vigia_demo.jsonl")
    lineas = [
        {"type": "user", "message": {"content": "¿cuánta gente probó la vara esta semana?"},
         "timestamp": "2026-09-07T09:00:00Z"},
        {"type": "assistant",
         "message": {"content": [{"type": "text",
                                   "text": "La probó el 73% de quienes abrieron el proyecto esta semana."}]},
         "timestamp": "2026-09-07T09:00:04Z"},
    ]
    with open(ruta, "w", encoding="utf-8") as fh:
        for d in lineas:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    return ruta


def _ejecutar_pieza(nombre_script, args, proyecto, avisar=print, timeout=30):
    """`subprocess.run([python, abyss/<nombre_script>] + args)` con `ABYSS_PROYECTO=proyecto`
    y stdin vacío — ver docstring del módulo (nunca se importan `varas.py`/`vigia.py` en este
    proceso)."""
    ruta = os.path.join(CODE, nombre_script)
    env = dict(os.environ)
    env["ABYSS_PROYECTO"] = proyecto
    try:
        return subprocess.run([sys.executable, ruta] + list(args), input="", capture_output=True,
                               text=True, encoding="utf-8", errors="replace", env=env, timeout=timeout)
    except Exception as e:
        raise PiezaNoDisponible(f"{nombre_script}: {type(e).__name__} {e}")


# ───────────────────────────── fotos y escenas sintéticas ─────────────────────────────

def _foto_demo(ruta, ancho=320, alto=180):
    """Paisaje geométrico sencillo con Pillow (degradado de cielo + un sol + dos montañas):
    algo con bordes y contraste para que `pintor.py` tenga contornos que seguir. No es una
    foto real del mundo — para eso está el bloque «mundo» aparte."""
    img = Image.new("RGB", (ancho, alto))
    px = img.load()
    for y in range(alto):
        t = y / max(1, alto - 1)
        fila = (int(40 + 110 * (1 - t)), int(65 + 95 * (1 - t)), int(95 + 130 * t))
        for x in range(ancho):
            px[x, y] = fila
    d = ImageDraw.Draw(img)
    r = alto * 0.14
    d.ellipse([ancho * 0.66 - r, alto * 0.14 - r, ancho * 0.66 + r, alto * 0.14 + r], fill=(250, 210, 110))
    d.polygon([(0, alto * 0.64), (ancho * 0.32, alto * 0.40), (ancho * 0.58, alto * 0.64)], fill=(66, 88, 68))
    d.polygon([(ancho * 0.40, alto * 0.64), (ancho * 0.76, alto * 0.34), (ancho, alto * 0.64)], fill=(52, 70, 56))
    d.rectangle([0, alto * 0.64, ancho, alto], fill=(34, 44, 40))
    img.save(ruta)
    return ruta


def _foto_texto_demo(ruta, ancho=800, alto=360):
    img = Image.new("RGB", (ancho, alto), (250, 248, 240))
    d = ImageDraw.Draw(img)
    f = _fuente(round(alto * 0.16), negrita=True)
    lineas = ["ABYSS", "mide, no decreta"]
    y = alto * 0.24
    for ln in lineas:
        w = _ancho_texto(d, ln, f)
        d.text(((ancho - w) / 2, y), ln, font=f, fill=(25, 25, 25))
        y += f.size * 1.35
    img.save(ruta)
    return ruta


def _foto_papel_demo(ruta, ancho=700, alto=900):
    """Una "hoja" clara, ligeramente rotada, sobre un fondo oscuro: contorno suficiente para
    que `lectura_visual._enderezar_documento()` encuentre algo real que enderezar."""
    fondo = Image.new("RGB", (ancho, alto), (28, 26, 24))
    hoja = Image.new("RGB", (int(ancho * 0.72), int(alto * 0.80)), (244, 243, 236))
    d = ImageDraw.Draw(hoja)
    f = _fuente(round(alto * 0.028))
    y = 30
    for i in range(9):
        d.text((28, y), f"línea {i + 1} del documento de ejemplo", font=f, fill=(35, 35, 35))
        y += f.size * 1.6
    hoja = hoja.rotate(3, expand=True, fillcolor=(28, 26, 24))
    fondo.paste(hoja, ((ancho - hoja.width) // 2, (alto - hoja.height) // 2))
    fondo.save(ruta)
    return ruta


# ───────────────────────────── un generador por bloque ─────────────────────────────
# Cada `_bloque_*(ctx)` devuelve una lista de fotogramas PIL (ya `ancho`×`alto`) que ocupa
# aproximadamente `ctx['duracion']` segundos, o lanza `PiezaNoDisponible`/cualquier excepción
# (el llamador trata ambas igual: el bloque se salta, nunca revienta el vídeo).

def _bloque_memoria(ctx):
    r = _ejecutar_pieza("varas.py", ["--index"], ctx["proyecto"], avisar=ctx["avisar"])
    salida = (r.stdout or "").strip()
    if r.returncode != 0:
        raise PiezaNoDisponible(f"varas.py --index: {salida or (r.stderr or '').strip()}")
    idx = os.path.join(ctx["proyecto"], "memory", "MEMORY.md")
    lineas_glifo = []
    try:
        with open(idx, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if "◆" in ln and not ln.startswith("> Varas"):  # esa es la leyenda, no un peso
                    lineas_glifo.append(ln)
    except OSError:
        pass
    cabecera = salida.splitlines()[-1] if salida else ""
    cuerpo = lineas_glifo or [ctx["T"]["memoria_sin_datos"]]
    frame = _frame_bloque(ctx["T"]["memoria_titulo"], f"{ctx['T']['memoria_sub']} — {cabecera}",
                           cuerpo, ctx["ancho"], ctx["alto"], indice=0)
    return _repetir(frame, ctx["duracion"])


def _bloque_honestidad(ctx):
    r = _ejecutar_pieza("vigia.py", ["--probar", ctx["transcript_honestidad"]], ctx["proyecto"],
                         avisar=ctx["avisar"])
    if r.returncode != 0:
        raise PiezaNoDisponible(f"vigia.py --probar: {(r.stdout or r.stderr or '').strip()}")
    # `vigia.py --probar` imprime el dict de `cazar()` con `indent=1` (varias líneas) y
    # DESPUÉS una línea "--- respuesta analizada (inicio): ..." — el JSON es todo lo que
    # viene antes de esa marca, no solo la primera línea.
    salida = (r.stdout or "")
    bloque_json = salida.split("\n--- respuesta analizada")[0].strip()
    cz = {}
    if bloque_json:
        try:
            cz = json.loads(bloque_json)
        except Exception:
            cz = {}
    T = ctx["T"]
    resumen = []
    if cz.get("numeros"):
        resumen.append(T["honestidad_numeros"].format(n=", ".join(cz["numeros"])))
    if cz.get("rutas"):
        resumen.append(T["honestidad_rutas"].format(n=", ".join(cz["rutas"])))
    if cz.get("dominios"):
        resumen.append(T["honestidad_dominios"].format(n=", ".join(cz["dominios"])))
    if not resumen:
        resumen = [T["honestidad_sin_caza"]]
    frame = _frame_bloque(T["honestidad_titulo"], T["honestidad_sub"], resumen,
                           ctx["ancho"], ctx["alto"], indice=1)
    return _repetir(frame, ctx["duracion"])


def _bloque_auditoria(ctx):
    r = auditar.auditar(ctx["paquete"])
    nombre_paquete = os.path.basename(os.path.normpath(ctx["paquete"])) or ctx["paquete"]
    lineas = auditar.a_texto(r).splitlines()
    if lineas:  # a_texto()[0] es "auditoría de <ruta ABSOLUTA>": un vídeo pensado para compartir
        lineas[0] = f"auditoría de {nombre_paquete}/"  # no debería enseñar la ruta del disco de quien lo generó
    T = ctx["T"]
    frame = _frame_bloque(T["auditoria_titulo"], f"{T['auditoria_sub']} ({nombre_paquete})",
                           lineas[:9], ctx["ancho"], ctx["alto"], indice=2)
    return _repetir(frame, ctx["duracion"])


def _bloque_sentidos(ctx):
    r1 = _ejecutar_pieza("cuerpo.py", [], ctx["proyecto"], avisar=ctx["avisar"])
    r2 = _ejecutar_pieza("exterocepcion.py", [], ctx["proyecto"], avisar=ctx["avisar"])
    lineas = []
    if r1.returncode == 0 and (r1.stdout or "").strip():
        lineas.append(r1.stdout.strip().splitlines()[-1])
    if r2.returncode == 0 and (r2.stdout or "").strip():
        lineas.append(r2.stdout.strip().splitlines()[-1])
    if not lineas:
        raise PiezaNoDisponible("cuerpo.py/exterocepcion.py sin salida")
    T = ctx["T"]
    frame = _frame_bloque(T["sentidos_titulo"], T["sentidos_sub"], lineas,
                           ctx["ancho"], ctx["alto"], indice=3)
    return _repetir(frame, ctx["duracion"])


def _bloque_pintor(ctx):
    foto = ctx["foto_demo"]
    salida_dir = os.path.join(ctx["tmp"], "pintor_demo")
    res = pintor.pintar(foto, salida=salida_dir, ancho=240, estilo="oleo", nombre="demo",
                         avisar=lambda *a, **k: None)
    clip = os.path.join(ctx["tmp"], "pintor_demo_clip.mp4")
    dur = max(1.5, ctx["duracion"])
    video_pintura.video(res["trazos"], clip, segundos=max(0.5, dur - 0.4), ancho=ctx["ancho"],
                         fps=FPS, hold_ini=0.15, hold_fin=0.25, avisar=lambda *a, **k: None)
    frames = _decodificar_mp4(clip, ctx["ancho"], ctx["alto"], avisar=ctx["avisar"])
    T = ctx["T"]
    encabezado = _frame_bloque(T["pintor_titulo"], T["pintor_sub"], [], ctx["ancho"], ctx["alto"], indice=4)
    return _repetir(encabezado, 0.8) + frames


def _bloque_estilos(ctx):
    foto = ctx["foto_demo"]
    estilos = ["oleo", "acuarela", "carbon", "tinta"]
    T = ctx["T"]
    lienzo, d, y0 = _cabecera_mosaico(T["estilos_titulo"], ctx["ancho"], ctx["alto"], indice=5)
    alto_disp = ctx["alto"] - y0
    mitad_ancho, mitad_alto = ctx["ancho"] // 2, alto_disp // 2
    f_etq = _fuente(round(ctx["alto"] * 0.022), negrita=True)
    for i, estilo in enumerate(estilos):
        salida_dir = os.path.join(ctx["tmp"], f"estilo_{estilo}")
        res = pintor.pintar(foto, salida=salida_dir, ancho=280, estilo=estilo, nombre="demo",
                             avisar=lambda *a, **k: None)
        tile = _encajar(Image.open(res["png"]).convert("RGB"), mitad_ancho, mitad_alto)
        x, y = (i % 2) * mitad_ancho, y0 + (i // 2) * mitad_alto
        lienzo.paste(tile, (x, y))
        d.rectangle([x + 10, y + 10, x + 10 + _ancho_texto(d, estilo, f_etq) + 16, y + 10 + f_etq.size + 10],
                    fill=(0, 0, 0))
        _dibujar_texto(d, (x + 18, y + 15), estilo, f_etq, "#ffffff")
    d.line([(mitad_ancho, y0), (mitad_ancho, ctx["alto"])], fill=COLORES["fondo"], width=4)
    d.line([(0, y0 + mitad_alto), (ctx["ancho"], y0 + mitad_alto)], fill=COLORES["fondo"], width=4)
    return _repetir(lienzo, ctx["duracion"])


def _bloque_mundo(ctx):
    T = ctx["T"]
    if os.environ.get("ABYSS_SIN_RED") == "1":
        raise PiezaNoDisponible(T["mundo_sin_red"])
    motivo = "torre eiffel"
    candidatos = mundo.buscar(motivo, fuentes=None, n=3, avisar=lambda *a, **k: None)
    if not candidatos:
        raise PiezaNoDisponible(T["mundo_sin_candidatos"])
    directorio = os.path.join(ctx["tmp"], "mundo_demo")
    ruta_img, _ruta_txt = mundo.descargar(candidatos[0], directorio)
    res = pintor.pintar(ruta_img, salida=directorio, ancho=300, estilo="impresionista",
                         nombre="mundo", avisar=lambda *a, **k: None)
    titulo = f"{T['mundo_titulo']} — {candidatos[0].get('titulo') or motivo}"
    lienzo, d, y0 = _cabecera_mosaico(titulo, ctx["ancho"], ctx["alto"], indice=6)
    alto_disp = ctx["alto"] - y0
    mitad = ctx["ancho"] // 2
    original = _encajar(Image.open(ruta_img).convert("RGB"), mitad, alto_disp)
    pintado = _encajar(Image.open(res["png"]).convert("RGB"), ctx["ancho"] - mitad, alto_disp)
    lienzo.paste(original, (0, y0))
    lienzo.paste(pintado, (mitad, y0))
    return _repetir(lienzo, ctx["duracion"])


def _bloque_ojo(ctx):
    T = ctx["T"]
    lienzo, d, y0 = _cabecera_mosaico(T["ojo_titulo"], ctx["ancho"], ctx["alto"], indice=7)
    alto_disp = ctx["alto"] - y0
    mitad = ctx["ancho"] // 2
    hubo_algo = False

    foto_texto = os.path.join(ctx["tmp"], "ojo_texto.png")
    _foto_texto_demo(foto_texto)
    try:
        texto_leido = lectura_visual.texto(foto_texto, avisar=lambda *a, **k: None)
    except Exception:
        texto_leido = None
    if texto_leido:
        hubo_algo = True
        miniatura = _encajar(Image.open(foto_texto).convert("RGB"), mitad, alto_disp // 2)
        lienzo.paste(miniatura, (0, y0))
        f = _fuente_mono(round(ctx["alto"] * 0.026))
        y = y0 + alto_disp // 2 + 12
        for ln in texto_leido.splitlines()[:6]:
            _dibujar_texto(d, (16, y), ln[:60], f, COLORES["texto"])
            y += f.size * 1.4

    if getattr(lectura_visual, "_CV2_OK", False):
        try:
            foto_papel = os.path.join(ctx["tmp"], "ojo_papel.png")
            _foto_papel_demo(foto_papel)
            arr, _recortado = lectura_visual.fotocopiar(foto_papel, modo="color", avisar=lambda *a, **k: None)
            cv2 = lectura_visual.cv2
            imagen_np = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB) if arr.ndim == 3 else arr
            modo_pil = "RGB" if arr.ndim == 3 else "L"
            pil = Image.fromarray(imagen_np, mode=modo_pil).convert("RGB")
            tile = _encajar(pil, ctx["ancho"] - mitad, alto_disp)
            lienzo.paste(tile, (mitad, y0))
            hubo_algo = True
        except Exception:
            pass

    if not hubo_algo:
        raise PiezaNoDisponible(T["ojo_sin_motor"])
    return _repetir(lienzo, ctx["duracion"])


def _bloque_threed(ctx):
    T = ctx["T"]
    if not render3d._buscar_navegador():
        raise PiezaNoDisponible(T["threed_sin_navegador"])
    escena = ctx["escena_3d"]
    n = max(3, min(8, round(ctx["duracion"])))
    primero = render3d.renderizar(escena, html=os.path.join(ctx["tmp"], "r3d_0.html"),
                                   png=os.path.join(ctx["tmp"], "r3d_0.png"), ancho=ctx["ancho"],
                                   alto=ctx["alto"], explosion=0.0, avisar=lambda *a, **k: None)
    centro, radio = primero["centro"], max(0.25, primero["radio"])
    frames = [Image.open(primero["png"]).convert("RGB")]
    for i in range(1, n):
        angulo = 2 * math.pi * i / n
        dist = radio * 2.2
        cam = [centro[0] + dist * math.cos(angulo), centro[1] + radio * 1.3, centro[2] + dist * math.sin(angulo)]
        explosion = 1.3 * i / (n - 1)
        res = render3d.renderizar(escena, html=os.path.join(ctx["tmp"], f"r3d_{i}.html"),
                                   png=os.path.join(ctx["tmp"], f"r3d_{i}.png"), ancho=ctx["ancho"],
                                   alto=ctx["alto"], camara=cam, mirar=centro, explosion=explosion,
                                   avisar=lambda *a, **k: None)
        frames.append(Image.open(res["png"]).convert("RGB"))
    return _repartir(frames, ctx["duracion"])


def _bloque_holograma(ctx):
    T = ctx["T"]
    if not render3d._buscar_navegador():
        raise PiezaNoDisponible(T["holograma_sin_navegador"])
    res = render3d.renderizar(ctx["escena_3d"], html=os.path.join(ctx["tmp"], "holo.html"),
                               png=os.path.join(ctx["tmp"], "holo.png"), ancho=ctx["ancho"],
                               alto=ctx["alto"], holograma=True, avisar=lambda *a, **k: None)
    im = Image.open(res["png"]).convert("RGB")
    return _repetir(im, ctx["duracion"])


GENERADORES = {
    "memoria": _bloque_memoria, "honestidad": _bloque_honestidad, "auditoria": _bloque_auditoria,
    "sentidos": _bloque_sentidos, "pintor": _bloque_pintor, "estilos": _bloque_estilos,
    "mundo": _bloque_mundo, "ojo": _bloque_ojo, "threed": _bloque_threed, "holograma": _bloque_holograma,
}


# ───────────────────────────── presupuesto de tiempo ─────────────────────────────

def _techo_por_bisección(valores, objetivo):
    """El techo `C` tal que `sum(min(v, C) for v in valores) ≈ objetivo` (bisección, 40
    pasos: de sobra para segundos con dos decimales). Es la forma exacta de "recortar los
    tramos más largos": cualquier valor por encima de `C` se corta A `C`; los que ya estaban
    por debajo no se tocan."""
    if not valores:
        return 0.0
    lo, hi = 0.0, max(valores)
    for _ in range(40):
        mid = (lo + hi) / 2
        if sum(min(v, mid) for v in valores) > objetivo:
            hi = mid
        else:
            lo = mid
    return hi


def _ajustar_presupuesto(ids_disponibles, objetivo, piso=PISO_BLOQUE):
    """`(asignadas: {id: segundos}, recortes: [(id, natural, asignada), ...])`. Sin recorte si
    la suma natural ya cabe; si no, techo común por bisección y, tras él, ningún bloque baja
    de `piso` (límite declarado: con muchos bloques y un `--segundos` muy pequeño el total
    puede acabar algo por encima de lo pedido — se prefiere eso a que un bloque desaparezca)."""
    naturales = {i: DURACION_NATURAL[i] for i in ids_disponibles}
    if not naturales:
        return {}, []
    suma = sum(naturales.values())
    if suma <= objetivo:
        return dict(naturales), []
    techo = _techo_por_bisección(list(naturales.values()), objetivo)
    asignadas = {i: max(piso, min(v, techo)) for i, v in naturales.items()}
    recortes = [(i, naturales[i], asignadas[i]) for i in ids_disponibles if asignadas[i] < naturales[i] - 1e-9]
    return asignadas, recortes


# ───────────────────────────── orquestación ─────────────────────────────

def _entero_par(v):
    v = int(round(v))
    return v + 1 if v % 2 else v


def generar(salida=None, idioma=None, segundos=60.0, ancho=1920, avisar=print,
            ruta_paquete=None, ruta_proyecto_ejemplo=None):
    """Genera el vídeo y devuelve un resumen (dict, ver más abajo). `ruta_paquete`/
    `ruta_proyecto_ejemplo`: para pruebas — sin darlos, el paquete es el propio repo de Abyss y
    el proyecto de ejemplo es uno construido aquí mismo en un directorio temporal."""
    if segundos <= 0:
        raise ValueError(f"--segundos debe ser positivo, no {segundos}")
    ancho = max(320, _entero_par(ancho))
    alto = _entero_par(ancho * 9 / 16)
    idioma = idioma if idioma in TEXTOS else _idioma_sistema()
    T = TEXTOS[idioma]
    salida = os.path.abspath(salida or "abyss_1min.mp4")
    os.makedirs(os.path.dirname(salida) or ".", exist_ok=True)

    tmp = tempfile.mkdtemp(prefix="abyss_presenta_")
    resultados = []
    recortes_log = []
    try:
        proyecto = ruta_proyecto_ejemplo or _construir_proyecto_ejemplo(tmp)
        paquete = ruta_paquete or RAIZ_PAQUETE
        transcript_honestidad = _transcript_honestidad(tmp)
        foto_demo = os.path.join(tmp, "foto_demo.png")
        _foto_demo(foto_demo)
        escena_3d = os.path.join(tmp, "escena_demo.json")
        with open(escena_3d, "w", encoding="utf-8") as fh:
            json.dump(ESCENA_3D_DEMO, fh, ensure_ascii=False)

        ctx_comun = {"ancho": ancho, "alto": alto, "idioma": idioma, "T": T, "tmp": tmp,
                     "proyecto": proyecto, "paquete": paquete, "avisar": avisar,
                     "transcript_honestidad": transcript_honestidad, "foto_demo": foto_demo,
                     "escena_3d": escena_3d}

        forzados_ausentes = {s.strip() for s in os.environ.get("ABYSS_PRESENTA_FORZAR_AUSENTE", "").split(",") if s.strip()}

        # Paso 1: disponibilidad + generación de contenido (sin decidir aún duración final).
        for id_bloque in ORDEN_BLOQUES:
            titulo = T[f"{id_bloque}_titulo"]
            if id_bloque in forzados_ausentes:
                motivo = "ABYSS_PRESENTA_FORZAR_AUSENTE"
                avisar(T["salta_log"].format(titulo=titulo, motivo=motivo))
                resultados.append({"id": id_bloque, "titulo": titulo, "disponible": False, "motivo": motivo})
                continue
            try:
                ctx = dict(ctx_comun, duracion=DURACION_NATURAL[id_bloque])
                frames = GENERADORES[id_bloque](ctx)
                if not frames:
                    raise PiezaNoDisponible("sin fotogramas que enseñar")
                resultados.append({"id": id_bloque, "titulo": titulo, "disponible": True, "frames": frames})
            except PiezaNoDisponible as e:
                avisar(T["salta_log"].format(titulo=titulo, motivo=str(e)))
                resultados.append({"id": id_bloque, "titulo": titulo, "disponible": False, "motivo": str(e)})
            except Exception as e:  # fail-closed: un fallo inesperado tampoco revienta el vídeo
                motivo = f"{type(e).__name__}: {e}"
                avisar(T["salta_log"].format(titulo=titulo, motivo=motivo))
                resultados.append({"id": id_bloque, "titulo": titulo, "disponible": False, "motivo": motivo})

        disponibles = [r for r in resultados if r["disponible"]]
        ausentes = [r for r in resultados if not r["disponible"]]

        # Paso 2: presupuesto de tiempo sobre lo YA generado (recortar sostiene MENOS
        # fotogramas de los que ya hay, nunca vuelve a generar).
        seg_tarjeta = min(3.0, max(0.7, segundos * 0.12))
        seg_omitidos = seg_tarjeta if ausentes else 0.0
        objetivo_bloques = max(1.0, float(segundos) - 2 * seg_tarjeta - seg_omitidos)
        asignadas, recortes = _ajustar_presupuesto([r["id"] for r in disponibles], objetivo_bloques)
        for id_bloque, natural, asignada in recortes:
            recortes_log.append((id_bloque, natural, asignada))
            avisar(T["recorte_log"].format(seg=segundos, titulo=T[f"{id_bloque}_titulo"],
                                            antes=natural, despues=asignada))

        # Paso 3: escribir el vídeo con lo recortado (o completo, si no hizo falta recortar).
        escritor = _EscritorVideo(salida, ancho, alto, FPS)
        escritor.escribir_todas(_repetir(_tarjeta(T["apertura_titulo"], T["apertura_sub"], ancho, alto,
                                                   indice=0), seg_tarjeta))
        for r in disponibles:
            objetivo_frames = max(1, round(asignadas[r["id"]] * FPS))
            frames = r["frames"]
            if len(frames) > objetivo_frames:
                frames = frames[:max(1, objetivo_frames)]
            escritor.escribir_todas(frames)
            r["segundos_reales"] = round(len(frames) / FPS, 2)
            del r["frames"]
        if ausentes:
            escritor.escribir_todas(_repetir(_frame_omitidos(ausentes, T, ancho, alto), seg_omitidos))
        escritor.escribir_todas(_repetir(_tarjeta(T["cierre_titulo"], T["cierre_sub"], ancho, alto,
                                                   indice=len(PALETA) - 1), seg_tarjeta))
        escritor.cerrar()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    duracion = round(escritor.frames / FPS, 2)
    avisar(f"vídeo: {salida} · {duracion:.1f} s · {ancho}x{alto} @ {FPS} fps · "
           f"{len(disponibles)} bloque(s) de {len(resultados)}")
    return {"mp4": salida, "duracion": duracion, "ancho": ancho, "alto": alto, "fps": FPS,
            "idioma": idioma, "bloques": resultados,
            "omitidos": [r["id"] for r in ausentes],
            "recortes": [{"bloque": i, "de": round(n, 2), "a": round(a, 2)} for i, n, a in recortes_log]}


# ───────────────────────────── CLI ─────────────────────────────

def _cli(argv):
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 1
    opts = {"salida": "abyss_1min.mp4", "idioma": None, "segundos": 60.0, "ancho": 1920}
    con_valor = {"--salida": "salida", "--idioma": "idioma", "--segundos": "segundos", "--ancho": "ancho"}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in con_valor and i + 1 < len(argv):
            i += 1
            v = argv[i]
            clave = con_valor[a]
            if clave == "segundos":
                try:
                    opts[clave] = float(v)
                except ValueError:
                    print(f'--segundos necesita un número, no "{v}"')
                    return 1
            elif clave == "ancho":
                try:
                    opts[clave] = int(v)
                except ValueError:
                    print(f'--ancho necesita un número entero, no "{v}"')
                    return 1
            elif clave == "idioma":
                if v not in ("es", "en"):
                    print(f'--idioma debe ser "es" o "en", no "{v}"')
                    return 1
                opts[clave] = v
            else:
                opts[clave] = v
        else:
            print(f'argumento no reconocido: {a} (usa --salida/--idioma/--segundos/--ancho)')
            return 1
        i += 1

    try:
        r = generar(**opts)
    except Exception as e:
        print(f"sin video: {type(e).__name__} {e}")
        return 2
    print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(_cli(sys.argv[1:]))
