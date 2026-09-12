# -*- coding: utf-8 -*-
"""Mapa de código: el índice de un repo Python, con `ast` (biblioteca estándar).

    python mapa_codigo.py <carpeta> [--salida fichero] [--json]
    python mapa_codigo.py --buscar <nombre>

Recorre todos los `.py` de `<carpeta>` (excluye `.git`, `venv`, `.venv`, `node_modules`,
`__pycache__`, `site-packages`) y, con `ast.parse` (nunca ejecuta el código), saca por
fichero: docstring y líneas totales; imports con su texto reconstruido; clases de nivel
de módulo con sus métodos (línea, firma reconstruida, decoradores, docstring); funciones
de nivel de módulo. Un fichero con error de sintaxis se lista como `(no parsea: <error>)`
sin tumbar el resto del recorrido; clases anidadas dentro de otra clase no se recorren.

Salida por defecto: texto greppable en `mem/mapas/<nombre de la carpeta>.txt`, una línea
por símbolo (`ruta:línea_ini-línea_fin  Clase.metodo(args)  — docstring`). `--salida
<fichero>` cambia el destino; `--json` escribe además la estructura completa por
fichero. `--buscar <nombre>` busca esa subcadena en el ÚLTIMO mapa `.txt` escrito (por
fecha de modificación), sin volver a analizar nada.

Mide siempre líneas de código frente a líneas del propio mapa — cuánto se lee de menos
si se consulta el mapa en vez del código fuente; no mide si el mapa basta para ENTENDER
el código.

Sin gancho ni red. Carpeta de datos: nunca `dirname(__file__)`; la resuelve
`rutas.resolver()` (§1 de ESPECIFICACION.md), solo dentro de `__main__`.
"""
import sys
try:                       # la consola de Windows y la salida tienen que hablar
    from . import consola  # el mismo idioma: ver abyss/consola.py
except ImportError:
    import consola
consola.preparar()
import os
import re
import ast
import json

try:
    from . import rutas
except ImportError:
    import rutas

EXCLUIR = {'.git', 'venv', '.venv', 'node_modules', '__pycache__', 'site-packages'}


def listar_py(carpeta):
    """Rutas absolutas de todos los `.py` bajo `carpeta`, sin bajar a los
    directorios de `EXCLUIR` (a cualquier profundidad)."""
    for raiz, dirs, ficheros in os.walk(carpeta):
        dirs[:] = [d for d in dirs if d not in EXCLUIR]
        for nombre in sorted(ficheros):
            if nombre.endswith('.py'):
                yield os.path.join(raiz, nombre)


def _primera_linea(doc):
    return doc.strip().split('\n', 1)[0].strip() if doc else None


def _firma(node):
    """Firma reconstruida (`a, b=1, *args, **kwargs`) desde el propio `ast`: clona el nodo
    con un cuerpo mínimo (`pass`) y pide a `ast.unparse` la cabecera. Si algo falla (Python
    sin `ast.unparse`, nodo atípico), se degrada a `'...'` en vez de reventar el recorrido."""
    try:
        cls = ast.AsyncFunctionDef if isinstance(node, ast.AsyncFunctionDef) else ast.FunctionDef
        copia = cls(name=node.name, args=node.args, body=[ast.Pass()],
                    decorator_list=[], returns=None, type_comment=None)
        ast.fix_missing_locations(copia)
        texto = ast.unparse(copia)
        m = re.search(r'\((.*)\)', texto, re.S)
        return re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''
    except Exception:
        return '...'


def _procesar_funcion(node):
    return {
        'nombre': node.name, 'linea_ini': node.lineno, 'linea_fin': node.end_lineno,
        'firma': _firma(node),
        'decoradores': [ast.unparse(d) for d in node.decorator_list],
        'docstring': _primera_linea(ast.get_docstring(node)),
    }


def _procesar_clase(node):
    metodos = [_procesar_funcion(m) for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return {
        'nombre': node.name, 'linea_ini': node.lineno, 'linea_fin': node.end_lineno,
        'bases': [ast.unparse(b) for b in node.bases],
        'docstring': _primera_linea(ast.get_docstring(node)),
        'metodos': metodos,
    }


def _texto_import(node):
    partes = [a.name + (f' as {a.asname}' if a.asname else '') for a in node.names]
    if isinstance(node, ast.Import):
        return 'import ' + ', '.join(partes)
    puntos = '.' * (node.level or 0)
    return f'from {puntos}{node.module or ""} import ' + ', '.join(partes)


def analizar_fichero(ruta):
    """Analiza UN fichero `.py`. Nunca lanza: un error de lectura o de sintaxis
    se devuelve como `{'error': ...}` (con `lineas` si se pudo contar), para que
    quien recorra varios ficheros no tenga que envolver la llamada en su propio
    `try`."""
    try:
        with open(ruta, encoding='utf-8-sig', errors='replace') as fh:
            fuente = fh.read()
    except Exception as e:
        return {'ruta': ruta, 'error': f'{type(e).__name__}: {e}', 'lineas': 0}
    lineas_totales = len(fuente.splitlines())
    try:
        arbol = ast.parse(fuente, filename=ruta)
    except SyntaxError as e:
        return {'ruta': ruta, 'error': f'{e.__class__.__name__}: {e.msg} (línea {e.lineno})', 'lineas': lineas_totales}
    clases, funciones, imports = [], [], []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Import, ast.ImportFrom)):
            imports.append({'linea_ini': nodo.lineno, 'linea_fin': nodo.end_lineno, 'texto': _texto_import(nodo)})
    for nodo in arbol.body:
        if isinstance(nodo, ast.ClassDef):
            clases.append(_procesar_clase(nodo))
        elif isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funciones.append(_procesar_funcion(nodo))
    return {
        'ruta': ruta, 'error': None, 'lineas': lineas_totales,
        'docstring': _primera_linea(ast.get_docstring(arbol)),
        'imports': imports, 'clases': clases, 'funciones': funciones,
    }


def _linea_funcion(rel, f, prefijo):
    decs = ''.join(f'@{d} ' for d in f['decoradores'])
    linea = f"{rel}:{f['linea_ini']}-{f['linea_fin']}  {decs}{prefijo}{f['nombre']}({f['firma']})"
    return linea + (f"  — {f['docstring']}" if f['docstring'] else '')


def lineas_texto(analisis, rel):
    """[líneas] greppables para UN fichero ya analizado (`analizar_fichero`)."""
    if analisis.get('error'):
        return [f"{rel}  (no parsea: {analisis['error']})"]
    out = [f"{rel}:1-{analisis['lineas']}  (módulo, {analisis['lineas']} líneas)"
           + (f"  — {analisis['docstring']}" if analisis['docstring'] else '')]
    for imp in analisis['imports']:
        rango = str(imp['linea_ini']) if imp['linea_ini'] == imp['linea_fin'] else f"{imp['linea_ini']}-{imp['linea_fin']}"
        out.append(f"{rel}:{rango}  {imp['texto']}")
    for c in analisis['clases']:
        bases = f"({', '.join(c['bases'])})" if c['bases'] else ''
        out.append(f"{rel}:{c['linea_ini']}-{c['linea_fin']}  class {c['nombre']}{bases}"
                   + (f"  — {c['docstring']}" if c['docstring'] else ''))
        for m in c['metodos']:
            out.append(_linea_funcion(rel, m, c['nombre'] + '.'))
    for f in analisis['funciones']:
        out.append(_linea_funcion(rel, f, ''))
    return out


def construir_mapa(carpeta):
    """(analisis_por_fichero, lineas_mapa, lineas_codigo_total). `analisis_por_fichero`
    es `[(ruta_relativa, analisis), ...]` en el mismo orden que `lineas_mapa`."""
    carpeta_abs = os.path.abspath(carpeta)
    analisis_por_fichero = []
    lineas_mapa = []
    lineas_codigo_total = 0
    for ruta in listar_py(carpeta_abs):
        analisis = analizar_fichero(ruta)
        rel = os.path.relpath(ruta, carpeta_abs).replace(os.sep, '/')
        lineas_codigo_total += analisis.get('lineas', 0)
        lineas_mapa.extend(lineas_texto(analisis, rel))
        analisis_por_fichero.append((rel, analisis))
    return analisis_por_fichero, lineas_mapa, lineas_codigo_total


def escribir_mapa(mem, carpeta, salida=None, con_json=False):
    """Construye el mapa de `carpeta` y lo escribe (texto en `salida` si se da,
    si no en `mem/mapas/<nombre de la carpeta>.txt`; `.json` además si
    `con_json`). Devuelve un dict con las rutas escritas y la medida
    (`lineas_codigo`, `lineas_mapa`, `proporcion`, `rotos`)."""
    analisis_por_fichero, lineas_mapa, lineas_codigo_total = construir_mapa(carpeta)
    if salida:
        ruta_txt = salida
    else:
        nombre_carpeta = os.path.basename(os.path.abspath(carpeta).rstrip(os.sep)) or 'raiz'
        ruta_txt = os.path.join(mem, 'mapas', f'{nombre_carpeta}.txt')
    directorio = os.path.dirname(os.path.abspath(ruta_txt))
    if directorio:
        os.makedirs(directorio, exist_ok=True)
    with open(ruta_txt, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lineas_mapa) + ('\n' if lineas_mapa else ''))
    ruta_json = None
    if con_json:
        ruta_json = os.path.splitext(ruta_txt)[0] + '.json'
        with open(ruta_json, 'w', encoding='utf-8') as fh:
            json.dump({rel: an for rel, an in analisis_por_fichero}, fh, ensure_ascii=False, indent=1)
    lineas_mapa_total = len(lineas_mapa)
    return {
        'ruta_txt': ruta_txt, 'ruta_json': ruta_json, 'ficheros': len(analisis_por_fichero),
        'lineas_codigo': lineas_codigo_total, 'lineas_mapa': lineas_mapa_total,
        'proporcion': (lineas_mapa_total / lineas_codigo_total) if lineas_codigo_total else None,
        'rotos': [rel for rel, an in analisis_por_fichero if an.get('error')],
    }


def ultimo_mapa(mem):
    """Ruta del `.txt` más reciente (por fecha de modificación) en `mem/mapas/`,
    o `None` si no hay ninguno todavía."""
    carpeta_mapas = os.path.join(mem, 'mapas')
    try:
        ficheros = [os.path.join(carpeta_mapas, f) for f in os.listdir(carpeta_mapas) if f.endswith('.txt')]
    except FileNotFoundError:
        return None
    return max(ficheros, key=os.path.getmtime) if ficheros else None


def buscar_en_mapa(ruta_mapa, nombre):
    """Líneas de `ruta_mapa` que contienen `nombre` como subcadena literal (grep
    de bolsillo: sin regex, sin distinguir mayúsculas)."""
    nombre_norm = nombre.lower()
    with open(ruta_mapa, encoding='utf-8') as fh:
        return [linea.rstrip('\n') for linea in fh if nombre_norm in linea.lower()]


def _sin_proyecto(argv):
    argv = list(argv)
    if '--proyecto' in argv:
        i = argv.index('--proyecto')
        del argv[i:i + 2]
    return argv


if __name__ == '__main__':
    proj, mem = rutas.resolver(sys.argv[1:])
    argv = _sin_proyecto(sys.argv[1:])

    if argv and argv[0] == '--buscar':
        if len(argv) < 2:
            print('uso: mapa_codigo.py --buscar <nombre>'); sys.exit(1)
        ruta_mapa = ultimo_mapa(mem)
        if not ruta_mapa:
            print('sin ningún mapa todavía: ejecuta antes mapa_codigo.py <carpeta>'); sys.exit(1)
        encontrados = buscar_en_mapa(ruta_mapa, argv[1])
        if not encontrados:
            print(f'nada con "{argv[1]}" en {os.path.basename(ruta_mapa)}'); sys.exit(0)
        print('\n'.join(encontrados))
        sys.exit(0)

    con_json = '--json' in argv
    if con_json:
        argv.remove('--json')
    salida = None
    if '--salida' in argv:
        i = argv.index('--salida')
        if i + 1 >= len(argv):
            print('--salida necesita un fichero detrás'); sys.exit(1)
        salida = argv[i + 1]
        del argv[i:i + 2]
    for a in argv:
        if a.startswith('--'):
            print(f'argumento no reconocido: {a} (usa --salida/--json/--buscar)'); sys.exit(1)
    posicionales = [a for a in argv if not a.startswith('--')]
    if not posicionales:
        print('uso: mapa_codigo.py <carpeta> [--salida fichero] [--json]'); sys.exit(1)
    if len(posicionales) > 1:
        print(f'argumento no reconocido: {posicionales[1]} (usa --salida/--json/--buscar)'); sys.exit(1)
    carpeta = posicionales[0]
    if not os.path.isdir(carpeta):
        print(f'no existe la carpeta: {carpeta}'); sys.exit(1)

    r = escribir_mapa(mem, carpeta, salida=salida, con_json=con_json)
    print(f"mapa: {r['ruta_txt']}")
    if r['ruta_json']:
        print(f"json: {r['ruta_json']}")
    prop = f" · proporción {r['proporcion']:.3f}" if r['proporcion'] is not None else ''
    print(f"ficheros analizados: {r['ficheros']} · código: {r['lineas_codigo']} líneas · mapa: {r['lineas_mapa']} líneas{prop}")
    if r['rotos']:
        print('no parsean: ' + ', '.join(r['rotos']))
