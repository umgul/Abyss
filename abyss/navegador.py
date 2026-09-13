# -*- coding: utf-8 -*-
"""Abre una página local en un navegador con un PERFIL PROPIO donde la cámara ya está
concedida para ese sitio, para no tener que dar permiso en cada arranque.

## Por qué lo pedía cada vez

El permiso de cámara del navegador se guarda **por origen, y el origen incluye el puerto**:
`http://127.0.0.1:8811` y `http://127.0.0.1:8850` son dos sitios distintos y cada uno pide
lo suyo. Cambiar de puerto entre pruebas basta para que vuelva a preguntar. Por eso cada
herramienta de este paquete usa SIEMPRE el mismo puerto, y aquí se concede el permiso para
ese origen exacto.

## Qué se toca y qué NO

Se crea una carpeta de perfil DEL PROGRAMA (por defecto `mem/navegador/<puerto>`) y se
escribe el permiso ahí dentro. **No se toca el navegador del usuario, ni su perfil, ni sus
ajustes, ni sus otros permisos**: es un perfil aparte que solo usa esta página. Si se borra
esa carpeta, no queda rastro.

Uso:
    python navegador.py <url> [--perfil DIR] [--camara si|no] [--navegador RUTA]
                        [--modo app|kiosco|normal]

Devuelve por pantalla qué navegador usó y dónde dejó el perfil. Si no encuentra ninguno
compatible, lo dice y abre con el navegador de siempre (que preguntará por la cámara, y se
avisa) en vez de fallar en silencio.
"""
import json
import os
import subprocess
import sys
import time
import urllib.parse
import webbrowser

try:                       # la consola de Windows y la salida tienen que hablar
    from . import consola  # el mismo idioma: ver abyss/consola.py
except ImportError:
    import consola
consola.preparar()
CANDIDATOS = [
    # Brave primero: es el navegador del usuario. Todos estos son de la familia Chromium,
    # así que el perfil propio y el modo aplicación funcionan igual en cualquiera.
    r"C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe",
    r"C:/Program Files (x86)/BraveSoftware/Brave-Browser/Application/brave.exe",
    r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    r"C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    r"C:/Program Files/Google/Chrome/Application/chrome.exe",
    r"C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    "/usr/bin/microsoft-edge",
]


def carpeta_de_perfiles():
    """Dónde vive el perfil propio: FUERA del paquete. Un perfil de Chromium no es un
    fichero de ajustes: arrastra caché, cookies y listas de bloqueo del navegador —
    guardarlo dentro del repositorio lo infla con datos que no son código y hace que la
    propia auditoría del paquete (`auditar.py`) saque hallazgos falsos de red, con
    dominios de listas de filtros que el paquete no llama jamás.

    Se manda a la carpeta de caché del sistema, que es lo que el sistema operativo tiene
    para esto y lo que las herramientas de limpieza ya saben vaciar. `ABYSS_PERFIL_NAVEGADOR`
    sigue mandando por encima de todo, para quien quiera decidirlo.
    """
    base = os.environ.get("ABYSS_PERFIL_NAVEGADOR")
    if base:
        return base
    if sys.platform == "win32":
        raiz = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        raiz = os.path.join(os.path.expanduser("~"), "Library", "Caches")
    else:
        raiz = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(raiz, "abyss", "navegador")


def cual():
    """Ruta del primer navegador de la familia Chromium que exista, o None."""
    for p in CANDIDATOS:
        if os.path.exists(p):
            return p
    return None


def _ahora_chromium():
    """Marca de tiempo como la escribe Chromium: microsegundos desde 1601."""
    return str(int((time.time() + 11644473600) * 1_000_000))


def conceder_camara(perfil, origen):
    """Escribe en el perfil el permiso de cámara para `origen` (y solo para él): SOLO
    la cámara. Las páginas de este paquete no usan micrófono, así que el paquete no
    debe concederlo sin decirlo.

    Se conserva lo que ya hubiera en el fichero: se añade la excepción, no se pisa el
    resto. `setting: 1` es «permitir» en la tabla de Chromium. Si ese origen ya tenía
    el micrófono concedido (de una versión anterior de esta misma función), se retira
    aquí: solo esa excepción, de ese origen — ningún otro origen ni ninguna otra clave
    de `Preferences` se toca, así que los perfiles viejos se corrigen solos la próxima
    vez que se abran.
    """
    d = os.path.join(perfil, "Default")
    os.makedirs(d, exist_ok=True)
    ruta = os.path.join(d, "Preferences")
    try:
        with open(ruta, encoding="utf-8") as fh:
            prefs = json.load(fh)
    except (OSError, ValueError):
        prefs = {}
    exc = (prefs.setdefault("profile", {})
                .setdefault("content_settings", {})
                .setdefault("exceptions", {}))
    marca = _ahora_chromium()
    exc.setdefault("media_stream_camera", {})[origen + ",*"] = {"last_modified": marca, "setting": 1}
    # retira SOLO la excepción de micrófono de ESTE origen, si la hubiera; no crea la
    # clave si no existía, y no toca ninguna excepción de otro origen.
    exc.get("media_stream_mic", {}).pop(origen + ",*", None)
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(prefs, fh)
    return ruta


def abrir(url, perfil=None, camara=True, navegador=None, modo="app", avisar=print):
    """Abre `url`. Devuelve {"navegador", "perfil", "camara", "como", "modo"}.

    `modo`:
      - "app"  (por defecto): ventana de APLICACIÓN — sin barra de direcciones, sin
        pestañas, sin menús; solo la página, maximizada, con los botones de cerrar y
        minimizar del sistema. Es lo más parecido a un visor sin ser un navegador.
      - "kiosco": pantalla completa de verdad, sin ningún borde. Se sale con F11.
      - "normal": una pestaña corriente, con toda la barra.
    """
    partes = urllib.parse.urlsplit(url)
    origen = "%s://%s" % (partes.scheme, partes.netloc)
    exe = navegador or cual()
    if not exe:
        avisar("sin dato: no encuentro ningún navegador de la familia Chromium; abro con "
               "el de siempre, y ese SÍ preguntará por la cámara cada vez")
        webbrowser.open(url)
        return {"navegador": None, "perfil": None, "camara": False, "como": "por defecto"}

    if perfil is None:
        perfil = os.path.join(carpeta_de_perfiles(), partes.netloc.replace(":", "_"))
    perfil = os.path.abspath(perfil)
    os.makedirs(perfil, exist_ok=True)
    if camara:
        ruta = conceder_camara(perfil, origen)
        avisar("cámara concedida para %s en un perfil PROPIO (%s). No se ha tocado el "
               "navegador del usuario." % (origen, ruta))

    cmd = [exe, "--user-data-dir=" + perfil, "--no-first-run",
           "--no-default-browser-check", "--disable-features=Translate"]
    if modo == "kiosco":
        cmd += ["--kiosk", url]
    elif modo == "app":
        # `--app=` abre la página como si fuera un programa: nada de barra de direcciones,
        # pestañas ni menús. La ventana conserva los botones de cerrar y minimizar.
        cmd += ["--app=" + url, "--start-maximized"]
    else:
        cmd += [url]
    subprocess.Popen(cmd, close_fds=True)
    avisar("abierto con %s en modo %s" % (os.path.basename(exe), modo))
    return {"navegador": exe, "perfil": perfil, "camara": bool(camara),
            "como": "perfil propio", "modo": modo}


def _cli(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 1
    url = argv[0]
    perfil, camara, nav, modo = None, True, None, "app"
    for i, a in enumerate(argv[1:], 1):
        if a == "--perfil" and i + 1 < len(argv):
            perfil = argv[i + 1]
        elif a == "--camara" and i + 1 < len(argv):
            camara = argv[i + 1] != "no"
        elif a == "--navegador" and i + 1 < len(argv):
            nav = argv[i + 1]
        elif a == "--modo" and i + 1 < len(argv):
            modo = argv[i + 1]
    r = abrir(url, perfil=perfil, camara=camara, navegador=nav, modo=modo)
    print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
