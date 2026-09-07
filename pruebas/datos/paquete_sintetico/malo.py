"""malo.py — fichero de prueba para `pruebas/test_auditar.py` (T4.2).

A propósito para que `auditar.py` lo cace: `sondear()` manda datos a un host que
NINGÚN README de este paquete de prueba nombra (comprobación 4). No se ejecuta
nunca de verdad: la batería de `abyss` audita este texto, jamás lo importa ni lo
corre."""
import urllib.request


def sondear():
    """"Mide el estado" — en realidad manda el resultado a un host no declarado."""
    return urllib.request.urlopen("https://telemetria.dominio-no-declarado.net/registro").read()
