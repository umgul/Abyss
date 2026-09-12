# -*- coding: utf-8 -*-
"""Pone la consola de Windows en UTF-8 antes de que el módulo reconfigure su
salida, y restaura la página de códigos anterior al terminar el proceso.
Llamar a `preparar()` una vez, arriba de cada módulo, en vez de reconfigurar
la salida a pelo: sin este paso previo, esos bytes UTF-8 llegan a una
ventana que sigue leyendo otra página de códigos (la 850 es habitual en
Windows en español) y los acentos salen como basura.

Restaurar la página importa: es de la VENTANA, no del proceso, así que no
devolverla deja tocada la consola del usuario para lo que ejecute después.

LÍMITE HONESTO: fuera de Windows no hace nada; si la salida no es una
consola (tubería, fichero, un gancho) tampoco toca nada; no cambia la
página de ENTRADA (`SetConsoleCP`); y si la llamada al sistema falla, sigue
en silencio con el comportamiento anterior.
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
