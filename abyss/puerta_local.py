# -*- coding: utf-8 -*-
"""Filtra de dónde viene una petición a este servidor local antes de atenderla.

Un POST por sí solo no basta: el navegador manda igual el POST de otra web, solo
cambia si esa web puede LEER la respuesta. Lo que sí frena que la dispare es
comprobar `Origin` y `Host` -- las pone el navegador, no quien pide --, y `Host`
además corta el DNS rebinding al exigir el puerto real de este servidor.
"""

_SEC_FETCH_SITE_AJENOS = ('cross-site', 'same-site')
_TOPE_CUERPO = 1 << 20

# Lo que un visor nunca manda abrir: con el programa asociado del sistema, abrirlo es
# ejecutarlo (un `.lnk` o un `.url` también llevan a otro programa).
NO_SE_ABREN = frozenset((
    '.exe', '.com', '.bat', '.cmd', '.ps1', '.psm1', '.vbs', '.vbe', '.js', '.jse', '.wsf', '.wsh',
    '.msi', '.msp', '.scr', '.pif', '.lnk', '.url', '.reg', '.hta', '.cpl', '.jar', '.appref-ms',
    '.application', '.gadget', '.inf', '.scf', '.sh', '.py', '.pyw', '.pyz', '.app', '.command',
))


def se_ejecutaria(ruta):
    """True si abrir `ruta` con el programa asociado del sistema ejecutaría algo."""
    import os
    return os.path.splitext(str(ruta))[1].lower() in NO_SE_ABREN


def rechazo(handler):
    """`None` si `handler` puede seguir; si no, un texto corto con el motivo.

    `handler` es el manejador HTTP en curso: se leen `.headers` (cabeceras de la
    petición) y `.server.server_address` (el puerto real en el que escucha ESTE
    servidor, nunca uno que traiga la propia petición)."""
    puerto = handler.server.server_address[1]

    host = (handler.headers.get('Host') or '').strip().lower()
    if host not in ('127.0.0.1:%d' % puerto, 'localhost:%d' % puerto):
        return 'host no reconocido'

    origen = handler.headers.get('Origin')
    if origen is not None:
        origen = origen.strip().lower()
        if origen not in ('http://127.0.0.1:%d' % puerto, 'http://localhost:%d' % puerto):
            return 'origin no reconocido'

    sitio = (handler.headers.get('Sec-Fetch-Site') or '').strip().lower()
    if sitio in _SEC_FETCH_SITE_AJENOS:
        return 'sec-fetch-site %s' % sitio

    return None


def descartar_cuerpo(handler):
    """Lee y tira el cuerpo de la petición rechazada, sin procesarlo.

    En Windows, cerrar un socket con bytes de entrada aún sin leer manda un RESET
    en vez de un cierre limpio, y ese reset puede llevarse por delante la respuesta
    de rechazo que se acaba de escribir; llamar a esto antes de responder lo evita."""
    try:
        largo = int(handler.headers.get('Content-Length') or 0)
    except ValueError:
        return
    if 0 < largo <= _TOPE_CUERPO:  # negativo leería hasta que el cliente cierre
        try:
            handler.rfile.read(largo)
        except OSError:
            pass
