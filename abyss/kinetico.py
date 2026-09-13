# -*- coding: utf-8 -*-
"""Kinético: cualquier montón de cosas, en tres dimensiones y movido con la mano.

    python kinetico.py arbol <carpeta> [--hondura 2] [--tope 2000] [--puerto 8890] [--fondo-escritorio]
    python kinetico.py datos <nodos.json> [--puerto 8890] [--sin-abrir]
    python kinetico.py estanteria <carpeta> [--fichas fichas.json] [--titulo T] [--hondura 3]
                                  [--fondo imagen | --fondo-escritorio]
    python kinetico.py <lo que sea> --solo-montar --salida <carpeta> [--sin-manos]

`estanteria` es una colección con portadas (libros, películas, discos, fotos): ver
`abyss/estanteria.py`.

## Qué es esto, y qué NO es

El visor no sabe de qué habla. Come un `nodos.json` con cosas que tienen nombre, grupo,
tamaño, descripción y —si las hay— conexiones, y las pone como esferas en plantas. Quién
decide qué es una cosa, qué es un grupo y qué cuenta el tamaño es un ADAPTADOR, y hay uno
por fuente. Añadir una fuente nueva es escribir un adaptador, nunca tocar el visor.

Esa costura ya existía sin querer: el visor del mapa de dependencias solo cargaba tres
ficheros y no conocía ni una propiedad del dominio. Esto la hace explícita.

## Lo que este módulo NO hace, y se dice

- **No inventa jerarquía.** Si la fuente no tiene grupos, `disposicion` es `plano`: un solo
  suelo, y la leyenda lo dice. No se decreta una profundidad para que quede bonito.
- **No inventa conexiones.** Un árbol de carpetas no lleva aristas: la contención ya la
  dice la posición, y una línea de padre a hijo no añade nada. `aristas: []` es un estado
  legal y el visor apaga las líneas y el panel de vecinos.
- **No inventa descripciones.** Sin texto, `descripcion` va vacía y `descripcion_como` dice
  «sin dato con fuente». Una carpeta de fotos saldrá honestamente muda.
- **No cabe todo.** Por encima de `--tope` una carpeta se colapsa en una sola bola que dice
  cuántos descendientes tiene, y `procedencia.recorte` cuenta qué quedó fuera. 40.000
  ficheros se navegan por niveles, nunca de una vez.

## Qué copia al montaje

    nodos.json          — lo que produce el adaptador
    fuente_sdf.png/json — la tipografía, generada para ESTOS nombres
    index.html          — `plantillas/kinetico.html` tal cual
    gestos_comun.js     — el vocabulario de la mano, copia única del paquete
    three.min.js        — de `vendor/`
    mp/                 — solo si se piden las manos
"""
import io
import json
import math
import os
import shutil
import sys
import tempfile

try:                       # la consola de Windows y la salida tienen que hablar
    from . import consola  # el mismo idioma: ver abyss/consola.py
except ImportError:
    import consola
consola.preparar()
RAIZ = os.path.dirname(os.path.abspath(__file__))
PLANTILLAS = os.path.join(RAIZ, "plantillas")
VENDOR = os.path.join(RAIZ, "vendor")

CELDA = 6.0            # lado de la casilla de la rejilla, en unidades de escena
ALTO_PLANTA = 40.0     # separación entre plantas
HUECO_BLOQUE = 1.0     # aire entre bloques de una misma planta
TOPE = 2000            # decretado: por encima, se colapsa. Se dice en la procedencia
PUERTO = 8890

# Lo que no se recorre nunca: no es contenido, es maquinaria.
EXCLUIR = {".git", "venv", ".venv", "node_modules", "__pycache__", "site-packages",
           ".mypy_cache", ".pytest_cache", ".idea", ".vscode"}

COLORES = ["#fdcb6e", "#6c5ce7", "#00cec9", "#e17055", "#5f27cd", "#0abde3", "#fd79a8",
           "#a29bfe", "#55efc4", "#ffeaa7"]


# ── la tipografía ───────────────────────────────────────────────────────────
def atlas_sdf(glifos, em=96, margen=12):
    """Atlas de campo de distancias: en vez del dibujo de la letra, su distancia al borde.

    Con eso el visor reconstruye el contorno a cualquier tamaño y el texto se lee igual de
    cerca que de lejos. Se genera por montaje, con los glifos que de verdad hacen falta.
    """
    try:
        import cv2
        import numpy as np
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:
        return None, {"error": "sin dato: falta OpenCV, numpy o Pillow — %s" % e}

    fuente = None
    usada = "por defecto de Pillow"
    for n in ("consola.ttf", "arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"):
        try:
            fuente = ImageFont.truetype(n, em); usada = n; break
        except OSError:
            continue
    if fuente is None:
        fuente = ImageFont.load_default()

    celda = em + 2 * margen
    lado = max(1, math.ceil(math.sqrt(len(glifos))))
    atlas = np.zeros((lado * celda, lado * celda), np.uint8)
    met, recortados = {}, []
    for k, g in enumerate(glifos):
        fila, col = divmod(k, lado)
        im = Image.new("L", (celda, celda), 0)
        d = ImageDraw.Draw(im)
        # todos con la MISMA pluma: comparten línea de base. Moviendo cada glifo a su propia
        # caja de tinta, un nombre sale con las letras a distintas alturas
        d.text((margen, margen), g, font=fuente, fill=255)
        caja = d.textbbox((margen, margen), g, font=fuente)
        if caja[1] < 0 or caja[3] > celda or caja[0] < 0 or caja[2] > celda:
            recortados.append(g)
        b = (np.asarray(im) > 127).astype(np.uint8)
        campo = np.clip((cv2.distanceTransform(b, cv2.DIST_L2, 5)
                         - cv2.distanceTransform(1 - b, cv2.DIST_L2, 5)) / margen, -1, 1)
        atlas[fila * celda:(fila + 1) * celda, col * celda:(col + 1) * celda] = \
            ((campo * 0.5 + 0.5) * 255).astype(np.uint8)
        met[g] = {"celda": k, "avance": round(d.textlength(g, font=fuente) / em, 4)}
    return atlas, {"rejilla": lado, "celda_px": celda, "em_px": em, "margen_px": margen,
                   "glifos": met, "tipografia": usada, "recortados": recortados}


def glifos_de(datos):
    """Los caracteres que hacen falta: los de los nombres, los de los rótulos de grupo, y
    los que escribe la propia interfaz. Si falta uno, el visor lo dibuja como recuadro."""
    g = set(" 0123456789…·")
    for it in datos["items"]:
        g |= set(it.get("corto") or "")
    for gr in datos["grupos"]:
        g |= set((gr.get("nombre") or "").lower())
        g |= set(str(gr.get("n", "")))
    return sorted(x for x in g if x.strip() or x == " ")


# ── la colocación ───────────────────────────────────────────────────────────
def coloca(datos):
    """Rejilla por grupo, y bloques dentro del grupo si los items tienen padre.

    Mismas posiciones en cada montaje: un puntero que se mueve con la mano necesita que las
    cosas estén donde estaban. Sin `padre`, degenera exactamente en la rejilla de siempre.
    """
    por_grupo = {}
    for it in datos["items"]:
        por_grupo.setdefault(it["grupo"], []).append(it)

    for gr in datos["grupos"]:
        items = por_grupo.get(gr["id"], [])
        gr["n"] = len(items)
        if not items:
            gr.update(ancho=CELDA, fondo=CELDA, y=gr["id"] * ALTO_PLANTA)
            continue
        y = gr["id"] * ALTO_PLANTA
        bloques = {}
        for it in items:
            bloques.setdefault(it.get("padre") or "", []).append(it)

        cajas = []
        for clave, trozo in bloques.items():
            cols = max(1, math.ceil(math.sqrt(len(trozo))))
            filas = math.ceil(len(trozo) / cols)
            cajas.append({"items": trozo, "cols": cols, "filas": filas,
                          "ancho": cols * CELDA, "fondo": filas * CELDA})
        cajas.sort(key=lambda c: -c["fondo"])
        area = sum((c["ancho"] + HUECO_BLOQUE) * (c["fondo"] + HUECO_BLOQUE) for c in cajas)
        objetivo = math.sqrt(1.3 * area) if area else CELDA   # 1,3: holgura del estanteado
        x = z = alto_fila = ancho_max = 0.0
        for c in cajas:
            if x and x + c["ancho"] > objetivo:
                z += alto_fila + HUECO_BLOQUE
                x, alto_fila = 0.0, 0.0
            c["x0"], c["z0"] = x, z
            x += c["ancho"] + HUECO_BLOQUE
            alto_fila = max(alto_fila, c["fondo"])
            ancho_max = max(ancho_max, x)
        fondo_total = z + alto_fila
        gr.update(ancho=round(ancho_max, 3), fondo=round(fondo_total, 3), y=y)

        for c in cajas:
            for k, it in enumerate(c["items"]):
                f, col = divmod(k, c["cols"])
                it["x"] = round(c["x0"] + col * CELDA - ancho_max / 2, 3)
                it["z"] = round(c["z0"] + f * CELDA - fondo_total / 2, 3)
                it["y"] = y
    return datos


# ── el adaptador de árbol de carpetas ───────────────────────────────────────
def _cuenta_dentro(carpeta):
    """Cuántos ficheros cuelgan de aquí, a cualquier profundidad. Es lo que hace que una
    carpeta cerrada diga algo en vez de ser una bola muda."""
    n = 0
    for _aqui, dirs, fs in os.walk(carpeta):
        dirs[:] = [d for d in dirs if d not in EXCLUIR and not d.startswith(".")]
        n += len(fs)
    return n


# Qué formato es cada cosa. Esta tabla vive AQUÍ y no en la plantilla a propósito: saber
# que un .xlsx es una hoja de cálculo es conocimiento del dominio «ficheros», y la plantilla
# no sabe de qué habla — come `clase` y `clases` y colorea por lo que le digan. El mismo
# visor pinta un mapa de módulos sin enterarse de que existen las extensiones.
# Las familias son por USO, no por extensión suelta: al mirar una carpeta uno busca «los
# documentos» o «las fotos», no «los .docx».
FORMATOS = [
    ("documento",   "#7aa2ff", (".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".tex")),
    ("pdf",         "#e0564f", (".pdf",)),
    ("hoja",        "#00b894", (".xls", ".xlsx", ".ods", ".csv", ".tsv")),
    ("presentación", "#f0a04b", (".ppt", ".pptx", ".odp", ".key")),
    ("imagen",      "#c77dff", (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif",
                                ".tiff", ".svg", ".heic", ".ico", ".psd")),
    ("vídeo",       "#ff6ec7", (".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".m4v")),
    ("audio",       "#5ff0d0", (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".mid")),
    ("código",      "#4fe3ff", (".py", ".js", ".mjs", ".ts", ".tsx", ".html", ".css", ".java",
                                ".c", ".h", ".cpp", ".cs", ".go", ".rs", ".rb", ".php",
                                ".sh", ".bat", ".ps1", ".sql", ".ipynb")),
    ("datos",       "#8b7bff", (".json", ".xml", ".yaml", ".yml", ".db", ".sqlite", ".jsonl",
                                ".parquet", ".pkl", ".npy", ".gz")),
    ("comprimido",  "#c9a227", (".zip", ".rar", ".7z", ".tar", ".xz", ".bz2", ".iso")),
    ("fuente tipográfica", "#9aa4ae", (".ttf", ".otf", ".woff", ".woff2")),
]
CLASE_CARPETA = ("carpeta", "#e6b422")
CLASE_OTROS = ("otro formato", "#79808a")


ANCHO_FONDO = 1920       # a lo que se reescala el fondo antes de servirlo


def fondo_del_escritorio(destino, avisar=print):
    """Copia el fondo de pantalla del sistema dentro de la escena, reescalado. Devuelve el
    dict que va en `nodos.json` (o None si no se puede). Se reescala a la fuerza: un fondo
    de escritorio puede pesar decenas de MB, y servir eso junto a un modelo de manos de
    27 MB tira el arranque a la basura por una imagen que se ve detrás de todo, con un
    velo encima. Solo Windows (en macOS/Linux el fondo no se pregunta igual, y aquí no se
    adivina). Se COPIA, no se enlaza: el navegador no puede leer un fichero de fuera de lo
    que se sirve, y la escena debe seguir igual aunque luego cambie el fondo real."""
    if sys.platform != "win32":
        avisar("sin dato: el fondo del escritorio solo se sabe pedir en Windows")
        return None
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(520)
        if not ctypes.windll.user32.SystemParametersInfoW(0x0073, 520, buf, 0):
            avisar("sin dato: el sistema no ha dicho cuál es el fondo de escritorio")
            return None
        origen = buf.value
    except Exception as e:
        avisar("sin dato: no se pudo preguntar por el fondo (%s)" % e)
        return None
    if not origen or not os.path.isfile(origen):
        avisar("sin dato: el fondo que declara el sistema no está en %r" % origen)
        return None
    try:
        from PIL import Image
    except ImportError:
        avisar("sin dato: hace falta Pillow para reescalar el fondo")
        return None
    # Pillow se niega a abrir imágenes enormes por si son una bomba de descompresión, y con
    # razón: es una defensa contra un fichero que llega de fuera. Aquí no llega de fuera —lo
    # ha dicho el propio sistema operativo y está en el disco del usuario, puesto por él como
    # fondo de pantalla— así que el límite se levanta SOLO para esta lectura y se devuelve
    # donde estaba; levantarlo para todo el proceso sí sería quitar la defensa.
    tope_antes = Image.MAX_IMAGE_PIXELS
    try:
        Image.MAX_IMAGE_PIXELS = None
        im = Image.open(origen)
        ancho_original, alto_original = im.size
        im = im.convert("RGB")
        if im.width > ANCHO_FONDO:
            im = im.resize((ANCHO_FONDO, max(1, round(im.height * ANCHO_FONDO / im.width))),
                           Image.LANCZOS)
        salida = os.path.join(destino, "fondo.jpg")
        im.save(salida, "JPEG", quality=82, optimize=True)
    except Exception as e:
        avisar("sin dato: no se pudo preparar el fondo (%s)" % e)
        return None
    finally:
        Image.MAX_IMAGE_PIXELS = tope_antes
    avisar("fondo del escritorio: %dx%d (%d bytes) -> fondo.jpg %dx%d (%d bytes)"
           % (ancho_original, alto_original, os.path.getsize(origen),
              im.width, im.height, os.path.getsize(salida)))
    # Velo a 0,45: por debajo, los nombres (casi en blanco) se leen sobre el escritorio; por
    # encima, la foto deja de distinguirse del negro. Lo declara la escena para poder
    # cambiarlo sin tocar la plantilla.
    return {"fichero": "fondo.jpg", "velo": 0.45,
            "de_donde": "el fondo de pantalla del sistema, preguntado con "
                        "SystemParametersInfoW(SPI_GETDESKWALLPAPER)",
            "que_se_le_hizo": "reescalado a %d px de ancho y guardado como JPEG de calidad 82 "
                              "(el original eran %d bytes)"
                              % (im.width, os.path.getsize(origen))}


def _es_oculto(ruta):
    """`True` si el sistema marca esto como oculto o de sistema. En Windows no basta con
    mirar si el nombre empieza por punto: `desktop.ini`, `Thumbs.db` y los enlaces de
    sistema no llevan punto delante y aun así el Explorador no los enseña, porque no son
    contenido de la carpeta — son fontanería de la carpeta. Enseñarlos llena la escena de
    cosas que el usuario no ha puesto ahí y que no puede abrir para nada.
    Fuera de Windows `st_file_attributes` no existe y esto devuelve False: allí el punto
    delante, que ya se filtra aparte, es la convención."""
    try:
        atrib = os.stat(ruta).st_file_attributes
    except (OSError, AttributeError):
        return False
    OCULTO, SISTEMA = 0x2, 0x4
    return bool(atrib & (OCULTO | SISTEMA))


def _clase_de(nombre):
    """La familia de formato de un fichero por su extensión, y su color. Lo que no está en
    la tabla NO se adivina: cae en «otro formato», que es un dato honesto, no un cajón."""
    ext = os.path.splitext(nombre)[1].lower()
    for nombre_clase, color, extensiones in FORMATOS:
        if ext in extensiones:
            return nombre_clase, color
    return CLASE_OTROS


def de_arbol(carpeta, tope=TOPE, hondura=2, techo=None):
    """Una carpeta del disco, como un explorador: los ficheros son bolas y las carpetas que
    no caben son bolas en las que se puede ENTRAR.

    Por qué no se vuelca todo: una carpeta con muchos miles de ficheros y niveles se
    convertiría en una nube de puntos sin nombre legible, porque el anti-solape de
    etiquetas ya no coloca casi ninguna. Se baja `hondura` niveles, y toda carpeta más
    honda se convierte en UNA bola con su cuenta de descendientes y `accion: entrar` —
    nunca se trunca en silencio (la peor respuesta: el edificio parecería completo sin
    estarlo); lo que no se dibuja queda detrás de una bola que dice cuánto lleva dentro.

    Los niveles siguen siendo DECRETADOS —la profundidad de carpeta es una decisión de quien
    monta, no una medida de la fuente— y así se escribe en la procedencia.
    """
    carpeta = os.path.abspath(carpeta)
    techo = os.path.abspath(techo) if techo else carpeta
    if not os.path.isdir(carpeta):
        return None, "sin dato: no existe la carpeta %s" % carpeta
    raiz_nombre = os.path.basename(carpeta.rstrip(chr(92) + chr(47))) or carpeta
    items, cerradas, recorte, ocultos = [], 0, 0, 0

    for aqui, dirs, ficheros in os.walk(carpeta):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUIR and not d.startswith("."))
        rel = os.path.relpath(aqui, carpeta)
        hondo = 0 if rel == "." else rel.count(os.sep) + 1
        padre = None if rel == "." else rel.replace("\\", "/")

        if hondo >= hondura:
            # de aquí no se baja: esta carpeta entera se resume en una bola
            dirs[:] = []

        for f in sorted(ficheros):
            if len(items) >= tope:
                recorte += 1
                continue
            ruta = os.path.join(aqui, f)
            if _es_oculto(ruta):
                ocultos += 1
                continue
            try:
                bytes_ = os.path.getsize(ruta)
            except OSError:
                bytes_ = 0
            ident = (padre + "/" + f) if padre else f
            items.append({
                "id": ident, "corto": f, "completo": ident,
                "grupo": hondo, "padre": padre,
                "cuenta": bytes_, "medidas": {"bytes": bytes_},
                "descripcion": "", "descripcion_como": "sin dato con fuente",
                "descripcion_fuente": "", "marcas": [],
                "clase": _clase_de(f)[0], "forma": "esfera",
                "accion": {"tipo": "abrir", "destino": ident},
            })

        if hondo >= hondura:
            continue
        for d in list(dirs):
            if hondo + 1 < hondura:
                continue          # en esa se va a entrar de verdad; no se resume
            dentro = os.path.join(aqui, d)
            cuantos = _cuenta_dentro(dentro)
            ident = ((padre + "/" + d) if padre else d)
            items.append({
                "id": ident, "corto": d + "/", "completo": ident,
                "grupo": hondo + 1, "padre": padre,
                "cuenta": max(1, cuantos), "medidas": {"ficheros dentro": cuantos},
                "descripcion": "", "descripcion_como": "sin dato con fuente",
                "descripcion_fuente": "", "marcas": ["carpeta"],
                "clase": CLASE_CARPETA[0], "forma": "cubo",
                "accion": {"tipo": "entrar", "destino": ident},
            })
            cerradas += 1

    # Volver arriba. Un explorador en el que se entra y no se sale no es un explorador:
    # es una trampa. Sube hasta el TECHO —la carpeta con la que se abrió— y ni un palmo más.
    arriba = os.path.dirname(carpeta)
    if carpeta != techo and os.path.isdir(arriba) and             os.path.commonpath([arriba, techo]) == techo:
        items.insert(0, {
            "id": "..", "corto": "↑ " + (os.path.basename(arriba) or arriba),
            "completo": arriba, "grupo": 0, "padre": None,
            "cuenta": 1, "medidas": {},
            "descripcion": "", "descripcion_como": "sin dato con fuente",
            "descripcion_fuente": "", "marcas": ["subir"],
            "clase": CLASE_CARPETA[0], "forma": "cubo",
            "accion": {"tipo": "entrar", "destino": ".."},
        })

    if not items:
        return None, "sin dato: no hay nada que enseñar en %s" % carpeta

    hondos = sorted({it["grupo"] for it in items})
    mapa_h = {h: i for i, h in enumerate(hondos)}
    for it in items:
        it["grupo"] = mapa_h[it["grupo"]]
    # El nivel 0 SÍ tiene nombre propio: es la carpeta que se está mirando. Los de más
    # adentro no lo tienen —a un nivel de profundidad hay muchas carpetas distintas, no
    # una—, así que se nombran por lo que de verdad son: lo que hay dentro de aquella.
    # Ponerle a todos el nombre de una carpeta sería decir algo que no es cierto.
    grupos = [{"id": mapa_h[h], "nombre": (raiz_nombre if h == 0
                                           else "dentro de %s" % raiz_nombre if h == 1
                                           else "%d niveles dentro de %s" % (h, raiz_nombre)),
               "color": COLORES[h % len(COLORES)], "padre": None,
               "grupo_como": "decretado", "grupo_fuente": "profundidad de carpeta",
               "color_como": "decretado"} for h in hondos]

    # La paleta de clases: SOLO las que de verdad han salido en esta carpeta, ordenadas por
    # cuántas hay. Meter las once familias siempre llenaría la leyenda de formatos que no
    # están, que es decir algo que no se ha medido.
    cuenta_clase = {}
    for it in items:
        cuenta_clase[it["clase"]] = cuenta_clase.get(it["clase"], 0) + 1
    color_de_clase = dict([(n, c) for n, c, _ in FORMATOS] + [CLASE_CARPETA, CLASE_OTROS])
    clases = [{"id": n, "nombre": n, "n": cuenta_clase[n],
               "color": color_de_clase.get(n, CLASE_OTROS[1]),
               "color_como": "decretado", "color_fuente": "familia de formato por extensión"}
              for n in sorted(cuenta_clase, key=lambda k: (-cuenta_clase[k], k))]

    datos = {
        "generado_por": "abyss/kinetico.py · arbol",
        "clases": clases,
        "titulo": raiz_nombre,
        "raiz": carpeta,
        "techo": techo,
        "procedencia": {
            "origen": "la carpeta %s, recorrida con os.walk" % raiz_nombre,
            "recorrido": ("se saltan %s, todo lo que empieza por punto, y %d que el sistema "
                          "marca como ocultos o de sistema (desktop.ini y parecidos: son "
                          "fontanería de la carpeta, no contenido)"
                          % (", ".join(sorted(EXCLUIR)), ocultos)),
            "niveles": "la planta es la PROFUNDIDAD de carpeta: decretada por quien monta, "
                       "no medida de la fuente",
            "color": "por FAMILIA DE FORMATO, decretada por la extensión del nombre "
                     "(ver FORMATOS en kinetico.py): no se abre ningún fichero ni se mira "
                     "su contenido, así que un .txt que en realidad sea otra cosa se pinta "
                     "como texto. Lo que no está en la tabla cae en «otro formato»",
            "forma": "cubo las carpetas, esfera los ficheros: decretado, no medido",
            "colocacion": "rejilla por planta y bloque por carpeta, calculada una vez: "
                          "mismas posiciones siempre",
            "cuenta": "el tamaño de una bola de fichero es su TAMAÑO EN BYTES; el de una "
                      "carpeta cerrada, CUÁNTOS FICHEROS lleva dentro",
            "descripciones": "ninguna: un fichero suelto no trae texto que contar",
            "aristas": "ninguna a propósito: la contención ya la dice la posición",
            "recorte": ("nada: cabe todo" if not (recorte or cerradas) else
                        "se bajaron %d niveles; %d carpetas quedan cerradas, cada una "
                        "diciendo cuántos ficheros lleva dentro%s"
                        % (hondura, cerradas,
                           "" if not recorte else "; y %d ficheros no caben en el tope de %d"
                           % (recorte, tope))),
        },
        "rotulos": {
            "cosas": "cosas", "grupos": "niveles",
            "salientes": "", "entrantes": "",
            "lista_salientes": "", "lista_entrantes": "",
            "sin_descripcion": "sin dato con fuente: un fichero no trae descripción",
            "sin_conexiones": "aquí no hay conexiones: lo que contiene a qué lo dice la posición",
            "cuenta_de": "bytes (ficheros) · ficheros dentro (carpetas)",
            "aviso_grupos": "las plantas son la profundidad de carpeta: una decisión de quien "
                            "montó esto, no una medida del origen",
            "marcas": {"carpeta": "carpeta cerrada: cierra el puño para entrar",
                       "subir": "la carpeta de arriba"},
        },
        "vista": {"celda": CELDA, "alto_planta": ALTO_PLANTA, "tope_etiquetas": 110},
        "disposicion": {"forma": "plantas_bloques" if len(grupos) > 1 else "plano"},
        "grupos": grupos, "items": items, "aristas": [],
    }
    return coloca(datos), None


# ── el montaje ──────────────────────────────────────────────────────────────
def monta(datos, destino, manos=True, avisar=print):
    os.makedirs(destino, exist_ok=True)
    with io.open(os.path.join(destino, "nodos.json"), "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=1)

    glifos = glifos_de(datos)
    atlas, met = atlas_sdf(glifos)
    if atlas is None:
        avisar(met["error"])
        return False
    from PIL import Image
    Image.fromarray(atlas).save(os.path.join(destino, "fuente_sdf.png"))
    with io.open(os.path.join(destino, "fuente_sdf.json"), "w", encoding="utf-8") as fh:
        json.dump(met, fh, ensure_ascii=False)
    avisar("tipografía: %d glifos · atlas %dx%d px · con %s"
           % (len(glifos), atlas.shape[1], atlas.shape[0], met["tipografia"]))
    if met["recortados"]:
        avisar("aviso: %d glifos no caben en su casilla (%s)"
               % (len(met["recortados"]), "".join(met["recortados"])))

    shutil.copy2(os.path.join(PLANTILLAS, "kinetico.html"), os.path.join(destino, "index.html"))
    shutil.copy2(os.path.join(PLANTILLAS, "gestos_comun.js"),
                 os.path.join(destino, "gestos_comun.js"))
    shutil.copy2(os.path.join(VENDOR, "three.min.js"), os.path.join(destino, "three.min.js"))
    mp = os.path.join(VENDOR, "mp")
    if manos and os.path.isdir(mp):
        destino_mp = os.path.join(destino, "mp")
        if not os.path.isdir(destino_mp):
            shutil.copytree(mp, destino_mp)
        avisar("mp/: copiado (manos activas)")
    elif manos:
        avisar("sin mp/ en vendor: el visor funcionará con el ratón, no con la mano "
               "(python instalar.py --manos lo baja)")
    return True


def _cli(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 1
    modo, resto = argv[0], argv[1:]
    def valor(bandera, defecto=None):
        return resto[resto.index(bandera) + 1] if bandera in resto and resto.index(bandera) + 1 < len(resto) else defecto

    if modo == "estanteria":
        return _cli_estanteria(resto, valor)
    salida = valor("--salida") or os.path.join(tempfile.gettempdir(), "abyss", "kinetico_montado")
    tope = int(valor("--tope", TOPE))
    hondura = int(valor("--hondura", 2))
    if modo == "arbol":
        if not resto or resto[0].startswith("--"):
            print("uso: kinetico.py arbol <carpeta> [--fondo-escritorio]"); return 1
        datos, err = de_arbol(resto[0], tope, hondura)
    elif modo == "datos":
        if not resto or resto[0].startswith("--"):
            print("uso: kinetico.py datos <nodos.json>"); return 1
        try:
            datos, err = json.load(io.open(resto[0], encoding="utf-8")), None
        except (OSError, ValueError) as e:
            datos, err = None, "sin dato: no puedo leer %s (%s)" % (resto[0], e)
    else:
        print("modo desconocido: %s (arbol | datos | estanteria)" % modo); return 1
    if err:
        print(err); return 2

    if not monta(datos, salida, manos="--sin-manos" not in resto):
        return 2
    # El fondo va DESPUÉS de montar: escribe dentro de la carpeta, que hasta aquí no existe.
    # Y se vuelve a escribir el nodos.json, porque la escena tiene que declarar su fondo:
    # una imagen que sale en pantalla sin decir de dónde viene es exactamente lo que este
    # paquete no hace.
    if "--fondo-escritorio" in resto:
        f = fondo_del_escritorio(salida)
        if f:
            datos["fondo"] = f
            datos.setdefault("procedencia", {})["fondo"] = (
                "%s; %s" % (f["de_donde"], f["que_se_le_hizo"]))
            with io.open(os.path.join(salida, "nodos.json"), "w", encoding="utf-8") as fh:
                json.dump(datos, fh, ensure_ascii=False)
    print("montado: %s (%d cosas, %d grupos, %d aristas)"
          % (salida, len(datos["items"]), len(datos["grupos"]), len(datos["aristas"])))
    if "--solo-montar" in resto:
        return 0

    try:
        from kinetico_servidor import sirve
    except ImportError:
        from abyss.kinetico_servidor import sirve

    def remontar(destino):
        """Entrar en una carpeta es volver a montar la escena ahí, en el mismo sitio: mismo
        puerto, misma ventana, mismo permiso de cámara. La página solo tiene que recargar."""
        nuevos, e = de_arbol(destino, tope, hondura, techo=os.path.abspath(resto[0]))
        if e:
            raise RuntimeError(e)
        monta(nuevos, salida, manos="--sin-manos" not in resto, avisar=lambda *a: None)

    return sirve(salida, int(valor("--puerto", PUERTO)), abrir="--sin-abrir" not in resto,
                 remontar=(remontar if modo == "arbol" else None))


def _cli_estanteria(resto, valor):
    if not resto or resto[0].startswith("--"):
        print("uso: kinetico.py estanteria <carpeta> [--fichas fichas.json] [--titulo T] [--fondo imagen]")
        return 1
    try:
        from . import estanteria
    except ImportError:
        import estanteria
    # su propio sitio de montaje: abrir una estantería no pisa el explorador que esté abierto
    salida = valor("--salida") or os.path.join(tempfile.gettempdir(), "abyss", "kinetico_estanteria")
    fondo = "escritorio" if "--fondo-escritorio" in resto else valor("--fondo")
    datos, portadas = estanteria.de_estanteria(resto[0], fichas=valor("--fichas"),
                                               hondura=int(valor("--hondura", estanteria.HONDURA)),
                                               titulo=valor("--titulo"),
                                               fondo=None if fondo == "escritorio" else fondo)
    if datos is None:
        print(portadas)
        return 2
    if not estanteria.monta(datos, portadas, salida, manos="--sin-manos" not in resto, fondo=fondo):
        return 2
    con = sum(1 for it in datos["items"] if it["fuente"])
    dibujadas = sum(1 for it in datos["items"] if it["aviso_portada"].startswith("portada dibujada"))
    print("montado: %s (%d obras, %d con ficha con fuente, %d portadas dibujadas, %d atlas)"
          % (salida, len(datos["items"]), con, dibujadas, datos["atlas"]))
    for it in datos["items"]:
        print("  %-60s %s" % (it["id"][:60], it["aviso_portada"]))
    if "--solo-montar" in resto:
        return 0
    try:
        from kinetico_servidor import sirve
    except ImportError:
        from abyss.kinetico_servidor import sirve
    return sirve(salida, int(valor("--puerto", PUERTO)), abrir="--sin-abrir" not in resto, remontar=None)


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
