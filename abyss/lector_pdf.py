# -*- coding: utf-8 -*-
"""Lector de PDF: leer solo lo que toca, no el PDF entero cada vez.

    python lector_pdf.py --indexar <pdf>
    python lector_pdf.py --secciones <pdf>
    python lector_pdf.py --buscar <pdf> "consulta" [k=5]
    python lector_pdf.py --leer <pdf> <sección|rango-de-páginas>
    python lector_pdf.py --ahorro <pdf> "consulta" [k=5]

`--indexar`: extrae texto con PyMuPDF (`fitz`) si está instalado, si no con `pypdf`; sin
ninguno, «sin dato: pip install pymupdf» y código 1 — nunca un fallback que invente
texto. Las secciones salen de una heurística de tamaño de fuente con `fitz` (más precisa)
o de texto en mayúsculas/numeración con `pypdf` (más pobre). El índice (texto de cada
página + secciones) se guarda en `mem/pdf/<sha1 del fichero>.json`, por HASH del
contenido: el mismo PDF nunca se re-extrae dos veces, y un PDF distinto con el mismo
nombre nunca pisa el índice de otro. Los demás verbos cargan el índice si ya existe o lo
construyen la primera vez.

`--buscar`: TF-IDF de biblioteca estándar sobre las páginas indexadas — no es semántico,
es frecuencia de términos. `--leer`: un rango de páginas o el título de una sección.
`--ahorro`: caracteres que leería `--buscar` frente al PDF entero, como proporción — mide
ahorro de LECTURA, nunca calidad de respuesta (eso solo lo mediría un A/B con preguntas y
respuestas reales, que esta pieza no hace).

Sin gancho: se invoca a mano, nunca desde `settings.json`. Sin red: nada sale de la
máquina, ni se sube el PDF a ningún sitio. `ABYSS_PDF_FORZAR_MOTOR=fitz|pypdf` fuerza un
motor aunque el otro esté instalado, para probar las dos heurísticas de sección en la
misma máquina.

Carpeta de datos: nunca `dirname(__file__)`; la resuelve `rutas.resolver()` (§1 de
ESPECIFICACION.md), solo dentro de `__main__`.
"""
import sys
try:                       # la consola de Windows y la salida tienen que hablar
    from . import consola  # el mismo idioma: ver abyss/consola.py
except ImportError:
    import consola
consola.preparar()
import os
import re
import json
import math
import hashlib
import logging
import unicodedata
from collections import Counter

try:
    from . import rutas
except ImportError:
    import rutas

STOP = set("""de la el en y a los del se las por un para con no una su al lo como mas pero sus le ya o
este si porque esta entre cuando muy sin sobre tambien me hasta hay donde quien desde todo nos durante
todos uno les ni contra otros ese eso ante ellos esto mi antes algunos que the and for with from that
this those these into onto your you are was were has have had not but all any can will just its it""".split())

RE_RANGO = re.compile(r'^p?(\d+)(?:-p?(\d+))?$', re.I)
RE_NUMERADA = re.compile(r'^(\d+(\.\d+)*\.?)\s+\S')
RE_CAPITULO = re.compile(r'^(cap[ií]tulo|chapter|secci[oó]n|section)\b', re.I)


# ---------- extracción (una función por motor) ----------

def extraer_fitz(ruta_pdf):
    """(paginas_texto, secciones) con PyMuPDF. `ImportError` si `fitz` no está
    instalado — no se atrapa aquí, la atrapa `extraer()`."""
    import fitz  # PyMuPDF
    doc = fitz.open(ruta_pdf)
    paginas = []
    secciones = []
    try:
        for i, pagina in enumerate(doc, start=1):
            paginas.append(pagina.get_text('text'))
            lineas = []  # [(texto, tamaño_max_de_letra)]
            for bloque in pagina.get_text('dict').get('blocks', []):
                for linea in bloque.get('lines', []):
                    spans = [s for s in linea.get('spans', []) if s.get('text', '').strip()]
                    if not spans:
                        continue
                    texto_linea = ''.join(s['text'] for s in spans).strip()
                    tamano = max(s.get('size', 0) for s in spans)
                    if texto_linea:
                        lineas.append((texto_linea, tamano))
            if not lineas:
                continue
            tamanos = sorted(t for _, t in lineas)
            n = len(tamanos)
            # mediana DE VERDAD (media de los dos centrales si n es par), no la mediana
            # superior `tamanos[n // 2]`: en una página de exactamente dos líneas (título
            # + una de cuerpo) la mediana superior coincide con el p90 y con el propio
            # título, y `tamano > mediana` nunca sería cierto.
            mediana = tamanos[n // 2] if n % 2 else (tamanos[n // 2 - 1] + tamanos[n // 2]) / 2
            p90 = tamanos[min(n - 1, max(0, round(0.9 * (n - 1))))]
            for texto_linea, tamano in lineas:
                # heurística: destaca de verdad (por encima de la mediana de SU
                # página, no solo >= p90 — en una página de tamaño uniforme
                # mediana == p90 y esto evita marcar cada línea como título) y es
                # corta, como suele serlo un título.
                if tamano >= p90 and tamano > mediana and len(texto_linea) <= 80:
                    secciones.append({'titulo': texto_linea, 'pagina_inicio': i})
    finally:
        doc.close()
    return paginas, secciones


def _es_titulo_heuristico(linea):
    linea = linea.strip()
    if not linea or len(linea) > 80:
        return False
    if RE_CAPITULO.match(linea):
        return True
    if RE_NUMERADA.match(linea):
        return True
    letras = [c for c in linea if c.isalpha()]
    return len(letras) >= 3 and all(c.isupper() for c in letras)


def extraer_pypdf(ruta_pdf):
    """(paginas_texto, secciones) con `pypdf`. Sin tamaños de fuente: la heurística de
    sección es de TEXTO — MAYÚSCULAS o numeración/«Capítulo». `ImportError` si `pypdf`
    no está instalado. Sube el logger raíz `pypdf` a CRITICAL solo durante esta llamada
    y lo restaura después, para no dejar pasar por STDERR los avisos de anomalías de un
    PDF que no lo es de verdad, cuando `extraer()` ya explica el motivo real por STDOUT."""
    from pypdf import PdfReader
    logger_pypdf = logging.getLogger('pypdf')
    nivel_previo = logger_pypdf.level
    logger_pypdf.setLevel(logging.CRITICAL)
    try:
        reader = PdfReader(ruta_pdf)
        paginas = []
        secciones = []
        for i, pagina in enumerate(reader.pages, start=1):
            texto = pagina.extract_text() or ''
            paginas.append(texto)
            for linea in texto.splitlines():
                if _es_titulo_heuristico(linea):
                    secciones.append({'titulo': linea.strip(), 'pagina_inicio': i})
        return paginas, secciones
    finally:
        logger_pypdf.setLevel(nivel_previo)


def extraer(ruta_pdf):
    """(paginas_texto, secciones, motor, motivo) probando `fitz` primero (usa tamaño de
    letra real) y `pypdf` como respaldo. `motor` es `None` si ninguno pudo leer el
    fichero; `motivo` explica por qué. `ABYSS_PDF_FORZAR_MOTOR=fitz|pypdf` fuerza uno de
    los dos aunque el otro esté disponible.

    Cada motor atrapa tanto `ImportError` (no instalado) como cualquier otra excepción
    (instalado pero no pudo con este fichero concreto: PDF truncado, cifrado, o un
    `.pdf` que en realidad es otra cosa) y deja que se intente el siguiente, sin
    propagar nunca un traceback crudo."""
    forzado = os.environ.get('ABYSS_PDF_FORZAR_MOTOR')
    fallos = []
    if forzado != 'pypdf':
        try:
            paginas, secciones = extraer_fitz(ruta_pdf)
            return paginas, secciones, 'fitz', None
        except ImportError:
            fallos.append(('fitz', 'no está instalado'))
            if forzado == 'fitz':
                return None, None, None, 'sin dato: pip install pymupdf'
        except Exception as e:
            fallos.append(('fitz', str(e) or type(e).__name__))
            if forzado == 'fitz':
                return None, None, None, f'fitz no pudo abrir el fichero: {e}'
    try:
        paginas, secciones = extraer_pypdf(ruta_pdf)
        return paginas, secciones, 'pypdf', None
    except ImportError:
        fallos.append(('pypdf', 'no está instalado'))
    except Exception as e:
        fallos.append(('pypdf', str(e) or type(e).__name__))
    if all(m == 'no está instalado' for _n, m in fallos):
        return None, None, None, 'sin dato: pip install pymupdf (o pypdf)'
    return None, None, None, ('no se pudo leer el PDF: ' +
                               '; '.join(f'{n} — {m}' for n, m in fallos))


# ---------- índice en disco (mem/pdf/<sha1>.json) ----------

def sha1_fichero(ruta):
    h = hashlib.sha1()
    with open(ruta, 'rb') as fh:
        for bloque in iter(lambda: fh.read(65536), b''):
            h.update(bloque)
    return h.hexdigest()


def _ruta_indice(mem, sha1):
    return os.path.join(mem, 'pdf', f'{sha1}.json')


def indexar(mem, ruta_pdf):
    """Construye (o reconstruye) el índice de `ruta_pdf` y lo escribe en
    `mem/pdf/<sha1>.json`. Devuelve `(indice, None)`, o `(None, mensaje)` si el fichero
    no existe o ningún motor pudo leerlo — nunca revienta con un traceback crudo (ver
    `extraer()`)."""
    if not ruta_pdf or not os.path.isfile(ruta_pdf):
        return None, f'no existe el fichero: {ruta_pdf}'
    sha1 = sha1_fichero(ruta_pdf)
    paginas, secciones, motor, motivo = extraer(ruta_pdf)
    if motor is None:
        return None, motivo
    indice = {
        'ruta': os.path.abspath(ruta_pdf), 'sha1': sha1, 'motor': motor,
        'num_paginas': len(paginas), 'paginas': paginas, 'secciones': secciones,
    }
    ruta_idx = _ruta_indice(mem, sha1)
    os.makedirs(os.path.dirname(ruta_idx), exist_ok=True)
    with open(ruta_idx, 'w', encoding='utf-8') as fh:
        json.dump(indice, fh, ensure_ascii=False, indent=1)
    return indice, None


def cargar_o_indexar(mem, ruta_pdf):
    """El índice ya guardado (por sha1 del CONTENIDO, no del nombre) si existe;
    si no, lo construye con `indexar()`."""
    if not ruta_pdf or not os.path.isfile(ruta_pdf):
        return None, f'no existe el fichero: {ruta_pdf}'
    ruta_idx = _ruta_indice(mem, sha1_fichero(ruta_pdf))
    if os.path.isfile(ruta_idx):
        try:
            with open(ruta_idx, encoding='utf-8') as fh:
                return json.load(fh), None
        except Exception:
            pass
    return indexar(mem, ruta_pdf)


def texto_secciones(indice):
    if not indice['secciones']:
        return '(sin secciones detectadas)'
    return '\n'.join(f"{i + 1}. {s['titulo']} (página {s['pagina_inicio']})"
                      for i, s in enumerate(indice['secciones']))


# ---------- búsqueda TF-IDF (biblioteca estándar) ----------

def _sin_acentos(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def tokens(texto):
    texto = _sin_acentos((texto or '').lower())
    return [t for t in re.findall(r'[a-z0-9]{3,}', texto) if t not in STOP]


def _tf(toks):
    c = Counter(toks)
    total = sum(c.values()) or 1
    return {t: n / total for t, n in c.items()}


def _idf(paginas_tokens):
    n = len(paginas_tokens)
    df = Counter()
    for tk in paginas_tokens:
        for t in set(tk):
            df[t] += 1
    return {t: math.log((n + 1) / (df[t] + 1)) + 1 for t in df}


def _seccion_de_pagina(indice, pagina):
    actual = None
    for s in indice['secciones']:
        if s['pagina_inicio'] <= pagina:
            actual = s['titulo']
        else:
            break
    return actual


def buscar(indice, consulta, k=5):
    """[{'pagina','puntuacion','seccion'}] de las hasta `k` páginas con mayor
    puntuación TF-IDF para `consulta`; páginas con puntuación 0 (ningún término de
    la consulta aparece) no entran."""
    paginas_tokens = [tokens(p) for p in indice['paginas']]
    idf = _idf(paginas_tokens)
    q = tokens(consulta)
    puntuaciones = []
    for i, tk in enumerate(paginas_tokens, start=1):
        tf = _tf(tk)
        score = sum(tf.get(t, 0.0) * idf.get(t, 0.0) for t in q)
        if score > 0:
            puntuaciones.append((i, score))
    puntuaciones.sort(key=lambda x: -x[1])
    return [{'pagina': p, 'puntuacion': round(s, 4), 'seccion': _seccion_de_pagina(indice, p)}
            for p, s in puntuaciones[:k]]


def leer(indice, especificacion):
    """Texto de un rango de páginas (`3`, `2-5`, `p2-p5`) o de una sección (título
    buscado como subcadena, sin acentos ni mayúsculas). `None` si no encaja con
    ninguna de las dos formas."""
    especificacion = (especificacion or '').strip()
    m = RE_RANGO.match(especificacion)
    n = len(indice['paginas'])
    if m:
        p1 = int(m.group(1)); p2 = int(m.group(2)) if m.group(2) else p1
        p1, p2 = sorted((p1, p2))
        p1 = max(1, p1); p2 = min(n, p2)
        if p1 > n or p2 < 1:
            return None
        return '\n\n'.join(indice['paginas'][p - 1] for p in range(p1, p2 + 1))
    buscado = _sin_acentos(especificacion.lower())
    for i, s in enumerate(indice['secciones']):
        if buscado and buscado in _sin_acentos(s['titulo'].lower()):
            inicio = s['pagina_inicio']
            fin = indice['secciones'][i + 1]['pagina_inicio'] - 1 if i + 1 < len(indice['secciones']) else n
            return '\n\n'.join(indice['paginas'][p - 1] for p in range(inicio, fin + 1))
    return None


def ahorro(indice, consulta, k=5):
    """(chars_buscados, chars_totales, proporcion) — lo que se LEERÍA con
    `--buscar` frente al PDF entero. Ahorro de LECTURA, no de calidad de
    respuesta (ver docstring del módulo)."""
    resultados = buscar(indice, consulta, k)
    chars_buscados = sum(len(indice['paginas'][r['pagina'] - 1]) for r in resultados)
    chars_totales = sum(len(p) for p in indice['paginas']) or 1
    return chars_buscados, chars_totales, chars_buscados / chars_totales


def _sin_proyecto(argv):
    argv = list(argv)
    if '--proyecto' in argv:
        i = argv.index('--proyecto')
        del argv[i:i + 2]
    return argv


if __name__ == '__main__':
    argv = _sin_proyecto(sys.argv[1:])
    proj, mem = rutas.resolver(sys.argv[1:])
    modo = argv[0] if argv else None
    resto = argv[1:]

    if modo == '--indexar':
        if not resto:
            print('uso: lector_pdf.py --indexar <pdf>'); sys.exit(1)
        indice, err = indexar(mem, resto[0])
        if err:
            print(err); sys.exit(1)
        print(f"indexado: {indice['num_paginas']} páginas, {len(indice['secciones'])} secciones detectadas (motor {indice['motor']})")
        sys.exit(0)

    if modo == '--secciones':
        if not resto:
            print('uso: lector_pdf.py --secciones <pdf>'); sys.exit(1)
        indice, err = cargar_o_indexar(mem, resto[0])
        if err:
            print(err); sys.exit(1)
        print(texto_secciones(indice))
        sys.exit(0)

    if modo == '--buscar':
        if len(resto) < 2:
            print('uso: lector_pdf.py --buscar <pdf> "consulta" [k]'); sys.exit(1)
        k = int(resto[2]) if len(resto) > 2 and resto[2].lstrip('-').isdigit() else 5
        indice, err = cargar_o_indexar(mem, resto[0])
        if err:
            print(err); sys.exit(1)
        resultados = buscar(indice, resto[1], k)
        if not resultados:
            print('sin resultados'); sys.exit(0)
        for r in resultados:
            print(f"página {r['pagina']}  puntuación {r['puntuacion']}  sección: {r['seccion'] or '(sin sección)'}")
            # Un trozo de texto real deja que quien lee decida si el candidato pega, sin
            # otra llamada a --leer (la búsqueda sigue siendo frecuencia de términos, esto
            # no la arregla). `paginas` es una lista y la página va en base 1: mismo
            # acceso que usan `leer()` y `ahorro()`.
            crudo = indice['paginas'][r['pagina'] - 1]
            trozo = ' '.join(str(crudo).split())[:280]
            if trozo:
                print(f"    {trozo}…" if len(trozo) == 280 else f"    {trozo}")
        sys.exit(0)

    if modo == '--leer':
        if len(resto) < 2:
            print('uso: lector_pdf.py --leer <pdf> <sección|rango-de-páginas>'); sys.exit(1)
        indice, err = cargar_o_indexar(mem, resto[0])
        if err:
            print(err); sys.exit(1)
        texto = leer(indice, resto[1])
        if texto is None:
            print(f'no encuentro "{resto[1]}" ni como sección ni como rango de páginas'); sys.exit(1)
        print(texto)
        sys.exit(0)

    if modo == '--ahorro':
        if len(resto) < 2:
            print('uso: lector_pdf.py --ahorro <pdf> "consulta" [k]'); sys.exit(1)
        k = int(resto[2]) if len(resto) > 2 and resto[2].lstrip('-').isdigit() else 5
        indice, err = cargar_o_indexar(mem, resto[0])
        if err:
            print(err); sys.exit(1)
        buscados, total, prop = ahorro(indice, resto[1], k)
        print(f'ahorro de lectura: {buscados}/{total} caracteres (proporción {prop:.2f}). '
              'Esto mide caracteres LEÍDOS, no calidad de respuesta: eso solo lo mediría un A/B '
              'con preguntas y respuestas reales, y no está hecho.')
        sys.exit(0)

    print('uso: lector_pdf.py --indexar|--secciones|--buscar|--leer|--ahorro <pdf> ...')
    sys.exit(1)
