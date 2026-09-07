# -*- coding: utf-8 -*-
"""Volumen: lo que el ojo VE en relieve — un despiece por capas (2,5D) de una foto, y un
prompt de diseño 3D medido de ella. NO es reconstrucción 3D ni un escáner de profundidad:
todo lo de aquí sale de heurísticas DECLARADAS sobre una sola imagen 2D, nunca de una
cámara estéreo ni de un sensor de profundidad — se dice aquí, en `skills/ojo/SKILL.md` y en
la propia página que abre `render3d.py` (ver más abajo, «--html»).

Uso:
    python volumen.py despiece <imagen> [--capas 4] [--salida escena.json] [--html]
    python volumen.py prompt3d <imagen> [--salida f.txt] [--escena f.json]

DEPENDENCIA obligatoria: OpenCV (`cv2`) y `numpy`. Sin ellas, este guion dice EXACTAMENTE
qué instalar («sin dato: pip install opencv-python numpy», igual que `lienzo.py`) y sale con
código 2 — nunca instala nada por su cuenta ni deja salir una traza cruda.

## despiece — GrabCut + una heurística de profundidad declarada

1. `cv2.grabCut` (inicializado con un rectángulo que deja un margen del 5% por lado; probado
   el 6-sep en este mismo paquete) separa el objeto principal del fondo. Si no separa nada
   (foto sin contraste claro, medido con una imagen de un solo color: 0 píxeles de primer
   plano) se avisa «GrabCut no separó nada: se toma el recuadro central como primer plano,
   sin fingir un recorte más fino» y se sigue con ese rectángulo entero.
2. Sobre el primer plano se mide, por píxel, una puntuación de «cercanía aparente» =
   0,6×nitidez_local + 0,4×luminancia, cada una normalizada por percentiles 5/95 DE ESTE
   primer plano (mismo patrón de cortes propios que el resto del paquete). La nitidez local
   es la varianza del laplaciano en una ventana de 9×9: MIDE contraste de borde, no
   distancia — una pared lisa y cercana sale tan «lejana» como una pared lisa y lejana. Es
   una heurística de composición fotográfica (lo enfocado y luminoso suele estar delante en
   una foto bien compuesta), NUNCA una medida de profundidad real, y se declara como tal.
3. El primer plano se reparte en `--capas`-1 tramos por PERCENTILES de esa puntuación (capa 0
   = puntuación más alta = "más cerca"); todo lo que GrabCut dejó fuera del primer plano es
   la última capa, el fondo. Una capa sin ningún píxel simplemente no aparece (el resultado
   dice cuántas capas *efectivas* salieron; nunca se inventa una capa vacía).
4. Cada capa se recorta a su caja delimitadora con un canal alfa (transparente fuera de esa
   capa) y se guarda como PNG aparte, en `<salida sin extensión>_capas/capa_N.png` — ESA es
   la textura real, con los píxeles de la foto. La `escena.json` no la referencia como
   textura (el «plano» de `render3d.py` no pinta texturas, solo color liso: no se ha tocado
   `render3d.py` para eso, fuera del encargo de esta tanda) — cada plano de la escena lleva
   el COLOR MEDIO de su capa y, en un campo extra `capa_png` que `render3d.py` ignora sin
   más (no valida campos desconocidos), la ruta a la imagen real, por si una tanda futura le
   añade materiales con textura. La escena resultante SÍ es la que abre `render3d.py` con su
   deslizador de explosión (mismo esquema `escena.json` que `pruebas/datos/escena_prueba.json`:
   piezas tipo/pos/tam/color/grupo — un grupo por capa, así cada una explosiona por separado).
5. Escala: el ancho TOTAL de la foto ocupa 2 unidades de escena (constante de diseño, igual
   de arbitraria que la de cualquier otro `escena.json` de este paquete — no es una medida
   real del objeto) y las capas se separan 0,2 unidades cada una en Z, capa 0 más cerca.
6. `--html`: además de la `escena.json`, llama a `render3d.renderizar()` (sin tocar su
   código: solo se le pasa la ruta) para escribir la página, y le inserta un aviso fijo en
   una esquina — «Despiece 2,5D — capas por heurística (nitidez+luminancia), NO
   reconstrucción 3D» — escrito sobre el HTML ya generado (no se modifica `render3d.py`
   para esto: es este guion quien retoca el fichero de salida que él mismo pidió escribir).

## prompt3d — lo que SE MIDE de la foto, nunca lo que se adivina

- **Paleta**: k-medias (`cv2.kmeans`, k=5 por defecto) sobre TODOS los píxeles de la foto en
  RGB; cada color con su proporción de píxeles, de mayor a menor. Es la paleta medida de
  ESTA foto, no un juicio de que "pega" o "no pega".
- **Proporciones del objeto**: caja delimitadora del primer plano (mismo GrabCut de arriba)
  → ancho/alto en píxeles y su razón. Sin primer plano separable: «sin dato».
- **Horizonte**: la línea recta más larga dentro de ±5° de la horizontal (Canny + Hough)
  sobre TODA la foto, como fracción de la altura. Sin ninguna línea así de clara: «sin
  dato» — no se inventa un horizonte en una foto que no lo tiene.
- **Formas dominantes**: por cada contorno externo del primer plano (o de los bordes Canny
  de toda la foto si GrabCut no separó nada) con área ≥1% de la foto, circularidad
  (4π·área/perímetro²) y vértices tras `approxPolyDP`:
    - circularidad ≥ 0,85               → "esfera" (silueta redonda)
    - 4-6 vértices y circularidad < 0,85 → "rectangulo" (silueta poligonal de pocos lados)
    - razón de aspecto ≥ 1,6 y circularidad entre 0,30 y 0,85, sin 4-6 vértices → "cilindro"
      (silueta alargada y redondeada — una elipse o un óvalo visto de perfil)
    - cualquier otro caso                → "irregular" (no se fuerza a encajar en las tres)
  Es una clasificación DECLARADA por geometría de la silueta 2D, no un reconocedor de
  objetos: no dice QUÉ es, dice qué círculo/rectángulo/óvalo se parece más a su contorno.
- Con estos cuatro números se escribe un prompt de diseño en castellano E inglés para
  three.js (`--salida f.txt`, por defecto `<base>_prompt3d.txt`) citando exactamente lo
  medido (paleta, razón del objeto, fracción de horizonte si la hay, formas con su
  circularidad). Con `--escena f.json` además se escribe una `escena.json` de primitivas
  (caja/cilindro/esfera reales de `render3d.py`, sin campos extra) colocadas y coloreadas
  según esas mismas formas medidas — sin adivinar qué es el objeto, solo lo que se vio.

Ninguno de los dos verbos toca `mem` ni resuelve un proyecto de Claude Code (como
`render3d.py`/`pintor.py`: guiones de fichero a fichero, sin gancho); por eso se puede
importar este módulo en el propio proceso de una prueba sin arriesgarse a que aborte
por falta de `--proyecto`/`ABYSS_PROYECTO`.
"""
import json
import math
import os
import sys

try:
    import numpy as np
    import cv2
except ImportError as _e:
    print(f'sin dato: pip install opencv-python numpy [falta {_e.name}]')
    sys.exit(2)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ANCHO_ESCENA_M = 2.0     # constante de diseño: el ancho de la foto ocupa esto en la escena
SEPARACION_CAPA_M = 0.2  # constante de diseño: distancia en Z entre capas consecutivas
MARGEN_GRABCUT = 0.05    # 5% por lado, deja el rectángulo inicial de GrabCut fuera del borde
ITER_GRABCUT = 5


# ───────────────────────────────── comunes: imagen y GrabCut ─────────────────────────────────

def _leer_imagen(ruta):
    ruta = os.path.abspath(ruta)
    if not os.path.isfile(ruta):
        raise FileNotFoundError(f'no existe: {ruta}')
    img = cv2.imread(ruta, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f'no se pudo leer como imagen: {ruta}')
    return img


def mascara_primer_plano(img, avisar=print):
    """Máscara booleana (True=primer plano) por GrabCut, inicializado con un rectángulo que
    deja fuera un margen de `MARGEN_GRABCUT` por cada lado. Si GrabCut no separa NADA
    (0 píxeles de primer plano — medido con una imagen de un único color de fondo a fondo),
    se avisa y se usa el propio rectángulo inicial entero como primer plano: fail-closed
    hacia "todo es objeto", nunca hacia una máscara vacía que dejaría el resto del guion
    sin nada que despiezar."""
    alto, ancho = img.shape[:2]
    mx = max(1, int(ancho * MARGEN_GRABCUT))
    my = max(1, int(alto * MARGEN_GRABCUT))
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


def _bbox(mascara):
    ys, xs = np.where(mascara)
    if xs.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _color_medio_hex(img, mascara):
    px = img[mascara]  # BGR
    if px.size == 0:
        return '#888888'
    b, g, r = (int(round(v)) for v in px.mean(axis=0))
    return '#%02x%02x%02x' % (r, g, b)


# ───────────────────────────────── despiece ─────────────────────────────────

def _mapa_profundidad(img, fg):
    """Puntuación de "cercanía aparente" por píxel = 0,6×nitidez_local + 0,4×luminancia,
    cada una normalizada por percentiles 5/95 DEL PRIMER PLANO (§ver docstring del módulo).
    Heurística de composición, no de distancia real."""
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    laplaciano = cv2.Laplacian(gris, cv2.CV_32F, ksize=3)
    nitidez = cv2.boxFilter(laplaciano * laplaciano, -1, (9, 9))
    luminancia = gris / 255.0

    def normaliza(mapa):
        vals = mapa[fg]
        if vals.size == 0:
            return np.zeros_like(mapa)
        lo, hi = np.percentile(vals, 5), np.percentile(vals, 95)
        if hi <= lo:
            return np.zeros_like(mapa)
        return np.clip((mapa - lo) / (hi - lo), 0.0, 1.0)

    return 0.6 * normaliza(nitidez) + 0.4 * normaliza(luminancia)


def _indices_de_capa(mapa, fg, num_capas):
    """Índice de capa por píxel: 0 = puntuación más alta ("más cerca") … `num_capas`-2 =
    puntuación más baja dentro del primer plano; `num_capas`-1 = fondo (todo lo que GrabCut
    dejó fuera). El primer plano se reparte por PERCENTILES de `mapa` (no por tramos iguales
    del rango de valores): así cada capa se lleva, a ojo, el mismo número de píxeles de
    objeto, no una porción arbitraria de la escala de puntuación."""
    fondo = num_capas - 1
    idx = np.full(mapa.shape, fondo, dtype=np.int32)
    if num_capas <= 1:
        return idx
    vals = mapa[fg]
    if vals.size == 0:
        return idx
    n_fg_capas = num_capas - 1  # capas de primer plano (todas menos el fondo)
    if n_fg_capas == 1:
        idx[fg] = 0
        return idx
    cortes = np.percentile(vals, [100.0 * i / n_fg_capas for i in range(1, n_fg_capas)])
    crudo = np.digitize(mapa, cortes)                  # 0 (puntuación baja) … n_fg_capas-1 (alta)
    capa_fg = np.clip((n_fg_capas - 1) - crudo, 0, n_fg_capas - 1)  # invierte: alta puntuación -> capa 0
    idx = np.where(fg, capa_fg, fondo)
    return idx


def despiece(ruta_imagen, capas=4, salida=None, html=False, avisar=print):
    """Ejecuta el despiece por capas descrito en el docstring del módulo. Devuelve un dict
    con `escena` (ruta de la escena.json escrita), `capas_pedidas`, `capas_efectivas`
    (cuántas tuvieron al menos un píxel), `capas_png` (rutas de los recortes) y, si `html`,
    `html` (ruta de la página de `render3d.py`)."""
    capas = max(2, int(capas))
    ruta_imagen = os.path.abspath(ruta_imagen)
    img = _leer_imagen(ruta_imagen)
    alto, ancho = img.shape[:2]
    fg = mascara_primer_plano(img, avisar=avisar)
    mapa = _mapa_profundidad(img, fg)
    idx = _indices_de_capa(mapa, fg, capas)

    base = os.path.splitext(os.path.basename(ruta_imagen))[0]
    carpeta = os.path.dirname(ruta_imagen) or '.'
    ruta_escena = salida if salida else os.path.join(carpeta, f'{base}_despiece.json')
    ruta_escena = os.path.abspath(ruta_escena)
    carpeta_capas = os.path.splitext(ruta_escena)[0] + '_capas'

    metros_por_px = ANCHO_ESCENA_M / ancho
    piezas = []
    rutas_png = []
    for i in range(capas):
        m = (idx == i)
        caja = _bbox(m)
        if caja is None:
            continue  # capa sin ningún píxel: no se inventa una pieza vacía
        x0, y0, x1, y1 = caja
        os.makedirs(carpeta_capas, exist_ok=True)
        ruta_png = os.path.join(carpeta_capas, f'capa_{i}.png')
        recorte_bgr = img[y0:y1 + 1, x0:x1 + 1]
        recorte_alfa = (m[y0:y1 + 1, x0:x1 + 1].astype(np.uint8)) * 255
        recorte_bgra = np.dstack([recorte_bgr, recorte_alfa])
        cv2.imwrite(ruta_png, recorte_bgra)
        rutas_png.append(ruta_png)

        cx_px, cy_px = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        w_px, h_px = (x1 - x0 + 1), (y1 - y0 + 1)
        nombre = f'capa_{i}_fondo' if i == capas - 1 else f'capa_{i}'
        piezas.append({
            'nombre': nombre, 'tipo': 'plano',
            'pos': [round((cx_px - ancho / 2.0) * metros_por_px, 5),
                    round((alto / 2.0 - cy_px) * metros_por_px, 5),
                    round((capas - 1 - i) * SEPARACION_CAPA_M, 5)],
            'tam': [round(w_px * metros_por_px, 5), round(h_px * metros_por_px, 5)],
            'color': _color_medio_hex(img, m),
            'grupo': f'capa_{i}',
            'capa_png': os.path.relpath(ruta_png, carpeta),
        })

    if not piezas:
        raise ValueError('el despiece no encontró ninguna capa con píxeles (¿imagen vacía?)')

    escena = {
        'unidades': 'm',
        'despiece': {'tipo': '2.5D', 'capas_pedidas': capas, 'capas_efectivas': len(piezas),
                     'heuristica': 'nitidez_local(laplaciano) + luminancia, por percentiles del primer plano (GrabCut)'},
        'piezas': piezas,
    }
    os.makedirs(os.path.dirname(ruta_escena) or '.', exist_ok=True)
    with open(ruta_escena, 'w', encoding='utf-8') as fh:
        json.dump(escena, fh, ensure_ascii=False, indent=1)
    avisar(f'escena: {ruta_escena} ({len(piezas)}/{capas} capas efectivas)')

    resultado = {'escena': ruta_escena, 'capas_pedidas': capas, 'capas_efectivas': len(piezas),
                 'capas_png': rutas_png}
    if html:
        import render3d  # sin rutas.resolver(): seguro importarlo aquí, ver docstring del módulo
        r = render3d.renderizar(ruta_escena, html=(html if isinstance(html, str) else None), explosion=0.3, avisar=avisar)
        _insertar_aviso_2_5d(r['html'])
        resultado['html'] = r['html']
    return resultado


_AVISO_2_5D = (
    '<div id="avisoDespiece" style="position:fixed;bottom:8px;right:8px;z-index:6;'
    'max-width:280px;background:#000000c0;color:#f2c94c;padding:8px 10px;border-radius:8px;'
    'font:11px/1.4 system-ui,sans-serif;">Despiece 2,5D por capas (nitidez+luminancia) — '
    'NO es una reconstrucción 3D del objeto.</div>\n'
)


def _insertar_aviso_2_5d(ruta_html):
    """Retoca el HTML que ACABA de escribir `render3d.renderizar()` (no su código: el
    fichero de salida) para dejar el aviso "no es 3D" también en la propia página, como
    pide el docstring del módulo. Si por lo que sea no hay `<body>` que anclar (HTML
    ajeno, no el que genera este mismo paquete), no revienta: no encuentra nada que
    insertar y deja el fichero tal cual estaba."""
    with open(ruta_html, encoding='utf-8') as fh:
        texto = fh.read()
    marca = '<body>'
    i = texto.find(marca)
    if i == -1:
        return
    i += len(marca)
    texto = texto[:i] + '\n' + _AVISO_2_5D + texto[i:]
    with open(ruta_html, 'w', encoding='utf-8') as fh:
        fh.write(texto)


# ───────────────────────────────── prompt3d ─────────────────────────────────

def paleta_dominante(img, k=5):
    """k-medias (`cv2.kmeans`) sobre TODOS los píxeles en RGB. Devuelve hasta `k` colores con
    su proporción de píxeles, de mayor a menor. Medido de ESTA foto, no un juicio estético.

    Cuando `k` pide más grupos de los que la foto realmente tiene (fotos con pocos colores
    reales: capturas sintéticas, ilustraciones planas), `cv2.kmeans` puede devolver dos
    centros casi idénticos en vez de uno vacío — medido con una imagen de 3 colores planos y
    k=5. Se fusionan aquí los centros a menos de 10 de distancia (suma de canales RGB) y se
    descartan los que se quedan sin ni un píxel asignado: la paleta que se devuelve son
    colores que de verdad aparecen en la foto, no ruido de una k demasiado alta."""
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    datos = rgb.reshape((-1, 3)).astype(np.float32)
    k = max(1, min(int(k), datos.shape[0]))
    criterios = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5)
    _, etiquetas, centros = cv2.kmeans(datos, k, None, criterios, 5, cv2.KMEANS_PP_CENTERS)
    cuentas = np.bincount(etiquetas.flatten(), minlength=k)
    total = datos.shape[0]

    fusionados = []  # [(centro, cuenta)], centros cercanos entre sí ya sumados
    usado = [False] * k
    for i in range(k):
        if usado[i] or cuentas[i] == 0:
            continue
        centro, cuenta = centros[i].copy(), int(cuentas[i])
        for j in range(i + 1, k):
            if not usado[j] and np.linalg.norm(centros[i] - centros[j]) < 10.0:
                cuenta += int(cuentas[j])
                usado[j] = True
        fusionados.append((centro, cuenta))
    fusionados.sort(key=lambda par: -par[1])

    paleta = []
    for centro, cuenta in fusionados:
        r, g, b = (int(round(c)) for c in np.clip(centro, 0, 255))
        paleta.append({'hex': '#%02x%02x%02x' % (r, g, b), 'proporcion': round(cuenta / total, 4)})
    return paleta


def proporciones_objeto(img, fg=None, avisar=print):
    """Caja delimitadora del primer plano → ancho/alto en píxeles y su razón. `None` (sin
    dato) si el primer plano queda vacío incluso tras el fallback de `mascara_primer_plano`
    (no debería pasar: ese fallback siempre deja algo; se comprueba de todos modos)."""
    if fg is None:
        fg = mascara_primer_plano(img, avisar=avisar)
    caja = _bbox(fg)
    if caja is None:
        return None
    x0, y0, x1, y1 = caja
    ancho, alto = x1 - x0 + 1, y1 - y0 + 1
    return {'ancho_px': ancho, 'alto_px': alto, 'razon': round(ancho / alto, 3), 'bbox': [x0, y0, x1, y1]}


def horizonte(img):
    """Fracción de la altura donde cae la línea recta más larga dentro de ±5° de la
    horizontal (Canny + `HoughLinesP`). `None` (sin dato) si no hay ninguna así de clara —
    no se inventa un horizonte en una foto que no lo tiene."""
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    alto, ancho = gris.shape[:2]
    bordes = cv2.Canny(gris, 60, 150)
    lineas = cv2.HoughLinesP(bordes, 1, math.pi / 180, threshold=max(20, ancho // 8),
                              minLineLength=max(10, ancho // 3), maxLineGap=max(2, ancho // 30))
    if lineas is None:
        return None
    mejor_y, mejor_long = None, 0.0
    for x1, y1, x2, y2 in lineas[:, 0]:
        dx, dy = float(x2 - x1), float(y2 - y1)
        longitud = math.hypot(dx, dy)
        angulo = abs(math.degrees(math.atan2(dy, dx)))
        angulo = min(angulo, 180.0 - angulo)
        if angulo <= 5.0 and longitud > mejor_long:
            mejor_long, mejor_y = longitud, (y1 + y2) / 2.0
    if mejor_y is None:
        return None
    return round(mejor_y / alto, 4)


def formas_dominantes(img, fg=None, avisar=print, area_minima_frac=0.01):
    """Contornos externos del primer plano (o de los bordes Canny de toda la foto si no hay
    primer plano separable) con área ≥ `area_minima_frac` de la foto: circularidad, vértices
    (`approxPolyDP`, épsilon 2% del perímetro) y razón de aspecto del rectángulo mínimo.
    Clasificación DECLARADA en el docstring del módulo — nunca un reconocedor de objetos.
    Lista ordenada por área descendente; vacía si no hay ningún contorno así de grande."""
    if fg is None:
        fg = mascara_primer_plano(img, avisar=avisar)
    fuente = (fg.astype(np.uint8)) * 255
    if not fuente.any():
        fuente = cv2.Canny(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 60, 150)
    contornos, _ = cv2.findContours(fuente, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area_img = img.shape[0] * img.shape[1]
    salida = []
    for c in contornos:
        area = cv2.contourArea(c)
        if area < area_minima_frac * area_img:
            continue
        perim = cv2.arcLength(c, True)
        if perim <= 0:
            continue
        circularidad = 4.0 * math.pi * area / (perim * perim)
        vertices = len(cv2.approxPolyDP(c, 0.02 * perim, True))
        (_cx, _cy), (rw, rh), _ang = cv2.minAreaRect(c)
        razon = (max(rw, rh) / min(rw, rh)) if min(rw, rh) > 0 else 1.0
        if circularidad >= 0.85:
            forma = 'esfera'
        elif 4 <= vertices <= 6:
            forma = 'rectangulo'
        elif razon >= 1.6 and 0.30 <= circularidad <= 0.85:
            forma = 'cilindro'
        else:
            forma = 'irregular'
        mascara_contorno = cv2.drawContours(np.zeros(fuente.shape, np.uint8), [c], -1, 255, -1) > 0
        salida.append({'forma': forma, 'area_px': round(float(area), 1),
                       'circularidad': round(float(circularidad), 3),
                       'vertices': vertices, 'razon_aspecto': round(float(razon), 3),
                       'color': _color_medio_hex(img, mascara_contorno)})
    salida.sort(key=lambda d: -d['area_px'])
    return salida


def _texto_prompt(ruta_imagen, paleta, prop, horiz, formas):
    colores = ', '.join(f'{p["hex"]} ({p["proporcion"] * 100:.0f}%)' for p in paleta)
    razon_txt = f'{prop["razon"]}:1 ({prop["ancho_px"]}×{prop["alto_px"]} px)' if prop else 'sin dato'
    horiz_txt = f'{horiz * 100:.0f}% de la altura' if horiz is not None else 'sin dato (no se detecta una línea de horizonte clara)'
    formas_txt = '; '.join(f'{f["forma"]} (circularidad {f["circularidad"]}, {f["vertices"]} vértices)' for f in formas) or 'sin dato (ningún contorno lo bastante grande)'
    return (
        f'# Prompt de diseño 3D — medido de {os.path.basename(ruta_imagen)}\n'
        f'# No es un reconocedor de objetos: son medidas geométricas y de color de esta foto,\n'
        f'# nunca una adivinanza de qué es. Para three.js.\n\n'
        f'ES: Diseña una escena three.js con esta paleta medida: {colores}. Proporción del '
        f'objeto principal: {razon_txt}. Horizonte: {horiz_txt}. Formas dominantes por '
        f'circularidad de contorno: {formas_txt}.\n\n'
        f'EN: Design a three.js scene with this measured palette: {colores}. Main subject '
        f'proportion: {razon_txt}. Horizon: {horiz_txt}. Dominant shapes by contour '
        f'circularity: {formas_txt}.\n'
    )


_TIPO_POR_FORMA = {'esfera': 'esfera', 'cilindro': 'cilindro', 'rectangulo': 'caja'}


def _escena_de_formas(img, formas, ancho_img, alto_img):
    metros_por_px = ANCHO_ESCENA_M / ancho_img
    piezas = []
    for i, f in enumerate(formas):
        tipo = _TIPO_POR_FORMA.get(f['forma'])
        if tipo is None:
            continue  # "irregular": no se fuerza a una primitiva que no midió
        lado = math.sqrt(f['area_px']) * metros_por_px
        if tipo == 'esfera':
            tam = [round(lado / 1.772, 4)]  # radio de una esfera con la misma área que el contorno (pi*r^2=area)
        elif tipo == 'cilindro':
            tam = [round(lado / 2, 4), round(lado / 2, 4), round(lado * f['razon_aspecto'] / 2, 4)]
        else:
            tam = [round(lado, 4), round(lado, 4), round(lado / 4, 4)]
        piezas.append({'nombre': f'{f["forma"]}_{i}', 'tipo': tipo, 'pos': [round(i * 0.4, 3), 0.0, 0.0],
                       'tam': tam, 'color': f['color'], 'grupo': f'forma_{i}'})
    return {'unidades': 'm', 'piezas': piezas} if piezas else None


def prompt3d(ruta_imagen, salida=None, escena=None, avisar=print):
    """Mide paleta, proporciones del objeto, horizonte y formas dominantes (ver docstring del
    módulo) y escribe un prompt de diseño ES/EN para three.js. Con `escena`, además escribe
    una `escena.json` de primitivas (solo con las formas que sí clasificó como
    caja/cilindro/esfera; las "irregular" no fuerzan ninguna). Devuelve un dict con `prompt`
    (ruta del .txt) y, si aplica, `escena` (ruta del .json) y `sin_escena` (motivo si no se
    escribió ninguna: ninguna forma clasificable)."""
    ruta_imagen = os.path.abspath(ruta_imagen)
    img = _leer_imagen(ruta_imagen)
    alto, ancho = img.shape[:2]
    fg = mascara_primer_plano(img, avisar=avisar)
    paleta = paleta_dominante(img)
    prop = proporciones_objeto(img, fg=fg, avisar=avisar)
    horiz = horizonte(img)
    formas = formas_dominantes(img, fg=fg, avisar=avisar)

    base = os.path.splitext(os.path.basename(ruta_imagen))[0]
    carpeta = os.path.dirname(ruta_imagen) or '.'
    ruta_txt = salida if salida else os.path.join(carpeta, f'{base}_prompt3d.txt')
    ruta_txt = os.path.abspath(ruta_txt)
    os.makedirs(os.path.dirname(ruta_txt) or '.', exist_ok=True)
    with open(ruta_txt, 'w', encoding='utf-8') as fh:
        fh.write(_texto_prompt(ruta_imagen, paleta, prop, horiz, formas))
    avisar(f'prompt: {ruta_txt}')

    resultado = {'prompt': ruta_txt, 'paleta': paleta, 'proporciones': prop, 'horizonte': horiz, 'formas': formas}
    if escena:
        datos_escena = _escena_de_formas(img, formas, ancho, alto)
        if datos_escena is None:
            resultado['sin_escena'] = 'ninguna forma medida se clasificó como caja/cilindro/esfera'
            avisar(f'sin escena: {resultado["sin_escena"]}')
        else:
            ruta_escena = os.path.abspath(escena)
            os.makedirs(os.path.dirname(ruta_escena) or '.', exist_ok=True)
            with open(ruta_escena, 'w', encoding='utf-8') as fh:
                json.dump(datos_escena, fh, ensure_ascii=False, indent=1)
            avisar(f'escena: {ruta_escena} ({len(datos_escena["piezas"])} piezas)')
            resultado['escena'] = ruta_escena
    return resultado


# ───────────────────────────────── CLI ─────────────────────────────────

def _cli(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0 if argv and argv[0] in ('-h', '--help') else 1
    verbo = argv[0]
    resto = argv[1:]
    if verbo not in ('despiece', 'prompt3d'):
        print(f'verbo no reconocido: "{verbo}" (usa despiece/prompt3d)')
        return 1
    if not resto or resto[0].startswith('--'):
        print(f'uso: volumen.py {verbo} <imagen> [opciones] (ver --help)')
        return 1
    imagen = resto[0]
    opts = resto[1:]

    def _valor(bandera, por_defecto=None):
        if bandera in opts:
            i = opts.index(bandera)
            if i + 1 < len(opts) and not opts[i + 1].startswith('--'):
                return opts[i + 1]
            return True
        return por_defecto

    try:
        if verbo == 'despiece':
            capas = _valor('--capas', 4)
            try:
                capas = int(capas)
            except (TypeError, ValueError):
                print(f'--capas necesita un número entero, no "{capas}"')
                return 1
            r = despiece(imagen, capas=capas, salida=_valor('--salida'), html=('--html' in opts))
        else:
            r = prompt3d(imagen, salida=_valor('--salida'), escena=_valor('--escena'))
    except (FileNotFoundError, ValueError) as e:
        print(f'sin dato: {e}')
        return 2
    print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    sys.exit(_cli(sys.argv[1:]))
