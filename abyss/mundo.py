# -*- coding: utf-8 -*-
"""Mundo: motivos DEL MUNDO REAL para pintar — museos, lugares, vistas a pie de calle.

    mundo.buscar(motivo, fuentes=None, n=5, cfg=None, ...) -> lista de candidatos
    mundo.descargar(candidato, dir) -> (ruta_imagen, ruta_atribucion)
    mundo.contexto(motivo, cfg=None) -> dict (qué es, dónde está, lat/lon) o {}

Petición del usuario (ESPECIFICACION_TANDA3.md, T3.3, 7-sep-2026): la búsqueda de
motivos «debe incluir Street View o Google Maps, webs museísticas, de historia, de
arte, no los repos de imágenes; tiene que plasmar cosas del mundo real». Seis fuentes
(medido 7-sep 07:54 desde la máquina del usuario, ESPECIFICACION_TANDA3.md):

    fuente     | qué da                                    | clave            | medido
    met        | obras de la colección, dominio público    | ninguna          | 200 en 0,5s; «Last Supper» 67 resultados; objeto 437213 con primaryImage
    artic      | obras del Art Institute of Chicago, IIIF  | ninguna          | 200 en 0,7s; «Michelangelo» 3 de dominio público
    commons    | la obra o el lugar en alta resolución      | ninguna          | La última cena de Leonardo: 9600x4800, dominio público
    streetview | vista a pie de calle (Google Street View) | google_maps_key  | 403 sin clave: «You must use an API key»
    mapillary  | vista a pie de calle, CC BY-SA             | mapillary_token  | error 190 sin token
    webcam     | cámara pública EN DIRECTO (Windy)          | windy_key        | 403 sin clave

`met`, `artic` y `commons` no piden clave: se prueban SIEMPRE que se pidan. Las otras
tres SÍ necesitan una clave o token en `imagen_config.json` (`google_maps_key`,
`mapillary_token`, `windy_key`, plantilla en `plantillas/imagen_config.json`) — sin
ella, ESTE módulo NUNCA intenta la red: avisa «sin clave: …» (nunca una traza) y esa
fuente sencillamente no aporta candidatos, igual que hacen los proveedores sin
configurar de `imagen.py crear`.

`contexto(motivo)` (Wikidata `wbsearchentities` + Wikipedia REST, sin clave; 200
medido) trae qué es el motivo, de quién y su latitud/longitud si Wikipedia la conoce
— así `buscar()` puede pedir la vista a pie de calle sin que el usuario tenga que dar
`--lugar` a mano cuando el motivo ya es un lugar reconocible. Nunca lanza: sin red o
sin resultado, `{}` (un candidato sin contexto no revienta la búsqueda entera).

Sin combinar ni componer (decisión del usuario, 7-sep, igual que `imagen.py buscar`):
el motivo se pinta tal cual llega, o se esboza en el taller y se pinta. El TEXTO del
motivo viaja a cada fuente que se consulte (se dice); `descargar()` además trae la
imagen (o el fotograma de la webcam) desde el host que indique cada fuente.

Este módulo no toca `imagen.py`: expone `buscar()`/`descargar()`/`contexto()` y su
propio `_cli()` para que `imagen.py mundo …` delegue en él (mismo patrón que
`pintar`/`video` delegan en `pintor.py`/`video_pintura.py`).
"""
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

UA = "abyss-mundo/1.0 (Claude Code; uso personal)"
T_CONECTAR = 8    # segundos: cada llamada de búsqueda/contexto
T_GENERAR = 60    # segundos: la descarga de la imagen elegida (pueden ser decenas de MB)

FUENTES_ABIERTAS = ("met", "artic", "commons")       # sin clave
FUENTES_CON_CLAVE = ("streetview", "mapillary", "webcam")  # clave/token en imagen_config.json
FUENTES_TODAS = FUENTES_ABIERTAS + FUENTES_CON_CLAVE


def _cfg(mem):
    try:
        with open(os.path.join(mem, "imagen_config.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _pedir(url, datos=None, cabeceras=None, timeout=T_CONECTAR, metodo=None):
    """Devuelve (código, cuerpo_bytes, content_type). Los errores HTTP no lanzan: se
    devuelven, igual que en `imagen.py` (mismo motivo: quien llama decide qué hacer
    con un 403/404 sin que la excepción le tape el código)."""
    cab = {"User-Agent": UA}
    cab.update(cabeceras or {})
    req = urllib.request.Request(url, data=datos, headers=cab, method=metodo or ("POST" if datos else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers.get("Content-Type", "")


def _sin_html(texto):
    if not texto:
        return None
    limpio = re.sub(r"<[^>]+>", "", texto).strip()
    return limpio or None


def _extension_de(content_type, url):
    ct = (content_type or "").split(";")[0].strip().lower()
    por_ct = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
              "image/gif": ".gif", "image/webp": ".webp", "image/tiff": ".tif"}
    if ct in por_ct:
        return por_ct[ct]
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
    return ext if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif") else ".jpg"


def _candidato(fuente, titulo, autor, licencia, tamano, url, pagina):
    return {"fuente": fuente, "titulo": titulo, "autor": autor, "licencia": licencia,
            "tamano": tamano, "url": url, "pagina": pagina}


# ── fuentes abiertas: sin clave ──────────────────────────────────────────────

def _buscar_met(motivo, n, cfg, pedir_fn):
    """The Met Collection API: sin clave. El buscador solo da `objectID`s; hay que
    pedir el detalle de cada uno para saber si trae `primaryImage` Y es de dominio
    público (no todos los objetos con `hasImages=true` cumplen las dos cosas) — se
    piden de sobra (hasta 5x `n`, tope 20) y se descartan los que no."""
    q = urllib.parse.urlencode({"q": motivo, "hasImages": "true"})
    cod, cuerpo, ct = pedir_fn(
        f"https://collectionapi.metmuseum.org/public/collection/v1/search?{q}",
        timeout=T_CONECTAR, metodo="GET")
    if cod != 200:
        raise RuntimeError(f"HTTP {cod}")
    ids = json.loads(cuerpo).get("objectIDs") or []
    candidatos = []
    for oid in ids[:min(max(n * 5, 10), 20)]:
        if len(candidatos) >= n:
            break
        cod2, cuerpo2, ct2 = pedir_fn(
            f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}",
            timeout=T_CONECTAR, metodo="GET")
        if cod2 != 200:
            continue
        o = json.loads(cuerpo2)
        if not o.get("primaryImage") or not o.get("isPublicDomain"):
            continue
        candidatos.append(_candidato(
            fuente="met", titulo=o.get("title") or "(sin título)",
            autor=o.get("artistDisplayName") or "desconocido",
            licencia="dominio público", tamano=o.get("dimensions"),
            url=o["primaryImage"], pagina=o.get("objectURL") or ""))
    return candidatos


def _buscar_artic(motivo, n, cfg, pedir_fn):
    """Art Institute of Chicago: sin clave. La URL IIIF se compone con el
    `config.iiif_url` que trae la propia respuesta (no uno fijo a ciegas: si el host
    IIIF cambiara, esto lo seguiría acertando)."""
    campos = "id,title,artist_display,dimensions,image_id,is_public_domain"
    q = urllib.parse.urlencode({"q": motivo, "fields": campos, "limit": n})
    cod, cuerpo, ct = pedir_fn(f"https://api.artic.edu/api/v1/artworks/search?{q}",
                               timeout=T_CONECTAR, metodo="GET")
    if cod != 200:
        raise RuntimeError(f"HTTP {cod}")
    d = json.loads(cuerpo)
    iiif = (d.get("config") or {}).get("iiif_url") or "https://www.artic.edu/iiif/2"
    candidatos = []
    for o in d.get("data") or []:
        if len(candidatos) >= n:
            break
        if not o.get("is_public_domain") or not o.get("image_id"):
            continue
        candidatos.append(_candidato(
            fuente="artic", titulo=o.get("title") or "(sin título)",
            autor=o.get("artist_display") or "desconocido",
            licencia="dominio público", tamano=o.get("dimensions"),
            url=f"{iiif}/{o['image_id']}/full/843,/0/default.jpg",
            pagina=f"https://www.artic.edu/artworks/{o.get('id')}"))
    return candidatos


def _buscar_commons(motivo, n, cfg, pedir_fn):
    """Wikimedia Commons: sin clave; sirve tanto para la obra como para el lugar. La
    URL de `imageinfo.url` YA es la de resolución completa, no una miniatura (medido
    en ESPECIFICACION_TANDA3.md: La última cena de Leonardo, 9600x4800). El `Artist`
    de la API trae HTML de verdad (enlaces, a veces anidados en `<bdi>`/`<span>`):
    `_sin_html()` lo deja en texto plano."""
    q = urllib.parse.urlencode({
        "action": "query", "generator": "search", "gsrnamespace": 6, "gsrsearch": motivo,
        "gsrlimit": int(n), "prop": "imageinfo", "iiprop": "url|extmetadata|size", "format": "json",
    })
    cod, cuerpo, ct = pedir_fn(f"https://commons.wikimedia.org/w/api.php?{q}",
                               timeout=T_CONECTAR, metodo="GET")
    if cod != 200:
        raise RuntimeError(f"HTTP {cod}")
    datos = json.loads(cuerpo)
    paginas = ((datos.get("query") or {}).get("pages") or {})
    candidatos = []
    for pagina in list(paginas.values())[:n]:
        infos = pagina.get("imageinfo") or [{}]
        info = infos[0] if infos else {}
        meta = info.get("extmetadata") or {}

        def _m(clave):
            return (meta.get(clave) or {}).get("value")

        tamano = f"{info['width']}x{info['height']}" if info.get("width") and info.get("height") else None
        candidatos.append(_candidato(
            fuente="commons", titulo=pagina.get("title") or "(sin título)",
            autor=_sin_html(_m("Artist")) or _sin_html(_m("Credit")) or "desconocido",
            licencia=_m("LicenseShortName") or _m("License") or "desconocida",
            tamano=tamano, url=info.get("url") or "", pagina=info.get("descriptionurl") or ""))
    return candidatos


DESPACHO_ABIERTAS = {"met": _buscar_met, "artic": _buscar_artic, "commons": _buscar_commons}


# ── fuentes con clave: NUNCA tocan la red sin ella ───────────────────────────

def _buscar_streetview(motivo, n, cfg, pedir_fn, opciones):
    """Google Street View Static: pide primero `/metadata` (gratis, no gasta cuota
    de imagen) para saber si el punto tiene cobertura antes de dar la URL de la
    imagen. Sin `google_maps_key`, ni se intenta la red (medido sin clave, HTTP 403
    «You must use an API key», ESPECIFICACION_TANDA3.md)."""
    clave = (cfg.get("google_maps_key") or "").strip()
    if not clave:
        raise RuntimeError("sin clave: pon google_maps_key en imagen_config.json")
    lugar = opciones.get("lugar")
    if not lugar:
        raise RuntimeError("sin lugar: da --lugar lat,lon (el motivo no trajo coordenadas)")
    lat, lon = lugar
    base = {"size": "640x640", "location": f"{lat},{lon}", "fov": opciones.get("campo", 80),
            "heading": opciones.get("rumbo", 0), "pitch": opciones.get("inclinacion", 0)}
    cod, cuerpo, ct = pedir_fn(
        "https://maps.googleapis.com/maps/api/streetview/metadata?" + urllib.parse.urlencode({**base, "key": clave}),
        timeout=T_CONECTAR, metodo="GET")
    if cod != 200:
        raise RuntimeError(f"HTTP {cod}")
    meta = json.loads(cuerpo)
    if meta.get("status") != "OK":
        raise RuntimeError(f"{meta.get('status', 'ERROR')}: {meta.get('error_message', '')}"[:160])
    url_img = "https://maps.googleapis.com/maps/api/streetview?" + urllib.parse.urlencode({**base, "key": clave})
    return [_candidato(
        fuente="streetview", titulo=f"Street View de {lat:.5f},{lon:.5f}",
        autor="Google Street View", licencia="© Google (uso según sus términos de servicio)",
        tamano="640x640", url=url_img,
        pagina=f"https://www.google.com/maps/@?api=1&map_action=pano&pano={meta.get('pano_id', '')}")]


def _buscar_mapillary(motivo, n, cfg, pedir_fn, opciones):
    """Mapillary Graph API: sin `mapillary_token`, ni se intenta la red (medido sin
    token, error 190, ESPECIFICACION_TANDA3.md). Vistas a pie de calle con licencia
    CC BY-SA 4.0."""
    token = (cfg.get("mapillary_token") or "").strip()
    if not token:
        raise RuntimeError("sin clave: pon mapillary_token en imagen_config.json")
    lugar = opciones.get("lugar")
    if not lugar:
        raise RuntimeError("sin lugar: da --lugar lat,lon (el motivo no trajo coordenadas)")
    lat, lon = lugar
    q = urllib.parse.urlencode({
        "access_token": token, "fields": "id,thumb_2048_url,captured_at,creator",
        "closeto": f"{lon},{lat}", "radius": 500, "limit": n,
    })
    cod, cuerpo, ct = pedir_fn(f"https://graph.mapillary.com/images?{q}", timeout=T_CONECTAR, metodo="GET")
    if cod != 200:
        raise RuntimeError(f"HTTP {cod} {cuerpo[:140]!r}")
    datos = json.loads(cuerpo)
    if isinstance(datos, dict) and datos.get("error"):
        raise RuntimeError(str(datos["error"].get("message", "error"))[:160])
    candidatos = []
    for im in (datos.get("data") or [])[:n]:
        candidatos.append(_candidato(
            fuente="mapillary", titulo=f"Mapillary de {lat:.5f},{lon:.5f}",
            autor=(im.get("creator") or {}).get("username") or "colaborador de Mapillary",
            licencia="CC BY-SA 4.0", tamano="2048 px (lado mayor)",
            url=im.get("thumb_2048_url") or "",
            pagina=f"https://www.mapillary.com/app/?pKey={im.get('id', '')}"))
    return candidatos


def _buscar_webcam(motivo, n, cfg, pedir_fn, opciones):
    """Windy webcams API v3: sin `windy_key`, ni se intenta la red (medido sin clave,
    HTTP 403, ESPECIFICACION_TANDA3.md). El mundo EN DIRECTO: a diferencia de las
    otras cinco fuentes, la imagen puede ser distinta en cada descarga."""
    clave = (cfg.get("windy_key") or "").strip()
    if not clave:
        raise RuntimeError("sin clave: pon windy_key en imagen_config.json")
    lugar = opciones.get("lugar")
    if not lugar:
        raise RuntimeError("sin lugar: da --lugar lat,lon (el motivo no trajo coordenadas)")
    lat, lon = lugar
    q = urllib.parse.urlencode({"nearby": f"{lat},{lon},50", "include": "images,location", "limit": n})
    cod, cuerpo, ct = pedir_fn(f"https://api.windy.com/webcams/api/v3/webcams?{q}",
                               cabeceras={"x-windy-api-key": clave}, timeout=T_CONECTAR, metodo="GET")
    if cod != 200:
        raise RuntimeError(f"HTTP {cod} {cuerpo[:140]!r}")
    datos = json.loads(cuerpo)
    candidatos = []
    for w in (datos.get("webcams") or [])[:n]:
        img = ((w.get("images") or {}).get("current") or {}).get("preview") or ""
        loc = w.get("location") or {}
        candidatos.append(_candidato(
            fuente="webcam", titulo=w.get("title") or "cámara pública",
            autor=", ".join(x for x in (loc.get("city"), loc.get("country")) if x) or "Windy",
            licencia="Windy (uso según sus términos de servicio)", tamano=None,
            url=img, pagina=f"https://www.windy.com/webcams/{w.get('id', '')}"))
    return candidatos


DESPACHO_CON_CLAVE = {"streetview": _buscar_streetview, "mapillary": _buscar_mapillary, "webcam": _buscar_webcam}


# ── contexto: Wikidata + Wikipedia, sin clave ────────────────────────────────

def contexto(motivo, cfg=None, pedir_fn=None):
    """Wikidata `wbsearchentities` + Wikipedia REST, sin clave (medido 7-sep: ambas
    200, ESPECIFICACION_TANDA3.md). Qué es el motivo, de quién, y su latitud/longitud
    SI Wikipedia la conoce (campo `coordinates` del resumen; ausente en artículos que
    no son de un lugar, p. ej. una persona) — para poder derivar la vista a pie de
    calle sin que el usuario dé `--lugar` a mano. Nunca lanza: sin red, sin resultado
    en Wikidata o sin resumen en Wikipedia, devuelve lo que haya podido reunir (o
    `{}` si nada respondió) — un motivo sin contexto no debe reventar la búsqueda."""
    pedir_fn = pedir_fn or _pedir
    try:
        q = urllib.parse.urlencode({"action": "wbsearchentities", "search": motivo,
                                     "language": "es", "uselang": "es", "format": "json", "limit": 1})
        cod, cuerpo, ct = pedir_fn(f"https://www.wikidata.org/w/api.php?{q}", timeout=T_CONECTAR, metodo="GET")
        if cod != 200:
            return {}
        resultados = json.loads(cuerpo).get("search") or []
        if not resultados:
            return {}
        e = resultados[0]
    except Exception:
        return {}
    ctx = {"titulo": e.get("label") or motivo, "descripcion": e.get("description"),
           "wikidata_id": e.get("id"),
           "wikidata_url": f"https://www.wikidata.org/wiki/{e['id']}" if e.get("id") else None,
           "lat": None, "lon": None, "extracto": None, "url_wikipedia": None}
    try:
        titulo_wiki = urllib.parse.quote(ctx["titulo"].replace(" ", "_"))
        cod, cuerpo, ct = pedir_fn(f"https://es.wikipedia.org/api/rest_v1/page/summary/{titulo_wiki}",
                                   timeout=T_CONECTAR, metodo="GET")
        if cod == 200:
            w = json.loads(cuerpo)
            coords = w.get("coordinates") or {}
            ctx["lat"], ctx["lon"] = coords.get("lat"), coords.get("lon")
            ctx["extracto"] = (w.get("extract") or "")[:400] or None
            ctx["url_wikipedia"] = ((w.get("content_urls") or {}).get("desktop") or {}).get("page")
            if not ctx["descripcion"]:
                ctx["descripcion"] = w.get("description")
    except Exception:
        pass  # sin resumen de Wikipedia: se queda con lo que trajo Wikidata (o nada)
    return ctx


# ── buscar / descargar: la API pública del módulo ────────────────────────────

def buscar(motivo, fuentes=None, n=5, cfg=None, lugar=None, rumbo=0, inclinacion=0, campo=80,
           avisar=print, pedir_fn=None, contexto_previo=None):
    """Devuelve una lista de candidatos (dicts `fuente`/`titulo`/`autor`/`licencia`/
    `tamano`/`url`/`pagina`) del `motivo` en las `fuentes` pedidas.

    `fuentes`: `None` → las tres abiertas (`met`, `artic`, `commons`); `"todas"` →
    las seis; un nombre suelto o una lista/tupla de nombres → exactamente esas.

    Nunca lanza: cada fuente que falle (sin clave, sin lugar, HTTP, parseo) se avisa
    por `avisar` con `"<fuente>: <motivo>"` y sencillamente no aporta candidatos —
    igual que `imagen.buscar()`. El texto de `motivo` viaja a cada fuente consultada.

    `lugar=(lat, lon)`: punto para `streetview`/`mapillary`/`webcam`. Si no se da y
    se pide alguna de esas tres, se intenta derivar de `contexto(motivo)` (Wikidata +
    Wikipedia); si tampoco esa trae coordenadas, esa fuente se avisa `"sin lugar: …"`
    y no aporta candidatos — nunca se inventa un punto. `contexto_previo`: si quien
    llama ya calculó `contexto(motivo, cfg)` por su cuenta (la CLI lo hace para poder
    avisar de él), se pasa aquí para no volver a pedirlo a Wikidata/Wikipedia.

    El resultado se recorta a `n` en total (no a `n` por fuente), igual que
    `imagen.buscar()`."""
    cfg = cfg or {}
    pedir_fn = pedir_fn or _pedir
    if fuentes is None:
        fuentes = FUENTES_ABIERTAS
    elif isinstance(fuentes, str):
        fuentes = FUENTES_TODAS if fuentes == "todas" else (fuentes,)

    lugar_efectivo = lugar
    if lugar_efectivo is None and any(f in FUENTES_CON_CLAVE for f in fuentes):
        ctx = contexto_previo if contexto_previo is not None else contexto(motivo, cfg, pedir_fn=pedir_fn)
        if ctx.get("lat") is not None and ctx.get("lon") is not None:
            lugar_efectivo = (ctx["lat"], ctx["lon"])

    opciones = {"lugar": lugar_efectivo, "rumbo": rumbo, "inclinacion": inclinacion, "campo": campo}
    candidatos = []
    for f in fuentes:
        try:
            if f in DESPACHO_ABIERTAS:
                candidatos += DESPACHO_ABIERTAS[f](motivo, n, cfg, pedir_fn)
            elif f in DESPACHO_CON_CLAVE:
                candidatos += DESPACHO_CON_CLAVE[f](motivo, n, cfg, pedir_fn, opciones)
            else:
                avisar(f"{f}: fuente desconocida")
        except Exception as e:
            avisar(f"{f}: {e}")
    return candidatos[:n]


def descargar(candidato, directorio, pedir_fn=None):
    """Descarga `candidato['url']` a `directorio` y escribe junto a ella un `.txt`
    con la atribución completa. Devuelve `(ruta_imagen, ruta_atribucion)`. Sin
    combinar ni componer: guarda la imagen (o el fotograma de la webcam) TAL CUAL
    llega."""
    if not candidato.get("url"):
        raise RuntimeError("el candidato no trae URL de imagen")
    pedir_fn = pedir_fn or _pedir
    os.makedirs(directorio, exist_ok=True)
    cod, cuerpo, ct = pedir_fn(candidato["url"], timeout=T_GENERAR, metodo="GET")
    if cod != 200 or not cuerpo:
        raise RuntimeError(f"descarga: HTTP {cod}")
    base = f"mundo_{candidato.get('fuente', 'x')}_{time.strftime('%Y%m%d_%H%M%S')}"
    ruta_img = os.path.join(directorio, base + _extension_de(ct, candidato["url"]))
    with open(ruta_img, "wb") as fh:
        fh.write(cuerpo)
    ruta_txt = os.path.join(directorio, base + ".txt")
    with open(ruta_txt, "w", encoding="utf-8") as fh:
        fh.write(
            f"Título: {candidato.get('titulo', '')}\n"
            f"Autor/lugar: {candidato.get('autor', '')}\n"
            f"Licencia: {candidato.get('licencia', '')}\n"
            f"Fuente: {candidato.get('fuente', '')}\n"
            f"Tamaño: {candidato.get('tamano') or '?'}\n"
            f"Página: {candidato.get('pagina', '')}\n"
            f"URL de la imagen: {candidato['url']}\n"
        )
    return ruta_img, ruta_txt


# ── CLI: `imagen.py mundo …` delega aquí (mismo patrón que pintar/video) ────

def _cli(argv, mem, pedir_fn=None):
    argv = list(argv)
    if "--proyecto" in argv:  # por si se invoca este guion suelto (ver __main__)
        i = argv.index("--proyecto")
        del argv[i:i + 2]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 1
    motivo = None
    opts = {"fuente": None, "n": 5, "descargar": False, "lugar": None,
            "rumbo": 0, "inclinacion": 0, "campo": 80}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--fuente" and i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            i += 1
            v = argv[i]
            if v != "todas" and v not in FUENTES_TODAS:
                print(f'--fuente debe ser {"/".join(FUENTES_TODAS)} o todas, no "{v}"')
                return 1
            opts["fuente"] = v
        elif a == "--n" and i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            i += 1
            try:
                opts["n"] = int(argv[i])
            except ValueError:
                print(f'--n necesita un número, no "{argv[i]}"')
                return 1
        elif a == "--descargar":
            opts["descargar"] = True
        elif a == "--lugar" and i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            i += 1
            try:
                lat_s, lon_s = argv[i].split(",")
                opts["lugar"] = (float(lat_s), float(lon_s))
            except Exception:
                print(f'--lugar necesita "lat,lon", no "{argv[i]}"')
                return 1
        elif a in ("--rumbo", "--inclinacion", "--campo") and i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            i += 1
            try:
                opts[a[2:]] = float(argv[i])
            except ValueError:
                print(f'--{a[2:]} necesita un número, no "{argv[i]}"')
                return 1
        elif not a.startswith("--") and motivo is None:
            motivo = a
        else:
            print(f"argumento no reconocido: {a} (usa --fuente/--n/--descargar/--lugar/--rumbo/--inclinacion/--campo)")
            return 1
        i += 1
    if motivo is None:
        print("falta el motivo")
        return 1

    cfg = _cfg(mem)
    # El contexto (Wikidata+Wikipedia) solo se pide si hace falta: una búsqueda
    # corriente de met/artic/commons no necesita lat/lon, y pedirlo siempre pagaría
    # dos llamadas de red de más en el camino común. Mismo criterio que usa `buscar()`
    # por dentro (para quien la llame sin pasar por esta CLI) — aquí se calcula antes
    # para poder AVISAR del contexto encontrado, y se pasa ya resuelto a `buscar()`
    # para no volver a pedirlo.
    fuentes_pedidas = (FUENTES_TODAS if opts["fuente"] == "todas"
                        else (opts["fuente"],) if opts["fuente"] else FUENTES_ABIERTAS)
    ctx = None
    if opts["lugar"] is None and any(f in FUENTES_CON_CLAVE for f in fuentes_pedidas):
        ctx = contexto(motivo, cfg, pedir_fn=pedir_fn)
        if ctx.get("lat") is not None and ctx.get("lon") is not None:
            opts["lugar"] = (ctx["lat"], ctx["lon"])
        if ctx.get("descripcion") or ctx.get("extracto"):
            linea = ctx.get("extracto") or ctx.get("descripcion")
            print(f"  contexto ({ctx.get('titulo', motivo)}): {linea}"
                  + (f" [{ctx['lat']:.5f},{ctx['lon']:.5f}]" if ctx.get("lat") is not None else ""))

    avisos = []
    candidatos = buscar(motivo, fuentes=opts["fuente"], n=opts["n"], cfg=cfg, lugar=opts["lugar"],
                         rumbo=opts["rumbo"], inclinacion=opts["inclinacion"], campo=opts["campo"],
                         avisar=avisos.append, pedir_fn=pedir_fn, contexto_previo=ctx)
    for av in avisos:
        print(f"  aviso: {av}")
    if not candidatos:
        print("sin candidatos:", " · ".join(avisos) or "ninguna fuente devolvió nada")
        # código 1 (config, nunca traza) cuando el único motivo de fallo fue la falta
        # de clave en TODAS las fuentes que se intentaron; 2 para cualquier otro caso
        # (sin red, sin resultados, sin lugar…) — mismo reparto que el resto del paquete.
        return 1 if avisos and all(av.split(": ", 1)[-1].startswith("sin clave:") for av in avisos) else 2
    for c in candidatos:
        print(f"[{c['fuente']}] {c['titulo']} — {c['autor']} — {c['licencia']} — {c.get('tamano') or '?'} — {c['url']}")
    if opts["descargar"]:
        try:
            ruta_img, ruta_txt = descargar(candidatos[0], os.path.join(mem, "imagenes"), pedir_fn=pedir_fn)
            print(f"descargado: {ruta_img} (atribución en {ruta_txt})")
        except Exception as e:
            print(f"sin descarga: {type(e).__name__} {e}")
            return 2
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    _proj, _mem = rutas.resolver(sys.argv[1:], {})
    sys.exit(_cli(sys.argv[1:], _mem))
