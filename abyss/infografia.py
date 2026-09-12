# -*- coding: utf-8 -*-
"""Infografía: de un CSV o JSON a un SVG limpio, sin más dependencia que la biblioteca estándar.

    python infografia.py <datos.csv|datos.json> --tipo barras|barras_h|lineas|tabla
                          [--x columna] [--y columna[,columna2,...]]
                          [--titulo "..."] [--subtitulo "..."] [--fuente "..."]
                          [--salida f.svg] [--ancho 1200] [--alto 675]
                          [--oscuro] [--es | --no-es]

Datos de entrada: un `.csv` con cabecera (una fila = un registro), o un `.json` que sea o
bien una LISTA de objetos (`[{"mes": "ene", "ventas": 120}, ...]`, cada objeto una fila) o
bien un objeto de COLUMNAS (`{"mes": ["ene", "feb"], "ventas": [120, 90]}`). El orden de las
columnas se conserva tal como viene en el fichero (cabecera del CSV, o claves del primer
objeto/del propio objeto de columnas en JSON).

`--x` (por defecto, la primera columna) marca la categoría/etiqueta; `--y` (por defecto, la
segunda columna) marca el valor — con varias separadas por comas, cada una es una SERIE (una
barra más por categoría, una `<polyline>` más). En `--tipo tabla` no hay `--x`/`--y`: se
dibujan todas las columnas, o solo las que traiga `--y` (como filtro de columnas, en ese
orden) si se da.

Paleta sobria fija de 5 tonos (se repiten si hay más de 5 series), fondo blanco o, con
`--oscuro`, sobre `#0f0e0e`. Tipografía `system-ui` con reserva a `sans-serif`. Ejes con
ticks "bonitos" (pasos 1-2-5 de la propia escala de los datos, nunca un número fijo de
rayas). Etiquetas de valor sobre cada barra/punto. Leyenda automática si hay más de una
serie. Pie con `--fuente` si se da. Todo texto pasa por `xml.sax.saxutils.escape` antes de
entrar en el SVG (un `<` o un `&` en un título no rompe el fichero). Números con coma
decimal y punto de millar si `--es` (por defecto sí; `--no-es` usa punto decimal y coma de
millar).

En `--tipo tabla`, `--alto` es un MÍNIMO: si hacen falta más filas de las que caben, el SVG
sale más alto (la altura la decide el número de filas, no al revés).

Límite declarado: no hay reescalado de las etiquetas del eje de categorías si son muchas o
largas — con muchas categorías se solapan; toca acortarlas en los datos de entrada o pedir un
`--ancho` mayor. Este guion no elige "el mejor" tipo de gráfico por ti; el tipo lo dices tú.

Qué sale de la máquina: nada. Sin red, sin `mem` (no resuelve un proyecto de Claude Code):
solo transforma el fichero de entrada en el SVG de salida.

El SVG no se convierte a PNG aquí (no hay rasterizado en la biblioteca estándar): se abre
tal cual en un navegador, o se incrusta con `<img src="...svg">`.
"""
import csv
import json
import math
import os
import sys
from xml.sax.saxutils import escape

TIPOS = ('barras', 'barras_h', 'lineas', 'tabla')
PALETA = ['#3B6E8F', '#C97B3B', '#5B8C5A', '#A24C4C', '#7A5C99']


def paleta_color(indice):
    return PALETA[indice % len(PALETA)]


def colores(oscuro):
    if oscuro:
        return {"fondo": "#0f0e0e", "texto": "#e8e4df", "eje": "#8a8580",
                "rejilla": "#2c2a29", "atenuado": "#b9b4ae"}
    return {"fondo": "#ffffff", "texto": "#1a1a1a", "eje": "#666666",
            "rejilla": "#e2e2e2", "atenuado": "#555555"}


def _a_float(valor):
    """`None` si `valor` no se puede leer como número; tolera coma decimal y punto de
    millar (o al revés) para no obligar a que el CSV/JSON de entrada venga en un único
    formato de número."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace(' ', '')
    if texto == '':
        return None
    if ',' in texto and '.' in texto:
        texto = texto.replace('.', '').replace(',', '.') if texto.rfind(',') > texto.rfind('.') \
            else texto.replace(',', '')
    elif ',' in texto:
        texto = texto.replace(',', '.')
    try:
        return float(texto)
    except ValueError:
        return None


def formatear_numero(valor, es=True):
    if valor is None:
        return ''
    neg = valor < 0
    valor = abs(valor)
    if abs(valor - round(valor)) < 1e-9:
        entero_txt, dec_txt = str(int(round(valor))), ''
    else:
        texto = f'{valor:.2f}'.rstrip('0').rstrip('.')
        entero_txt, _, dec_txt = texto.partition('.')
    grupos = []
    while len(entero_txt) > 3:
        grupos.insert(0, entero_txt[-3:])
        entero_txt = entero_txt[:-3]
    grupos.insert(0, entero_txt)
    sep_miles, sep_dec = ('.', ',') if es else (',', '.')
    salida = sep_miles.join(grupos)
    if dec_txt:
        salida += sep_dec + dec_txt
    return ('-' if neg else '') + salida


def ticks_bonitos(vmin, vmax, objetivo=5):
    """Pasos "bonitos" (1-2-5 × potencia de diez) sobre el propio rango de los datos:
    nunca un número de rayas fijo, siempre sacado de `vmin`/`vmax`."""
    if vmin == vmax:
        vmin, vmax = (vmin, vmin + 1.0) if vmin >= 0 else (vmin - 1.0, vmin)
    rango = vmax - vmin
    paso_crudo = rango / objetivo
    exp = math.floor(math.log10(paso_crudo))
    base = 10 ** exp
    paso = base
    for m in (1, 2, 5, 10):
        paso = m * base
        if paso >= paso_crudo:
            break
    inicio = math.floor(vmin / paso) * paso
    fin = math.ceil(vmax / paso) * paso
    n = int(round((fin - inicio) / paso))
    return [inicio + i * paso for i in range(n + 1)]


def _escala(v, vmin, vmax, y0, y1):
    """Posición en pantalla (entre y0 arriba e y1 abajo) del valor `v` dentro de
    [vmin, vmax]: a más valor, menos "y" (arriba en SVG es y pequeño)."""
    if vmax == vmin:
        return (y0 + y1) / 2
    return y1 - (v - vmin) / (vmax - vmin) * (y1 - y0)


def _margenes(opts):
    arriba = 26 + (34 if opts['titulo'] else 0) + (22 if opts['subtitulo'] else 0)
    abajo = 46 + (14 if opts['fuente'] else 0)
    return {"izq": 90, "der": 32, "arriba": arriba, "abajo": abajo}


def _marco(ancho, alto, oscuro, titulo, subtitulo, fuente):
    c = colores(oscuro)
    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho} {alto}" '
              f'width="{ancho}" height="{alto}" '
              f'font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif">']
    if titulo:
        partes.append(f'<title>{escape(titulo)}</title>')
    partes.append(f'<rect x="0" y="0" width="{ancho}" height="{alto}" fill="{c["fondo"]}" data-role="fondo"/>')
    y_texto = 30
    if titulo:
        partes.append(f'<text x="28" y="{y_texto}" font-size="22" font-weight="600" '
                       f'fill="{c["texto"]}">{escape(titulo)}</text>')
        y_texto += 26
    if subtitulo:
        partes.append(f'<text x="28" y="{y_texto}" font-size="14" '
                       f'fill="{c["atenuado"]}">{escape(subtitulo)}</text>')
    if fuente:
        partes.append(f'<text x="28" y="{alto - 14}" font-size="11" '
                       f'fill="{c["atenuado"]}">Fuente: {escape(fuente)}</text>')
    return partes, c


def _leyenda(partes, colr, series, ancho, m):
    if len(series) <= 1:
        return
    ly = max(16, m['arriba'] - 8)
    anchos = [12 + 7 * len(nombre) + 22 for nombre, _ in series]
    cursor = (ancho - m['der']) - sum(anchos)
    for j, (nombre, _) in enumerate(series):
        partes.append(f'<rect x="{cursor:.1f}" y="{ly - 10}" width="10" height="10" '
                       f'fill="{paleta_color(j)}"/>')
        partes.append(f'<text x="{cursor + 14:.1f}" y="{ly - 1}" font-size="11" '
                       f'fill="{colr["texto"]}">{escape(nombre)}</text>')
        cursor += anchos[j]


def _series_numericas(filas, y_cols):
    series = []
    for col in y_cols:
        vals = [_a_float(r.get(col)) for r in filas]
        if any(v is None for v in vals):
            raise ValueError(f'la columna "{col}" no es numérica en alguna fila')
        series.append((col, vals))
    return series


def _dibujar_barras(filas, x_col, y_cols, opts, horizontal=False):
    es = opts['es']
    m = _margenes(opts)
    ancho, alto = opts['ancho'], opts['alto']
    partes, colr = _marco(ancho, alto, opts['oscuro'], opts['titulo'], opts['subtitulo'], opts['fuente'])
    categorias = [str(r.get(x_col, '')) for r in filas]
    series = _series_numericas(filas, y_cols)
    todos = [v for _, vals in series for v in vals] or [0.0]
    vmin, vmax = min(0.0, min(todos)), max(0.0, max(todos))
    if vmin == vmax:
        vmax = vmin + 1.0
    ticks = ticks_bonitos(vmin, vmax)
    vmin_t, vmax_t = min(ticks[0], vmin), max(ticks[-1], vmax)
    x0, x1 = m['izq'], ancho - m['der']
    y0, y1 = m['arriba'], alto - m['abajo']
    n_cat = max(1, len(categorias))
    n_ser = max(1, len(series))

    if not horizontal:
        for t in ticks:
            y = _escala(t, vmin_t, vmax_t, y0, y1)
            partes.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" '
                           f'stroke="{colr["rejilla"]}" stroke-width="1"/>')
            partes.append(f'<text x="{x0 - 10}" y="{y + 4:.1f}" font-size="11" text-anchor="end" '
                           f'fill="{colr["atenuado"]}">{formatear_numero(t, es)}</text>')
        y_base = _escala(0, vmin_t, vmax_t, y0, y1)
        partes.append(f'<line x1="{x0}" y1="{y_base:.1f}" x2="{x1}" y2="{y_base:.1f}" '
                       f'stroke="{colr["eje"]}" stroke-width="1.4"/>')
        ancho_grupo = (x1 - x0) / n_cat
        ancho_barra = ancho_grupo * 0.7 / n_ser
        for i, cat in enumerate(categorias):
            cx0 = x0 + i * ancho_grupo + ancho_grupo * 0.15
            for j, (_, vals) in enumerate(series):
                v = vals[i]
                bx = cx0 + j * ancho_barra
                y_v = _escala(v, vmin_t, vmax_t, y0, y1)
                y_top, alto_barra = min(y_v, y_base), abs(y_v - y_base)
                partes.append(f'<rect x="{bx:.1f}" y="{y_top:.1f}" width="{ancho_barra * 0.86:.1f}" '
                               f'height="{alto_barra:.1f}" fill="{paleta_color(j)}"/>')
                y_txt = y_top - 6 if v >= 0 else y_top + alto_barra + 12
                partes.append(f'<text x="{bx + ancho_barra * 0.43:.1f}" y="{y_txt:.1f}" font-size="10" '
                               f'text-anchor="middle" fill="{colr["texto"]}">{formatear_numero(v, es)}</text>')
            partes.append(f'<text x="{x0 + i * ancho_grupo + ancho_grupo / 2:.1f}" y="{y1 + 18}" '
                           f'font-size="11" text-anchor="middle" fill="{colr["texto"]}">{escape(cat)}</text>')
    else:
        for t in ticks:
            x = x0 + (t - vmin_t) / (vmax_t - vmin_t) * (x1 - x0)
            partes.append(f'<line x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y1}" '
                           f'stroke="{colr["rejilla"]}" stroke-width="1"/>')
            partes.append(f'<text x="{x:.1f}" y="{y1 + 16}" font-size="11" text-anchor="middle" '
                           f'fill="{colr["atenuado"]}">{formatear_numero(t, es)}</text>')
        x_base = x0 + (0 - vmin_t) / (vmax_t - vmin_t) * (x1 - x0)
        partes.append(f'<line x1="{x_base:.1f}" y1="{y0}" x2="{x_base:.1f}" y2="{y1}" '
                       f'stroke="{colr["eje"]}" stroke-width="1.4"/>')
        alto_grupo = (y1 - y0) / n_cat
        alto_barra = alto_grupo * 0.7 / n_ser
        for i, cat in enumerate(categorias):
            cy0 = y0 + i * alto_grupo + alto_grupo * 0.15
            for j, (_, vals) in enumerate(series):
                v = vals[i]
                by = cy0 + j * alto_barra
                x_v = x0 + (v - vmin_t) / (vmax_t - vmin_t) * (x1 - x0)
                x_izq, ancho_barra_px = min(x_v, x_base), abs(x_v - x_base)
                partes.append(f'<rect x="{x_izq:.1f}" y="{by:.1f}" width="{ancho_barra_px:.1f}" '
                               f'height="{alto_barra * 0.86:.1f}" fill="{paleta_color(j)}"/>')
                ancla = 'start' if v >= 0 else 'end'
                x_txt = x_v + 6 if v >= 0 else x_v - 6
                partes.append(f'<text x="{x_txt:.1f}" y="{by + alto_barra * 0.43 + 4:.1f}" font-size="10" '
                               f'text-anchor="{ancla}" fill="{colr["texto"]}">{formatear_numero(v, es)}</text>')
            partes.append(f'<text x="{x0 - 10}" y="{y0 + i * alto_grupo + alto_grupo / 2 + 4:.1f}" '
                           f'font-size="11" text-anchor="end" fill="{colr["texto"]}">{escape(cat)}</text>')

    _leyenda(partes, colr, series, ancho, m)
    partes.append('</svg>')
    return '\n'.join(partes)


def _dibujar_lineas(filas, x_col, y_cols, opts):
    es = opts['es']
    m = _margenes(opts)
    ancho, alto = opts['ancho'], opts['alto']
    partes, colr = _marco(ancho, alto, opts['oscuro'], opts['titulo'], opts['subtitulo'], opts['fuente'])
    categorias = [str(r.get(x_col, '')) for r in filas]
    series = _series_numericas(filas, y_cols)
    todos = [v for _, vals in series for v in vals] or [0.0]
    vmin, vmax = min(todos), max(todos)
    if vmin == vmax:
        vmin, vmax = vmin - 1.0, vmax + 1.0
    ticks = ticks_bonitos(vmin, vmax)
    vmin_t, vmax_t = min(ticks[0], vmin), max(ticks[-1], vmax)
    x0, x1 = m['izq'], ancho - m['der']
    y0, y1 = m['arriba'], alto - m['abajo']

    for t in ticks:
        y = _escala(t, vmin_t, vmax_t, y0, y1)
        partes.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" '
                       f'stroke="{colr["rejilla"]}" stroke-width="1"/>')
        partes.append(f'<text x="{x0 - 10}" y="{y + 4:.1f}" font-size="11" text-anchor="end" '
                       f'fill="{colr["atenuado"]}">{formatear_numero(t, es)}</text>')
    partes.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="{colr["eje"]}" stroke-width="1.4"/>')
    partes.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="{colr["eje"]}" stroke-width="1.4"/>')

    n = max(1, len(categorias) - 1)

    def _x_de(i):
        return (x0 + x1) / 2 if len(categorias) <= 1 else x0 + (i / n) * (x1 - x0)

    for i, cat in enumerate(categorias):
        partes.append(f'<text x="{_x_de(i):.1f}" y="{y1 + 18}" font-size="11" text-anchor="middle" '
                       f'fill="{colr["texto"]}">{escape(cat)}</text>')
    for j, (_, vals) in enumerate(series):
        puntos = [f'{_x_de(i):.1f},{_escala(v, vmin_t, vmax_t, y0, y1):.1f}' for i, v in enumerate(vals)]
        partes.append(f'<polyline points="{" ".join(puntos)}" fill="none" stroke="{paleta_color(j)}" '
                       f'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')
        for i, v in enumerate(vals):
            partes.append(f'<circle cx="{_x_de(i):.1f}" cy="{_escala(v, vmin_t, vmax_t, y0, y1):.1f}" '
                           f'r="3" fill="{paleta_color(j)}"/>')

    _leyenda(partes, colr, series, ancho, m)
    partes.append('</svg>')
    return '\n'.join(partes)


def _dibujar_tabla(filas, columnas, opts):
    es = opts['es']
    cols = [c.strip() for c in opts['y'].split(',')] if opts['y'] else list(columnas)
    m = _margenes(opts)
    alto_fila, alto_cabecera = 30, 34
    alto_necesario = m['arriba'] + alto_cabecera + alto_fila * len(filas) + m['abajo']
    ancho, alto = opts['ancho'], max(opts['alto'], math.ceil(alto_necesario))
    partes, colr = _marco(ancho, alto, opts['oscuro'], opts['titulo'], opts['subtitulo'], opts['fuente'])
    x0, x1 = 28, ancho - 28
    y0 = m['arriba']
    ancho_col = (x1 - x0) / max(1, len(cols))

    partes.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{alto_cabecera}" '
                   f'fill="{paleta_color(0)}"/>')
    for j, col in enumerate(cols):
        partes.append(f'<text x="{x0 + j * ancho_col + 10:.1f}" y="{y0 + alto_cabecera - 11:.1f}" '
                       f'font-size="12" font-weight="600" fill="#ffffff">{escape(col)}</text>')

    y = y0 + alto_cabecera
    for i, fila in enumerate(filas):
        if i % 2 == 1:
            partes.append(f'<rect x="{x0:.1f}" y="{y:.1f}" width="{x1 - x0:.1f}" height="{alto_fila}" '
                           f'fill="{colr["rejilla"]}"/>')
        for j, col in enumerate(cols):
            numero = _a_float(fila.get(col))
            texto = formatear_numero(numero, es) if numero is not None else str(fila.get(col, ''))
            if numero is not None:
                cx, ancla = x0 + (j + 1) * ancho_col - 10, 'end'
            else:
                cx, ancla = x0 + j * ancho_col + 10, 'start'
            partes.append(f'<text x="{cx:.1f}" y="{y + alto_fila - 10:.1f}" font-size="12" '
                           f'text-anchor="{ancla}" fill="{colr["texto"]}">{escape(texto)}</text>')
        y += alto_fila

    partes.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y - y0:.1f}" '
                   f'fill="none" stroke="{colr["eje"]}" stroke-width="1"/>')
    partes.append('</svg>')
    return '\n'.join(partes)


def leer_datos(ruta):
    """Devuelve `(filas, columnas)`: `filas` es una lista de dicts, `columnas` el orden de
    las claves tal como viene en el fichero de entrada."""
    ext = os.path.splitext(ruta)[1].lower()
    if ext == '.csv':
        with open(ruta, encoding='utf-8-sig', newline='') as fh:
            lector = csv.DictReader(fh)
            columnas = list(lector.fieldnames or [])
            filas = [dict(r) for r in lector]
    elif ext == '.json':
        with open(ruta, encoding='utf-8') as fh:
            datos = json.load(fh)
        if isinstance(datos, list):
            filas = [dict(r) for r in datos]
            columnas = list(filas[0].keys()) if filas else []
        elif isinstance(datos, dict):
            columnas = list(datos.keys())
            n = max((len(v) for v in datos.values() if isinstance(v, list)), default=0)
            filas = [{c: (datos[c][i] if isinstance(datos[c], list) and i < len(datos[c]) else None)
                      for c in columnas} for i in range(n)]
        else:
            raise ValueError('el JSON debe ser una lista de filas o un objeto de columnas')
    else:
        raise ValueError(f'extensión no soportada: "{ext}" (usa .csv o .json)')
    return filas, columnas


def generar_svg(filas, columnas, opts):
    if opts['tipo'] == 'tabla':
        return _dibujar_tabla(filas, columnas, opts)
    x_col = opts['x'] or (columnas[0] if columnas else None)
    y_cols = [c.strip() for c in opts['y'].split(',')] if opts['y'] else \
        ([columnas[1]] if len(columnas) > 1 else [])
    if not x_col or not y_cols:
        raise ValueError('faltan columnas: pásalas con --x/--y, o usa un CSV/JSON con al menos 2 columnas')
    # `--x`/`--y` con un nombre de columna que no existe debe fallar con un mensaje
    # claro (ESPECIFICACION.md §3: ningún argumento que no encaje se traga en
    # silencio) — se valida ANTES de dibujar, con las columnas reales del fichero en
    # el mensaje, en vez de dejar que `r.get(col)` calle el error con `None`.
    for c in [x_col] + y_cols:
        if c not in columnas:
            raise ValueError(f'no existe la columna "{c}"; las columnas de este fichero '
                              f'son: {", ".join(columnas)}')
    if opts['tipo'] == 'barras':
        return _dibujar_barras(filas, x_col, y_cols, opts, horizontal=False)
    if opts['tipo'] == 'barras_h':
        return _dibujar_barras(filas, x_col, y_cols, opts, horizontal=True)
    if opts['tipo'] == 'lineas':
        return _dibujar_lineas(filas, x_col, y_cols, opts)
    raise ValueError(f'tipo desconocido: "{opts["tipo"]}"')


def _cli(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 1
    ruta_datos = argv[0]
    resto = argv[1:]
    opts = {"tipo": None, "x": None, "y": None, "titulo": None, "subtitulo": None, "fuente": None,
            "salida": None, "ancho": 1200, "alto": 675, "oscuro": False, "es": True}
    con_valor = {"--tipo": "tipo", "--x": "x", "--y": "y", "--titulo": "titulo",
                 "--subtitulo": "subtitulo", "--fuente": "fuente", "--salida": "salida",
                 "--ancho": "ancho", "--alto": "alto"}
    i = 0
    while i < len(resto):
        a = resto[i]
        if a in con_valor and i + 1 < len(resto) and not resto[i + 1].startswith('--'):
            i += 1
            v = resto[i]
            clave = con_valor[a]
            if clave in ('ancho', 'alto'):
                try:
                    opts[clave] = int(v)
                except ValueError:
                    print(f'--{clave} necesita un número, no "{v}"')
                    return 1
            else:
                opts[clave] = v
        elif a == '--oscuro':
            opts['oscuro'] = True
        elif a == '--es':
            opts['es'] = True
        elif a == '--no-es':
            opts['es'] = False
        else:
            print(f'argumento no reconocido: {a} (usa --tipo/--x/--y/--titulo/--subtitulo/'
                  f'--fuente/--salida/--ancho/--alto/--oscuro/--no-es)')
            return 1
        i += 1

    if opts['tipo'] not in TIPOS:
        print(f'--tipo es obligatorio y debe ser uno de: {", ".join(TIPOS)}')
        return 1

    # Un --ancho/--alto por debajo de los márgenes del módulo no deja lienzo que
    # dibujar (SVG con width/height negativos que ningún navegador dibuja):
    # ESPECIFICACION.md §3 exige código 1 y un mensaje claro, nunca tragárselo en
    # silencio. El mínimo sale de los propios márgenes, no de un número decretado.
    m_min = _margenes(opts)
    minimo_ancho = m_min['izq'] + m_min['der']
    if opts['ancho'] <= minimo_ancho:
        print(f'--ancho debe ser mayor que {minimo_ancho} (los márgenes ya ocupan eso), no "{opts["ancho"]}"')
        return 1
    minimo_alto = m_min['arriba'] + m_min['abajo']
    if opts['alto'] <= minimo_alto:
        print(f'--alto debe ser mayor que {minimo_alto} (los márgenes ya ocupan eso), no "{opts["alto"]}"')
        return 1

    try:
        filas, columnas = leer_datos(ruta_datos)
    except Exception as e:
        print(f'sin infografía: {type(e).__name__} {e}')
        return 2
    if not filas:
        print('sin infografía: no hay filas que dibujar')
        return 2

    try:
        svg = generar_svg(filas, columnas, opts)
    except Exception as e:
        print(f'sin infografía: {type(e).__name__} {e}')
        return 2

    salida = opts['salida'] or (os.path.splitext(ruta_datos)[0] + '_infografia.svg')
    with open(salida, 'w', encoding='utf-8') as fh:
        fh.write(svg)
    print(salida)
    return 0


if __name__ == '__main__':
    try:                       # la consola de Windows y la salida tienen que hablar
        from . import consola  # el mismo idioma: ver abyss/consola.py
    except ImportError:
        import consola
    consola.preparar()
    sys.exit(_cli(sys.argv[1:]))
