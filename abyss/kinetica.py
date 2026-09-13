# -*- coding: utf-8 -*-
"""Kinetica: de UNA foto de un objeto compuesto a un despiece por COMPONENTES REALES (no capas
de nitidez, a diferencia del despiece 2,5D de `volumen.py`) que la mano maneja en 3D.

Uso:
    python kinetica.py <imagen> [--regiones f.json] [--fichas f.json] [--salida DIR]
                       [--puerto 8811] [--sin-abrir] [--solo-montar] [--rellenar]
                       [--quitar-fondo | --fondo-tal-cual]
                       [--reconocer [--permitir-nombre-fichero] | --reconocimiento f.json]
Dos caminos, ninguno inventa qué hay en la foto. `--regiones f.json` (recomendado): lista de
`{clave, titulo, poligono:[[x,y],...], rumbo:[x,y,z], orden, prioridad}` puesta a mano
(reconocimiento asistido, no un detector entrenado); `cv2.grabCut` decide el borde de cada
pieza sembrado desde el polígono, con núcleo/holgura que ESCALAN al lado corto del recuadro
(18%/6%, mínimo 3/2 px) para no depender del tamaño de la foto. Solapes: gana la `prioridad`
más alta. Defaults: `titulo`=`clave`, `rumbo`=`[0, 0, 0.3]`, `orden`=posición en la lista,
`prioridad`=0. Sin `--regiones`: componentes conexos del primer plano (`grabCut` +
`connectedComponentsWithStats`, hasta `AUTOMATICO_MAX_PIEZAS` mayores que superen el 1% del
área); se declara automático en `piezas.json` (`procedencia.modo`), sin nombre real y peor que
con regiones — nunca se finge reconocer el producto; `rumbo` = vector centro-de-foto→
centroide; `--rellenar` no aplica aquí. `--rellenar` (solo con `--regiones`): píxeles tapados
por una pieza de más prioridad se reconstruyen con `cv2.inpaint` — INVENTADOS, no fotografiados;
se cuentan en `relleno_px` y se declaran en `procedencia.relleno`.
`--salida DIR` (por defecto `<carpeta de la imagen>/<base>_kinetica/`) monta la carpeta que
espera `abyss/plantillas/kinetica.html` (leída, nunca modificada):

    piezas/piezas.json     — ancho, alto, original, procedencia, piezas[] con clave/titulo/
                             orden/caja_px/centro/tam_frac/rumbo/png/area_px/relleno_px
    piezas/<clave>.png     — cada componente recortado, con canal alfa
    original.jpg            — copia de la imagen de entrada, recodificada a JPEG si no lo era
    three.min.js / index.html / gestos_comun.js — vendor, plantilla y vocabulario de la mano
    fichas.json (opcional) — copia de `--fichas f.json`; sin ella, "sin dato con fuente"
    mp/                      — MediaPipe Tasks Vision (`vision_bundle.mjs`, `wasm/`, `.task`)

`mp/` nunca se inventa: si `abyss/vendor/mp/vision_bundle.mjs` no existe, no se copia nada de
manos y se imprime el procedimiento exacto (`MENSAJE_MEDIAPIPE`: `python instalar.py --manos`,
necesita red en otra máquina); se escribe un `vision_bundle.mjs` SUSTITUTO que carga la página
y solo falla, con mensaje claro, si de verdad se enciende la cámara.

Servidor SOLO en `127.0.0.1`, con las cabeceras COOP/COEP que el `.wasm` de MediaPipe necesita
para cargar como módulo ES (por eso no se abre con `file://`: CORS lo bloquea). Abre el
navegador salvo `--sin-abrir`; `--solo-montar` deja la carpeta lista sin servir nada. Dependencia
obligatoria: OpenCV (`cv2`), `numpy` y Pillow — sin alguna, dice qué instalar y sale con código 2
antes de tocar la imagen. Guión de fichero a fichero (como `render3d.py`/`volumen.py`/
`taller.py`): no llama a `rutas.resolver()`, no lee stdin, no escribe en `mem`.
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

try:
    from . import puerta_local
except ImportError:
    import puerta_local

try:
    import numpy as np
    import cv2
    from PIL import Image
except ImportError as _e:
    print(f'sin dato: pip install opencv-python numpy Pillow [falta {_e.name}]')
    sys.exit(2)

CODE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(CODE, 'vendor')
PLANTILLA = os.path.join(CODE, 'plantillas', 'kinetica.html')
MP_VENDOR = os.path.join(VENDOR, 'mp')

MARGEN_GRABCUT = 0.05        # igual que volumen.mascara_primer_plano: 5% de margen por lado
ITER_GRABCUT = 5
AUTOMATICO_MAX_PIEZAS = 8
AUTOMATICO_AREA_MIN_FRAC = 0.01   # componente por debajo de esto del área de la foto: ruido
PUERTO_POR_DEFECTO = 8811

AVISO_AUTOMATICO = (
    'sin --regiones: separación AUTOMÁTICA por componentes conexos del primer plano '
    '(GrabCut con rectángulo + connectedComponents). Las piezas NO tienen nombre real y '
    'el resultado es peor que dando regiones a mano: esto separa bultos, no reconoce el '
    'producto.'
)

MENSAJE_MEDIAPIPE = (
    "Para el control por gestos con las manos activo (la página sirve igual sin esto, solo\n"
    "sin manos), este paquete ya trae el comando para bajarlo, una vez y con red:\n"
    "  python instalar.py --manos\n"
    "Baja a abyss/vendor/mp/ los seis ficheros de MediaPipe Tasks Vision (JS+wasm de\n"
    "jsdelivr, el modelo de manos de storage.googleapis.com) — SOLO los que falten, con\n"
    "un aviso limpio y sin traza si no hay red. Hecho eso una vez, cada\n"
    "'python kinetica.py <imagen> ...' futuro copia mp/ solo."
)

_STUB_VISION_BUNDLE = (
    "// Sustituto SIN MediaPipe de verdad: abyss/vendor/mp/ no existe en esta instalación\n"
    "// (ver el aviso que imprimió kinetica.py al montar esta carpeta). Deja cargar la\n"
    "// página entera y solo falla, con un mensaje claro, cuando de verdad se intenta\n"
    "// encender la cámara — la propia página ya captura ese error y lo enseña en pantalla.\n"
    "export class FilesetResolver {\n"
    "  static async forVisionTasks() {\n"
    "    throw new Error('MediaPipe no está instalado en este servidor (falta abyss/vendor/mp/)');\n"
    "  }\n"
    "}\n"
    "export class HandLandmarker {\n"
    "  static async createFromOptions() {\n"
    "    throw new Error('MediaPipe no está instalado en este servidor (falta abyss/vendor/mp/)');\n"
    "  }\n"
    "}\n"
)


# ───────────────────────────────── imagen y máscaras ─────────────────────────────────

def _leer_imagen(ruta):
    """`(bgr, alfa)`: `bgr` siempre de 3 canales con la orientación EXIF ya aplicada
    (`IMREAD_COLOR`; `IMREAD_UNCHANGED` no la aplica y puede dar canales/bit-depth que
    `grabCut` rechaza). `alfa` sale de una segunda lectura, aceptada solo si encaja con
    `bgr` — la silueta real si el fondo ya se quitó de antemano; ver `montar()`."""
    ruta = os.path.abspath(ruta)
    if not os.path.isfile(ruta):
        raise FileNotFoundError(f'no existe: {ruta}')
    img = cv2.imread(ruta, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f'no se pudo leer como imagen: {ruta}')
    crudo = cv2.imread(ruta, cv2.IMREAD_UNCHANGED)
    alfa = None
    if (crudo is not None and crudo.ndim == 3 and crudo.shape[2] == 4
            and crudo.dtype == np.uint8 and crudo.shape[:2] == img.shape[:2]):
        alfa = crudo[:, :, 3]
    return img, alfa


def _mascara_de_poligono(alto, ancho, poligono):
    m = np.zeros((alto, ancho), np.uint8)
    cv2.fillPoly(m, [np.array(poligono, np.int32)], 255)
    return m


def _mascara_cruda_de_region(img, region, iteraciones=ITER_GRABCUT):
    """Máscara binaria de UNA región, antes de resolver solapes con las demás (ver
    docstring del módulo: núcleo/holgura escalados al lado corto de SU propio recuadro,
    no constantes fijas). El borde lo decide `cv2.grabCut` sembrado con máscara, nunca el
    polígono a mano tal cual."""
    alto, ancho = img.shape[:2]
    propia = _mascara_de_poligono(alto, ancho, region['poligono'])
    xs = [p[0] for p in region['poligono']]
    ys = [p[1] for p in region['poligono']]
    lado_corto = max(4.0, min(max(xs) - min(xs), max(ys) - min(ys)))
    k_nucleo = max(3, int(round(lado_corto * 0.18)))
    holgura = max(2, int(round(lado_corto * 0.06)))

    nucleo = cv2.erode(propia, np.ones((k_nucleo, k_nucleo), np.uint8), iterations=1)
    if not nucleo.any():
        nucleo = propia.copy()  # región demasiado fina para la erosión: todo el polígono es núcleo
    tope = cv2.dilate(propia, np.ones((holgura * 2 + 1, holgura * 2 + 1), np.uint8), iterations=1)

    mascara = np.full((alto, ancho), cv2.GC_PR_BGD, np.uint8)
    mascara[propia > 0] = cv2.GC_PR_FGD
    mascara[nucleo > 0] = cv2.GC_FGD
    mascara[tope == 0] = cv2.GC_BGD

    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(img, mascara, None, bgd, fgd, iteraciones, cv2.GC_INIT_WITH_MASK)
    fg = np.where((mascara == cv2.GC_FGD) | (mascara == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    fg[tope == 0] = 0

    n, etiquetas, estad, _ = cv2.connectedComponentsWithStats(fg, 8)
    if n > 1:  # el trozo conectado más grande: quita motas sueltas
        mayor = 1 + int(np.argmax(estad[1:, cv2.CC_STAT_AREA]))
        fg = np.where(etiquetas == mayor, 255, 0).astype(np.uint8)
    return cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))


def _resolver_solapes(crudas, regiones):
    """Donde dos máscaras crudas se pisan, gana la de `prioridad` más alta (estrictamente
    mayor, igual que el guión de referencia): con prioridades iguales ninguna cede."""
    finales = {}
    for r in regiones:
        fg = crudas[r['clave']].copy()
        for o in regiones:
            if o['clave'] != r['clave'] and o['prioridad'] > r['prioridad']:
                fg[crudas[o['clave']] > 0] = 0
        n, etiquetas, estad, _ = cv2.connectedComponentsWithStats(fg, 8)
        if n > 1:  # restar puede partir la pieza en trozos: se queda el mayor
            mayor = 1 + int(np.argmax(estad[1:, cv2.CC_STAT_AREA]))
            fg = np.where(etiquetas == mayor, 255, 0).astype(np.uint8)
        finales[r['clave']] = fg
    return finales


def _recorte_de_mascara(img_bgr, fg):
    """`(rgba recortado a su caja, caja_px, área_px)`, o `None` si la máscara quedó
    vacía. El borde alfa se suaviza (`GaussianBlur` 5×5) para no dejar dientes de sierra."""
    ys, xs = np.where(fg > 0)
    if xs.size == 0:
        return None
    alfa = cv2.GaussianBlur(fg, (5, 5), 0)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    rgba = np.dstack([rgb, alfa])[y0:y1 + 1, x0:x1 + 1]
    return rgba, (x0, y0, x1, y1), int((fg > 0).sum())


def _rellenar_ocultos(img_bgr, crudas, finales, regiones):
    """Píxeles que la máscara CRUDA de una región tenía y la FINAL (tras resolver solapes)
    perdió —tapados por una pieza de más prioridad—: con `--rellenar` se reconstruyen con
    `cv2.inpaint` (Telea), INVENTADOS, no fotografiados. Devuelve
    `(imagen_por_clave_rellenada, relleno_px_por_clave)`; un hueco <50 px no se toca."""
    rellenos_img = {}
    conteo = {r['clave']: 0 for r in regiones}
    base = img_bgr.copy()
    for r in regiones:
        clave = r['clave']
        hueco = ((crudas[clave] > 0) & (finales[clave] == 0)).astype(np.uint8) * 255
        hueco = cv2.dilate(hueco, np.ones((5, 5), np.uint8), iterations=1)
        n_px = int((hueco > 0).sum())
        if n_px < 50:
            continue
        parche = cv2.inpaint(base, hueco, 6, cv2.INPAINT_TELEA)
        rellenos_img[clave] = np.where(hueco[:, :, None] > 0, parche, img_bgr)
        finales[clave] = np.maximum(finales[clave], hueco)
        conteo[clave] = n_px
    return rellenos_img, conteo


def _leer_regiones(ruta):
    with open(os.path.abspath(ruta), encoding='utf-8') as fh:
        datos = json.load(fh)
    if not isinstance(datos, list) or not datos:
        raise ValueError('el fichero de regiones debe ser una lista no vacía de objetos')
    regiones = []
    for i, r in enumerate(datos):
        if not isinstance(r, dict) or 'clave' not in r or 'poligono' not in r:
            raise ValueError(f'región #{i}: faltan "clave" y/o "poligono"')
        poligono = r['poligono']
        if not isinstance(poligono, list) or len(poligono) < 3:
            raise ValueError(f'región "{r["clave"]}": "poligono" necesita al menos 3 puntos [x,y]')
        regiones.append({
            'clave': str(r['clave']),
            'titulo': str(r.get('titulo') or r['clave']),
            'poligono': [(float(p[0]), float(p[1])) for p in poligono],
            'rumbo': [float(v) for v in (r.get('rumbo') or [0.0, 0.0, 0.3])],
            'orden': int(r['orden']) if 'orden' in r else i,
            'prioridad': int(r.get('prioridad', 0)),
        })
    return regiones


def _fondo_liso(img, tolerancia=16, minimo_frac=0.25):
    """(máscara del objeto, descripción) si la foto tiene fondo de UN solo color; si no,
    (None, motivo). Si la foto ya trae el fondo quitado (ver `fondo.py`), la silueta se
    mide restando el color de fondo en vez de estimarse: cada píxel del objeto cae en
    ALGUNA pieza y no queda nada que reconstruir."""
    alto, ancho = img.shape[:2]
    c = min(40, alto // 4, ancho // 4)
    esq = np.concatenate([img[:c, :c].reshape(-1, 3), img[:c, -c:].reshape(-1, 3),
                          img[-c:, :c].reshape(-1, 3), img[-c:, -c:].reshape(-1, 3)])
    desv = float(esq.std(axis=0).max())
    if desv > 6:
        return None, 'las esquinas no son de un solo color (desviación %.1f)' % desv
    color = np.median(esq, axis=0)
    fondo = np.abs(img.astype(np.int16) - color).sum(axis=2) <= tolerancia
    if fondo.mean() < minimo_frac:
        return None, 'ese color solo ocupa el %.0f%% del cuadro' % (100 * fondo.mean())
    obj = (~fondo).astype(np.uint8) * 255
    # el objeto puede tener zonas casi del color del fondo (metal claro sobre blanco):
    # se cierran rellenando desde una esquina, que sí es fondo con seguridad
    relleno = obj.copy()
    cv2.floodFill(relleno, np.zeros((alto + 2, ancho + 2), np.uint8), (0, 0), 255)
    obj = obj | cv2.bitwise_not(relleno)
    obj = cv2.morphologyEx(obj, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, et, est, _ = cv2.connectedComponentsWithStats(obj, 8)
    if n > 1:
        mayor = 1 + int(np.argmax(est[1:, cv2.CC_STAT_AREA]))
        obj = np.where(et == mayor, 255, 0).astype(np.uint8)
    return obj, ('fondo liso %s, %.0f%% del cuadro' %
                 (tuple(int(v) for v in color), 100 * fondo.mean()))


def _reparto_por_regiones(obj, regiones, alto, ancho):
    """Reparte CADA píxel del objeto entre las piezas: dentro de un polígono manda la
    `prioridad` más alta y, fuera de todos, va a la región más cercana. Así no se pierde
    ni un píxel del objeto — lo que antes se veía «comido» era justo eso."""
    etiqueta = np.full((alto, ancho), -1, np.int16)
    for i, r in sorted(enumerate(regiones), key=lambda kv: kv[1]['prioridad']):
        etiqueta[_mascara_de_poligono(alto, ancho, r['poligono']) > 0] = i
    huerfanos = (obj > 0) & (etiqueta < 0)
    if huerfanos.any():
        mejor = np.full((alto, ancho), np.inf, np.float32)
        for i, r in enumerate(regiones):
            m = _mascara_de_poligono(alto, ancho, r['poligono'])
            d = cv2.distanceTransform((m == 0).astype(np.uint8), cv2.DIST_L2, 3)
            etiqueta[huerfanos & (d < mejor)] = i
            mejor = np.minimum(mejor, d)
    salida = {}
    for i, r in enumerate(regiones):
        fg = ((etiqueta == i) & (obj > 0)).astype(np.uint8) * 255
        n, et, est, _ = cv2.connectedComponentsWithStats(fg, 8)
        if n > 1:
            mayor = 1 + int(np.argmax(est[1:, cv2.CC_STAT_AREA]))
            fg = np.where(et == mayor, 255, 0).astype(np.uint8)
        salida[r['clave']] = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    return salida


def _separar_manual(img, regiones, rellenar, avisar, obj_conocido=None):
    """`obj_conocido`, si se da, es `(mascara, nota)` con una silueta YA exacta (por
    ejemplo, del canal alfa de la imagen de entrada — ver `montar()`): se usa tal cual y
    no se vuelve a calcular con `_fondo_liso`."""
    alto, ancho = img.shape[:2]
    obj, nota = obj_conocido if obj_conocido is not None else _fondo_liso(img)
    if obj is not None:
        avisar('silueta: %s -> exacta, sin GrabCut' % nota)
        crudas = _reparto_por_regiones(obj, regiones, alto, ancho)
        finales = dict(crudas)          # el reparto ya es excluyente: no hay solapes
    else:
        avisar('silueta: %s -> se estima con GrabCut sembrado (mejor resultado si la '
               'foto viene sin fondo: python fondo.py <imagen>)' % nota)
        crudas = {r['clave']: _mascara_cruda_de_region(img, r) for r in regiones}
        finales = _resolver_solapes(crudas, regiones)
    rellenos_img, conteo = {}, {r['clave']: 0 for r in regiones}
    if rellenar:
        rellenos_img, conteo = _rellenar_ocultos(img, crudas, finales, regiones)

    piezas = []
    for r in regiones:
        fuente = rellenos_img.get(r['clave'], img)
        rec = _recorte_de_mascara(fuente, finales[r['clave']])
        if rec is None:
            avisar(f'región "{r["clave"]}": GrabCut no dejó ningún píxel, se omite')
            continue
        rgba, caja, area = rec
        piezas.append({'clave': r['clave'], 'titulo': r['titulo'], 'orden': r['orden'],
                        'rumbo': r['rumbo'], 'rgba': rgba, 'caja_px': caja,
                        'area_px': area, 'relleno_px': conteo[r['clave']]})
    piezas.sort(key=lambda p: p['orden'])
    # el `orden` del fichero de regiones solo ORDENA (puede numerar 1,2,3 o dejar
    # huecos, ver docstring del módulo); la plantilla lo usa como índice denso 0..N-1,
    # así que aquí se reasigna a la posición final tras ordenar.
    for i, p in enumerate(piezas):
        p['orden'] = i
    return piezas


# ───────────────────────────── reconocer el producto, o no ───────────────────────────────
# Regla dura por defecto: el enlace oficial de una pieza SOLO puede salir de lo que se lee EN
# LA FOTO. El título de `fichas.json` lo escribe una persona; apoyarse en él sería presentar
# como reconocimiento un dato dictado. Si no se lee nada, no hay enlace, y se dice por qué.
#
# Un logotipo puede ser un DIBUJO que ningún OCR lee, sin que la marca sea un misterio para
# quien nombró el fichero. Por eso existe `permitir_nombre_fichero` (opt-in en `montar()`/
# `--permitir-nombre-fichero`, APAGADO por defecto): con él, si la foto no dio marca se mira
# TAMBIÉN el nombre del fichero — pero eso no es leer la foto y nunca se disfraza de tal; ese
# camino guarda como='nombre_fichero' y `por_que` dice que la marca vino del NOMBRE DEL
# FICHERO. Sin marca conocida tampoco ahí, sigue sin haber enlace. Ver `_reconocer_por_nombre`.
MARCAS = {
    # marca legible -> sitio oficial. Se amplía a mano; una marca que no esté aquí se
    # registra igualmente como "texto leído" pero sin enlace.
    'vivo': 'https://www.vivo.com',
    'zeiss': 'https://www.zeiss.com',
    'leica': 'https://leica-camera.com',
    'hasselblad': 'https://www.hasselblad.com',
    'sony': 'https://www.sony.com',
    'canon': 'https://global.canon',
    'nikon': 'https://www.nikon.com',
    'fujifilm': 'https://www.fujifilm.com',
    'audi': 'https://www.audi.com',
}


def _reconocer_por_nombre(ruta_imagen):
    """Tercer 'como', junto a 'ocr' y 'ocr_sin_marca': la marca (y el modelo, si el resto
    del nombre lo trae) salen del NOMBRE DEL FICHERO, nunca de la foto — un dato DICTADO
    por quien lo guardó, no un reconocimiento, y así lo dice siempre `por_que`. Solo se
    llama desde `_reconocer` cuando `permitir_nombre_fichero=True` (opt-in). Si el nombre
    no trae ninguna marca de `MARCAS`, no hay enlace y se dice por qué: nunca se adivina."""
    nombre = os.path.basename(ruta_imagen)
    base = os.path.splitext(nombre)[0]
    normalizado = re.sub(r'[^a-z0-9]+', ' ', base.lower()).strip()
    if not normalizado:
        return {'como': 'nombre_fichero', 'texto_leido': [], 'url': None,
                'marca': None, 'modelo': None,
                'por_que': ('el nombre del fichero ("%s") no tiene letras ni dígitos '
                            'aprovechables: no se le puede sacar ninguna marca' % nombre)}
    for marca, url in MARCAS.items():
        m = re.search(r'(?:^|\s)%s(?:\s|$)' % re.escape(marca), normalizado)
        if not m:
            continue
        resto = (normalizado[:m.start()] + ' ' + normalizado[m.end():]).split()
        modelo = ' '.join(resto) or None
        return {'como': 'nombre_fichero',
                'texto_leido': [{'pieza': '-', 'texto': nombre}],
                'url': url, 'marca': marca, 'modelo': modelo,
                'por_que': ('marca tomada del NOMBRE DEL FICHERO ("%s"), NO leída en la '
                            'foto: el enlace es el sitio oficial de %s. %s'
                            % (nombre, marca,
                               ('el modelo también sale del nombre del fichero, no de la '
                                'foto: "%s"' % modelo) if modelo else
                               'del nombre no sale ningún modelo, solo la marca'))}
    return {'como': 'nombre_fichero', 'texto_leido': [{'pieza': '-', 'texto': nombre}],
            'url': None, 'marca': None, 'modelo': None,
            'por_que': ('el nombre del fichero ("%s") tampoco contiene ninguna marca de '
                        'MARCAS: no se enlaza a nada adivinado' % nombre)}


def _con_respaldo_de_nombre(sin_enlace, ruta_imagen, permitir_nombre_fichero):
    """Se llama en cada punto de `_reconocer` donde la foto no dio enlace. Con
    `permitir_nombre_fichero` apagado (por defecto) o sin `ruta_imagen`, devuelve
    `sin_enlace` tal cual; encendido, una marca en el nombre del fichero sustituye al
    resultado de la foto, y si tampoco hay nada en el nombre se añade una frase a
    `por_que` dejando constancia de que también se miró."""
    if not permitir_nombre_fichero or not ruta_imagen:
        return sin_enlace
    por_nombre = _reconocer_por_nombre(ruta_imagen)
    if por_nombre['url']:
        return por_nombre
    sin_enlace = dict(sin_enlace)
    sin_enlace['por_que'] = sin_enlace['por_que'] + '; ' + por_nombre['por_que']
    return sin_enlace


def _reconocer(piezas, img, avisar, ruta_imagen=None, permitir_nombre_fichero=False):
    """{'como', 'texto_leido', 'url', 'por_que'} — nunca inventa un enlace. `ruta_imagen`
    y `permitir_nombre_fichero` solo alimentan el respaldo por nombre de fichero (ver
    `_reconocer_por_nombre`/`_con_respaldo_de_nombre`); con `permitir_nombre_fichero=False`
    (el valor por defecto), solo cuenta lo que lee el OCR en la foto."""
    try:
        import importlib.util as _u
        _e = _u.spec_from_file_location('lectura_visual', os.path.join(CODE, 'lectura_visual.py'))
        lv = _u.module_from_spec(_e); _e.loader.exec_module(lv)
    except Exception as e:
        return _con_respaldo_de_nombre(
            {'como': 'ninguno', 'texto_leido': [], 'url': None,
             'por_que': 'no se pudo cargar el lector de texto: %s' % e},
            ruta_imagen, permitir_nombre_fichero)
    if not lv.motor_winrt_disponible() and not getattr(lv, '_tesseract_disponible', lambda: False)():
        return _con_respaldo_de_nombre(
            {'como': 'ninguno', 'texto_leido': [], 'url': None,
             'por_que': 'no hay ningún motor de OCR en esta máquina'},
            ruta_imagen, permitir_nombre_fichero)

    import tempfile
    leido = []
    for pz in piezas:
        rgba = pz['rgba']
        base = np.full(rgba.shape[:2] + (3,), 255, np.uint8)
        a = (rgba[:, :, 3:4].astype(np.float32) / 255.0)
        compuesta = (rgba[:, :, :3] * a + base * (1 - a)).astype(np.uint8)
        grande = cv2.resize(compuesta, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            ruta = f.name
        cv2.imwrite(ruta, cv2.cvtColor(grande, cv2.COLOR_RGB2BGR))
        try:
            texto = (lv.texto(ruta, avisar=lambda *a, **k: None) or '').strip()
        except Exception:
            texto = ''
        finally:
            try:
                os.unlink(ruta)
            except OSError:
                pass
        for linea in texto.splitlines():
            linea = linea.strip()
            if len(linea) >= 3:
                leido.append({'pieza': pz['clave'], 'texto': linea})

    if not leido:
        return _con_respaldo_de_nombre(
            {'como': 'ninguno', 'texto_leido': [], 'url': None,
             'por_que': ('el OCR no leyó ningún texto en las piezas. Los logotipos '
                         'estilizados no son texto para un OCR: sin texto no hay '
                         'reconocimiento, y sin reconocimiento no hay enlace')},
            ruta_imagen, permitir_nombre_fichero)
    # Límite de palabra, el mismo que usa `_reconocer_por_nombre`: una subcadena cruda
    # dejaría que una pieza con solo "AUDIO" impreso devolviera como='ocr' y el sitio
    # oficial de Audi, afirmando una lectura que nunca ocurrió — el fraude que esta
    # sección existe para impedir.
    junto = re.sub(r'[^a-z0-9]+', ' ', ' '.join(x['texto'] for x in leido).lower())
    for marca, url in MARCAS.items():
        if re.search(r'(?:^|\s)%s(?:\s|$)' % re.escape(marca), junto):
            return {'como': 'ocr', 'texto_leido': leido, 'url': url,
                    'por_que': ('se leyó «%s» en la propia foto; el enlace es el sitio '
                                'oficial de esa marca, no una página de producto: el '
                                'modelo concreto NO se ha leído' % marca)}
    return _con_respaldo_de_nombre(
        {'como': 'ocr_sin_marca', 'texto_leido': leido, 'url': None,
         'por_que': ('se leyó texto pero ninguna marca conocida; no se enlaza a ningún '
                     'sitio adivinado a partir de un texto suelto')},
        ruta_imagen, permitir_nombre_fichero)


def _leer_reconocimiento(ruta):
    """Reconocimiento hecho por quien mira la foto (el asistente), leído de un fichero.

    Formato: {"visto": ["texto o marca que se ve, y dónde"], "marca": "vivo", "modelo":
    null, "url": "https://...", "confianza": "alta|media|baja"}. Reglas no negociables:
    sin `visto` no se acepta nada (una afirmación sin evidencia no es reconocimiento); si
    `modelo` es null la url no puede apuntar a una página de producto concreto, y se anota
    que no se leyó; lo que se guarda incluye SIEMPRE quién lo dijo, para no confundirlo
    con una medida."""
    with open(ruta, encoding='utf-8') as fh:
        d = json.load(fh)
    visto = [str(v) for v in (d.get('visto') or []) if str(v).strip()]
    if not visto:
        raise ValueError('el fichero de reconocimiento no dice qué se vio ("visto" vacío): '
                         'sin evidencia no hay reconocimiento')
    url = d.get('url') or None
    return {'como': 'asistente', 'texto_leido': [{'pieza': '-', 'texto': v} for v in visto],
            'url': url, 'marca': d.get('marca'), 'modelo': d.get('modelo'),
            'confianza': d.get('confianza', 'sin declarar'),
            'por_que': ('lo reconoció el asistente MIRANDO la foto (%s). %s'
                        % ('; '.join(visto),
                           'El modelo concreto NO se leyó en la imagen: el enlace es de marca.'
                           if not d.get('modelo') else
                           'Modelo leído en la imagen: %s.' % d.get('modelo')))}


# ───────────────────────────────── separación automática ─────────────────────────────────

def _mascara_primer_plano_rect(img, avisar):
    """`cv2.grabCut` con un rectángulo (margen `MARGEN_GRABCUT` por lado) — misma
    heurística que `volumen.mascara_primer_plano`, repetida aquí para que este módulo
    siga siendo de fichero a fichero, sin acoplarse a `volumen.py`. Con 0 píxeles de
    primer plano (foto sin contraste), se avisa y se usa el rectángulo entero."""
    alto, ancho = img.shape[:2]
    mx, my = max(1, int(ancho * MARGEN_GRABCUT)), max(1, int(alto * MARGEN_GRABCUT))
    rect = (mx, my, max(1, ancho - 2 * mx), max(1, alto - 2 * my))
    mascara = np.zeros((alto, ancho), np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(img, mascara, rect, bgd, fgd, ITER_GRABCUT, cv2.GC_INIT_WITH_RECT)
    fg = (mascara == cv2.GC_FGD) | (mascara == cv2.GC_PR_FGD)
    if not fg.any():
        avisar('GrabCut no separó nada (foto sin contraste claro): se sigue con el '
               'recuadro central como primer plano, sin fingir un recorte más fino')
        fg = np.zeros((alto, ancho), dtype=bool)
        fg[rect[1]:rect[1] + rect[3], rect[0]:rect[0] + rect[2]] = True
    return fg


def _separar_automatico(img, avisar, max_piezas=AUTOMATICO_MAX_PIEZAS, obj_conocido=None):
    """`obj_conocido`, si se da, es una máscara YA exacta (por ejemplo, del canal alfa de
    la imagen de entrada — ver `montar()`): sustituye a `_mascara_primer_plano_rect`
    (GrabCut con rectángulo) en vez de adivinar el primer plano."""
    if obj_conocido is not None:
        avisar('separación automática: silueta exacta desde el canal alfa de entrada, sin GrabCut')
        fg = obj_conocido > 0
    else:
        fg = _mascara_primer_plano_rect(img, avisar)
    fuente = fg.astype(np.uint8) * 255
    n, etiquetas, estad, centroides = cv2.connectedComponentsWithStats(fuente, 8)
    area_total = img.shape[0] * img.shape[1]

    candidatos = [(i, int(estad[i, cv2.CC_STAT_AREA])) for i in range(1, n)
                  if estad[i, cv2.CC_STAT_AREA] >= AUTOMATICO_AREA_MIN_FRAC * area_total]
    candidatos.sort(key=lambda t: -t[1])
    candidatos = candidatos[:max_piezas]
    if not candidatos:
        avisar('separación automática: ningún componente conexo lo bastante grande '
               '(¿imagen sin contraste, o un único bloque sin huecos?)')

    alto, ancho = img.shape[:2]
    cx_img, cy_img = ancho / 2.0, alto / 2.0
    piezas = []
    for orden, (etiqueta, _area) in enumerate(candidatos):
        mascara = np.where(etiquetas == etiqueta, 255, 0).astype(np.uint8)
        rec = _recorte_de_mascara(img, mascara)
        if rec is None:
            continue
        rgba, caja, area_medida = rec
        cx, cy = centroides[etiqueta]
        dx, dy = cx - cx_img, cy - cy_img
        norma = math.hypot(dx, dy) or 1.0
        rumbo = [round(dx / norma, 4), round(-dy / norma, 4), 0.3]
        piezas.append({'clave': f'auto_{orden + 1}',
                        'titulo': f'componente automático {orden + 1} (sin nombre real)',
                        'orden': orden, 'rumbo': rumbo, 'rgba': rgba, 'caja_px': caja,
                        'area_px': area_medida, 'relleno_px': 0})
    return piezas


# ───────────────────────────────── ficha piezas.json ─────────────────────────────────

def _escribir_piezas_json(ruta_json, ancho, alto, ruta_original_rel, procedencia, piezas,
                          reconocimiento=None):
    salida = []
    for p in piezas:
        x0, y0, x1, y1 = p['caja_px']
        cx, cy = (x0 + x1) / 2.0 / ancho, (y0 + y1) / 2.0 / alto
        w_frac, h_frac = (x1 - x0 + 1) / ancho, (y1 - y0 + 1) / alto
        salida.append({
            'clave': p['clave'], 'titulo': p['titulo'], 'orden': p['orden'],
            'caja_px': [x0, y0, x1, y1],
            'centro': [round(cx, 5), round(cy, 5)],
            'tam_frac': [round(w_frac, 5), round(h_frac, 5)],
            'rumbo': [round(float(v), 4) for v in p['rumbo']],
            # ruta relativa a la raíz servida (URL, no de disco: "/" literal, nunca
            # os.path.join) — kinetica.html carga la textura con `carg.load(p.png, ...)`
            'png': 'piezas/' + p['clave'] + '.png',
            'area_px': p['area_px'], 'relleno_px': p['relleno_px'],
        })
    ficha = {'ancho': ancho, 'alto': alto, 'original': ruta_original_rel,
             'procedencia': procedencia, 'piezas': salida,
             # Sin reconocimiento NO hay enlace. Un enlace apoyado en el título que
             # escribió una persona sería un dato dictado disfrazado de hallazgo.
             'reconocimiento': reconocimiento or {
                 'como': 'ninguno', 'texto_leido': [], 'url': None,
                 'por_que': 'no se pidió reconocer (--reconocer o --reconocimiento f.json)'}}
    with open(ruta_json, 'w', encoding='utf-8') as fh:
        json.dump(ficha, fh, ensure_ascii=False, indent=1)
    return ficha


# ───────────────────────────────── mp/ (MediaPipe vendorizado) ─────────────────────────────────

def _montar_mp(destino, avisar):
    destino_mp = os.path.join(destino, 'mp')
    if os.path.isdir(MP_VENDOR) and os.path.isfile(os.path.join(MP_VENDOR, 'vision_bundle.mjs')):
        if os.path.isdir(destino_mp):
            shutil.rmtree(destino_mp)
        shutil.copytree(MP_VENDOR, destino_mp)
        avisar(f'mp/: copiado de {MP_VENDOR} (manos activas)')
        return 'copiado'
    os.makedirs(destino_mp, exist_ok=True)
    with open(os.path.join(destino_mp, 'vision_bundle.mjs'), 'w', encoding='utf-8') as fh:
        fh.write(_STUB_VISION_BUNDLE)
    avisar('sin dato: falta abyss/vendor/mp/ (MediaPipe Tasks Vision) — el visor se sirve '
           'SIN manos (la cámara avisará en pantalla al encenderla).\n' + MENSAJE_MEDIAPIPE)
    return 'sin dato: falta abyss/vendor/mp/'


# ───────────────────────────────── montar() ─────────────────────────────────

def montar(ruta_imagen, regiones_json=None, fichas_json=None, salida=None, rellenar=False,
           quitar_fondo=False, dejar_fondo=False, reconocer=False,
           reconocimiento_json=None, permitir_nombre_fichero=False, avisar=print):
    """Ejecuta el recorte descrito en el docstring del módulo y escribe la carpeta de
    trabajo completa. Devuelve un dict con `destino`, `modo` (`'manual'`/`'automatico'`),
    `piezas` (sus claves) y `mp` (estado de `mp/`, ver `_montar_mp`)."""
    ruta_imagen = os.path.abspath(ruta_imagen)
    # el nombre para el respaldo de `_reconocer_por_nombre` es el que trajo QUIEN LLAMÓ,
    # nunca uno intermedio (el "_sin_fondo" que puede escribir fondo.quitar más abajo, ni
    # el "original.jpg" con el que este módulo copia la foto en la carpeta de salida): es
    # el nombre que puso la persona al guardar la foto, no uno que este módulo inventó.
    ruta_imagen_dada = ruta_imagen

    # ── el fondo se quita SOLO cuando estorba, y sin que haya que pedirlo ────────
    # Si el fondo no es liso y hay un motor disponible, se quita solo y se avisa; se puede
    # desactivar con `--fondo-tal-cual` para quien quiera la foto como vino.
    #
    # Si la imagen YA trae canal alfa útil (entre 2% y 98% de píxeles transparentes: fuera
    # de ese rango es ruido o una imagen sin recortar), esa máscara ES la silueta exacta y
    # no hace falta estimar nada con `_fondo_liso` ni `fondo.quitar()` — reusarla evita que
    # un motor de recorte adivine la silueta de un objeto que ya la trae gratis en su alfa.
    nota_fondo = 'la foto se usa tal cual: no se le quitó el fondo'
    por_su_cuenta = False
    obj_de_alfa = None
    _nota_alfa = None
    if not quitar_fondo and not dejar_fondo:
        try:
            _prueba, _alfa_prueba = _leer_imagen(ruta_imagen)
        except Exception:
            _prueba, _alfa_prueba = None, None
        _frac_transp = float((_alfa_prueba < 128).mean()) if _alfa_prueba is not None else 0.0
        if _alfa_prueba is not None and 0.02 <= _frac_transp <= 0.98:
            obj_de_alfa = np.where(_alfa_prueba >= 128, 255, 0).astype(np.uint8)
            _nota_alfa = ('canal alfa de la imagen de entrada (%.1f%% transparente)'
                          % (100 * _frac_transp))
            nota_fondo = ('%s: esa máscara ES la silueta, no se estima con GrabCut ni se '
                          'llama a fondo.quitar()' % _nota_alfa)
            avisar('%s -> se usa como silueta exacta, sin GrabCut ni fondo.quitar()' % _nota_alfa)
        else:
            try:
                _obj, _nota = _fondo_liso(_prueba) if _prueba is not None else (object(), None)
            except Exception:
                _obj, _nota = object(), None
            if _obj is None:                   # `_fondo_liso` devuelve None si NO es liso
                quitar_fondo = por_su_cuenta = True
                avisar('el fondo no es liso (%s): se quita antes de separar, que es lo que hace '
                       'la silueta exacta' % (_nota or 'sin dato'))

    if quitar_fondo:
        # Un fondo liso hace la silueta EXACTA (ver `_fondo_liso`), asi que se ofrece
        # quitarlo antes de separar. Lo hace `fondo.py`, que dice siempre con que motor.
        try:
            import fondo as _fondo
        except ImportError:
            import importlib.util as _u
            _e = _u.spec_from_file_location('fondo', os.path.join(CODE, 'fondo.py'))
            _fondo = _u.module_from_spec(_e); _e.loader.exec_module(_fondo)
        r = _fondo.quitar(ruta_imagen, salida=None, sobre='blanco', avisar=avisar)
        avisar('fondo quitado con el motor %s: el objeto ocupa el %.1f%% del cuadro'
               % (r['motor'], 100 * r['cobertura']))
        if r['cobertura'] < 0.03:
            avisar('AVISO: el recorte se ha quedado casi con nada. Se sigue con la foto '
                   'ORIGINAL, sin quitar el fondo, en vez de despiezar un cuadro vacio.')
            nota_fondo = ('se intentó quitar el fondo con el motor %s y el recorte se quedó '
                          'en el %.1f%% del cuadro: DESCARTADO, se sigue con la foto original'
                          % (r['motor'], 100 * r['cobertura']))
        else:
            ruta_imagen = r['salida']
            nota_fondo = ('fondo quitado con el motor %s (el objeto ocupa el %.1f%% del '
                          'cuadro); %s' % (r['motor'], 100 * r['cobertura'],
                                           'decidido por el programa porque el fondo no era '
                                           'liso' if por_su_cuenta else 'pedido con --quitar-fondo'))
    img, alfa = _leer_imagen(ruta_imagen)
    alto, ancho = img.shape[:2]

    if regiones_json:
        regiones = _leer_regiones(regiones_json)
        avisar(f'regiones: {len(regiones)} puestas a mano en {os.path.basename(regiones_json)}')
        piezas = _separar_manual(img, regiones, rellenar, avisar,
                                  obj_conocido=((obj_de_alfa, _nota_alfa) if obj_de_alfa is not None else None))
        procedencia = {
            'modo': 'manual',
            'regiones': (f'puestas a mano en {os.path.basename(regiones_json)} '
                         '(reconocimiento asistido, no un detector entrenado)'),
            'recorte': ('cv2.grabCut con máscara sembrada desde cada polígono; solapes '
                        'resueltos por prioridad con las máscaras reales'),
            'rumbos': 'el eje de montaje declarado en cada región del fichero de regiones',
            'relleno': (('los píxeles que una pieza tenía tapados por otra se reconstruyen '
                         'con cv2.inpaint (Telea): son inventados, no fotografiados; la '
                         'cuenta está en relleno_px de cada pieza') if rellenar else
                        'no pedido (--rellenar): los huecos tapados por otra pieza quedan transparentes'),
        }
    else:
        avisar(AVISO_AUTOMATICO)
        piezas = _separar_automatico(img, avisar, obj_conocido=obj_de_alfa)
        procedencia = {
            'modo': 'automatico',
            'regiones': ('NINGUNA dada: separación automática por componentes conexos del '
                         'primer plano (GrabCut con rectángulo + connectedComponents, los '
                         f'{AUTOMATICO_MAX_PIEZAS} mayores) — sin nombre real, peor que con '
                         'regiones puestas a mano'),
            'recorte': 'cv2.grabCut con rectángulo inicial + cv2.connectedComponentsWithStats',
            'rumbos': ('vector del centro de la imagen al centroide de cada componente '
                       '(heurística de dirección, no un eje de montaje real)'),
            'relleno': 'no aplica en modo automático (los componentes conexos no se solapan)',
        }
        if rellenar:
            avisar('--rellenar no aplica en modo automático: los componentes conexos no '
                   'se solapan entre sí, no hay nada tapado que reconstruir')

    if not piezas:
        raise ValueError('no se separó ninguna pieza (¿imagen vacía, o regiones sin píxeles?)')

    base = os.path.splitext(os.path.basename(ruta_imagen))[0]
    destino = os.path.abspath(salida) if salida else os.path.join(
        os.path.dirname(ruta_imagen) or '.', f'{base}_kinetica')
    piezas_dir = os.path.join(destino, 'piezas')
    os.makedirs(piezas_dir, exist_ok=True)

    for p in piezas:
        Image.fromarray(p['rgba']).save(os.path.join(piezas_dir, f'{p["clave"]}.png'))

    # la plantilla siempre pide 'original.jpg' (kinetica.html: carg.load('original.jpg', ...)),
    # así que aquí SIEMPRE se escribe con ese nombre; si la entrada no era JPEG, se
    procedencia['fondo'] = nota_fondo

    # recodifica desde `img` (ya cargada) — y `procedencia.original` lo declara.
    nombre_original = 'original.jpg'
    ext_original = os.path.splitext(ruta_imagen)[1].lower()
    ruta_original_destino = os.path.join(destino, nombre_original)
    if alfa is not None and not dejar_fondo:
        # `img` es SIEMPRE de 3 canales (ver `_leer_imagen`), así que escribirlo tal cual
        # cuando la entrada traía alfa resucitaría lo que hubiera bajo los píxeles
        # transparentes. Se compone sobre blanco en su lugar — mismo criterio que ya usa
        # `fondo.quitar(..., sobre='blanco')` (fondo.py) — y se sigue guardando como JPEG:
        # la plantilla (`carg.load('original.jpg', ...)`) no cambia ni una letra.
        _mez = (alfa.astype(np.float32) / 255.0)[:, :, None]
        _compuesta = (img.astype(np.float32) * _mez + 255.0 * (1 - _mez)).astype(np.uint8)
        if not cv2.imwrite(ruta_original_destino, _compuesta):
            raise ValueError(f'no se pudo componer original.jpg para: {ruta_imagen}')
        procedencia['original'] = (
            'la entrada traía canal alfa: se compuso sobre blanco (mismo criterio que '
            'fondo.quitar(sobre="blanco")) en vez de resucitar el fondo que hubiera '
            'debajo de los píxeles transparentes; se guardó como JPEG, la plantilla no cambia'
        )
    elif ext_original in ('.jpg', '.jpeg'):
        shutil.copy2(ruta_imagen, ruta_original_destino)
        procedencia['original'] = 'copia tal cual de la imagen de entrada (ya era JPEG)'
    else:
        if not cv2.imwrite(ruta_original_destino, img):
            raise ValueError(f'no se pudo recodificar a JPEG la imagen de entrada: {ruta_imagen}')
        procedencia['original'] = (
            f'recodificada a JPEG desde "{ext_original or "(sin extensión)"}" — la plantilla '
            'siempre carga original.jpg'
        )

    # dentro de piezas/, junto a las <clave>.png: la plantilla la pide con
    # fetch('piezas/piezas.json'), no en la raíz de la carpeta servida.
    if permitir_nombre_fichero and not reconocer:
        avisar('--permitir-nombre-fichero no hace nada sin --reconocer: no se está '
               'pidiendo ningún reconocimiento')

    recon = None
    if reconocimiento_json:
        recon = _leer_reconocimiento(reconocimiento_json)
        avisar('reconocimiento: %s' % recon['por_que'])
    elif reconocer:
        recon = _reconocer(piezas, img, avisar, ruta_imagen=ruta_imagen_dada,
                            permitir_nombre_fichero=permitir_nombre_fichero)
        avisar('reconocimiento: %s' % recon['por_que'])
    _escribir_piezas_json(os.path.join(piezas_dir, 'piezas.json'), ancho, alto,
                           nombre_original, procedencia, piezas,
                          reconocimiento=recon)

    if fichas_json:
        shutil.copy2(os.path.abspath(fichas_json), os.path.join(destino, 'fichas.json'))
        avisar(f'fichas: copiado {os.path.basename(fichas_json)} (los carteles tendrán datos con fuente)')
    else:
        avisar('sin --fichas: cada cartel dirá "sin dato con fuente" (lo decide la propia plantilla)')

    shutil.copy2(os.path.join(VENDOR, 'three.min.js'), os.path.join(destino, 'three.min.js'))
    shutil.copy2(PLANTILLA, os.path.join(destino, 'index.html'))
    # la plantilla lo importa: sin esto, el visor se queda sin mano
    shutil.copy2(os.path.join(CODE, 'plantillas', 'gestos_comun.js'),
                 os.path.join(destino, 'gestos_comun.js'))
    mp_estado = _montar_mp(destino, avisar)

    modo = 'manual' if regiones_json else 'automatico'
    avisar(f'montado: {destino} ({len(piezas)} piezas, modo {modo})')
    return {'destino': destino, 'modo': modo, 'piezas': [p['clave'] for p in piezas],
            'mp': mp_estado}


# ───────────────────────────────── servidor (SOLO 127.0.0.1) ─────────────────────────────────

def _abre_fuera(url):
    """Le da la URL al navegador del sistema, en su propia ventana. No es el navegador de
    la escena: se abre aparte a proposito, para que la escena siga viva detras."""
    if sys.platform == 'win32':
        os.startfile(url)                                    # noqa: S606 (es la via del SO)
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', url], close_fds=True)
    else:
        subprocess.Popen(['xdg-open', url], close_fds=True)


def _elegir_manejador(directorio):
    class Manejador(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=directorio, **kw)

        def end_headers(self):
            # el .wasm de MediaPipe, cargado como módulo ES, exige estas dos cabeceras
            self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
            self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
            super().end_headers()

        def _json(self, datos, codigo=200):
            cuerpo = json.dumps(datos, ensure_ascii=False).encode('utf-8')
            self.send_response(codigo)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):
            motivo = puerta_local.rechazo(self)
            if motivo:
                puerta_local.descartar_cuerpo(self)
                self._json({'ok': False, 'por_que': motivo}, 403)
                return
            super().do_GET()

        def do_HEAD(self):
            motivo = puerta_local.rechazo(self)
            if motivo:
                puerta_local.descartar_cuerpo(self)
                self._json({'ok': False, 'por_que': motivo}, 403)
                return
            super().do_HEAD()

        def do_POST(self):
            """Un solo verbo: abrir el sitio oficial FUERA de esta ventana — `window.open`
            desde un gesto lo bloquea el navegador, asi que lo abre el sistema y la escena
            sigue viva detras. No se acepta ninguna URL ajena: solo la que ya este escrita
            en `reconocimiento.url` del `piezas.json` de ESTA escena; el cuerpo no se lee.
            POST evita que un enlace o una precarga lo disparen solos; que no lo dispare
            OTRA WEB lo corta `puerta_local.rechazo()` comprobando `Origin`/`Host`."""
            motivo = puerta_local.rechazo(self)
            if motivo:
                puerta_local.descartar_cuerpo(self)
                self.close_connection = True  # cierra tras el rechazo: no reusar esta conexión
                self._json({'ok': False, 'por_que': motivo}, 403)
                return
            if self.path.split('?')[0] != '/abrir-enlace':
                self.send_error(404, 'aqui no se escribe nada')
                return
            url = None
            try:
                with open(os.path.join(directorio, 'piezas', 'piezas.json'),
                          encoding='utf-8') as fh:
                    url = (json.load(fh).get('reconocimiento') or {}).get('url')
            except (OSError, ValueError):
                url = None
            if not url or not str(url).startswith('https://'):
                cuerpo = {'ok': False, 'por_que': 'esta escena no reconocio ningun sitio oficial'}
            else:
                try:
                    _abre_fuera(url)
                    cuerpo = {'ok': True, 'url': url}
                except Exception as e:
                    cuerpo = {'ok': False, 'por_que': '%s %s' % (type(e).__name__, e)}
            self._json(cuerpo)

        def log_message(self, *a):
            pass  # silencio: por stdout solo va el aviso de arranque

    return Manejador


def servir(destino, puerto=PUERTO_POR_DEFECTO, abrir=True, avisar=print):
    """`ThreadingHTTPServer` ligado a `127.0.0.1` — NUNCA `0.0.0.0` — sirviendo `destino`
    como raíz estática, con las cabeceras COOP/COEP que el `.wasm` de MediaPipe necesita.
    Bloquea en `serve_forever()` hasta Ctrl+C."""
    servidor = ThreadingHTTPServer(('127.0.0.1', puerto), _elegir_manejador(destino))
    puerto_real = servidor.server_address[1]
    url = f'http://127.0.0.1:{puerto_real}/'
    avisar(f'[kinetica] sirviendo {destino}')
    avisar(f'[kinetica] escuchando en {url}')
    if abrir:
        try:
            try:
                import importlib.util as _u
                _e = _u.spec_from_file_location('navegador', os.path.join(CODE, 'navegador.py'))
                _nav = _u.module_from_spec(_e); _e.loader.exec_module(_nav)
                _nav.abrir(url, avisar=avisar)
            except Exception as _err:
                avisar('no pude abrir con perfil propio (%s): se abre con el navegador de '
                       'siempre, que pedira permiso de camara cada vez' % _err)
                webbrowser.open(url)
        except Exception as e:
            avisar(f'sin dato: no se pudo abrir el navegador solo ({type(e).__name__}: {e}); abre {url} a mano')
    sys.stdout.flush()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


# ───────────────────────────────── CLI ─────────────────────────────────

def _valor(opts, bandera, por_defecto=None):
    if bandera in opts:
        i = opts.index(bandera)
        if i + 1 < len(opts) and not opts[i + 1].startswith('--'):
            return opts[i + 1]
        return True
    return por_defecto


def _cli(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0 if argv and argv[0] in ('-h', '--help') else 1
    if argv[0].startswith('--'):
        print('uso: kinetica.py <imagen> [opciones] (ver --help)')
        return 1
    imagen = argv[0]
    opts = argv[1:]

    puerto = _valor(opts, '--puerto', PUERTO_POR_DEFECTO)
    try:
        puerto = int(puerto)
    except (TypeError, ValueError):
        print(f'--puerto necesita un número entero, no "{puerto}"')
        return 1

    try:
        r = montar(imagen, regiones_json=_valor(opts, '--regiones'),
                   fichas_json=_valor(opts, '--fichas'), salida=_valor(opts, '--salida'),
                   rellenar=('--rellenar' in opts),
                   quitar_fondo=('--quitar-fondo' in opts),
                   dejar_fondo=('--fondo-tal-cual' in opts),
                   reconocer=('--reconocer' in opts),
                   reconocimiento_json=_valor(opts, '--reconocimiento'),
                   permitir_nombre_fichero=('--permitir-nombre-fichero' in opts))
    except (FileNotFoundError, ValueError) as e:
        print(f'sin dato: {e}')
        return 2
    except Exception as e:
        # cualquier otro fallo sale como "sin dato", nunca como traza cruda (mismo
        # criterio que volumen.py/taller.py)
        print(f'sin dato: {type(e).__name__} {e}')
        return 2

    print(json.dumps(r, ensure_ascii=False))
    if '--solo-montar' in opts:
        return 0

    servir(r['destino'], puerto=puerto, abrir=('--sin-abrir' not in opts))
    return 0


if __name__ == '__main__':
    try:                       # la consola de Windows y la salida tienen que hablar
        from . import consola  # el mismo idioma: ver abyss/consola.py
    except ImportError:
        import consola
    consola.preparar()
    sys.exit(_cli(sys.argv[1:]))
