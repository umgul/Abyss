# -*- coding: utf-8 -*-
"""Que los acentos salgan bien en la consola de Windows.

## El fallo, medido

34 módulos de este paquete hacían `sys.stdout.reconfigure(encoding="utf-8")` y ninguno
tocaba la página de códigos de la consola. Eso escribe bytes UTF-8 correctos a una ventana
que no está leyendo UTF-8: en una consola española la página activa suele ser la **850**
(medido el 9-sep-2026 en la máquina de desarrollo con `chcp`), y ahí los dos bytes de una
`ñ` —C3 y B1— se pintan como `├` y `▒`. `á` sale `├í` y `é` sale `├®`.

No era un fallo de codificación: los bytes siempre estuvieron bien. Era que la salida y la
ventana hablaban idiomas distintos, y solo se veía al correrlo en una consola de verdad —
por una tubería o redirigido a un fichero se ve correcto, que es justo por qué había
sobrevivido tanto.

## Lo que hace

Pone la consola en UTF-8 (página 65001) ANTES de reconfigurar la salida, y la deja como
estaba al terminar el proceso. Medido: `SetConsoleOutputCP(65001)` devuelve 1 y `chcp` pasa
de 850 a 65001; al salir vuelve a 850.

Restaurarla no es cortesía vacía: la página de códigos es de la VENTANA, no del proceso, así
que un programa que la cambia y no la devuelve deja tocada la consola del usuario para todo
lo que ejecute después, incluidos programas que no son suyos.

## Lo que NO hace

- Fuera de Windows no hace nada: allí las consolas ya hablan UTF-8 y no hay página que
  cambiar.
- Si la salida NO es una consola (una tubería, un fichero, un gancho de Claude Code), no
  toca nada tampoco: ahí no hay ventana que confundir y forzar UTF-8 ya es lo correcto.
- No cambia la página de entrada (`SetConsoleCP`): este paquete escribe en la consola, no
  lee de ella.
- Si la llamada falla —una consola que no lo admite, un Windows sin esa función— se sigue
  adelante en silencio con el comportamiento de antes: peor la letra, pero nunca una traza
  en la cara del usuario por un acento.
"""
import atexit
import sys

PAGINA_UTF8 = 65001


def preparar():
    """Llamar una vez, arriba del todo de cada módulo, en vez de reconfigurar a pelo."""
    if sys.platform == "win32":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            # solo si de verdad hay una consola detrás: con la salida redirigida, esto
            # devolvería 0 y no habría nada que arreglar
            antes = k.GetConsoleOutputCP()
            if antes and antes != PAGINA_UTF8 and k.SetConsoleOutputCP(PAGINA_UTF8):
                atexit.register(lambda: k.SetConsoleOutputCP(antes))
        except Exception:
            pass                        # sin página nueva, pero el programa sigue
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
