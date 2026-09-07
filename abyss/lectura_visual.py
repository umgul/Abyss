# -*- coding: utf-8 -*-
"""Lectura visual: lo que el ojo LEE — OCR y sus tres usos (ESPECIFICACION_TANDA4.md, T4.3).

Uso:
    python lectura_visual.py texto <imagen> [--portapapeles] [--salida f.txt]
    python lectura_visual.py fotocopia (<imagen>|--camara [indice]) [--escaner]
                             [--salida f.png|f.pdf] [--color|--gris|--umbral] [--paginas n]
    python lectura_visual.py tarjeta <imagen> [--salida base]
    python lectura_visual.py manual <imagen...> [--salida f.md]
    (con `--proyecto <cwd>` en cualquiera, igual que el resto del paquete — §1)

Motor de OCR, en este orden fijo, nunca se instala nada:
  1. El de Windows por WinRT (`Windows.Media.Ocr`, vía `abyss/ocr_win.ps1`): viene YA
     instalado en cualquier Windows con el paquete de idioma del perfil puesto — no
     hace falta `pip install` nada. Medido el 7-sep-2026 en la máquina de desarrollo:
     imagen sintética de 900×420, 6 líneas, con acentos y `correo@ejemplo.es`/
     `Tel. +34 600 123 456` intactos, en 443 ms, idioma `es-ES` (el del perfil) — ver
     ESPECIFICACION_TANDA4.md §0.
  2. `tesseract`, si está en el PATH, como segunda vía (en la máquina de desarrollo,
     medido, NO está en el PATH). Su salida TSV (`-c tessedit_create_tsv=1`) da
     posición y tamaño por palabra, agrupadas aquí por línea, así `tarjeta`/`manual`
     funcionan igual con cualquiera de los dos motores.
  Sin Windows (o sin el paquete de idioma de Windows) y sin `tesseract` en PATH:
  «sin dato: no hay motor OCR» y código 2. Nunca se instala nada (ni `pip`, ni
  `winget`): si falta, el mensaje dice qué instalar y decide quien lo lea.

`texto`: imprime las líneas en el orden que da el motor (de arriba abajo). Con
`--portapapeles`, además YA COPIADO: en Windows por `Set-Clipboard` de PowerShell
(medido disponible junto a `clip.exe`, ESPECIFICACION_TANDA4.md §0 — se prefiere
`Set-Clipboard` porque recibe el texto ya como objeto Unicode; `clip.exe` decodifica
su entrada con la code page de la consola y desfigura acentos/`ñ` si esa code page
no es UTF-8, el caso normal de `cmd.exe`); en macOS por `pbcopy`; en Linux por
`xclip -selection clipboard` si está instalado. Sin ningún instrumento: lo dice,
no revienta la orden por eso.

`fotocopia`: **CORRECCIÓN DEL AUTOR (7-sep-2026 19:15), manda sobre cualquier
versión anterior de este módulo**: el escáner es el SOFTWARE, no un aparato.

La vía NORMAL es una FOTO — un fichero ya existente o un fotograma de la webcam
(`--camara [índice]`, por defecto cámara 0; mismo `cv2.VideoCapture` con
`CAP_DSHOW` en Windows que `ojo.py`/`gestos.py`) — se da UNA de las dos, nunca
las dos a la vez ni ninguna (error de uso, código 1: este guion no da por
hecho que quien lo usa tiene un fichero a mano en vez de cámara, ni al revés).
Sobre esa foto: endereza el papel (contorno CUADRILÁTERO de mayor área con
`cv2` — bordes de Canny + `findContours` + `approxPolyDP` — y, si cubre al
menos una quinta parte de la imagen, `getPerspectiveTransform`/
`warpPerspective` para dejarlo plano y recortado a sus 4 esquinas). **Sin
cuadrilátero claro** (declarado, nunca fingido): no recorta nada — endereza
por el ángulo dominante de los bordes (`HoughLines`) y lo dice por stdout y en
el JSON de salida (`"recortado": false`). Corrige iluminación con un fondo
estimado por mediana de kernel grande (aproxima sombra/viñeteado del papel;
el texto, a escala mucho más fina, no se ve afectado) y normaliza dividiendo
por él. `--color` (por defecto): color con esa corrección. `--gris`: escala
de grises. `--umbral`: blanco y negro por umbral adaptativo
(`adaptiveThreshold`) sobre la versión en gris ya corregida — el aspecto
"fotocopia de verdad". Y GUARDA el resultado en LOCAL como PNG o PDF de varias
páginas. **Prohibido**: no imprime nada, no manda nada a ninguna impresora, y
no da por hecho que quien lo use tenga escáner ni impresora.

`--paginas n` (solo tiene sentido con `--camara`; con un fichero ya dado es un
error de uso — una foto no tiene "página siguiente"): toma `n` fotogramas EN
SECUENCIA, con una pausa entre cada uno para recolocar la hoja siguiente
delante de la cámara, cada uno enderezado/iluminado por separado, y los junta
en UN solo PDF multipágina. Con `n` > 1 la salida tiene que terminar en
`.pdf` (error de uso si no: un PNG no admite varias páginas y este guion no
inventa un formato para forzarlo).

`--escaner`: un escáner WIA, SI EXISTE en la máquina, es una fuente OPCIONAL
MÁS — **nunca el camino**. Se intenta ANTES que la vía normal (medido el
7-sep-2026: «HP DeskJet 3700 series» responde como dispositivo WIA tipo 1 —
escáner — en esta máquina): si responde, se usa su hoja y no se toca ni el
fichero ni la cámara que también se hayan dado. **Si no hay escáner
disponible, NO es un error**: se imprime «sin escáner: uso la cámara o un
fichero» y se sigue por la vía normal ya indicada (`<imagen>` o `--camara`),
tal cual si `--escaner` no se hubiera puesto. Por eso `--escaner` nunca basta
por sí solo: la vía normal (fichero o cámara) es obligatoria siempre, la
acabe usando o no. **Este camino no se ejerce contra hardware real en la
batería de pruebas del paquete** (T4.3): solo se prueba que detecta la
ausencia sin reventar y cae a la vía normal sin error.

Sin `--salida`: si la entrada es un fichero, `<carpeta_de_la_imagen>/
<base>_fotocopia.png`; si viene de `--escaner` o `--camara`, un fichero en
`mem` con fecha y hora (`.pdf` si hay más de una página, si no `.png`), como
`ojo.py`. La prueba de la suite usa una foto SINTÉTICA de un folio torcido
(escrita una vez con Pillow, nunca una cámara ni un escáner reales); el
camino `--camara` se prueba con `ABYSS_LECTURA_VISUAL_SIN_CAMARA` forzando
"sin cámara" (mismo patrón que `--escaner`/WIA con
`ABYSS_LECTURA_VISUAL_SIN_WIA`) — la suite nunca abre una webcam de verdad.

`tarjeta`: OCR + extracción por patrones sobre las LÍNEAS que da el motor (nunca
sobre la imagen entera de una vez): teléfono (dígitos suficientes tras quitar
espacios/separadores), correo (`@`), web (dominio con TLD conocido o `www.`/`http`).
De lo que sobra, nombre/cargo/empresa es una HEURÍSTICA declarada, no un lector
certificado de tarjetas: la línea de mayor ALTURA de caja (proxy de cuerpo de letra
— con el motor de Windows, la propia caja que envuelve las palabras de esa línea) es
el nombre; entre el resto, la primera con un sufijo societario conocido (S.L., S.A.,
Inc., Ltd., Corp., GmbH...) es la empresa; la siguiente que quede, el cargo. Lo que
no encaja en ningún hueco se queda fuera: **no se inventa un cargo** con el texto que
sobre. Escribe `<base>.vcf` (vCard 3.0 válido; los campos vacíos, ausentes del
`.vcf`, nunca puestos a un valor inventado) y `<base>.png` (tarjeta compuesta con
Pillow, con "sin dato" en los campos que no se reconocieron). `--salida base` fija
el prefijo común de ambos ficheros; sin él, `<imagen_sin_extensión>_tarjeta`.

`manual`: OCR de una o varias fotos/páginas. Ordena por NÚMERO DE PÁGINA si todas y
cada una de las imágenes dan uno (líneas «página N»/«page N», «N/M», o una línea que
es solo un número — el primer patrón que acierte en cada página manda); si falta en
alguna, se queda con el orden en que se dieron los ficheros (declarado: no se
adivina un orden a medias). Une palabras partidas por un guion de corte a final de
línea («informa-» + «ción» → «información»); no une nada más. **Honestidad** (T4.3):
el guion NO RESUME — entrega el texto limpio y ordenado, con las líneas que detecta
como paso numerado («1.», «Paso 2», «Step 3», una viñeta) reescritas a una lista
markdown consistente; el resto del texto, tal cual lo leyó el motor. Resumir ese
texto es cosa del asistente, con el texto delante — la skill lo dice así. `--salida
f.md`; sin él, `<carpeta_de_la_primera_imagen>/manual.md`.

Nada de esto sale de la máquina: los dos motores de OCR son locales (WinRT es del
propio Windows; `tesseract`, si está, corre en local); `fotocopia`/`tarjeta` no
tocan la red en absoluto. El escáner WIA, la cámara y el portapapeles son
instrumentos LOCALES (`cv2.VideoCapture`, `New-Object -ComObject WIA.DeviceManager`,
`Set-Clipboard`), igual que otras piezas del paquete usan `powershell.exe` para
medir la propia máquina (ver `abyss/huella.py`).

Carpeta de datos: `rutas.resolver()` (§1) — solo para saber dónde va el registro
de cada llamada (`mem/lectura_visual.log`) y, con `--escaner`/`--camara`, dónde cae
el fichero capturado por defecto; el resto de rutas de entrada/salida son las que
se dan en la propia orden, como en `render3d.py`/`pintor.py`.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

try:
    from . import rutas
except Exception:  # ejecutado como guion suelto
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import rutas

CODE = rutas.CODE
OCR_WIN_PS1 = os.path.join(CODE, 'ocr_win.ps1')

try:
    import cv2
    import numpy as np
    _CV2_OK = True
except ImportError:
    _CV2_OK = False

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_OK = True
except ImportError:
    _PIL_OK = False


class SinMotorOCR(RuntimeError):
    """Ni el motor de Windows (WinRT) ni `tesseract` (PATH) están disponibles."""


# ───────────────────────────── motor: WinRT (Windows) ─────────────────────────────

def _powershell_json(args, timeout):
    """Lanza `powershell.exe` con `args` y devuelve el dict de la ÚLTIMA línea no
    vacía de su stdout (siempre JSON — ver `ocr_win.ps1`), o `None` si ni
    siquiera se pudo ejecutar, se agotó el tiempo, o la salida no era JSON
    legible. `None` NUNCA distingue "el motor dijo que no" (eso es un dict con
    `ok: false`) de "no sé lo que ha pasado" — quien llama trata ambos como
    "no disponible" y sigue a la siguiente vía, igual que un `None` de
    `huella._powershell()`."""
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass'] + args,
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    except Exception:
        return None
    lineas = [l for l in r.stdout.splitlines() if l.strip()]
    if not lineas:
        return None
    try:
        return json.loads(lineas[-1])
    except Exception:
        return None


def _ocr_winrt(ruta_abs, idioma=None, timeout=25):
    args = ['-File', OCR_WIN_PS1, '-Ruta', ruta_abs]
    if idioma:
        args += ['-Idioma', idioma]
    return _powershell_json(args, timeout)


def _comprobar_winrt(idioma=None, timeout=10):
    args = ['-File', OCR_WIN_PS1, '-Comprobar']
    if idioma:
        args += ['-Idioma', idioma]
    return _powershell_json(args, timeout)


def _sin_winrt_forzado():
    """`ABYSS_LECTURA_VISUAL_SIN_WINRT` fuerza el camino "sin motor de Windows"
    sin depender de qué idiomas tenga instalados la máquina que corre la suite
    — mismo patrón que `ABYSS_RENDER3D_NAVEGADOR=''` en `render3d.py`. En uso
    normal nunca se define."""
    return (os.name != 'nt') or bool(os.environ.get('ABYSS_LECTURA_VISUAL_SIN_WINRT'))


def motor_winrt_disponible(idioma=None):
    """True si esta máquina puede hacer OCR con el motor de Windows para el
    idioma pedido (o los del perfil, si `idioma` es `None`). Llama de verdad a
    `ocr_win.ps1 -Comprobar` (no adivina por `os.name` a secas): un Windows sin
    el paquete de idioma también debe dar `False` aquí."""
    if _sin_winrt_forzado():
        return False
    d = _comprobar_winrt(idioma)
    return bool(d and d.get('ok'))


def _lineas_normalizadas(x):
    """Como `huella._normalizar_lista()`: `ConvertTo-Json` da un objeto suelto
    (no una lista de un elemento) cuando la colección de origen tiene
    EXACTAMENTE una fila, y `null`/ausente con cero — aquí, además, `ocr_win.ps1`
    ya envuelve con `@(...)` antes de emitir (ver su comentario), así que este
    caso no debería darse desde ahí; se deja por si acaso llega de otra vía."""
    if not x:
        return []
    if isinstance(x, dict):
        return [x]
    return x


# ───────────────────────────── motor: tesseract (segunda vía) ─────────────────────────────

def _tesseract_disponible():
    """`ABYSS_LECTURA_VISUAL_SIN_TESSERACT` fuerza "no está", sin importar el
    PATH real de la máquina — para poder probar el camino "sin ningún motor" de
    forma determinista aunque algún día `tesseract` SÍ esté instalado aquí."""
    if os.environ.get('ABYSS_LECTURA_VISUAL_SIN_TESSERACT'):
        return None
    return shutil.which('tesseract')


def _ocr_tesseract(ruta_tess, ruta_abs, idioma=None, timeout=30):
    """Segunda vía (T4.3): TSV de `tesseract` (`left/top/width/height` por
    PALABRA) agrupado por línea (`block_num`,`par_num`,`line_num`) para dar el
    mismo formato de línea+caja que `ocr_win.ps1` — así `tarjeta`/`manual`
    funcionan igual con cualquiera de los dos motores. No medido en esta
    máquina (`tesseract` no está en el PATH, ESPECIFICACION_TANDA4.md §0): la
    prueba de este camino se salta con motivo si no lo encuentra."""
    args = [ruta_tess, ruta_abs, 'stdout', '--psm', '3']
    if idioma:
        args += ['-l', idioma]
    args += ['tsv']
    r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f'tesseract: {(r.stderr or "").strip()[:200] or "código " + str(r.returncode)}')
    filas = r.stdout.splitlines()
    if len(filas) < 2:
        return []
    cab = filas[0].split('\t')
    idx = {n: i for i, n in enumerate(cab)}
    necesarias = ('text', 'left', 'top', 'width', 'height', 'block_num', 'par_num', 'line_num')
    if not all(n in idx for n in necesarias):
        raise RuntimeError('tesseract: TSV sin las columnas esperadas')
    grupos = {}
    orden = []
    for fila in filas[1:]:
        cols = fila.split('\t')
        if len(cols) < len(cab):
            continue
        texto = cols[idx['text']].strip()
        if not texto:
            continue
        try:
            x = float(cols[idx['left']]); y = float(cols[idx['top']])
            w = float(cols[idx['width']]); h = float(cols[idx['height']])
        except ValueError:
            continue
        clave = (cols[idx['block_num']], cols[idx['par_num']], cols[idx['line_num']])
        if clave not in grupos:
            grupos[clave] = {'palabras': [], 'x1': x, 'y1': y, 'x2': x + w, 'y2': y + h}
            orden.append(clave)
        g = grupos[clave]
        g['palabras'].append(texto)
        g['x1'] = min(g['x1'], x); g['y1'] = min(g['y1'], y)
        g['x2'] = max(g['x2'], x + w); g['y2'] = max(g['y2'], y + h)
    out = []
    for clave in orden:
        g = grupos[clave]
        out.append({'texto': ' '.join(g['palabras']), 'x': round(g['x1'], 1), 'y': round(g['y1'], 1),
                    'ancho': round(g['x2'] - g['x1'], 1), 'alto': round(g['y2'] - g['y1'], 1)})
    return out


# ───────────────────────────── API pública de OCR ─────────────────────────────

def leer(ruta_imagen, idioma=None, avisar=print):
    """OCR de una imagen. Devuelve `{"motor": "winrt"|"tesseract", "lineas": [...],
    "angulo": .. , "ms": ..}` donde cada línea es `{"texto","x","y","ancho","alto"}`
    (caja en píxeles; `x`/`y`/`ancho`/`alto` a 0 si el motor no la da). Nunca
    inventa texto ni posición: lo que no mide, no aparece.

    Orden (T4.3, ver docstring del módulo): WinRT primero si esta máquina es
    Windows y el motor existe para el idioma pedido; si no, `tesseract` si está
    en el PATH; si ninguno, `SinMotorOCR` ("sin dato: no hay motor OCR").

    Un fallo de WinRT sobre ESTA imagen en concreto (fichero ilegible, motor que
    lanzó una excepción procesándola) es distinto de "no hay motor": se
    propaga tal cual (no se enmascara como "sin motor" ni se cae a `tesseract`,
    que probablemente tropezaría con lo mismo)."""
    ruta_abs = os.path.abspath(ruta_imagen)
    if not os.path.isfile(ruta_abs):
        raise FileNotFoundError(f'no existe: {ruta_abs}')

    if not _sin_winrt_forzado():
        d = _ocr_winrt(ruta_abs, idioma)
        if d is not None and d.get('ok'):
            return {'motor': 'winrt', 'lineas': _lineas_normalizadas(d.get('lineas')),
                    'angulo': d.get('angulo'), 'ms': d.get('ms')}
        if d is not None and not d.get('ok'):
            motivo = str(d.get('motivo') or '')
            if not motivo.startswith('sin dato'):
                raise RuntimeError(motivo or 'el motor OCR de Windows falló sobre esta imagen')
            avisar(f'  {motivo}: se prueba tesseract')
        else:
            avisar('  no se pudo ejecutar powershell.exe/ocr_win.ps1: se prueba tesseract')

    ruta_tess = _tesseract_disponible()
    if ruta_tess:
        return {'motor': 'tesseract', 'lineas': _ocr_tesseract(ruta_tess, ruta_abs, idioma), 'angulo': None, 'ms': None}

    if os.name != 'nt':
        detalle = 'esta máquina no es Windows y tesseract no está en el PATH (instálalo: https://github.com/tesseract-ocr/tesseract)'
    else:
        detalle = 'falta el paquete de idioma de Windows (Configuración > Hora e idioma > Idioma y región) y tesseract no está en el PATH'
    raise SinMotorOCR(f'sin dato: no hay motor OCR ({detalle})')


def texto(ruta_imagen, idioma=None, avisar=print):
    """Texto plano, una línea del motor por línea de salida, en el orden en que
    lo lee (arriba a abajo, tal como lo da el motor)."""
    r = leer(ruta_imagen, idioma=idioma, avisar=avisar)
    return '\n'.join(l['texto'] for l in r['lineas'] if str(l.get('texto', '')).strip())


# ───────────────────────────── portapapeles ─────────────────────────────

def copiar_portapapeles(texto_plano):
    """Copia `texto_plano` al portapapeles del sistema (ver docstring del
    módulo). Devuelve `True` si se copió, `False` si no hay ningún instrumento
    (nunca lanza: quien llama lo dice y sigue)."""
    try:
        if os.name == 'nt':
            r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', '$input | Set-Clipboard'],
                                input=texto_plano, text=True, encoding='utf-8', errors='replace', timeout=8)
            return r.returncode == 0
        if sys.platform == 'darwin' and shutil.which('pbcopy'):
            r = subprocess.run(['pbcopy'], input=texto_plano, text=True, encoding='utf-8', errors='replace', timeout=8)
            return r.returncode == 0
        if shutil.which('xclip'):
            r = subprocess.run(['xclip', '-selection', 'clipboard'], input=texto_plano, text=True,
                                encoding='utf-8', errors='replace', timeout=8)
            return r.returncode == 0
        return False
    except Exception:
        return False


# ───────────────────────────── fotocopia: enderezar + iluminación ─────────────────────────────

def _ordenar_puntos(pts):
    """4 puntos (Nx2) a (arriba-izq, arriba-der, abajo-der, abajo-izq): la suma
    x+y es mínima en arriba-izq y máxima en abajo-der; la resta x-y es mínima en
    arriba-der y máxima en abajo-izq (truco estándar de OpenCV para esto)."""
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).reshape(-1)
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(d)]
    bl = pts[np.argmax(d)]
    return np.array([tl, tr, br, bl], dtype='float32')


def _angulo_dominante(bordes):
    """Ángulo (grados, ~[-45,45)) de la familia de líneas más votada por
    `HoughLines` sobre `bordes`, agrupando horizontal/vertical en el mismo
    rango (una hoja puede estar más cerca de un giro de 90° que de 0°). `0.0`
    si no encuentra ninguna línea con suficientes votos."""
    lineas = cv2.HoughLines(bordes, 1, np.pi / 180, threshold=120)
    if lineas is None:
        return 0.0
    angulos = []
    for l in lineas[:50]:
        _rho, theta = l[0]
        grados = (theta * 180.0 / np.pi) - 90.0
        grados = ((grados + 45.0) % 90.0) - 45.0
        angulos.append(grados)
    return float(np.median(angulos)) if angulos else 0.0


def _rotar(img, angulo_grados):
    if abs(angulo_grados) < 0.3:
        return img
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angulo_grados, 1.0)
    return cv2.warpAffine(img, m, (w, h), borderMode=cv2.BORDER_REPLICATE)


def _enderezar_documento(img_bgr, avisar=print):
    """(imagen_bgr, recortado: bool). Busca el contorno cuadrilátero de mayor
    área que cubra al menos 1/5 de la imagen (bordes de Canny dilatados,
    `findContours` + `approxPolyDP` a 4 esquinas convexas) y aplica una
    transformación de perspectiva. Sin ninguno así: NO recorta (declarado, T4.3)
    — solo endereza por el ángulo dominante de los bordes."""
    gris = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    borroso = cv2.GaussianBlur(gris, (5, 5), 0)
    bordes = cv2.Canny(borroso, 50, 150)
    bordes_d = cv2.dilate(bordes, np.ones((5, 5), np.uint8), iterations=1)
    contornos, _jerarquia = cv2.findContours(bordes_d, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    h, w = img_bgr.shape[:2]
    area_total = float(w * h)
    mejor, mejor_area = None, 0.0
    for c in contornos:
        area = cv2.contourArea(c)
        if area < area_total * 0.2 or area <= mejor_area:
            continue
        perim = cv2.arcLength(c, True)
        aprox = cv2.approxPolyDP(c, 0.02 * perim, True)
        if len(aprox) == 4 and cv2.isContourConvex(aprox):
            mejor, mejor_area = aprox.reshape(4, 2).astype('float32'), area
    if mejor is None:
        avisar('  sin cuadrilátero claro: se endereza por el ángulo dominante de los bordes, sin recortar')
        return _rotar(img_bgr, _angulo_dominante(bordes_d)), False
    (tl, tr, br, bl) = _ordenar_puntos(mejor)
    ancho = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    alto = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    ancho, alto = max(ancho, 2), max(alto, 2)
    destino = np.array([[0, 0], [ancho - 1, 0], [ancho - 1, alto - 1], [0, alto - 1]], dtype='float32')
    m = cv2.getPerspectiveTransform(np.array([tl, tr, br, bl], dtype='float32'), destino)
    return cv2.warpPerspective(img_bgr, m, (ancho, alto)), True


def _corregir_iluminacion_gris(img_bgr):
    """Escala de grises con el fondo (mediana de kernel grande, aproxima sombra
    y viñeteado del papel) dividido fuera: el texto, a escala mucho más fina
    que el kernel, no se ve tocado por la mediana y queda con más contraste."""
    gris = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    fondo = cv2.medianBlur(gris, 41).astype('float32')
    fondo = np.where(fondo < 1, 1, fondo)
    normalizado = np.clip((gris.astype('float32') / fondo) * 255.0, 0, 255)
    return normalizado.astype('uint8')


def _corregir_iluminacion_color(img_bgr):
    """Igual que `_corregir_iluminacion_gris` pero aplicando la MISMA ganancia
    (255/fondo, calculada sobre el gris) a los tres canales, para no desviar el
    color al corregir la sombra."""
    gris = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    fondo = cv2.medianBlur(gris, 41).astype('float32')
    fondo = np.where(fondo < 1, 1, fondo)
    ganancia = 255.0 / fondo
    out = img_bgr.astype('float32') * ganancia[:, :, None]
    return np.clip(out, 0, 255).astype('uint8')


def _procesar_documento(img_bgr, modo='color', avisar=print):
    """(imagen_np, recortado: bool). El núcleo de `fotocopia` (enderezar +
    corregir iluminación) sobre una imagen YA CARGADA en memoria — lo
    comparten `fotocopiar()` (lee de disco) y la vía `--camara`/`--paginas`
    (lee fotogramas de la webcam), para no duplicar la lógica entre "vino de
    fichero" y "vino de cámara". `modo`: color/gris/umbral (ver docstring del
    módulo)."""
    plano, recortado = _enderezar_documento(img_bgr, avisar=avisar)
    if modo == 'gris':
        return _corregir_iluminacion_gris(plano), recortado
    if modo == 'umbral':
        gris = _corregir_iluminacion_gris(plano)
        umbral = cv2.adaptiveThreshold(gris, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 15)
        return umbral, recortado
    return _corregir_iluminacion_color(plano), recortado


def _guardar_imagen(imagen_np, ruta_salida):
    os.makedirs(os.path.dirname(os.path.abspath(ruta_salida)) or '.', exist_ok=True)
    if os.path.splitext(ruta_salida)[1].lower() == '.pdf':
        if not _PIL_OK:
            raise RuntimeError('sin dato: instala Pillow (pip install Pillow) para guardar en PDF')
        pil = Image.fromarray(imagen_np, mode='L') if imagen_np.ndim == 2 else \
            Image.fromarray(cv2.cvtColor(imagen_np, cv2.COLOR_BGR2RGB))
        pil.save(ruta_salida, 'PDF')
    else:
        cv2.imwrite(ruta_salida, imagen_np)


def _guardar_paginas(paginas_np, ruta_salida):
    """Guarda 1 o más imágenes ya procesadas (arrays de `_procesar_documento`)
    en `ruta_salida`. Con una sola página, igual que `_guardar_imagen` (PNG o
    PDF según la extensión). Con varias (`--paginas` > 1, solo vía `--camara`):
    EXIGE que `ruta_salida` termine en `.pdf` — un PNG no admite varias
    páginas y este guion no inventa un formato para forzarlo (`ValueError`,
    que la CLI convierte en un mensaje de uso) — y las escribe como un único
    PDF multipágina con Pillow (`save_all=True, append_images=...`)."""
    if len(paginas_np) <= 1:
        _guardar_imagen(paginas_np[0], ruta_salida)
        return
    if os.path.splitext(ruta_salida)[1].lower() != '.pdf':
        raise ValueError('con --paginas más de 1 la salida debe terminar en .pdf (un PNG no admite varias páginas)')
    if not _PIL_OK:
        raise RuntimeError('sin dato: instala Pillow (pip install Pillow) para guardar en PDF')
    os.makedirs(os.path.dirname(os.path.abspath(ruta_salida)) or '.', exist_ok=True)
    paginas_pil = []
    for arr in paginas_np:
        pil = Image.fromarray(arr, mode='L') if arr.ndim == 2 else Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))
        paginas_pil.append(pil.convert('RGB'))
    paginas_pil[0].save(ruta_salida, 'PDF', save_all=True, append_images=paginas_pil[1:])


def fotocopiar(ruta_imagen, modo='color', avisar=print):
    """(imagen_np, recortado: bool) a partir de un FICHERO en disco (para la
    vía `--camara`, que ya trae la imagen en memoria, ver
    `_procesar_documento` directamente). `modo`: color/gris/umbral (ver
    docstring del módulo). No escribe nada — quien llama decide la ruta de
    salida."""
    img = cv2.imread(ruta_imagen)
    if img is None:
        raise RuntimeError(f'no se pudo leer como imagen: {ruta_imagen}')
    return _procesar_documento(img, modo=modo, avisar=avisar)


# ───────────────────────────── fotocopia: cámara (vía normal) ─────────────────────────────

def _abrir_camara(indice):
    """Abre `cv2.VideoCapture(indice)`; en Windows probando antes `CAP_DSHOW`
    (arranca más rápido con la mayoría de webcams UVC) — mismo patrón que
    `ojo.py`/`gestos.py`."""
    if os.name == 'nt':
        cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
        if cap.isOpened():
            return cap
    return cv2.VideoCapture(indice)


def _sin_camara_forzada():
    """`ABYSS_LECTURA_VISUAL_SIN_CAMARA` fuerza "sin cámara" SIN tocar
    `cv2.VideoCapture` en absoluto — para que la suite pueda probar el
    cableado de `--camara`/`--paginas` sin encender nunca una webcam de
    verdad (regla dura del encargo: la cámara solo se abre cuando de verdad
    hace falta), mismo patrón que `ABYSS_LECTURA_VISUAL_SIN_WIA`."""
    return bool(os.environ.get('ABYSS_LECTURA_VISUAL_SIN_CAMARA'))


def capturar_camara(indice=0, n=1, avisar=print, pausa=2.0):
    """Captura `n` fotogramas EN SECUENCIA de la cámara `indice` (uno solo si
    `n` es 1: el uso normal de `--camara`), con una pausa de `pausa` segundos
    entre cada uno para recolocar la hoja siguiente (solo importa con `n` > 1,
    `--paginas`). Devuelve `{"ok": True, "fotogramas": [np.ndarray, ...]}` o
    `{"ok": False, "motivo": "sin dato: ..."}` — nunca lanza, igual que
    `escanear_wia()`. Antes de cada fotograma se descartan varias lecturas (la
    cámara suele dar los primeros fotogramas oscuros mientras ajusta la
    exposición), como `ojo.py`.

    Ver `_sin_camara_forzada()`: con esa variable puesta, la suite NUNCA llega
    a `cv2.VideoCapture` — se responde "sin dato" directamente."""
    if _sin_camara_forzada():
        return {'ok': False, 'motivo': f'sin dato: cámara {indice} no disponible (forzado para pruebas)'}
    if not _CV2_OK:
        return {'ok': False, 'motivo': 'sin dato: instala opencv-python y numpy (pip install opencv-python numpy) para "--camara"'}
    cap = _abrir_camara(indice)
    if not cap.isOpened():
        return {'ok': False, 'motivo': f'sin dato: cámara {indice} no disponible'}
    fotogramas = []
    try:
        for pagina in range(max(1, n)):
            if pagina > 0:
                avisar(f'  página {pagina + 1}/{n}: coloca la siguiente hoja...')
                time.sleep(pausa)
            ok, frame = False, None
            for _ in range(8):
                ok, frame = cap.read()
                time.sleep(0.1)
            if not ok or frame is None:
                return {'ok': False, 'motivo': f'la cámara abrió pero no dio fotograma (página {pagina + 1}/{n})'}
            fotogramas.append(frame)
    finally:
        cap.release()
    return {'ok': True, 'fotogramas': fotogramas}


# ───────────────────────────── fotocopia: escáner WIA (fuente opcional) ─────────────────────────────

def _ps_str(v):
    """Cadena entrecomillada de forma segura para un literal PowerShell de
    comillas simples (dobla cualquier comilla simple que lleve dentro)."""
    return "'" + str(v).replace("'", "''") + "'"


# WIA: `@($dm.DeviceInfos) | Where-Object {...}` con EXACTAMENTE un resultado da
# el objeto COM suelto, no un array de un elemento — el mismo aplanado de
# pipeline que documenta `huella._normalizar_lista()` (medido 7-sep sobre esta
# misma máquina, con el único escáner que tiene conectado: `$infos.Count` salía
# vacío). Se envuelve TODO el resultado del pipeline en un `@()` exterior, no
# solo la colección de partida, para que sobreviva a esa reducción.
_PS_ESCANER = r'''
$ErrorActionPreference = "Stop"
function Emitir($o) { Write-Output ($o | ConvertTo-Json -Compress -Depth 4) }
try {
    $dm = New-Object -ComObject WIA.DeviceManager
} catch {
    Emitir @{ ok = $false; motivo = "sin dato: no hay escáner WIA (WIA no disponible: $($_.Exception.Message))" }
    exit 2
}
$infos = @(@($dm.DeviceInfos) | Where-Object { $_.Type -eq 1 })
if ($infos.Count -eq 0) {
    Emitir @{ ok = $false; motivo = "sin dato: no hay escáner WIA conectado" }
    exit 2
}
try {
    $nombre = $infos[0].Properties.Item("Name").Value
    $device = $infos[0].Connect()
    $item = $device.Items.Item(1)
    $formatoBmp = "{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}"
    $img = $item.Transfer($formatoBmp)
    $ruta = __RUTA__
    if (Test-Path -LiteralPath $ruta) { Remove-Item -LiteralPath $ruta -Force }
    $img.SaveFile($ruta)
} catch {
    Emitir @{ ok = $false; motivo = "el escáner falló: $($_.Exception.Message)" }
    exit 1
}
Emitir @{ ok = $true; ruta = $ruta; dispositivo = $nombre }
exit 0
'''


def escanear_wia(ruta_salida, timeout=60):
    """Adquiere una hoja del escáner WIA tipo 1 (medido: «HP DeskJet 3700
    series», ESPECIFICACION_TANDA4.md §0) y la guarda en `ruta_salida`. Devuelve
    el dict `{"ok":true,"ruta":...,"dispositivo":...}` o `{"ok":false,"motivo":...}`
    (nunca lanza: quien llama decide qué hacer según `ok` — en `fotocopia`,
    caer a la vía normal sin tratarlo como error, ver docstring del módulo).

    `ABYSS_LECTURA_VISUAL_SIN_WIA` fuerza la rama "sin escáner" SIN tocar WIA en
    absoluto (ni siquiera para preguntar si hay uno): existe para poder probar
    el camino "sin dato" sin depender de qué tenga enchufado la máquina que
    corre la suite, y sobre todo para que la suite NUNCA accione un escáner de
    verdad (T4.3: ese camino no se ejerce contra hardware real) — mismo patrón
    que `ABYSS_RENDER3D_NAVEGADOR`."""
    if os.environ.get('ABYSS_LECTURA_VISUAL_SIN_WIA'):
        return {'ok': False, 'motivo': 'sin dato: no hay escáner WIA conectado'}
    script = _PS_ESCANER.replace('__RUTA__', _ps_str(os.path.abspath(ruta_salida)))
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    except Exception as e:
        return {'ok': False, 'motivo': f'sin dato: no se pudo ejecutar powershell.exe ({type(e).__name__})'}
    lineas = [l for l in r.stdout.splitlines() if l.strip()]
    if not lineas:
        return {'ok': False, 'motivo': 'sin dato: no hay escáner WIA (sin respuesta de PowerShell)'}
    try:
        return json.loads(lineas[-1])
    except Exception:
        return {'ok': False, 'motivo': 'sin dato: no hay escáner WIA (respuesta ilegible de PowerShell)'}


# ───────────────────────────── tarjeta: patrones + heurística de posición ─────────────────────────────

RE_EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[A-Za-z]{2,}')
RE_TEL = re.compile(r'(\+?\d[\d\s().-]{6,}\d)')
RE_WEB = re.compile(
    r'\b(?:https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.(?:com|es|net|org|info|io|co|biz|shop|studio|dev|app)(?:/[^\s]*)?)\b')
RE_EMPRESA_SUFIJO = re.compile(
    r'\b(S\.?L\.?U?\.?|S\.?A\.?|Ltd\.?|Inc\.?|Corp\.?|GmbH|LLC|Group|Studio|Coop(?:erativa)?\.?)\b', re.I)


def _clasificar_lineas(lineas_ocr):
    """`lineas_ocr`: lo que da `leer()['lineas']`. Devuelve (telefono, correo,
    web, resto): el PRIMER acierto de cada patrón (cadena vacía si ninguno), y
    `resto` = las líneas que no encajan en ningún patrón (con su caja, para la
    heurística de nombre/cargo/empresa)."""
    telefono = correo = web = ''
    resto = []
    for ln in lineas_ocr:
        t = str(ln.get('texto', '')).strip()
        if not t:
            continue
        m = RE_EMAIL.search(t)
        if m and not correo:
            correo = m.group(0)
            continue
        m = RE_TEL.search(t)
        if m and not telefono and sum(c.isdigit() for c in m.group(1)) >= 7:
            telefono = re.sub(r'\s+', ' ', m.group(1)).strip()
            continue
        m = RE_WEB.search(t)
        if m and not web and '@' not in t:
            web = m.group(0)
            continue
        resto.append(ln)
    return telefono, correo, web, resto


def _nombre_cargo_empresa(resto):
    """Heurística declarada (T4.3 — "por posición y tamaño"): la línea de mayor
    ALTURA de caja es el nombre; entre las demás, la primera con un sufijo
    societario conocido es la empresa; la que quede, por orden de aparición, es
    el cargo. Lo que sobra se queda fuera (nunca se inventa un cargo)."""
    if not resto:
        return '', '', ''
    ordenado = sorted(resto, key=lambda l: float(l.get('alto') or 0), reverse=True)
    nombre_linea = ordenado[0]
    nombre = str(nombre_linea.get('texto', '')).strip()
    restantes = [l for l in resto if l is not nombre_linea]
    empresa = ''
    for l in list(restantes):
        if RE_EMPRESA_SUFIJO.search(str(l.get('texto', ''))):
            empresa = str(l.get('texto', '')).strip()
            restantes.remove(l)
            break
    cargo = str(restantes[0].get('texto', '')).strip() if restantes else ''
    return nombre, cargo, empresa


def tarjeta(ruta_imagen, idioma=None, avisar=print):
    """Dict `{"nombre","cargo","empresa","telefono","correo","web"}` (cadena
    vacía en lo que no se reconoció, nunca inventado)."""
    r = leer(ruta_imagen, idioma=idioma, avisar=avisar)
    telefono, correo, web, resto = _clasificar_lineas(r['lineas'])
    nombre, cargo, empresa = _nombre_cargo_empresa(resto)
    return {'nombre': nombre, 'cargo': cargo, 'empresa': empresa, 'telefono': telefono, 'correo': correo, 'web': web}


def _escapar_vcard(v):
    return (v or '').replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\n', '\\n')


def vcard_de(datos):
    """vCard 3.0 (RFC 2426) a partir del dict de `tarjeta()`. Un campo vacío en
    `datos` no aparece como línea en el `.vcf` (ninguna línea `TEL:` vacía) — no
    hay valor inventado que poner. `N` no separa nombre y apellido (el OCR no
    los distingue): el nombre completo va en el hueco de "nombre" de pila,
    declarado, no fingido como un apellido correcto."""
    nombre = datos.get('nombre') or ''
    lineas = ['BEGIN:VCARD', 'VERSION:3.0']
    lineas.append(f'N:;{_escapar_vcard(nombre)};;;')
    lineas.append(f'FN:{_escapar_vcard(nombre) or "(sin nombre reconocido)"}')
    if datos.get('empresa'):
        lineas.append(f'ORG:{_escapar_vcard(datos["empresa"])}')
    if datos.get('cargo'):
        lineas.append(f'TITLE:{_escapar_vcard(datos["cargo"])}')
    if datos.get('telefono'):
        lineas.append(f'TEL;TYPE=CELL,VOICE:{_escapar_vcard(datos["telefono"])}')
    if datos.get('correo'):
        lineas.append(f'EMAIL;TYPE=INTERNET:{_escapar_vcard(datos["correo"])}')
    if datos.get('web'):
        web = datos['web']
        if not re.match(r'^https?://', web, re.I):
            web = 'http://' + web
        lineas.append(f'URL:{_escapar_vcard(web)}')
    lineas.append('END:VCARD')
    return '\r\n'.join(lineas) + '\r\n'


def _fuente(tam, negrita=False):
    """`arial.ttf`/`arialbd.ttf` si están (Windows los trae de serie); si no,
    la bitmap por defecto de Pillow — se ve peor pero no revienta."""
    for nombre in (('arialbd.ttf', 'Arial Bold.ttf') if negrita else ('arial.ttf', 'Arial.ttf')):
        try:
            return ImageFont.truetype(nombre, tam)
        except Exception:
            continue
    return ImageFont.load_default()


def componer_tarjeta_png(datos, ruta_salida):
    """Tarjeta `.png` compuesta con Pillow a partir del dict de `tarjeta()`: no
    reproduce el diseño original (no hay reconstrucción de eso), es una ficha
    de contacto limpia con lo reconocido; lo que falta dice "sin dato"."""
    ancho, alto = 900, 460
    img = Image.new('RGB', (ancho, alto), '#ffffff')
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, ancho, 110], fill='#1d3557')
    d.text((36, 32), datos.get('nombre') or 'sin dato', fill='#ffffff', font=_fuente(38, negrita=True))
    y = 128
    if datos.get('cargo'):
        d.text((36, y), datos['cargo'], fill='#1d3557', font=_fuente(22)); y += 32
    if datos.get('empresa'):
        d.text((36, y), datos['empresa'], fill='#444444', font=_fuente(22)); y += 32
    y += 16
    d.line([(36, y), (ancho - 36, y)], fill='#dddddd', width=2)
    y += 26
    f_campo = _fuente(20)
    for etiqueta, clave in (('Tel.', 'telefono'), ('Email', 'correo'), ('Web', 'web')):
        d.text((36, y), f'{etiqueta}: {datos.get(clave) or "sin dato"}', fill='#222222', font=f_campo)
        y += 32
    os.makedirs(os.path.dirname(os.path.abspath(ruta_salida)) or '.', exist_ok=True)
    img.save(ruta_salida)


# ───────────────────────────── manual: orden + limpieza + pasos ─────────────────────────────

_RE_PAGINA = (
    re.compile(r'\bp[aá]gina\s+(\d{1,4})\b', re.I),
    re.compile(r'\bpage\s+(\d{1,4})\b', re.I),
    re.compile(r'\b(\d{1,4})\s*/\s*\d{1,4}\b'),
    re.compile(r'^\s*[-–—]?\s*(\d{1,4})\s*[-–—]?\s*$'),
)


def _detectar_pagina(lineas_texto):
    """Primer patrón (por orden de especificidad: "página N" antes que un
    número suelto) que acierte en CUALQUIER línea de la página. `None` si
    ninguno acierta — declarado: no se adivina un número a partir de nada."""
    for pat in _RE_PAGINA:
        for t in lineas_texto:
            m = pat.search(t.strip())
            if m:
                try:
                    return int(m.group(1))
                except ValueError:
                    pass
    return None


def _unir_guiones_de_corte(lineas_texto):
    """Junta una palabra partida por un guion de corte a final de línea
    («informa-» + «ción...» → «información...»): solo cuando la línea acaba en
    un guion pegado a una letra (nunca un guion suelto, ni un rango «10-20»).
    Se pega SIN espacio a la línea siguiente entera (a veces el OCR ya trae ahí
    el resto de una frase distinta, y no hay forma de saberlo sin adivinar)."""
    out = []
    pendiente = ''
    for t in lineas_texto:
        actual = (pendiente + t) if pendiente else t
        pendiente = ''
        m = re.match(r'^(.*[a-zA-ZÁÉÍÓÚÑÜáéíóúñü])-$', actual.strip())
        if m:
            pendiente = m.group(1)
            continue
        out.append(actual)
    if pendiente:
        out.append(pendiente)
    return out


_RE_PASO_NUM = re.compile(r'^\s*(\d{1,3})[.)]\s+(.*\S)\s*$')
_RE_PASO_PALABRA = re.compile(r'^\s*(?:paso|step)\s*(\d{1,3})?\s*[:.\-]?\s*(.*\S)\s*$', re.I)
_RE_VINETA = re.compile(r'^\s*[•●▪○\-\*]\s+(.*\S)\s*$')


def _formatear_paso(linea, contador):
    """(línea_reescrita, es_paso). Reescribe lo detectado a una lista markdown
    consistente («1. …» o «- …»); lo demás vuelve tal cual, sin tocar."""
    m = _RE_PASO_NUM.match(linea)
    if m:
        return f'{int(m.group(1))}. {m.group(2)}', True
    m = _RE_PASO_PALABRA.match(linea)
    if m:
        n = int(m.group(1)) if m.group(1) else contador
        return f'{n}. {m.group(2)}', True
    m = _RE_VINETA.match(linea)
    if m:
        return f'- {m.group(1)}', True
    return linea, False


def _cuerpo_pagina_md(lineas_texto):
    unidas = _unir_guiones_de_corte(lineas_texto)
    out, contador = [], 1
    for l in unidas:
        l = l.strip()
        if not l:
            continue
        formateada, es_paso = _formatear_paso(l, contador)
        if es_paso:
            contador += 1
        out.append(formateada)
    return '\n'.join(out)


def manual(rutas_imagenes, idioma=None, avisar=print):
    """Markdown de T4.3 (ver docstring del módulo): OCR de cada imagen, orden
    por página SI TODAS la dan, guiones de corte unidos, pasos detectados
    reescritos como lista — el resto del texto tal cual. No resume nada."""
    paginas = []
    for i, ruta in enumerate(rutas_imagenes):
        r = leer(ruta, idioma=idioma, avisar=avisar)
        textos = [str(l.get('texto', '')) for l in r['lineas']]
        paginas.append({'indice': i, 'ruta': ruta, 'numero': _detectar_pagina(textos),
                        'cuerpo': _cuerpo_pagina_md(textos)})
    if len(paginas) > 1 and all(p['numero'] is not None for p in paginas):
        paginas.sort(key=lambda p: p['numero'])
    md = ['# Manual (OCR, texto limpio y ordenado — sin resumir)', '']
    for p in paginas:
        titulo = f"página {p['numero']}" if p['numero'] is not None else f"imagen {p['indice'] + 1}"
        md.append(f'## {titulo} — `{os.path.basename(p["ruta"])}`')
        md.append('')
        md.append(p['cuerpo'] or '_(sin texto reconocido)_')
        md.append('')
    return '\n'.join(md)


# ───────────────────────────── registro de uso ─────────────────────────────

def _log(mem, verbo, detalle):
    with open(os.path.join(mem, 'lectura_visual.log'), 'a', encoding='utf-8') as fh:
        fh.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")}\t{verbo}\t{detalle}\n')


# ───────────────────────────── CLI ─────────────────────────────

def _tomar_valor(resto, i, clave, opts, conversor=str):
    if i + 1 < len(resto) and not resto[i + 1].startswith('--'):
        try:
            opts[clave] = conversor(resto[i + 1])
        except ValueError:
            print(f'--{clave} necesita un valor válido, no "{resto[i + 1]}"')
            return i, False
        return i + 1, True
    print(f'--{clave} necesita un valor')
    return i, False


def _cli_texto(resto, mem):
    opts = {'portapapeles': False, 'salida': None}
    imagen = None
    i = 0
    while i < len(resto):
        a = resto[i]
        if a == '--portapapeles':
            opts['portapapeles'] = True
        elif a == '--salida':
            i, ok = _tomar_valor(resto, i, 'salida', opts)
            if not ok:
                return 1
        elif not a.startswith('--') and imagen is None:
            imagen = a
        else:
            print(f'argumento no reconocido: {a}')
            return 1
        i += 1
    if imagen is None:
        print('falta la imagen')
        return 1
    if not os.path.isfile(imagen):
        print(f'no existe: {imagen}')
        return 2
    try:
        contenido = texto(imagen)
    except SinMotorOCR as e:
        print(str(e))
        return 2
    except Exception as e:
        print(f'sin texto: {type(e).__name__} {e}')
        return 2
    print(contenido)
    if opts['salida']:
        with open(opts['salida'], 'w', encoding='utf-8') as fh:
            fh.write(contenido + ('\n' if contenido else ''))
        print(f'guardado: {opts["salida"]}')
    if opts['portapapeles']:
        if copiar_portapapeles(contenido):
            print('copiado al portapapeles')
        else:
            print('sin portapapeles: no se encontró ningún instrumento (Set-Clipboard/clip.exe/pbcopy/xclip)')
    _log(mem, 'texto', f'{imagen}\t{len(contenido)} caracteres')
    return 0


def _cli_fotocopia(resto, mem):
    opts = {'salida': None, 'modo': None, 'escaner': False, 'camara': None, 'paginas': 1}
    imagen = None
    i = 0
    while i < len(resto):
        a = resto[i]
        if a == '--escaner':
            opts['escaner'] = True
        elif a == '--camara':
            opts['camara'] = 0
            if i + 1 < len(resto) and re.fullmatch(r'-?\d+', resto[i + 1] or ''):
                opts['camara'] = int(resto[i + 1])
                i += 1
        elif a in ('--color', '--gris', '--umbral'):
            if opts['modo'] is not None:
                print('usa como mucho uno de --color/--gris/--umbral')
                return 1
            opts['modo'] = a[2:]
        elif a == '--paginas':
            i, ok = _tomar_valor(resto, i, 'paginas', opts, conversor=int)
            if not ok:
                return 1
        elif a == '--salida':
            i, ok = _tomar_valor(resto, i, 'salida', opts)
            if not ok:
                return 1
        elif not a.startswith('--') and imagen is None:
            imagen = a
        else:
            print(f'argumento no reconocido: {a}')
            return 1
        i += 1

    # vía normal: un fichero O --camara, nunca las dos, nunca ninguna
    # (--escaner es una fuente OPCIONAL MÁS, ver docstring del módulo: nunca basta sola).
    if imagen is not None and opts['camara'] is not None:
        print('usa la imagen O --camara, no las dos')
        return 1
    if imagen is None and opts['camara'] is None:
        print('falta la imagen (o usa --camara)')
        return 1
    if opts['paginas'] < 1:
        print('--paginas debe ser 1 o más')
        return 1
    if opts['paginas'] > 1 and opts['camara'] is None:
        print('--paginas (más de 1) solo vale con --camara: un fichero ya dado no tiene "página siguiente"')
        return 1
    if opts['paginas'] > 1 and opts['salida'] and os.path.splitext(opts['salida'])[1].lower() != '.pdf':
        print('con --paginas más de 1 usa --salida algo.pdf (un PNG no admite varias páginas)')
        return 1
    if not _CV2_OK:
        print('sin dato: instala opencv-python y numpy (pip install opencv-python numpy) para "fotocopia"')
        return 2

    modo = opts['modo'] or 'color'
    origen = None
    if opts['escaner']:
        ruta_captura = os.path.join(mem, f'escaner_{time.strftime("%Y%m%d_%H%M%S")}.bmp')
        res = escanear_wia(ruta_captura)
        if res.get('ok'):
            origen = 'escaner'
            ruta_desde_escaner = res.get('ruta') or ruta_captura
        else:
            print('sin escáner: uso la cámara o un fichero')

    paginas_np = []
    recortado_alguna = False
    try:
        if origen == 'escaner':
            img = cv2.imread(ruta_desde_escaner)
            if img is None:
                print(f'no se pudo leer como imagen: {ruta_desde_escaner}')
                return 2
            final, recortado = _procesar_documento(img, modo=modo)
            paginas_np.append(final)
            recortado_alguna = recortado
            entrada_log = ruta_desde_escaner
        elif opts['camara'] is not None:
            origen = 'camara'
            res = capturar_camara(opts['camara'], n=opts['paginas'])
            if not res.get('ok'):
                print(res.get('motivo') or 'sin dato: no hay cámara')
                return 2
            for frame in res['fotogramas']:
                final, recortado = _procesar_documento(frame, modo=modo)
                paginas_np.append(final)
                recortado_alguna = recortado_alguna or recortado
            entrada_log = f'cámara {opts["camara"]} ({len(paginas_np)} página(s))'
        else:
            origen = 'fichero'
            if not os.path.isfile(imagen):
                print(f'no existe: {imagen}')
                return 2
            img = cv2.imread(imagen)
            if img is None:
                print(f'no se pudo leer como imagen: {imagen}')
                return 2
            final, recortado = _procesar_documento(img, modo=modo)
            paginas_np.append(final)
            recortado_alguna = recortado
            entrada_log = imagen
    except Exception as e:
        print(f'sin fotocopia: {type(e).__name__} {e}')
        return 2

    if opts['salida']:
        salida = opts['salida']
    elif origen == 'fichero':
        salida = os.path.splitext(os.path.abspath(imagen))[0] + '_fotocopia.png'
    else:
        ext = '.pdf' if len(paginas_np) > 1 else '.png'
        salida = os.path.join(mem, f'fotocopia_{time.strftime("%Y%m%d_%H%M%S")}{ext}')

    try:
        _guardar_paginas(paginas_np, salida)
    except Exception as e:
        print(f'sin fotocopia: {type(e).__name__} {e}')
        return 2

    print(json.dumps({'entrada': entrada_log, 'salida': salida, 'modo': modo,
                       'recortado': recortado_alguna, 'paginas': len(paginas_np)}, ensure_ascii=False))
    _log(mem, 'fotocopia',
         f'{entrada_log}\t{salida}\tmodo={modo}\trecortado={recortado_alguna}\tpaginas={len(paginas_np)}')
    return 0


def _cli_tarjeta(resto, mem):
    opts = {'salida': None}
    imagen = None
    i = 0
    while i < len(resto):
        a = resto[i]
        if a == '--salida':
            i, ok = _tomar_valor(resto, i, 'salida', opts)
            if not ok:
                return 1
        elif not a.startswith('--') and imagen is None:
            imagen = a
        else:
            print(f'argumento no reconocido: {a}')
            return 1
        i += 1
    if imagen is None:
        print('falta la imagen')
        return 1
    if not os.path.isfile(imagen):
        print(f'no existe: {imagen}')
        return 2
    if not _PIL_OK:
        print('sin dato: instala Pillow (pip install Pillow) para "tarjeta"')
        return 2
    try:
        datos = tarjeta(imagen)
    except SinMotorOCR as e:
        print(str(e))
        return 2
    except Exception as e:
        print(f'sin tarjeta: {type(e).__name__} {e}')
        return 2
    base = opts['salida'] or (os.path.splitext(os.path.abspath(imagen))[0] + '_tarjeta')
    ruta_vcf, ruta_png = base + '.vcf', base + '.png'
    os.makedirs(os.path.dirname(os.path.abspath(ruta_vcf)) or '.', exist_ok=True)
    with open(ruta_vcf, 'w', encoding='utf-8', newline='') as fh:
        fh.write(vcard_de(datos))
    componer_tarjeta_png(datos, ruta_png)
    faltan = [k for k in ('nombre', 'telefono', 'correo') if not datos.get(k)]
    if faltan:
        print('sin dato en: ' + ', '.join(faltan) + ' (no se inventa)')
    print(json.dumps({'vcf': ruta_vcf, 'png': ruta_png, **datos}, ensure_ascii=False))
    _log(mem, 'tarjeta', f'{imagen}\t{ruta_vcf}\t{ruta_png}')
    return 0


def _cli_manual(resto, mem):
    opts = {'salida': None}
    imagenes = []
    i = 0
    while i < len(resto):
        a = resto[i]
        if a == '--salida':
            i, ok = _tomar_valor(resto, i, 'salida', opts)
            if not ok:
                return 1
        elif not a.startswith('--'):
            imagenes.append(a)
        else:
            print(f'argumento no reconocido: {a}')
            return 1
        i += 1
    if not imagenes:
        print('falta al menos una imagen')
        return 1
    faltantes = [im for im in imagenes if not os.path.isfile(im)]
    if faltantes:
        print('no existe(n): ' + ', '.join(faltantes))
        return 2
    try:
        md = manual(imagenes)
    except SinMotorOCR as e:
        print(str(e))
        return 2
    except Exception as e:
        print(f'sin manual: {type(e).__name__} {e}')
        return 2
    salida = opts['salida'] or os.path.join(os.path.dirname(os.path.abspath(imagenes[0])), 'manual.md')
    os.makedirs(os.path.dirname(os.path.abspath(salida)) or '.', exist_ok=True)
    with open(salida, 'w', encoding='utf-8') as fh:
        fh.write(md)
    print(f'guardado: {salida} ({len(imagenes)} imagen(es))')
    _log(mem, 'manual', f'{len(imagenes)} imagenes\t{salida}')
    return 0


def _cli(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 1
    verbo, resto = argv[0], list(argv[1:])
    proj, mem = rutas.resolver(resto, {})
    if '--proyecto' in resto:  # ya resuelto arriba: fuera también su valor (mismo criterio que imagen.py)
        i = resto.index('--proyecto')
        del resto[i:i + 2]
    if verbo == 'texto':
        return _cli_texto(resto, mem)
    if verbo == 'fotocopia':
        return _cli_fotocopia(resto, mem)
    if verbo == 'tarjeta':
        return _cli_tarjeta(resto, mem)
    if verbo == 'manual':
        return _cli_manual(resto, mem)
    print('verbo desconocido:', verbo, '(usa texto/fotocopia/tarjeta/manual)')
    return 1


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    sys.exit(_cli(sys.argv[1:]))
