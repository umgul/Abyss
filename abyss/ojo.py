# -*- coding: utf-8 -*-
"""Ojo: el órgano de visión de Abyss, con verbos — nunca por gancho (T4.6).

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

Ocho verbos, un solo punto de entrada. Este guion NO repite ninguna lógica de
visión propia: salvo `mirar` ("lo de hoy" — un fotograma suelto, sin cambios
desde antes de esta tanda), cada verbo DELEGA entero en el módulo que de
verdad lo implementa y ya tiene su propia batería de pruebas:

  - `texto` / `fotocopia` / `tarjeta` / `manual` → `lectura_visual._cli()`
    (T4.3: OCR por el motor de Windows o `tesseract`; enderezar/umbralizar un
    documento fotografiado o escaneado; extraer una tarjeta a `.vcf`; ordenar
    varias fotos de un manual en markdown).
  - `despiece` / `prompt3d` → `volumen._cli()` (T4.4: despiece por capas 2,5D
    con GrabCut + nitidez/luminancia; o un prompt de diseño 3D con lo medido
    de la foto — paleta, proporción, horizonte, formas).
  - `gestos` → `gestos._cli()` (T4.5: MediaPipe + vocabulario PROPIO del
    paquete; sirve el estado por HTTP SOLO en `127.0.0.1`).

Cada módulo delegado declara sus propias dependencias opcionales y su propio
límite; este guion no los repite ni los debilita — falla EXACTAMENTE como
falla el módulo delegado (mismo mensaje, mismo código de salida), porque le
pasa el mismo argv que recibiría si se invocara directo
(`python <modulo>.py <verbo> <resto...>`). El import de cada módulo delegado
es PEREZOSO, dentro de la rama del verbo que lo necesita: `volumen.py` exige
`numpy`/`cv2` a nivel de módulo y sale con código 2 si faltan — un `mirar` (o
un `--help`) no debe pagar ese precio ni reventar por una dependencia que ese
verbo concreto no usa.

`mirar` sigue siendo lo de hoy, sin tocar: abre la cámara indicada (por
defecto la 0), descarta los primeros fotogramas (la exposición tarda en
ajustarse) y guarda uno como `.jpg`, apuntado en `mem/ojo.log`. DEPENDENCIA
declarada: OpenCV (`cv2`) es OPCIONAL — sin ella, «sin cv2: no hay ojo» y sale
con código 1; no es biblioteca estándar, lo instala quien quiera este verbo
(nunca este guion: regla dura de todo el paquete — nada se instala con pip
desde dentro).

NINGÚN verbo se dispara desde un gancho: la cámara (`mirar`, `fotocopia
--camara`, `gestos`) solo se enciende cuando este guion se invoca A MANO, con
el consentimiento del turno actual — no hay preferencia guardada ni patrón de
mensaje que la encienda sola. Una cámara que se enciende sola no es un ojo,
es vigilancia.

Carpeta de datos: NUNCA `dirname(__file__)`; se resuelve con `rutas.resolver()`
(§1 de ESPECIFICACION.md), UNA sola vez, aquí, antes de mirar el verbo. Como
este guion se invoca siempre a mano (nunca hay stdin de un gancho), la pista
normal es `--proyecto <cwd>` o la variable `ABYSS_PROYECTO`; si ninguna
resuelve, `rutas.resolver()` avisa claro por stderr y sale (fail-closed: sin
proyecto no hay dónde guardar nada). Tras resolver, `proj` se deja en
`os.environ['ABYSS_PROYECTO']` (mismo patrón que `vigia.py`) para que el
módulo delegado — que resuelve su propio `mem` por su cuenta, con la MISMA
`rutas.resolver()` — no tenga que repetir `--proyecto` en su propio argv ni
releer un stdin ya vacío. `despiece`/`prompt3d`/`gestos` no tocan `mem` en
absoluto (son guiones de fichero a fichero o de servidor HTTP efímero, como
ya declaran sus propios docstrings): resolver `proj`/`mem` aquí no les afecta
en nada, solo asegura que `mirar`/`texto`/`fotocopia`/`tarjeta`/`manual`
tengan dónde escribir su registro.
"""
import importlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rutas  # noqa: E402

VERBOS = ('mirar', 'texto', 'fotocopia', 'tarjeta', 'manual', 'despiece', 'prompt3d', 'gestos')

# Verbo -> módulo que lo implementa de verdad. `mirar` y `gestos` no están aquí
# a propósito: `mirar` no delega (ver docstring), y `gestos._cli()` no lleva el
# nombre del verbo como primer argumento (solo banderas), a diferencia de estos
# cuatro y de `despiece`/`prompt3d` (que SÍ llevan su verbo delante, igual que
# si se invocara `python lectura_visual.py <verbo> ...` / `python volumen.py
# <verbo> ...` directamente).
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
    """Verbo `mirar`: idéntico al `ojo.py` de antes de esta tanda (ver docstring
    del módulo) — la única pieza de este guion que NO delega en otro módulo."""
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
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    sys.exit(main())
