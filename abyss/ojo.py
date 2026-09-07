"""Ojo: un fotograma de la webcam, SOLO cuando el usuario lo pide.

    python ojo.py [ruta_salida.jpg] [indice_camara] [--proyecto <cwd>]

DEPENDENCIA declarada: OpenCV (`cv2`) es OPCIONAL — sin él, «sin cv2: no hay ojo» y se
sale con código 1; no es biblioteca estándar, lo instala quien quiera este módulo.

Guarda el fotograma y escribe la ruta; luego yo lo leo con la herramienta de imágenes.
Cada captura queda apuntada en `mem/ojo.log` (cuándo, cámara, tamaño). No se dispara desde
ningún gancho: una cámara que se enciende sola no es un ojo, es una vigilancia.

Carpeta de datos: NUNCA `dirname(__file__)`; se resuelve con `rutas.resolver()` (§1 de
ESPECIFICACION.md). Como este guion se invoca siempre a mano (nunca hay stdin de un
gancho), la pista normal es `--proyecto <cwd>` o la variable `ABYSS_PROYECTO`; si
ninguna resuelve, `rutas.resolver()` avisa claro por stderr y sale (fail-closed: sin
proyecto no hay dónde guardar el fotograma).
"""
import sys; sys.stdout.reconfigure(encoding="utf-8")
import os, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rutas  # noqa: E402


def _sin_proyecto(argv):
    """`argv` sin el flag `--proyecto <valor>` que ya consumió `rutas.resolver()`, para no
    confundir ese valor con los posicionales propios de este guion (salida, índice)."""
    argv = list(argv)
    if '--proyecto' in argv:
        i = argv.index('--proyecto')
        del argv[i:i + 2]
    return argv


argv = sys.argv[1:]
proj, mem = rutas.resolver(argv=argv)  # si no hay proyecto, sale aquí con mensaje claro
argv = _sin_proyecto(argv)
salida = argv[0] if len(argv) > 0 else os.path.join(mem, f'ojo_{time.strftime("%Y%m%d_%H%M%S")}.jpg')
if len(argv) > 1:
    try:
        idx = int(argv[1])
    except ValueError:
        print(f'el índice de cámara debe ser un número, no "{argv[1]}"')
        sys.exit(1)
else:
    idx = 0
try:
    import cv2
except ImportError:
    print('sin cv2: no hay ojo'); sys.exit(1)
cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
if not cap.isOpened():
    cap = cv2.VideoCapture(idx)
if not cap.isOpened():
    print(f'cámara {idx} no disponible'); sys.exit(2)
ok, frame = False, None
for _ in range(8):  # las primeras lecturas suelen venir oscuras: dejar que ajuste exposición
    ok, frame = cap.read()
    time.sleep(0.1)
cap.release()
if not ok or frame is None:
    print('la cámara abrió pero no dio fotograma'); sys.exit(3)
cv2.imwrite(salida, frame)
with open(os.path.join(mem, 'ojo.log'), 'a', encoding='utf-8') as fh:
    fh.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} cámara {idx} → {salida} {frame.shape[1]}x{frame.shape[0]}\n')
print(salida)
