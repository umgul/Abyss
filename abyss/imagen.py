# -*- coding: utf-8 -*-
"""Imagen: crear una imagen por texto, o pintar una foto pincelada a pincelada («Monet»).

    python imagen.py crear "lo que quieres ver" [salida.png] [--ancho N] [--alto N] [--semilla N]
                            [--via local|pollinations|cloudflare|together|huggingface|horde]
    python imagen.py pintar <foto> [salida_dir] [--ancho N] [--alta] [--suave [2]] [--acabado] [--html]
    python imagen.py video <trazos.json.gz> <salida.mp4> [--segundos 9] [--ancho 1080] [--suave] [--retrato]
    python imagen.py vias                     (qué proveedores están configurados y cuáles responden)
    python imagen.py buscar "texto" [--n 5] [--fuente openverse|commons|ambas] [--descargar]
    python imagen.py render <modelo.glb|.gltf|.obj|.stl|escena.json> [--html [salida.html]] [--png [salida.png]]
                            [--explosion N] [--camara x,y,z] [--mirar x,y,z] [--fondo #rrggbb]
                            [--luz calida|fria|neutra] [--ancho N] [--alto N]
                            [--pintar [--estilo oleo|impresionista|acuarela|pastel|carbon|tinta]
                                      [--alta] [--acabado] [--suave [2]]]
    python imagen.py mundo "<motivo>" [--fuente met|artic|commons|streetview|mapillary|webcam|todas]
                           [--n 5] [--descargar] [--lugar lat,lon --rumbo N --inclinacion N --campo N]

`crear` recorre una CASCADA de proveedores y se queda con el primero que devuelva una imagen:
  1. `local`: un servidor de imagen en tu máquina, estilo A1111/Forge/SD.Next (POST /sdapi/v1/txt2img)
     o compatible con OpenAI (POST /v1/images/generations, p. ej. stable-diffusion.cpp). Es la única
     vía en la que el prompt NO sale de tu máquina.
  2. Proveedores con clave, en el orden en que los pongas en `imagen_config.json`:
     `pollinations` (gen.pollinations.ai, clave en enter.pollinations.ai/keys),
     `cloudflare` (Workers AI, flux-1-schnell: account_id + api_token),
     `together` (api.together.xyz, modelo FLUX.1-schnell-Free),
     `huggingface` (router.huggingface.co, FLUX.1-schnell).
  3. `horde`: AI Horde (aihorde.net) con la clave anónima pública `0000000000`: sin registro, cola
     de voluntarios con prioridad mínima; el prompt se procesa en máquinas de terceros. La imagen
     final se descarga de un host de almacenamiento que algunas redes bloquean.
Medido el 6-sep-2026: el host antiguo image.pollinations.ai ya no sirve imágenes sin clave.

Lo que sale de la máquina: con cualquier vía que no sea `local`, el texto del prompt viaja a un
servidor ajeno. Ningún proveedor del lote declara en una página legible cuánto tiempo guarda los
prompts. Nada íntimo ni de casa por aquí.

Configuración: `<memoria>/imagen_config.json` (plantilla en plantillas/). Claves solo ahí, nunca en el
código. Cada petición se apunta en `<memoria>/imagen.log` (cuándo, vía, bytes, ruta, prompt recortado).
Las imágenes van a `<memoria>/imagenes/` salvo que des una salida.

`pintar` y `video` son locales por completo (Pillow + numpy; el vídeo, imageio-ffmpeg). Ver pintor.py
y video_pintura.py para las opciones.

`buscar` NO genera nada: busca imágenes con licencia libre ya hechas por alguien, en dos bancos sin
clave — Openverse (`api.openverse.org/v1/images/?q=…&license_type=commercial`, MEDIDO 6-sep: 200 en
0,6 s) y Wikimedia Commons (`commons.wikimedia.org/w/api.php?action=query&generator=search&
gsrnamespace=6&prop=imageinfo&iiprop=url|extmetadata`, MEDIDO 6-sep: 200 en 0,6 s). Imprime título,
autor, licencia y URL de cada resultado; con `--descargar` guarda la PRIMERA en `<memoria>/imagenes/`
junto a un `.txt` con la atribución completa (título, autor, licencia, página de origen, URL). Solo
busca y trae con atribución: NO monta, NO compone ni entiende la escena (decisión del usuario, 7-sep:
fuera el montaje automático de imágenes buscadas). Lo que sale de la máquina: el TEXTO de la búsqueda
viaja a esos dos servicios (nunca al resto de proveedores de `crear`); con `--descargar`, además, se
descarga la imagen elegida desde el host que indique cada banco. Las URLs base son fijas salvo por
`ABYSS_OPENVERSE_URL`/`ABYSS_COMMONS_URL`, que solo existen para poder probar esta pieza sin red
(`pruebas/test_imagen_buscar.py`, contra JSON guardado): en uso normal nunca se definen.

`render` delega en `render3d.renderizar()`: escribe SIEMPRE la
página three.js autocontenida y, con `--png` (o con `--pintar`, que necesita una imagen de la que
partir y por eso fuerza `--png` aunque no se pida a mano), una captura vía navegador sin cabeza —
sin uno, «sin dato: no hay navegador sin cabeza» y código 2 (la página HTML ya se ha escrito: eso
no depende del navegador). Con `--pintar`, el PNG resultante se pasa tal cual a
`pintor.pintar(..., estilo=...)`: las DOS salidas (el render y, si toca, el cuadro) se apuntan en
`<memoria>/imagen.log`, igual que `crear`. El resto de banderas (`--explosion`, `--camara`,
`--mirar`, `--fondo`, `--luz`) son las de `render3d.py`, que documenta también sus límites (visor y
editor de vistas, no modelador; three.js embebido en `abyss/vendor/`, sin red para verlo).

`mundo` delega ENTERO en `mundo._cli()`: motivos DEL MUNDO REAL
para pintar — The Met, el Art Institute of Chicago y Wikimedia Commons sin clave; Street View,
Mapillary y las webcams de Windy con clave/token propios en `imagen_config.json`
(`google_maps_key`, `mapillary_token`, `windy_key`) — sin ellas, esa fuente ni toca la red: avisa
«sin clave: …» y sencillamente no aporta candidatos. Sin combinar ni componer (mismo criterio que
`buscar`): el motivo se pinta tal cual llega. Ver `mundo.py` para el detalle de cada fuente y de
`contexto()` (Wikidata + Wikipedia: deriva lat/lon del motivo cuando hace falta `--lugar` para
streetview/mapillary/webcam y no se ha dado a mano).
"""
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    from . import rutas
except Exception:  # ejecutado como guion suelto
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import rutas

UA = "abyss-imagen/1.0 (Claude Code; uso personal)"
T_CONECTAR = 8       # segundos: si un host no contesta en esto, se pasa al siguiente
T_GENERAR = 120      # segundos: espera máxima de la generación en sí
ORDEN_POR_DEFECTO = ["local", "pollinations", "cloudflare", "together", "huggingface", "horde"]


def _cfg(mem):
    try:
        with open(os.path.join(mem, "imagen_config.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _log(mem, etiqueta, texto):
    """Añade una línea a `<mem>/imagen.log`: fecha, etiqueta (verbo) y detalle, en
    columnas separadas por tabulador. Usada por `render`/`render --pintar` (T3.1: "las
    dos salidas se apuntan en mem/imagen.log") — el mismo fichero donde `crear()`
    escribe su propia línea (con su propio formato de columnas, sin tocar aquí)."""
    with open(os.path.join(mem, "imagen.log"), "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{etiqueta}\t{texto}\n")


def _pedir(url, datos=None, cabeceras=None, timeout=T_GENERAR, metodo=None):
    """Devuelve (código, cuerpo_bytes, content_type). Los errores HTTP no lanzan: se devuelven."""
    cab = {"User-Agent": UA}
    cab.update(cabeceras or {})
    req = urllib.request.Request(url, data=datos, headers=cab, method=metodo or ("POST" if datos else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers.get("Content-Type", "")


def _es_imagen(datos, ct):
    return datos and len(datos) > 2000 and (ct.startswith("image/") or datos[:4] in (b"\x89PNG", b"RIFF", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1", b"\xff\xd8\xff\xdb"))


# ── proveedores: cada uno devuelve bytes de imagen o lanza RuntimeError con el motivo ──

def _local(prompt, ancho, alto, semilla, c):
    url = (c.get("local_url") or "").rstrip("/")
    if not url:
        raise RuntimeError("sin local_url en imagen_config.json")
    estilo = c.get("local_estilo", "a1111")
    if estilo == "openai":
        cod, cuerpo, ct = _pedir(url + "/v1/images/generations",
                                 json.dumps({"prompt": prompt, "size": f"{ancho}x{alto}", "n": 1,
                                             "response_format": "b64_json"}).encode(),
                                 {"Content-Type": "application/json"}, timeout=T_GENERAR)
        if cod != 200:
            raise RuntimeError(f"HTTP {cod}")
        d = json.loads(cuerpo)
        return base64.b64decode(d["data"][0]["b64_json"])
    carga = {"prompt": prompt, "width": int(ancho), "height": int(alto),
             "steps": int(c.get("local_steps", 20)), "cfg_scale": float(c.get("local_cfg", 6.0))}
    if semilla is not None:
        carga["seed"] = int(semilla)
    cod, cuerpo, ct = _pedir(url + "/sdapi/v1/txt2img", json.dumps(carga).encode(),
                             {"Content-Type": "application/json"}, timeout=T_GENERAR)
    if cod != 200:
        raise RuntimeError(f"HTTP {cod}")
    d = json.loads(cuerpo)
    return base64.b64decode(d["images"][0])


def _pollinations(prompt, ancho, alto, semilla, c):
    key = (c.get("pollinations_key") or "").strip()
    if not key:
        raise RuntimeError("sin pollinations_key (gen.pollinations.ai exige clave desde 2026)")
    q = f"?width={int(ancho)}&height={int(alto)}&nologo=true" + (f"&seed={int(semilla)}" if semilla is not None else "")
    url = "https://gen.pollinations.ai/image/" + urllib.parse.quote(prompt[:500]) + q
    cod, cuerpo, ct = _pedir(url, cabeceras={"Authorization": f"Bearer {key}"}, timeout=T_GENERAR)
    if not _es_imagen(cuerpo, ct):
        raise RuntimeError(f"HTTP {cod} {cuerpo[:100]!r}")
    return cuerpo


def _cloudflare(prompt, ancho, alto, semilla, c):
    cuenta = (c.get("cloudflare_account_id") or "").strip()
    token = (c.get("cloudflare_api_token") or "").strip()
    if not (cuenta and token):
        raise RuntimeError("sin cloudflare_account_id/cloudflare_api_token")
    url = f"https://api.cloudflare.com/client/v4/accounts/{cuenta}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    carga = {"prompt": prompt[:2048]}
    if semilla is not None:
        carga["seed"] = int(semilla)
    cod, cuerpo, ct = _pedir(url, json.dumps(carga).encode(),
                             {"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    if cod != 200:
        raise RuntimeError(f"HTTP {cod} {cuerpo[:100]!r}")
    if _es_imagen(cuerpo, ct):
        return cuerpo
    d = json.loads(cuerpo)  # formato JSON con la imagen en base64 (no medido con clave real: se prueba)
    img = (d.get("result") or {}).get("image") or ""
    if not img:
        raise RuntimeError("respuesta sin imagen")
    return base64.b64decode(img)


def _together(prompt, ancho, alto, semilla, c):
    key = (c.get("together_key") or "").strip()
    if not key:
        raise RuntimeError("sin together_key")
    carga = {"model": c.get("together_modelo", "black-forest-labs/FLUX.1-schnell-Free"), "prompt": prompt[:2048],
             "width": int(ancho), "height": int(alto), "n": 1, "response_format": "b64_json"}
    if semilla is not None:
        carga["seed"] = int(semilla)
    cod, cuerpo, ct = _pedir("https://api.together.xyz/v1/images/generations", json.dumps(carga).encode(),
                             {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    if cod != 200:
        raise RuntimeError(f"HTTP {cod} {cuerpo[:100]!r}")
    d = json.loads(cuerpo)
    return base64.b64decode(d["data"][0]["b64_json"])


def _huggingface(prompt, ancho, alto, semilla, c):
    key = (c.get("huggingface_key") or "").strip()
    if not key:
        raise RuntimeError("sin huggingface_key")
    url = "https://router.huggingface.co/hf-inference/models/" + c.get("huggingface_modelo", "black-forest-labs/FLUX.1-schnell")
    carga = {"inputs": prompt[:1000], "parameters": {"width": int(ancho), "height": int(alto)}}
    if semilla is not None:
        carga["parameters"]["seed"] = int(semilla)
    cod, cuerpo, ct = _pedir(url, json.dumps(carga).encode(),
                             {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    if not _es_imagen(cuerpo, ct):
        raise RuntimeError(f"HTTP {cod} {cuerpo[:100]!r}")
    return cuerpo


def _horde(prompt, ancho, alto, semilla, c):
    key = (c.get("horde_key") or "0000000000").strip()
    base = "https://aihorde.net/api/v2"
    cab = {"apikey": key, "Content-Type": "application/json", "Client-Agent": "abyss-imagen:1.0:(github)"}
    a = max(64, int(ancho) // 64 * 64)
    h = max(64, int(alto) // 64 * 64)
    carga = {"prompt": prompt[:1000], "params": {"width": a, "height": h, "steps": int(c.get("horde_steps", 20)), "n": 1},
             "nsfw": False, "censor_nsfw": True}
    if semilla is not None:
        carga["params"]["seed"] = str(int(semilla))
    cod, cuerpo, ct = _pedir(base + "/generate/async", json.dumps(carga).encode(), cab, timeout=T_CONECTAR * 3)
    if cod != 202:
        raise RuntimeError(f"encolar: HTTP {cod} {cuerpo[:100]!r}")
    ident = json.loads(cuerpo)["id"]
    limite = time.time() + T_GENERAR
    while time.time() < limite:
        time.sleep(6)
        cod, cuerpo, ct = _pedir(f"{base}/generate/check/{ident}", cabeceras={"apikey": key}, timeout=T_CONECTAR * 2)
        if cod == 200 and json.loads(cuerpo).get("done"):
            break
    else:
        raise RuntimeError(f"la cola no acabó en {T_GENERAR} s")
    cod, cuerpo, ct = _pedir(f"{base}/generate/status/{ident}", cabeceras={"apikey": key}, timeout=T_CONECTAR * 2)
    gens = json.loads(cuerpo).get("generations") or []
    if not gens:
        raise RuntimeError("sin generaciones")
    url = gens[0].get("img") or ""
    if not url.startswith("http"):
        return base64.b64decode(url)  # algunos workers devuelven base64 en vez de URL
    cod, cuerpo, ct = _pedir(url, timeout=T_CONECTAR * 3)
    if not _es_imagen(cuerpo, ct):
        raise RuntimeError(f"descarga: HTTP {cod} (host de almacenamiento bloqueado en esta red?)")
    return cuerpo


VIAS = {"local": _local, "pollinations": _pollinations, "cloudflare": _cloudflare, "together": _together,
        "huggingface": _huggingface, "horde": _horde}


def _configuradas(c):
    return {"local": bool(c.get("local_url")), "pollinations": bool(c.get("pollinations_key")),
            "cloudflare": bool(c.get("cloudflare_account_id") and c.get("cloudflare_api_token")),
            "together": bool(c.get("together_key")), "huggingface": bool(c.get("huggingface_key")), "horde": True}


def crear(prompt, mem, salida=None, ancho=1024, alto=1024, semilla=None, via=None, avisar=print):
    """Devuelve (ruta, bytes, vía). Lanza RuntimeError con el motivo de cada vía si ninguna sirve."""
    c = _cfg(mem)
    orden = [via] if via else list(c.get("orden") or ORDEN_POR_DEFECTO)
    conf = _configuradas(c)
    dir_img = os.path.join(mem, "imagenes")
    os.makedirs(dir_img, exist_ok=True)
    salida = salida or os.path.join(dir_img, f"imagen_{time.strftime('%Y%m%d_%H%M%S')}.png")
    errores = []
    for nombre in orden:
        fn = VIAS.get(nombre)
        if fn is None:
            errores.append(f"{nombre}: vía desconocida")
            continue
        if not conf.get(nombre) and nombre != via:
            errores.append(f"{nombre}: sin configurar")
            continue
        t0 = time.time()
        try:
            datos = fn(prompt, ancho, alto, semilla, c)
            if not datos or len(datos) < 2000:
                raise RuntimeError(f"respuesta demasiado corta ({len(datos or b'')} bytes)")
            with open(salida, "wb") as fh:
                fh.write(datos)
            with open(os.path.join(mem, "imagen.log"), "a", encoding="utf-8") as fh:
                fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{nombre}\t{len(datos)}B\t{time.time() - t0:.1f}s\t{salida}\t{prompt[:200]}\n")
            return salida, len(datos), nombre
        except Exception as e:
            errores.append(f"{nombre}: {type(e).__name__} {str(e)[:140]} ({time.time() - t0:.1f}s)")
            avisar(f"  {errores[-1]}")
    raise RuntimeError(" · ".join(errores))


def vias(mem):
    """Qué vías están configuradas y si su host contesta (sin gastar cuota: solo un GET a la raíz)."""
    c = _cfg(mem)
    conf = _configuradas(c)
    hosts = {"local": (c.get("local_url") or "").rstrip("/") or None, "pollinations": "https://gen.pollinations.ai/",
             "cloudflare": "https://api.cloudflare.com/client/v4/", "together": "https://api.together.xyz/",
             "huggingface": "https://router.huggingface.co/", "horde": "https://aihorde.net/api/v2/status/heartbeat"}
    filas = []
    for n in ORDEN_POR_DEFECTO:
        h = hosts[n]
        if not h:
            filas.append((n, conf[n], "sin host"))
            continue
        t0 = time.time()
        try:
            cod, _, _ = _pedir(h, timeout=T_CONECTAR)
            filas.append((n, conf[n], f"HTTP {cod} en {time.time() - t0:.1f}s"))
        except Exception as e:
            filas.append((n, conf[n], f"sin respuesta ({type(e).__name__}) en {time.time() - t0:.1f}s"))
    return filas


# ── buscar: Openverse y Wikimedia Commons, sin clave, solo busca y trae con atribución ──

def _url_openverse():
    """Fija salvo `ABYSS_OPENVERSE_URL` (solo para pruebas sin red: ver docstring del módulo)."""
    return os.environ.get("ABYSS_OPENVERSE_URL") or "https://api.openverse.org/v1/images/"


def _url_commons():
    """Fija salvo `ABYSS_COMMONS_URL` (solo para pruebas sin red: ver docstring del módulo)."""
    return os.environ.get("ABYSS_COMMONS_URL") or "https://commons.wikimedia.org/w/api.php"


def _sin_html(texto):
    if not texto:
        return None
    limpio = re.sub(r"<[^>]+>", "", texto).strip()
    return limpio or None


def buscar_openverse(consulta, n=5, pedir_fn=None):
    """Hasta `n` resultados de Openverse: lista de dicts {"fuente","titulo","autor",
    "licencia","url","pagina"}. `pedir_fn` (por defecto `_pedir`) se puede sustituir en
    pruebas para no tocar la red de verdad."""
    pedir_fn = pedir_fn or _pedir
    q = urllib.parse.urlencode({"q": consulta, "license_type": "commercial", "page_size": int(n)})
    cod, cuerpo, ct = pedir_fn(_url_openverse() + "?" + q, timeout=T_CONECTAR, metodo="GET")
    if cod != 200:
        raise RuntimeError(f"HTTP {cod}")
    datos = json.loads(cuerpo)
    resultados = []
    for r in (datos.get("results") or [])[:n]:
        licencia = (r.get("license") or "").upper()
        if r.get("license_version"):
            licencia += " " + r["license_version"]
        resultados.append({
            "fuente": "openverse",
            "titulo": r.get("title") or "(sin título)",
            "autor": r.get("creator") or "desconocido",
            "licencia": licencia or "desconocida",
            "url": r.get("url") or "",
            "pagina": r.get("foreign_landing_url") or r.get("url") or "",
        })
    return resultados


def buscar_commons(consulta, n=5, pedir_fn=None):
    """Hasta `n` resultados de Wikimedia Commons (mismo formato de dict que `buscar_openverse`)."""
    pedir_fn = pedir_fn or _pedir
    q = urllib.parse.urlencode({
        "action": "query", "generator": "search", "gsrnamespace": 6, "gsrsearch": consulta,
        "gsrlimit": int(n), "prop": "imageinfo", "iiprop": "url|extmetadata", "format": "json",
    })
    cod, cuerpo, ct = pedir_fn(_url_commons() + "?" + q, timeout=T_CONECTAR, metodo="GET")
    if cod != 200:
        raise RuntimeError(f"HTTP {cod}")
    datos = json.loads(cuerpo)
    paginas = ((datos.get("query") or {}).get("pages") or {})
    resultados = []
    for pagina in list(paginas.values())[:n]:
        infos = pagina.get("imageinfo") or [{}]
        info = infos[0] if infos else {}
        meta = info.get("extmetadata") or {}

        def _m(clave):
            return (meta.get(clave) or {}).get("value")

        resultados.append({
            "fuente": "commons",
            "titulo": pagina.get("title") or "(sin título)",
            "autor": _sin_html(_m("Artist")) or "desconocido",
            "licencia": _m("LicenseShortName") or _m("License") or "desconocida",
            "url": info.get("url") or "",
            "pagina": info.get("descriptionurl") or "",
        })
    return resultados


BUSCADORES = {"openverse": buscar_openverse, "commons": buscar_commons}


def buscar(consulta, n=5, fuente="ambas"):
    """Devuelve `(resultados, errores)`: `resultados` mezcla lo que devuelva cada fuente
    pedida (recortado a `n` en total), `errores` es una lista de avisos "fuente: motivo"
    de las fuentes que fallaron (nunca lanza si al menos una fuente responde)."""
    fuentes = ("openverse", "commons") if fuente == "ambas" else (fuente,)
    resultados, errores = [], []
    for f in fuentes:
        try:
            resultados += BUSCADORES[f](consulta, n)
        except Exception as e:
            errores.append(f"{f}: {type(e).__name__} {str(e)[:140]}")
    return resultados[:n], errores


def _extension_de(content_type, url):
    ct = (content_type or "").split(";")[0].strip().lower()
    por_ct = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
              "image/gif": ".gif", "image/webp": ".webp", "image/svg+xml": ".svg"}
    if ct in por_ct:
        return por_ct[ct]
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
    return ext if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg") else ".jpg"


def descargar_con_atribucion(resultado, mem):
    """Descarga `resultado['url']` a `<mem>/imagenes/` y escribe junto a ella un `.txt` con
    la atribución completa. Devuelve `(ruta_imagen, ruta_txt)`."""
    if not resultado.get("url"):
        raise RuntimeError("el resultado no trae URL de imagen")
    dir_img = os.path.join(mem, "imagenes")
    os.makedirs(dir_img, exist_ok=True)
    cod, cuerpo, ct = _pedir(resultado["url"], timeout=T_GENERAR, metodo="GET")
    if cod != 200 or not cuerpo:
        raise RuntimeError(f"descarga: HTTP {cod}")
    base = f"buscar_{resultado.get('fuente', 'x')}_{time.strftime('%Y%m%d_%H%M%S')}"
    ruta_img = os.path.join(dir_img, base + _extension_de(ct, resultado["url"]))
    with open(ruta_img, "wb") as fh:
        fh.write(cuerpo)
    ruta_txt = os.path.join(dir_img, base + ".txt")
    with open(ruta_txt, "w", encoding="utf-8") as fh:
        fh.write(
            f"Título: {resultado.get('titulo', '')}\n"
            f"Autor: {resultado.get('autor', '')}\n"
            f"Licencia: {resultado.get('licencia', '')}\n"
            f"Fuente: {resultado.get('fuente', '')}\n"
            f"Página: {resultado.get('pagina', '')}\n"
            f"URL de la imagen: {resultado['url']}\n"
        )
    return ruta_img, ruta_txt


def _cli(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 1
    verbo, resto = argv[0], list(argv[1:])
    proj, mem = rutas.resolver(resto, {})
    if "--proyecto" in resto:  # se resolvió arriba: fuera también su valor, o queda
        i = resto.index("--proyecto")  # colándose como salida/prompt del verbo (medido 6-sep)
        del resto[i:i + 2]
    if verbo == "vias":
        for n, ok, estado in vias(mem):
            print(f"{n:12s} {'configurada' if ok else 'sin configurar':15s} {estado}")
        return 0
    if verbo == "buscar":
        if not resto:
            print("falta el texto a buscar")
            return 1
        opts = {"n": 5, "fuente": "ambas", "descargar": False}
        consulta = None
        i = 0
        while i < len(resto):
            a = resto[i]
            if a == "--n" and i + 1 < len(resto) and not resto[i + 1].startswith("--"):
                i += 1
                try:
                    opts["n"] = int(resto[i])
                except ValueError:
                    print(f'--n necesita un número, no "{resto[i]}"')
                    return 1
            elif a == "--fuente" and i + 1 < len(resto) and not resto[i + 1].startswith("--"):
                i += 1
                if resto[i] not in ("openverse", "commons", "ambas"):
                    print(f'--fuente debe ser openverse, commons o ambas, no "{resto[i]}"')
                    return 1
                opts["fuente"] = resto[i]
            elif a == "--descargar":
                opts["descargar"] = True
            elif not a.startswith("--") and consulta is None:
                consulta = a
            else:
                print(f"argumento no reconocido: {a} (usa --n/--fuente/--descargar)")
                return 1
            i += 1
        if consulta is None:
            print("falta el texto a buscar")
            return 1
        resultados, errores = buscar(consulta, n=opts["n"], fuente=opts["fuente"])
        for e in errores:
            print(f"  aviso: {e}")
        if not resultados:
            print("sin resultados:", " · ".join(errores) or "ninguna fuente devolvió nada")
            return 2
        for r in resultados:
            print(f"[{r['fuente']}] {r['titulo']} — {r['autor']} — {r['licencia']} — {r['url']}")
        if opts["descargar"]:
            try:
                ruta_img, ruta_txt = descargar_con_atribucion(resultados[0], mem)
                print(f"descargada: {ruta_img} (atribución en {ruta_txt})")
            except Exception as e:
                print(f"sin descarga: {type(e).__name__} {e}")
                return 2
        return 0
    if verbo == "crear":
        if not resto:
            print("falta el texto")
            return 1
        prompt = resto[0]
        opts = {"salida": None, "ancho": 1024, "alto": 1024, "semilla": None, "via": None}
        i = 1
        while i < len(resto):
            a = resto[i]
            # `i + 1 < len(resto)` sin más ya no basta (fallo "roza" del revisor 3,
            # 6-sep): si detrás de una bandera conocida viene OTRA bandera
            # (`--ancho --via local`), eso es un valor que falta, no un valor —
            # tratarlo como si lo fuera reventaba `int()` con una traza cruda. Se
            # exige además que el siguiente token no empiece por `--`.
            if a in ("--ancho", "--alto", "--semilla", "--via") and i + 1 < len(resto) and not resto[i + 1].startswith("--"):
                i += 1
                v = resto[i]
                k = a[2:]
                if k == "via":
                    opts[k] = v
                else:
                    try:
                        opts[k] = int(v)
                    except ValueError:
                        print(f'--{k} necesita un número, no "{v}"')
                        return 1
            elif not a.startswith("--") and opts["salida"] is None:
                opts["salida"] = a
            else:
                # antes: cualquier otra cosa (un segundo posicional, un `--ancho`
                # sin valor detrás, una bandera desconocida) se tragaba en silencio
                # y `crear` seguía con sus valores por defecto (1024x1024, semilla
                # al azar) sin avisar de que el argumento pedido no se había usado
                # (ESPECIFICACION.md §3, medido 6-sep: `crear "gato" g1.png 512 384
                # 7 --via local` generaba 1024x1024, los tres posicionales de más
                # ignorados del todo). También cae aquí una bandera conocida sin
                # valor real detrás (fin de la lista, o seguida de otra bandera).
                print(f"argumento no reconocido: {a} (usa --ancho/--alto/--semilla)")
                return 1
            i += 1
        try:
            ruta, n, nombre = crear(prompt, mem, **opts)
            print(f"imagen ({nombre}): {ruta} ({n} bytes)")
            return 0
        except Exception as e:
            print("sin imagen:", str(e)[:600])
            return 2
    if verbo == "pintar":
        try:
            import pintor
        except ModuleNotFoundError as e:
            # pintor.py importa Pillow y numpy a nivel de módulo (sin fallback
            # silencioso): sin ellas, ANTES esto dejaba salir la traza cruda de
            # ModuleNotFoundError — el README promete "nunca con una traza cruda".
            print(f"sin cuadro: falta Pillow/numpy (pip install Pillow numpy) [{e.name}]")
            return 2
        if not resto:
            print("falta la foto")
            return 1
        args = list(resto)
        if len(args) > 1 and not args[1].startswith("--"):
            args = [args[0], "--salida", args[1]] + args[2:]
        return pintor._cli(args)
    if verbo == "video":
        try:
            import video_pintura
        except ModuleNotFoundError as e:
            # video_pintura.py importa Pillow a nivel de módulo; imageio_ffmpeg se
            # comprueba dentro (RuntimeError con mensaje claro), pero sin Pillow el
            # import entero fallaba con una traza cruda antes de llegar ahí.
            print(f"sin video: falta Pillow/imageio-ffmpeg (pip install Pillow imageio-ffmpeg) [{e.name}]")
            return 2
        return video_pintura._cli(resto)
    if verbo == "render":
        if not resto:
            print("falta el modelo o la escena (.glb/.gltf/.obj/.stl/escena.json)")
            return 1
        entrada = resto[0]
        opts = {"html": None, "png": None, "explosion": 0.0, "ancho": 1600, "alto": 900,
                "camara": None, "mirar": None, "fondo": None, "luz": "neutra"}
        pintar_pedido = False
        pintar_opts = {"estilo": "oleo", "alta": False, "acabado": False, "supermuestreo": 1}
        i = 1
        while i < len(resto):
            a = resto[i]
            if a == "--html":
                if i + 1 < len(resto) and not resto[i + 1].startswith("--"):
                    i += 1
                    opts["html"] = resto[i]
                else:
                    opts["html"] = True
            elif a == "--png":
                if i + 1 < len(resto) and not resto[i + 1].startswith("--"):
                    i += 1
                    opts["png"] = resto[i]
                else:
                    opts["png"] = True
            elif a in ("--explosion", "--ancho", "--alto") and i + 1 < len(resto) and not resto[i + 1].startswith("--"):
                i += 1
                clave = a[2:]
                try:
                    opts[clave] = float(resto[i]) if clave == "explosion" else int(resto[i])
                except ValueError:
                    print(f'--{clave} necesita un número, no "{resto[i]}"')
                    return 1
            elif a in ("--camara", "--mirar", "--fondo") and i + 1 < len(resto) and not resto[i + 1].startswith("--"):
                i += 1
                opts[a[2:]] = resto[i]
            elif a == "--luz" and i + 1 < len(resto):
                i += 1
                if resto[i] not in ("calida", "fria", "neutra"):
                    print(f'--luz debe ser calida/fria/neutra, no "{resto[i]}"')
                    return 1
                opts["luz"] = resto[i]
            elif a == "--pintar":
                pintar_pedido = True
            elif a == "--estilo" and i + 1 < len(resto) and not resto[i + 1].startswith("--"):
                i += 1
                pintar_opts["estilo"] = resto[i]
            elif a == "--alta":
                pintar_opts["alta"] = True
            elif a == "--acabado":
                pintar_opts["acabado"] = True
            elif a == "--suave":
                pintar_opts["supermuestreo"] = 2
                if i + 1 < len(resto) and resto[i + 1].isdigit():
                    i += 1
                    pintar_opts["supermuestreo"] = int(resto[i])
            else:
                print(f"argumento no reconocido: {a}")
                return 1
            i += 1
        if pintar_pedido and opts["png"] is None:
            opts["png"] = True  # --pintar necesita un PNG de partida aunque no se pida --png a mano
        import render3d
        try:
            r = render3d.renderizar(entrada, **opts)
        except render3d.SinNavegador as e:
            print(f"sin dato: {e}")
            return 2
        except Exception as e:
            print(f"sin render: {type(e).__name__} {e}")
            return 2
        _log(mem, "render", f"{entrada}\t{r['html']}\t{r.get('png') or '-'}")
        print(json.dumps(r, ensure_ascii=False))
        if not pintar_pedido:
            return 0
        if not r.get("png"):
            print("sin cuadro: el render no produjo PNG (--pintar necesita una imagen de partida)")
            return 2
        try:
            import pintor
        except ModuleNotFoundError as e:
            print(f"sin cuadro: falta Pillow/numpy (pip install Pillow numpy) [{e.name}]")
            return 2
        try:
            p = pintor.pintar(r["png"], estilo=pintar_opts["estilo"], alta=pintar_opts["alta"],
                               acabado=pintar_opts["acabado"], supermuestreo=pintar_opts["supermuestreo"])
        except Exception as e:
            print(f"sin cuadro: {type(e).__name__} {e}")
            return 2
        _log(mem, "pintar", f"{r['png']}\t{p['png']}\t{p['trazos']}")
        print(json.dumps(p, ensure_ascii=False))
        return 0
    if verbo == "mundo":
        import mundo
        return mundo._cli(resto, mem)
    print("verbo desconocido:", verbo)
    return 1


if __name__ == "__main__":
    try:                       # la consola de Windows y la salida tienen que hablar
        from . import consola  # el mismo idioma: ver abyss/consola.py
    except ImportError:
        import consola
    consola.preparar()
    sys.exit(_cli(sys.argv[1:]))
