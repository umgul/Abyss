# -*- coding: utf-8 -*-
"""Sirve una escena kinética y le da dos verbos: ENTRAR en una carpeta y ABRIR un fichero.
Hace falta un servidor local (no vale abrir el .html a pelo): la página carga MediaPipe
como módulo ES y el navegador bloquea los módulos servidos por file://.

Los dos verbos van por lista blanca: una página web que le pide a un programa local «abre
esto» es exactamente la forma de un agujero, así que aquí no se pega ninguna ruta.

  - `POST /entrar`  {"destino": "<id>"} — vuelve a montar la escena dentro de esa carpeta.
  - `POST /abrir`   {"destino": "<id>"} — abre ese fichero con el programa que el sistema
    tenga asociado.

En los dos casos el `destino` se busca en el diccionario de la escena que está montada: no
es una ruta que llegue de fuera, es una clave que tiene que existir en el `nodos.json` que
este servidor acaba de escribir. Lo que no esté en la escena no existe, y una ruta con `..`
dentro no llega a ninguna parte porque nunca se concatena nada; además se comprueba que lo
resuelto siga colgando de la raíz de la escena. Los dos son POST a propósito: una visita
suelta, una precarga o un enlace no abren nada.

Lo que este servidor NO hace: no sirve nada fuera de la carpeta de montaje; no ejecuta nada
(`abrir` le pasa el fichero al sistema, que decide con qué se abre); no recuerda nada entre
arranques.
"""
import functools
import http.server
import io
import json
import os
import socketserver
import subprocess
import sys
import threading
import urllib.parse

try:                       # la consola de Windows y la salida tienen que hablar
    from . import consola  # el mismo idioma: ver abyss/consola.py
except ImportError:
    import consola
consola.preparar()
SW_SHOWNORMAL = 1        # que la ventana salga en su tamaño, ni minimizada ni maximizada
ASFW_ANY = -1            # «cualquier proceso que se lance a continuación puede tomar el primer plano»


def _abre_con_el_sistema(ruta):
    """Se lo da al sistema. En Windows `os.startfile`; fuera, `open`/`xdg-open`.

    Windows tiene un bloqueo de primer plano: un proceso sin foco (este servidor nunca lo
    tiene; el foco lo tiene la ventana del visor) tampoco puede dárselo al que lanza, así
    que el programa recién abierto se queda parpadeando en la barra de tareas. Se arregla
    con dos cosas: `AllowSetForegroundWindow(ASFW_ANY)` cede el turno de primer plano al
    siguiente proceso que se lance, y `show_cmd=SW_SHOWNORMAL` evita que un programa que
    recuerde haberse cerrado minimizado vuelva a abrirse minimizado. Si
    `AllowSetForegroundWindow` falla, se abre igual: se pierde el primer plano, no el
    fichero.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(ASFW_ANY)
        except Exception:
            pass                                             # sin primer plano, pero abre
        try:
            os.startfile(ruta, show_cmd=SW_SHOWNORMAL)       # noqa: S606 (es la vía del SO)
        except TypeError:
            os.startfile(ruta)                               # Python < 3.10: sin show_cmd
    elif sys.platform == "darwin":
        subprocess.Popen(["open", ruta], close_fds=True)
    else:
        subprocess.Popen(["xdg-open", ruta], close_fds=True)


def sirve(carpeta, puerto=8890, abrir=True, remontar=None, avisar=print):
    """Levanta la escena montada en `carpeta`.

    `remontar(destino_absoluto)` es lo que sabe volver a montar en otra carpeta; se lo pasa
    quien llama (hoy `kinetico.py`), para que este servidor no tenga que saber cómo se monta
    una escena — solo cuándo hay que hacerlo.
    """
    carpeta = os.path.abspath(carpeta)

    def escena():
        try:
            with io.open(os.path.join(carpeta, "nodos.json"), encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    class M(http.server.SimpleHTTPRequestHandler):
        def log_message(self, formato, *args):
            pass

        def end_headers(self):
            self.send_header("Cross-Origin-Opener-Policy", "same-origin")
            self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def _json(self, datos, codigo=200):
            cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def _destino(self):
            """El `destino` del cuerpo, resuelto contra la escena. None si no vale."""
            largo = int(self.headers.get("Content-Length") or 0)
            try:
                pedido = json.loads(self.rfile.read(largo).decode("utf-8") or "{}")
            except ValueError:
                return None, "no entiendo la petición"
            clave = pedido.get("destino")
            e = escena()
            raiz = e.get("raiz")
            if not raiz:
                return None, "esta escena no sale de una carpeta: no hay dónde entrar"
            # la clave TIENE que estar en la escena; no se acepta una ruta de fuera
            conocidas = {it.get("id"): it for it in e.get("items", [])}
            if clave not in conocidas:
                return None, "eso no está en la escena"
            # el TECHO es la carpeta con la que se abrió: subir llega hasta ahí y no más
            techo = os.path.abspath(e.get("techo") or raiz)
            if clave == "..":
                destino = os.path.dirname(os.path.abspath(raiz))
            else:
                destino = os.path.abspath(os.path.join(raiz, *str(clave).split("/")))
            if os.path.commonpath([destino, techo]) != techo:
                return None, "fuera de lo que se abrió"
            return destino, None

        def do_POST(self):
            ruta = urllib.parse.urlparse(self.path).path
            if ruta not in ("/entrar", "/abrir"):
                self.send_error(404, "aqui no se escribe nada")
                return
            destino, err = self._destino()
            if err:
                self._json({"ok": False, "por_que": err})
                return
            if ruta == "/abrir":
                if not os.path.isfile(destino):
                    self._json({"ok": False, "por_que": "ya no está ahí"})
                    return
                try:
                    _abre_con_el_sistema(destino)
                    self._json({"ok": True, "que": "abierto con el programa del sistema"})
                except Exception as e:
                    self._json({"ok": False, "por_que": "%s %s" % (type(e).__name__, e)})
                return
            # entrar
            if not os.path.isdir(destino):
                self._json({"ok": False, "por_que": "eso no es una carpeta"})
                return
            if remontar is None:
                self._json({"ok": False, "por_que": "este servidor no sabe volver a montar"})
                return
            try:
                remontar(destino)
                self._json({"ok": True, "que": "montado", "titulo": os.path.basename(destino)})
            except Exception as e:
                self._json({"ok": False, "por_que": "%s %s" % (type(e).__name__, e)})

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", puerto),
                                functools.partial(M, directory=carpeta)) as srv:
        url = "http://127.0.0.1:%d/index.html" % puerto
        avisar("sirviendo %s" % carpeta)
        avisar("abre: %s" % url)
        avisar("para parar: Ctrl+C")
        if abrir:
            def _abrir():
                nav = os.path.join(os.path.dirname(os.path.abspath(__file__)), "navegador.py")
                try:
                    import importlib.util as u
                    e = u.spec_from_file_location("navegador", nav)
                    m = u.module_from_spec(e); e.loader.exec_module(m)
                    m.abrir(url, modo="app", avisar=lambda *a: None)
                except Exception as err:
                    avisar("sin perfil propio (%s): ábrelo a mano" % err)
            threading.Timer(0.8, _abrir).start()
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            avisar("\nparado")
    return 0
