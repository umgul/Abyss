# -*- coding: utf-8 -*-
"""Hablar con un navegador sin ventana por su propio protocolo, sin dependencias.

## Por qué existe

Capturar una página se venía haciendo con la bandera `--screenshot` de la línea de órdenes.
Eso dejó de funcionar. Medido el 9-sep-2026 con Edge 152.0.4191.66 en la máquina de
desarrollo:

  - página trivial (tres líneas de HTML): la misma orden da 0 bytes en un intento y 1.981 en
    el siguiente. No está rota: es una carrera, el proceso termina antes de escribir.
  - página con WebGL (la que genera `render3d.py`): **0 bytes en las tres variantes
    probadas** — `--headless`, `--headless=old` y `--headless=new`, con y sin
    `--disable-gpu`, con y sin SwiftShader. Tres intentos, todos vacíos.
  - la MISMA página por este camino: 51.109 bytes, y `webgl2` disponible.

Así que el arreglo no es otra bandera: es dejar de pedir la foto por la puerta de la calle y
pedirla por el protocolo del navegador, que responde cuando la página está lista en vez de
cuando al proceso le parece.

## Por qué a mano y no con una biblioteca

El protocolo va por WebSocket y la biblioteca habitual no es dependencia de este paquete.
Añadir una dependencia para hacer un apretón de manos y mandar cuatro mensajes de texto sale
más caro que escribirlos: son unas setenta líneas y no hay nada que actualizar.

## Lo que NO hace

- No interpreta la página ni ejecuta guiones del usuario: solo navega, espera y fotografía.
- No reutiliza el navegador del usuario ni su perfil: abre uno temporal y lo borra.
- Si no hay navegador, lo dice y devuelve None. Nunca instala nada.
"""
import base64
import json
import os
import random
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request

try:                       # la consola de Windows y la salida tienen que hablar
    from . import consola  # el mismo idioma: ver abyss/consola.py
except ImportError:
    import consola
consola.preparar()
# ── el mínimo de WebSocket que hace falta ───────────────────────────────────
class _Ws:
    """Cliente de WebSocket de usar y tirar: apretón de manos, mandar y recibir texto.

    Solo lo que pide el protocolo del navegador: marcos de texto, sin extensiones, sin
    compresión. Los marcos del cliente van enmascarados porque la norma lo exige; los del
    servidor llegan sin máscara.
    """

    def __init__(self, url, timeout=30):
        sin_esquema = url.split("://", 1)[1]
        hostpuerto, _, camino = sin_esquema.partition("/")
        host, _, puerto = hostpuerto.partition(":")
        self.s = socket.create_connection((host, int(puerto or 80)), timeout=timeout)
        self.s.settimeout(timeout)
        clave = base64.b64encode(bytes(random.getrandbits(8) for _ in range(16))).decode()
        pet = ("GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n"
               % (camino, hostpuerto, clave))
        self.s.sendall(pet.encode())
        cabeceras = b""
        while b"\r\n\r\n" not in cabeceras:
            trozo = self.s.recv(4096)
            if not trozo:
                raise RuntimeError("el navegador cerró durante el apretón de manos")
            cabeceras += trozo
        if b" 101 " not in cabeceras.split(b"\r\n", 1)[0]:
            raise RuntimeError("el navegador no aceptó el WebSocket: %s"
                               % cabeceras.split(b"\r\n", 1)[0][:120])
        self.resto = cabeceras.split(b"\r\n\r\n", 1)[1]

    def _leer(self, n):
        while len(self.resto) < n:
            trozo = self.s.recv(65536)
            if not trozo:
                raise RuntimeError("el navegador cerró la conexión")
            self.resto += trozo
        salida, self.resto = self.resto[:n], self.resto[n:]
        return salida

    def manda(self, obj):
        carga = json.dumps(obj).encode("utf-8")
        cab = bytearray([0x81])                      # FIN + marco de texto
        n = len(carga)
        if n < 126:
            cab.append(0x80 | n)
        elif n < 65536:
            cab.append(0x80 | 126); cab += struct.pack(">H", n)
        else:
            cab.append(0x80 | 127); cab += struct.pack(">Q", n)
        mascara = bytes(random.getrandbits(8) for _ in range(4))
        cab += mascara
        self.s.sendall(bytes(cab) + bytes(c ^ mascara[i % 4] for i, c in enumerate(carga)))

    def recibe(self):
        """Un mensaje de texto entero, juntando los trozos si vino partido."""
        partes = []
        while True:
            b1, b2 = self._leer(2)
            fin, opcode = b1 & 0x80, b1 & 0x0F
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._leer(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._leer(8))[0]
            carga = self._leer(n)
            if opcode == 0x8:                        # el otro lado cierra
                raise RuntimeError("el navegador cerró la conexión")
            if opcode == 0x9:                        # ping: se contesta y se sigue
                continue
            partes.append(carga)
            if fin:
                return json.loads(b"".join(partes).decode("utf-8"))

    def cierra(self):
        try:
            self.s.close()
        except OSError:
            pass


def _puerto_de(perfil, espera=25):
    """El puerto que el navegador escribe en su propio perfil al arrancar."""
    ruta = os.path.join(perfil, "DevToolsActivePort")
    hasta = time.time() + espera
    while time.time() < hasta:
        if os.path.isfile(ruta):
            try:
                with open(ruta, encoding="utf-8") as fh:
                    linea = fh.readline().strip()
                if linea.isdigit():
                    return int(linea)
            except OSError:
                pass
        time.sleep(0.15)
    return None


def captura(exe, url, ruta_png, ancho, alto, segundos=3.0, avisar=print):
    """Abre `url` en un navegador sin ventana y guarda la foto. Devuelve bytes o None.

    `segundos` es lo que se espera a que la página se asiente antes de disparar. Una escena
    con WebGL necesita ese respiro: pedir la foto nada más navegar da un lienzo en blanco,
    que es exactamente lo que no se distingue de un error.
    """
    perfil = tempfile.mkdtemp(prefix="abyss_cdp_")
    proc = None
    ws = None
    try:
        proc = subprocess.Popen(
            [exe, "--headless=new", "--remote-debugging-port=0",
             "--user-data-dir=" + perfil, "--no-first-run", "--no-default-browser-check",
             "--hide-scrollbars", "--disable-extensions",
             "--window-size=%d,%d" % (int(ancho), int(alto)), "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        puerto = _puerto_de(perfil)
        if not puerto:
            avisar("  el navegador no publicó su puerto de control")
            return None
        objetivos = json.load(urllib.request.urlopen(
            "http://127.0.0.1:%d/json/list" % puerto, timeout=10))
        wsurl = next((t["webSocketDebuggerUrl"] for t in objetivos
                      if t.get("type") == "page" and t.get("webSocketDebuggerUrl")), None)
        if not wsurl:
            avisar("  el navegador no ofreció ninguna pestaña")
            return None

        ws = _Ws(wsurl)
        n = [0]

        def orden(metodo, params=None):
            n[0] += 1
            ws.manda({"id": n[0], "method": metodo, "params": params or {}})
            while True:
                r = ws.recibe()
                if r.get("id") == n[0]:
                    if "error" in r:
                        raise RuntimeError("%s: %s" % (metodo, r["error"].get("message")))
                    return r.get("result", {})

        orden("Page.enable")
        # el tamaño se fija aquí, no con la ventana: así el PNG sale con las medidas pedidas
        orden("Emulation.setDeviceMetricsOverride",
              {"width": int(ancho), "height": int(alto), "deviceScaleFactor": 1,
               "mobile": False})
        orden("Page.navigate", {"url": url})
        time.sleep(segundos)
        res = orden("Page.captureScreenshot", {"format": "png"})
        datos = base64.b64decode(res["data"])
        with open(ruta_png, "wb") as fh:
            fh.write(datos)
        return datos
    except Exception as e:
        avisar("  por el protocolo del navegador: %s %s" % (type(e).__name__, e))
        return None
    finally:
        if ws:
            ws.cierra()
        if proc:
            try:
                proc.terminate(); proc.wait(timeout=8)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        shutil.rmtree(perfil, ignore_errors=True)
