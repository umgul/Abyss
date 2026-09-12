# -*- coding: utf-8 -*-
"""Ojo: el órgano de visión de Abyss, con verbos — nunca por gancho.

Uso:
    python ojo.py mirar [ruta_salida.jpg] [indice_camara] [--proyecto <cwd>]
    python ojo.py texto <imagen> [--portapapeles] [--salida f.txt] [--proyecto <cwd>]
    python ojo.py fotocopia (<imagen>|--camara [indice]) [--escaner]
                  [--salida f.png|f.pdf] [--color|--gris|--umbral] [--paginas n] [--proyecto <cwd>]
    python ojo.py tarjeta <imagen> [--salida base] [--proyecto <cwd>]
    python ojo.py manual <imagen...> [--salida f.md] [--proyecto <cwd>]
    python ojo.py despiece <imagen> [--capas 4] [--salida escena.json] [--html]
    python ojo.py prompt3d <imagen> [--salida f.txt] [--escena f.json]
    python ojo.py gestos [--camara 0] [--puerto 8799] [--escena f.json] [--holograma] [--vocabulario f.json]

Ocho verbos, un solo punto de entrada. Salvo `mirar`, cada verbo delega
entero en el módulo que lo implementa (mismo argv, mensaje y código de salida):

  - `texto` / `fotocopia` / `tarjeta` / `manual` → `lectura_visual._cli()`
    (OCR; enderezar/umbralizar un documento fotografiado o escaneado;
    extraer una tarjeta a `.vcf`; ordenar fotos de un manual en markdown).
  - `despiece` / `prompt3d` → `volumen._cli()` (despiece por capas 2,5D con
    GrabCut; o un prompt de diseño 3D con lo medido de la foto).
  - `gestos` → `gestos._cli()` (MediaPipe con vocabulario propio; sirve el
    estado por HTTP SOLO en `127.0.0.1`).

El import de cada módulo delegado es PEREZOSO: `volumen.py` exige
`numpy`/`cv2` a nivel de módulo, y un `mirar` o un `--help` no debe pagar ese precio.

`mirar` no delega: abre la cámara indicada (por defecto la 0), descarta
los primeros fotogramas mientras ajusta la exposición, y guarda uno como
`.jpg` en `mem/ojo.log`. OpenCV (`cv2`) es OPCIONAL — sin ella, «sin cv2: no
hay ojo» (código 1); no la instala este guion (nada se instala con pip).

NINGÚN verbo se dispara desde un gancho: la cámara (`mirar`, `fotocopia
--camara`, `gestos`) solo se enciende al invocarse este guion A MANO.

Carpeta de datos: nunca `dirname(__file__)`; se resuelve con
`rutas.resolver()` (§1 de ESPECIFICACION.md) por `--proyecto <cwd>` o
`ABYSS_PROYECTO`; sin ninguna, sale con aviso claro por stderr (fail-closed).
Tras resolver, `proj` queda en `os.environ['ABYSS_PROYECTO']` para que el
módulo delegado no repita `--proyecto` ni relea un stdin ya vacío.
"""
import importlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rutas  # noqa: E402

VERBOS = ('mirar', 'texto', 'fotocopia', 'tarjeta', 'manual', 'despiece', 'prompt3d', 'gestos')

# Verbo -> módulo que lo implementa. `mirar` no delega (ver docstring del
# módulo); `gestos._cli()` no lleva el verbo como primer argumento (solo
# banderas), a diferencia de estos cuatro y de `despiece`/`prompt3d`.
_DELEGA = {
    'texto': 'lectura_visual', 'fotocopia': 'lectura_visual',
    'tarjeta': 'lectura_visual', 'manual': 'lectura_visual',
    'despiece': 'volumen', 'prompt3d': 'volumen',
}


def _sin_proyecto(argv):
    """`argv` sin el flag `--proyecto <valor>` que ya consumió `rutas.resolver()`, para no
    confundir ese valor con el verbo o los positionales propios de cada uno."""
    argv = list(argv)
    if '--proyecto' in argv:
        i = argv.index('--proyecto')
        del argv[i:i + 2]
    return argv


def _cli_mirar(resto, mem):
    """Verbo `mirar`: la única pieza de este guion que NO delega en otro
    módulo (ver docstring del módulo)."""
    salida = resto[0] if len(resto) > 0 else os.path.join(mem, f'ojo_{time.strftime("%Y%m%d_%H%M%S")}.jpg')
    if len(resto) > 1:
        try:
            idx = int(resto[1])
        except ValueError:
            print(f'el índice de cámara debe ser un número, no "{resto[1]}"')
            return 1
    else:
        idx = 0
    try:
        import cv2
    except ImportError:
        print('sin cv2: no hay ojo')
        return 1
    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        print(f'cámara {idx} no disponible')
        return 2
    ok, frame = False, None
    for _ in range(8):  # las primeras lecturas suelen venir oscuras: dejar que ajuste exposición
        ok, frame = cap.read()
        time.sleep(0.1)
    cap.release()
    if not ok or frame is None:
        print('la cámara abrió pero no dio fotograma')
        return 3
    cv2.imwrite(salida, frame)
    with open(os.path.join(mem, 'ojo.log'), 'a', encoding='utf-8') as fh:
        fh.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} cámara {idx} → {salida} {frame.shape[1]}x{frame.shape[0]}\n')
    print(salida)
    return 0


def _delegar(modulo_nombre, verbo, resto):
    """Import PEREZOSO de `modulo_nombre` (solo cuando este verbo concreto lo
    necesita — ver docstring del módulo) y delegación ENTERA en su propio
    `_cli()`, con el mismo argv que recibiría si se invocara directo: mismo
    mensaje, mismo código de salida, sin repetir ni debilitar su lógica aquí."""
    modulo = importlib.import_module(modulo_nombre)
    return modulo._cli([verbo] + resto)


def _cli(argv, proj, mem):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 1
    verbo, resto = argv[0], list(argv[1:])
    if verbo == 'mirar':
        return _cli_mirar(resto, mem)
    if verbo in _DELEGA:
        return _delegar(_DELEGA[verbo], verbo, resto)
    if verbo == 'gestos':
        gestos = importlib.import_module('gestos')
        return gestos._cli(resto)
    print(f'verbo desconocido: "{verbo}" (usa {"/".join(VERBOS)})')
    return 1


def main():
    argv = sys.argv[1:]
    proj, mem = rutas.resolver(argv=argv)  # si no hay proyecto, sale aquí con mensaje claro
    argv = _sin_proyecto(argv)
    os.environ['ABYSS_PROYECTO'] = proj  # para que el módulo delegado no relea un stdin ya vacío
    return _cli(argv, proj, mem)


if __name__ == '__main__':
    try:                       # la consola de Windows y la salida tienen que hablar
        from . import consola  # el mismo idioma: ver abyss/consola.py
    except ImportError:
        import consola
    consola.preparar()
    sys.exit(main())
