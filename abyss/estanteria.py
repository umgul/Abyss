# -*- coding: utf-8 -*-
"""Estantería kinética: una colección de una carpeta —libros, películas y series, discos,
fotos, documentos— como una estantería 3D que se recorre con la mano.

    python kinetico.py estanteria <carpeta> [--fichas fichas.json] [--hondura 3] [--titulo T]
                                  [--fondo imagen | --fondo-escritorio] [--salida DIR]
                                  [--puerto 8890] [--sin-abrir] [--solo-montar] [--sin-manos]

Cada fichero es una obra con su portada, que sale de la propia carpeta: una imagen con el
mismo título (el póster de una película, la carátula de un disco; si la comparten varias
obras numeradas, cada una lleva su número encima), la primera página de un PDF, un fotograma
de un vídeo, la miniatura que guarda un documento de Office o la propia imagen. Sin nada de
eso, una portada dibujada, y la ficha lo dice.

Autor, año y sinopsis NO se deducen: los trae `--fichas`, que escribe quien monta buscando
cada obra en una fuente, y solo se enseñan si la ficha lleva `fuente` http(s). Formato:

    {"titulo": "…", "etiqueta_autor": "director",
     "obras": [{"ficheros": ["ruta/relativa.mkv"]  o  "patron": "texto del nombre",
                "titulo": "…", "autor": "…", "anio": 1982, "sinopsis": "…",
                "fuente": "https://…", "nota": "Episodio {n} de la serie. ",
                "portada": "ruta/relativa/a/una/imagen.png"}]}

`titulo` solo se aplica si la ficha apunta a un único fichero; `{n}` en `nota` es el número
final del título. Opcionales, con su hueco dicho si faltan: PyMuPDF (primera página de un
PDF) e imageio-ffmpeg (fotograma y duración de un vídeo). Pillow es obligatoria. No usa la
red. Solo LEE la carpeta: lo que escribe va a la carpeta de montaje.
"""
import io
import json
import os
import re
import shutil
import subprocess
import unicodedata
import zipfile
from difflib import SequenceMatcher

try:
    from . import kinetico as _k
    from . import puerta_local
except ImportError:
    import kinetico as _k
    import puerta_local

SIN_DATO = "sin dato con fuente"
CW, CH, REJ = 256, 384, 8        # casilla de portada (2:3) y rejilla de 8x8 por atlas
HONDURA = 3
TOPE = 600
VACIAS = {"the", "of", "in", "to", "a", "an", "and", "el", "la", "los", "las", "de", "del", "y",
          "un", "una", "le", "les", "du", "des", "et"}
FAMILIAS_SIN_POSTER = {"imagen"}  # una imagen es su propia portada


def _normaliza(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def titulo_de(rel):
    """Título legible de un fichero: sin carpeta, sin extensión y sin la numeración delante."""
    base = os.path.splitext(os.path.basename(rel))[0]
    return re.sub(r"^\s*\d+\s*[.\-_)]\s*", "", base).strip() or base


def fichas_de(texto):
    return [t for t in re.findall(r"[a-z]+|\d+", _normaliza(texto)) if t not in VACIAS]


def _parecido(a, b):
    # 0,8 deja pasar una errata de una letra en una palabra de 4 o más («blrade» / «blade»)
    # y no confunde años distintos («2032» / «2022» dan 0,75)
    return a == b or (len(a) >= 4 and len(b) >= 4 and not (a.isdigit() or b.isdigit())
                      and SequenceMatcher(None, a, b).ratio() >= 0.8)


def es_su_poster(nombre_imagen, rel_obra):
    """¿Esta imagen es la portada de esta obra por el nombre? Todas las palabras de la imagen
    tienen que estar en la obra, y lo que le sobre a la obra solo puede ser un número corto
    (el episodio o el tomo): «Serie X.png» vale para «Serie X 3.mkv», no para «Serie Y 3.mkv»."""
    img = fichas_de(titulo_de(nombre_imagen))
    obra = fichas_de(titulo_de(rel_obra))
    if not img:
        return False
    usadas = set()
    for t in img:
        j = next((j for j, o in enumerate(obra) if j not in usadas and _parecido(t, o)), None)
        if j is None:
            return False
        usadas.add(j)
    sobra = [o for j, o in enumerate(obra) if j not in usadas]
    return all(o.isdigit() and len(o) <= 2 for o in sobra)


def _numero_final(titulo):
    m = re.search(r"(\d{1,3})\s*$", titulo)
    return m.group(1) if m else None


def _clave_natural(rel):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", rel)]


def _tamano(b):
    if b >= 1e9:
        return ("%.1f GB" % (b / 1e9)).replace(".", ",")
    if b >= 1e6:
        return "%d MB" % round(b / 1e6)
    return "%d KB" % max(1, round(b / 1e3))


def _duracion(seg):
    m = int(round(seg / 60))
    return "%d h %02d min" % (m // 60, m % 60) if m >= 60 else "%d min" % max(1, m)


# ── lo que se sabe de cada fichero, sin red ────────────────────────────────────
def _ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _segundos(ruta, ff):
    r = subprocess.run([ff, "-hide_banner", "-i", ruta], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60)
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else None


def _fotograma(ruta, seg, ff):
    """El fotograma más contrastado y menos oscuro de cinco repartidos por el vídeo."""
    from PIL import Image, ImageStat
    mejor = None
    for f in (0.15, 0.3, 0.45, 0.6, 0.75):
        t = (seg or 60) * f
        try:
            r = subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-ss", "%.2f" % t, "-i", ruta,
                                "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                               capture_output=True, timeout=120)
        except subprocess.TimeoutExpired:
            continue
        if r.returncode == 0 and r.stdout:
            im = Image.open(io.BytesIO(r.stdout)).convert("RGB")
            est = ImageStat.Stat(im.convert("L"))
            nota = est.stddev[0] * min(1.0, est.mean[0] / 90)
            if mejor is None or nota > mejor[0]:
                mejor = (nota, im, t)
    return mejor


def _primera_pagina(ruta):
    from PIL import Image
    import fitz
    doc = fitz.open(ruta)
    try:
        pg = doc[0]
        z = CH * 2 / pg.rect.height
        pix = pg.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples), doc.page_count
    finally:
        doc.close()


def _de_zip(ruta):
    """(miniatura, diapositivas) de un documento Office o un epub: la miniatura que guarda
    el propio fichero, si la guarda."""
    from PIL import Image
    with zipfile.ZipFile(ruta) as z:
        nombres = z.namelist()
        diap = sum(1 for x in nombres if re.match(r"ppt/slides/slide\d+\.xml$", x)) or None
        cand = [x for x in nombres if x.lower().startswith("docprops/thumbnail")]
        if not cand:
            cand = [x for x in nombres if "cover" in x.lower() and x.lower().endswith((".jpg", ".jpeg", ".png"))]
        im = Image.open(io.BytesIO(z.read(cand[0]))) if cand else None
        return im, diap


def _fuente_tipografica(tam):
    from PIL import ImageFont
    carpetas = [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
                "/usr/share/fonts/truetype/dejavu", "/Library/Fonts", "/System/Library/Fonts"]
    for c in carpetas:
        for f in ("bahnschrift.ttf", "segoeui.ttf", "arial.ttf", "DejaVuSans.ttf", "Arial.ttf"):
            try:
                return ImageFont.truetype(os.path.join(c, f), tam)
            except OSError:
                pass
    return ImageFont.load_default()


def portada_dibujada(titulo, familia, color):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (CW, CH), (20, 22, 26))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, CW, 10], fill=color)
    d.text((16, 26), familia.upper(), font=_fuente_tipografica(16), fill=color)
    f = _fuente_tipografica(22)
    y, linea = 70, ""
    for palabra in titulo.split():
        prueba = (linea + " " + palabra).strip()
        if d.textlength(prueba, font=f) > CW - 32 and linea:
            d.text((16, y), linea, font=f, fill=(232, 234, 237))
            y, linea = y + 30, palabra
            if y > CH - 60:
                break
        else:
            linea = prueba
    if linea and y <= CH - 60:
        d.text((16, y), linea, font=f, fill=(232, 234, 237))
    return im


def _encaja(im):
    from PIL import Image, ImageOps
    return ImageOps.fit(im.convert("RGB"), (CW, CH), Image.LANCZOS, centering=(0.5, 0.45))


def _con_numero(im, n):
    from PIL import ImageDraw
    im = im.copy()
    d = ImageDraw.Draw(im)
    texto = "Nº %s" % n
    f = _fuente_tipografica(26)
    w = d.textlength(texto, font=f)
    x, y = (CW - w) / 2, CH - 58
    d.rounded_rectangle([x - 14, y - 8, x + w + 14, y + 36], radius=8, fill=(10, 10, 14))
    d.text((x, y), texto, font=f, fill=(255, 90, 90))
    return im


# ── las fichas ──────────────────────────────────────────────────────────────────
def carga_fichas(ruta, rels, avisar=print):
    """(cabecera, {rel: ficha}) de `fichas.json`. Una ficha que no apunta a nada que exista se
    dice y se ignora; una sin `fuente` http(s) conserva título y portada, pero no autor, año
    ni sinopsis."""
    with io.open(ruta, encoding="utf-8") as fh:
        d = json.load(fh)
    por_rel = {}
    for o in d.get("obras", []):
        if o.get("ficheros"):
            objetivo = [str(f).replace("\\", "/") for f in o["ficheros"]]
            for f in objetivo:
                if f not in rels:
                    avisar("ficha sin fichero: %s no está en la carpeta" % f)
            objetivo = [f for f in objetivo if f in rels]
        elif o.get("patron"):
            p = _normaliza(str(o["patron"]))
            objetivo = [r for r in rels if p in _normaliza(r)]
            if not objetivo:
                avisar("ficha sin fichero: ningún nombre contiene %r" % o["patron"])
        else:
            avisar("ficha sin «ficheros» ni «patron»: ignorada")
            continue
        if not re.match(r"https?://", str(o.get("fuente") or "")) and (o.get("sinopsis") or o.get("autor") or o.get("anio")):
            avisar("ficha sin fuente http(s) para %s: su autor, año y sinopsis no se enseñan"
                   % (o.get("titulo") or o.get("patron") or objetivo[:1]))
        for r in objetivo:
            por_rel[r] = dict(o, _cuantos=len(objetivo))
    return d, por_rel


def _dentro(raiz, rel):
    ruta = os.path.realpath(os.path.join(raiz, *str(rel).replace("\\", "/").split("/")))
    raiz = os.path.realpath(raiz)
    try:
        return ruta if os.path.commonpath([ruta, raiz]) == raiz and os.path.isfile(ruta) else None
    except ValueError:
        return None


# ── la escena ───────────────────────────────────────────────────────────────────
def recorre(carpeta, hondura=HONDURA):
    """Rutas relativas (con `/`) de los ficheros visibles hasta `hondura` niveles, en orden
    natural (2 antes que 10)."""
    raiz = os.path.abspath(carpeta)
    rels = []
    for dirpath, dirnames, ficheros in os.walk(raiz):
        nivel = os.path.relpath(dirpath, raiz).count(os.sep) + (0 if dirpath == raiz else 1)
        dirnames[:] = [d for d in dirnames
                       if not d.startswith(".") and not _k._es_oculto(os.path.join(dirpath, d))
                       and nivel + 1 < hondura]
        for f in ficheros:
            p = os.path.join(dirpath, f)
            # un ejecutable no es una obra, y el puño lo lanzaría
            if f.startswith(".") or _k._es_oculto(p) or puerta_local.se_ejecutaria(f):
                continue
            rels.append(os.path.relpath(p, raiz).replace(os.sep, "/"))
    return sorted(rels, key=_clave_natural)


def de_estanteria(carpeta, fichas=None, hondura=HONDURA, titulo=None, fondo=None, avisar=print):
    """(datos de la escena, portadas en orden) o (None, error)."""
    try:
        from PIL import Image
    except ImportError:
        return None, "sin dato: hace falta Pillow para las portadas (pip install Pillow)"
    raiz = os.path.abspath(carpeta)
    if not os.path.isdir(raiz):
        return None, "sin dato: %s no es una carpeta" % carpeta
    rels = recorre(raiz, hondura)
    cabecera, por_rel = ({}, {})
    if fichas:
        try:
            cabecera, por_rel = carga_fichas(fichas, set(rels), avisar)
        except (OSError, ValueError) as e:
            return None, "sin dato: no puedo leer %s (%s)" % (fichas, e)

    # imágenes que son portada de otra obra (por nombre o porque una ficha lo dice): no son obras
    fondo_rel = None
    if fondo:
        fondo_abs = os.path.realpath(fondo if os.path.isabs(fondo) else os.path.join(raiz, fondo))
        try:
            dentro = os.path.commonpath([fondo_abs, os.path.realpath(raiz)]) == os.path.realpath(raiz)
        except ValueError:  # otra unidad
            dentro = False
        if dentro and os.path.isfile(fondo_abs):
            fondo_rel = os.path.relpath(fondo_abs, os.path.realpath(raiz)).replace(os.sep, "/")
        else:
            avisar("fondo ignorado: tiene que ser una imagen dentro de la carpeta (%s)" % fondo)
    familia = {r: _k._clase_de(r) for r in rels}
    imagenes = [r for r in rels if familia[r][0] == "imagen" and r != fondo_rel]
    no_imagen = [r for r in rels if familia[r][0] not in FAMILIAS_SIN_POSTER]
    poster_de, usadas = {}, set()
    for r in no_imagen:
        o = por_rel.get(r) or {}
        if o.get("portada"):
            if _dentro(raiz, o["portada"]):
                poster_de[r] = str(o["portada"]).replace("\\", "/")
                usadas.add(poster_de[r])
                continue
            avisar("portada de ficha fuera de la carpeta o inexistente: %s" % o["portada"])
        cand = [i for i in imagenes if es_su_poster(i, r)]
        if cand:
            cand.sort(key=lambda i: (len(fichas_de(titulo_de(i))), i), reverse=True)  # la más específica
            poster_de[r] = cand[0]
            usadas.add(cand[0])
    compartidas = {}
    for r, p in poster_de.items():
        compartidas[p] = compartidas.get(p, 0) + 1

    obras = [r for r in rels if r not in usadas and r != fondo_rel]
    recorte = max(0, len(obras) - TOPE)
    obras = obras[:TOPE]
    ff = _ffmpeg()
    items, portadas = [], []
    for i, r in enumerate(obras):
        ruta = os.path.join(raiz, *r.split("/"))
        nombre_fam, color = familia[r]
        o = por_rel.get(r) or {}
        tit = o["titulo"] if o.get("titulo") and o.get("_cuantos") == 1 else titulo_de(r)
        n = _numero_final(titulo_de(r))
        bytes_ = os.path.getsize(ruta)
        datos, portada, aviso = [], None, None
        try:
            if r in poster_de:
                portada = _encaja(Image.open(os.path.join(raiz, *poster_de[r].split("/"))))
                if compartidas[poster_de[r]] > 1 and n:
                    portada = _con_numero(portada, n)
                aviso = "portada: %s (%s)" % (poster_de[r], "la dice la ficha" if o.get("portada")
                                               else "misma obra por el nombre")
            if nombre_fam == "imagen":
                im = Image.open(ruta)
                datos.append("%d×%d px" % im.size)
                portada, aviso = _encaja(im), "portada: la propia imagen"
            elif nombre_fam == "pdf":
                try:
                    pag, paginas = _primera_pagina(ruta)
                    datos.append("%d páginas" % paginas)
                    if portada is None:
                        portada, aviso = _encaja(pag), "portada: la primera página del PDF"
                except ImportError:
                    datos.append("páginas sin dato (falta PyMuPDF)")
            elif nombre_fam in ("vídeo", "audio"):
                if ff:
                    seg = _segundos(ruta, ff)
                    datos.append(_duracion(seg) if seg else "duración sin dato")
                    if portada is None and nombre_fam == "vídeo":
                        mejor = _fotograma(ruta, seg, ff)
                        if mejor:
                            portada = _encaja(mejor[1])
                            aviso = "portada: fotograma del propio vídeo en el segundo %d" % mejor[2]
                else:
                    datos.append("duración sin dato (falta imageio-ffmpeg)")
            elif zipfile.is_zipfile(ruta) and os.path.splitext(r)[1].lower() in (
                    ".pptx", ".docx", ".xlsx", ".odt", ".odp", ".ods", ".epub"):
                mini, diap = _de_zip(ruta)
                if diap:
                    datos.append("%d diapositiva%s" % (diap, "" if diap == 1 else "s"))
                if portada is None and mini is not None:
                    portada, aviso = _encaja(mini), "portada: la miniatura que guarda el propio fichero"
        except Exception as e:
            avisar("aviso: %s no se pudo leer entero (%s: %s)" % (r, type(e).__name__, e))
        if portada is None:
            portada = portada_dibujada(tit, nombre_fam, color)
            aviso = "portada dibujada: el fichero no trae una ni hay imagen con su nombre"
        datos.append(_tamano(bytes_))

        con_fuente = bool(re.match(r"https?://", str(o.get("fuente") or "")))
        autor = str(o["autor"]) if con_fuente and o.get("autor") else ""
        if con_fuente and o.get("anio"):
            datos.insert(0, str(o["anio"]))
        sinopsis = SIN_DATO
        if con_fuente and o.get("sinopsis"):
            sinopsis = str(o.get("nota") or "").replace("{n}", n or "") + str(o["sinopsis"])
        items.append({"id": r, "titulo": tit, "autor": autor, "datos": " · ".join(datos),
                      "sinopsis": sinopsis, "fuente": str(o["fuente"]) if con_fuente else "",
                      "familia": nombre_fam, "color": color, "bytes": bytes_,
                      "atlas": i // (REJ * REJ), "casilla": i % (REJ * REJ), "aviso_portada": aviso})
        portadas.append(portada)

    con = sum(1 for it in items if it["fuente"])
    pie = ("%d obras · portadas: la imagen con su nombre, o lo que trae el propio fichero, o dibujada "
           "si no hay nada · autor, año y sinopsis solo con fuente (%d con fuente); el resto dice "
           "sin dato con fuente" % (len(items), con))
    if recorte:
        pie += " · %d ficheros más no caben (tope %d)" % (recorte, TOPE)
    datos_escena = {
        "tipo": "estanteria", "titulo": titulo or cabecera.get("titulo") or os.path.basename(raiz),
        "etiqueta_autor": cabecera.get("etiqueta_autor") or "autor",
        "raiz": raiz, "techo": raiz, "rejilla": REJ, "casilla_px": [CW, CH],
        "atlas": max(1, -(-len(items) // (REJ * REJ))), "items": items, "grupos": [], "aristas": [],
        "pie": pie,
        "procedencia": {"obras": "ficheros visibles de la carpeta hasta %d niveles, en orden natural" % hondura,
                        "portadas": "imagen con el mismo título; primera página, fotograma o miniatura del "
                                    "propio fichero; dibujada si no hay nada",
                        "fichas": "de %s; sin fuente http(s) no se enseñan autor, año ni sinopsis"
                                  % (os.path.basename(fichas) if fichas else "ninguna"),
                        "recorte": recorte},
        "_fondo_rel": fondo_rel,
    }
    return datos_escena, portadas


def monta(datos, portadas, destino, manos=True, fondo=None, avisar=print):
    """Escribe la escena en `destino`: nodos.json, atlas de portadas, la página y lo que
    necesita. Devuelve True si quedó montada. Se niega a montar dentro de la colección o
    encima de una carpeta que no sea un montaje de estantería: borra su `atlas/` y su
    `fondo.jpg` al rehacerlo."""
    from PIL import Image
    real_dest, real_raiz = os.path.realpath(destino), os.path.realpath(datos["raiz"])
    try:
        dentro = os.path.commonpath([real_dest, real_raiz]) == real_raiz
    except ValueError:
        dentro = False
    if dentro:
        avisar("no se monta dentro de la colección: elige otra --salida")
        return False
    if os.path.isdir(destino) and os.listdir(destino):
        try:
            with io.open(os.path.join(destino, "nodos.json"), encoding="utf-8") as fh:
                nuestra = json.load(fh).get("tipo") == "estanteria"
        except (OSError, ValueError):
            nuestra = False
        if not nuestra:
            avisar("--salida %s ya tiene cosas y no es un montaje de estantería: no se toca" % destino)
            return False
    os.makedirs(destino, exist_ok=True)
    carpeta_atlas = os.path.join(destino, "atlas")
    shutil.rmtree(carpeta_atlas, ignore_errors=True)
    os.makedirs(carpeta_atlas, exist_ok=True)
    for a in range(datos["atlas"]):
        hoja = Image.new("RGB", (CW * REJ, CH * REJ), (0, 0, 0))
        for it, p in zip(datos["items"], portadas):
            if it["atlas"] == a:
                hoja.paste(p, ((it["casilla"] % REJ) * CW, (it["casilla"] // REJ) * CH))
        hoja.save(os.path.join(carpeta_atlas, "atlas_%d.jpg" % a), quality=88)

    datos = dict(datos)
    fondo_rel = datos.pop("_fondo_rel", None)
    if os.path.exists(os.path.join(destino, "fondo.jpg")):
        os.remove(os.path.join(destino, "fondo.jpg"))
    if fondo == "escritorio":
        f = _k.fondo_del_escritorio(destino, avisar=avisar)
        if f:
            datos["fondo"] = f
    elif fondo_rel:
        try:
            im = Image.open(os.path.join(datos["raiz"], *fondo_rel.split("/"))).convert("RGB")
            if im.width > _k.ANCHO_FONDO:
                im = im.resize((_k.ANCHO_FONDO, max(1, round(im.height * _k.ANCHO_FONDO / im.width))), Image.LANCZOS)
            im.save(os.path.join(destino, "fondo.jpg"), "JPEG", quality=82, optimize=True)
            datos["fondo"] = {"fichero": "fondo.jpg", "de_donde": fondo_rel,
                              "que_se_le_hizo": "reescalado a %d px de ancho, JPEG de calidad 82" % im.width}
        except Exception as e:
            avisar("sin dato: no se pudo preparar el fondo %s (%s)" % (fondo_rel, e))

    with io.open(os.path.join(destino, "nodos.json"), "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=1)
    shutil.copy2(os.path.join(_k.PLANTILLAS, "estanteria.html"), os.path.join(destino, "index.html"))
    shutil.copy2(os.path.join(_k.PLANTILLAS, "gestos_comun.js"), os.path.join(destino, "gestos_comun.js"))
    shutil.copy2(os.path.join(_k.VENDOR, "three.min.js"), os.path.join(destino, "three.min.js"))
    mp = os.path.join(_k.VENDOR, "mp")
    if manos and os.path.isdir(mp):
        if not os.path.isdir(os.path.join(destino, "mp")):
            shutil.copytree(mp, os.path.join(destino, "mp"))
    elif manos:
        avisar("sin mp/ en vendor: la estantería funcionará con el ratón, no con la mano "
               "(python instalar.py --manos lo baja)")
    return True
