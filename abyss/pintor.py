# -*- coding: utf-8 -*-
"""Pintor por pinceladas («Monet»): reproduce una foto como un cuadro, de pincel grueso a fino.

Método (Hertzmann 1998, simplificado): por cada radio de pincel se difumina la referencia a ese
radio, se mide el error entre lienzo y referencia por celdas y, donde el error supera el umbral de
la capa, se pone una pincelada del color de la referencia, perpendicular al gradiente (sigue el
contorno) y con curvatura suave. Las capas gruesas dan la mancha; las finas, pestañas y mechones.
Motor único: los estilos de abajo son el MISMO bucle con otro dict de parámetros, no un algoritmo
distinto.

Uso:
    python pintor.py <foto> [--salida DIR] [--ancho N] [--alta] [--suave [2]] [--acabado]
                     [--html] [--html-r-min N] [--semilla N] [--nombre base]
                     [--estilo oleo|impresionista|acuarela|pastel|carbon|tinta]
                     [--radios 28,14,7,4,2] [--umbral 60,45,32,24,18] [--longitud 12,12,10,8,6]
                     [--alfa 0.42] [--jitter-color 14] [--jitter-rumbo 0.35] [--papel #f9f7f0]
                     [--saturacion 1.18] [--luz 1.05] [--mezcla-blanco 0.28]

--suave [N]: pinta a N veces el tamaño (2 por defecto) y reduce al final: pinceladas sin dientes
de sierra; cuesta unas N² veces más en el dibujo. --acabado: capa final extra de 1 px con umbral
más bajo que repasa lo que quedó sin cubrir. Las dos se miden: el error medio se imprime siempre.
Ambas valen para cualquier --estilo (una capa más, o un tamaño mayor, del mismo motor).

## Estilos: un dict de parámetros, no un algoritmo distinto

`--estilo` elige un dict de partida (tabla abajo); cualquier bandera suelta (`--radios`,
`--umbral`, `--longitud`, `--alfa`, `--jitter-color`, `--jitter-rumbo`, `--papel`,
`--saturacion`, `--luz`, `--mezcla-blanco`) pisa SOLO esa clave del dict elegido, tanto por
CLI como llamando a `pintar(..., estilo="acuarela", alfa=0.3)`. `--radios`/`--umbral` van en
píxel/error; `--longitud` en radios de pincel; `--jitter-rumbo` en radianes; `--papel` en
`#rrggbb`. `--alfa` es la opacidad de CADA capa entera (no de cada trazo): la capa se pinta en
una imagen aparte a opacidad plena y se compone sobre el lienzo con ese alfa de una vez — así
sale la transparencia por capas de la acuarela sin que los trazos se acumulen unos sobre otros
dentro de la misma capa. `--saturacion`/`--luz`/`--mezcla-blanco` (con blanco: pastel/acuarela)
se aplican a la foto ANTES de pintar, con `PIL.ImageEnhance` y `Image.blend`.

| estilo         | radios         | umbral         | longitud    | alfa | jit.color | jit.rumbo | papel            | sat. | luz  | mezcla blanco |
|----------------|----------------|----------------|-------------|------|-----------|-----------|------------------|------|------|---------------|
| oleo (defecto) | 28,14,7,4,2 ¹  | 60,45,32,24,18¹| 12,12,10,8,6| 1.0  | 0         | 0.0       | #08 06 07 (FONDO)| 1.0  | 1.0  | 0.0           |
| impresionista  | 22,12,7,4      | 55,40,30,22    | 5,5,4,4     | 0.95 | 14        | 0.35      | #ece4d6          | 1.18 | 1.05 | 0.0           |
| acuarela       | 40,22,12,7     | 50,38,28,22    | 16,14,10,8  | 0.42 | 6         | 0.15      | #faf7f0          | 0.95 | 1.10 | 0.28          |
| pastel         | 30,16,9,5      | 52,40,30,24    | 8,8,6,5     | 0.70 | 8         | 0.25      | #f5f0e8          | 0.65 | 1.12 | 0.18          |
| carbon ²       | 6,3,2,1        | 26,20,16,12    | 7,6,5,4     | 0.60 | 0         | 0.50      | #dcdbdb          | 0.0  | 1.0  | 0.0           |
| tinta ³        | 3,1            | 70,55          | 6,4         | 1.0  | 0         | 0.0       | #ffffff          | 0.0  | 1.0  | 0.0           |

¹ "oleo" hereda de `CAPAS_NORMAL`/`CAPAS_ALTA` (7 capas con `--alta`) — es el pincel de siempre.
² carbon: la mitad de las pinceladas (al azar) cruza 45° sobre el rumbo normal — tramado, no un
  algoritmo nuevo — y al acabar todas las capas hay un difuminado final suave (radio 1, esfumino)
  sobre el lienzo entero. ³ tinta: papel blanco + umbral alto ⇒ donde la referencia ya es clara el
  error contra el papel blanco no llega al umbral y esa zona se queda sin pintar (blanco de
  verdad, no un blanco pintado).

El JSON de trazos guarda el estilo, el papel y el alfa para que `video_pintura.py` reproduzca el
cuadro igual (papel de fondo, cada capa compuesta con su alfa). Para no cambiar la forma de las
otras tres claves del `.json.gz` (`W`, `H`, `trazos` — de las que ya dependen pruebas y guiones),
esos tres datos viajan DENTRO de `"radios"`, que pasa de ser una lista a un dict:
`"radios": {"lista": [...], "estilo": "acuarela", "papel": "#faf7f0", "alfa": 0.42}`.
Un `.json.gz` viejo (con `"radios"` como lista) se sigue leyendo: sin ese dict,
`video_pintura.py` asume `estilo="oleo"`, el papel oscuro de siempre y alfa 1.0.

Salida (en --salida; por defecto, junto a la foto):
    <base>_pintada.png        el cuadro
    <base>_trazos.json.gz     todas las pinceladas: {"W","H","radios":{"lista",...,"estilo",
                              "papel","alfa"},"trazos":[[radio,"#rrggbb",[x0,y0,x1,y1,...]], ...]}
    <base>_pintor.html        con --html: repinta las pinceladas en el navegador, con control de
                              velocidad; solo pinceles >= --html-r-min (2 por defecto) para que pese poco;
                              pinta sobre el PAPEL del estilo (no el fondo oscuro fijo de oleo) y, si el
                              estilo compone por capas con alfa < 1 (impresionista/acuarela/pastel/
                              carbon), compone cada capa (grupo de radio) de una vez con ese alfa sobre
                              lo ya pintado, igual que `pintar()` y `video_pintura.py`

--alta: anchura nativa de la foto (tope 3000 px) y pincel de 1 px; tarda minutos y el .json.gz
pasa de 10 MB. Sin --alta: 1400 px de ancho y pincel mínimo de 2 px (menos de un minuto). --alta
solo cambia la tabla de capas de "oleo" (`CAPAS_ALTA`, más fina); los demás estilos pintan con su
propia tabla de radios a cualquier ancho.

Depende de Pillow y numpy (ModuleNotFoundError al importar si faltan: sin fallback silencioso).
No sale nada de la máquina: la foto no viaja a ningún servicio. Si la foto no existe o no se
puede leer, la CLI imprime «sin cuadro: <motivo>» y sale con código 2 (no revienta con una traza).
"""
import gzip
import json
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

CAPAS_NORMAL = ([28, 14, 7, 4, 2], [60, 45, 32, 24, 18], [12, 12, 10, 8, 6])
CAPAS_ALTA = ([40, 20, 10, 5, 3, 2, 1], [60, 45, 32, 24, 18, 14, 12], [12, 12, 10, 8, 6, 5, 4])
ANCHO_ALTA_MAX = 3000
FONDO = (8, 6, 7)

# Estilos: motor único (el bucle de pintar() más abajo), cada uno un dict de parámetros —
# ver la tabla del docstring. "oleo" no lleva radios/umbral/longitud propios: hereda de
# CAPAS_NORMAL/CAPAS_ALTA según --alta, que es el comportamiento de siempre.
ESTILOS = {
    "oleo": dict(alfa=1.0, jitter_color=0, jitter_rumbo=0.0, papel=FONDO,
                 saturacion=1.0, luz=1.0, mezcla_blanco=0.0),
    "impresionista": dict(radios=[22, 12, 7, 4], umbral=[55, 40, 30, 22], longitud=[5, 5, 4, 4],
                           alfa=0.95, jitter_color=14, jitter_rumbo=0.35, papel=(236, 228, 214),
                           saturacion=1.18, luz=1.05, mezcla_blanco=0.0),
    "acuarela": dict(radios=[40, 22, 12, 7], umbral=[50, 38, 28, 22], longitud=[16, 14, 10, 8],
                      alfa=0.42, jitter_color=6, jitter_rumbo=0.15, papel=(250, 247, 240),
                      saturacion=0.95, luz=1.1, mezcla_blanco=0.28),
    "pastel": dict(radios=[30, 16, 9, 5], umbral=[52, 40, 30, 24], longitud=[8, 8, 6, 5],
                   alfa=0.7, jitter_color=8, jitter_rumbo=0.25, papel=(245, 240, 232),
                   saturacion=0.65, luz=1.12, mezcla_blanco=0.18),
    # "Estilos añadidos" (7-sep 07:54, petición del usuario: "el David a carbón"):
    "carbon": dict(radios=[6, 3, 2, 1], umbral=[26, 20, 16, 12], longitud=[7, 6, 5, 4],
                   alfa=0.6, jitter_color=0, jitter_rumbo=0.5, papel=(220, 219, 219),
                   saturacion=0.0, luz=1.0, mezcla_blanco=0.0,
                   angulo_cruzado=math.pi / 4, difuminado_final=1),
    "tinta": dict(radios=[3, 1], umbral=[70, 55], longitud=[6, 4],
                  alfa=1.0, jitter_color=0, jitter_rumbo=0.0, papel=(255, 255, 255),
                  saturacion=0.0, luz=1.0, mezcla_blanco=0.0),
}
# claves que un ajuste suelto (CLI o kwarg) puede pisar del dict de estilo elegido
_CLAVES_ESTILO = {"radios", "umbral", "longitud", "alfa", "jitter_color", "jitter_rumbo", "papel",
                   "saturacion", "luz", "mezcla_blanco", "angulo_cruzado", "difuminado_final"}

_HTML = """<!doctype html><html lang="es"><head><meta charset="utf-8"><title>%(titulo)s</title>
<style>html,body{margin:0;background:#050405;color:#cfc8c2;font:14px system-ui}
#c{display:block;margin:12px auto;max-width:96vw;height:auto;box-shadow:0 0 40px #000}
#b{text-align:center;padding:6px} button{background:#2a2226;color:#eee;border:0;padding:6px 14px;margin:0 4px;border-radius:6px;cursor:pointer}
input{vertical-align:middle}</style></head><body>
<div id="b"><button id="go">Pintar</button><button id="rs">Borrar</button> velocidad <input id="v" type="range" min="1" max="400" value="60"> <span id="n"></span></div>
<canvas id="c" width="%(W)d" height="%(H)d"></canvas>
<script>
const T=%(trazos)s;
const PAPEL=%(papel)s,ALFA=%(alfa)s;  // del estilo: antes esta plantilla los ignoraba
const c=document.getElementById('c'),x=c.getContext('2d'),n=document.getElementById('n'),v=document.getElementById('v');
x.lineCap='round';x.lineJoin='round';let i=0,run=false;
// alfa<1 (impresionista/acuarela/pastel/carbon): cada capa (grupo de radio) se pinta aparte y se
// compone de una vez con ALFA sobre el papel, como pintar()/video_pintura.py — así los trazos que
// se solapan DENTRO de una misma capa no se acumulan. alfa=1 (oleo/tinta): dibuja directo, como antes.
let capaC=null,capaX=null,capaR=null;
function nuevaCapa(r){capaC=document.createElement('canvas');capaC.width=c.width;capaC.height=c.height;capaX=capaC.getContext('2d');capaX.lineCap='round';capaX.lineJoin='round';capaR=r;}
function flushCapa(){if(capaC){x.globalAlpha=ALFA;x.drawImage(capaC,0,0);x.globalAlpha=1;}capaC=null;capaX=null;capaR=null;}
function borra(){x.fillStyle=PAPEL;x.fillRect(0,0,c.width,c.height);i=0;n.textContent='';capaC=null;capaX=null;capaR=null;}
function traza(t){let ctx=x;if(ALFA<0.999){if(t[0]!==capaR)nuevaCapa(t[0]);ctx=capaX;}ctx.strokeStyle=t[1];ctx.lineWidth=2*t[0];ctx.beginPath();const p=t[2];ctx.moveTo(p[0],p[1]);for(let k=2;k<p.length;k+=2)ctx.lineTo(p[k],p[k+1]);ctx.stroke();}
function paso(){if(!run)return;const k=+v.value;for(let j=0;j<k&&i<T.length;j++,i++)traza(T[i]);n.textContent=i+' / '+T.length+' pinceladas';if(i<T.length){requestAnimationFrame(paso);}else{if(ALFA<0.999)flushCapa();run=false;}}
document.getElementById('go').onclick=()=>{if(i>=T.length)borra();run=true;paso();};
document.getElementById('rs').onclick=()=>{run=false;borra();};
borra();
</script></body></html>"""


def _cargar(ruta, ancho, alta):
    img = Image.open(ruta)
    if "A" in img.getbands():  # bordes transparentes: sobre negro
        fondo = Image.new("RGBA", img.size, (0, 0, 0, 255))
        fondo.alpha_composite(img.convert("RGBA"))
        img = fondo
    img = img.convert("RGB")
    if ancho is None:
        ancho = min(img.width, ANCHO_ALTA_MAX) if alta else 1400
    alto = max(2, round(img.height * ancho / img.width))
    return img.resize((ancho, alto), Image.LANCZOS)


def _a_rgb(color):
    """Admite una tupla (r,g,b) o un "#rrggbb" (como llega de --papel en la CLI)."""
    if isinstance(color, str):
        c = color.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(int(v) for v in color)


def pintar(ruta, salida=None, ancho=None, alta=False, html=False, html_r_min=2, semilla=7,
           nombre=None, supermuestreo=1, acabado=False, estilo="oleo", avisar=print, **ajustes):
    """Pinta `ruta` con el estilo `estilo` y devuelve un dict con las rutas escritas y las medidas.

    ancho=None: 1400 px (o el nativo hasta 3000 con alta=True). estilo: "oleo" (por defecto),
    "impresionista", "acuarela", "pastel", "carbon" o "tinta" — tabla de parámetros en el
    docstring del módulo. `ajustes` pisa sueltas claves de ese estilo (`radios`, `umbral`,
    `longitud`, `alfa`, `jitter_color`, `jitter_rumbo`, `papel`, `saturacion`, `luz`,
    `mezcla_blanco`) sin cambiar las demás — un `TypeError` si llega una clave que ningún
    estilo usa (probable error de escritura).
    supermuestreo=2: pinta a doble tamaño y reduce al final (pinceladas sin dientes de sierra;
    cuesta ~4x en el dibujo). acabado=True: una capa final más de pincel de 1 px con umbral
    más bajo, que repasa lo que las capas anteriores dejaron sin cubrir. Las dos valen para
    cualquier estilo.
    Devuelve {"png", "trazos", "html" (o None), "pinceladas", "error_medio", "W", "H", "estilo"}."""
    if estilo not in ESTILOS:
        raise ValueError(f"estilo desconocido: {estilo!r} (usa uno de: {', '.join(ESTILOS)})")
    desconocidos = sorted(k for k in ajustes if k not in _CLAVES_ESTILO)
    if desconocidos:
        raise TypeError(f"ajustes de estilo desconocidos: {desconocidos} (válidos: {sorted(_CLAVES_ESTILO)})")

    ruta = os.path.abspath(ruta)
    salida = os.path.abspath(salida) if salida else os.path.dirname(ruta)
    os.makedirs(salida, exist_ok=True)
    base = nombre or os.path.splitext(os.path.basename(ruta))[0]

    p = dict(ESTILOS[estilo])
    if "radios" not in p:  # "oleo": la tabla de capas de siempre, según --alta
        r, u, m = (list(c) for c in (CAPAS_ALTA if alta else CAPAS_NORMAL))
        p["radios"], p["umbral"], p["longitud"] = r, u, m
    for clave, valor in ajustes.items():
        if valor is not None:
            p[clave] = valor

    radios = [int(v) for v in p["radios"]]
    umbrales = [float(v) for v in p["umbral"]]
    maxlen = [int(v) for v in p["longitud"]]
    if acabado:
        radios.append(1); umbrales.append(6 if alta else 10); maxlen.append(3)
    SS = max(1, int(supermuestreo))
    rnd = random.Random(semilla)

    img = _cargar(ruta, ancho, alta)
    saturacion = float(p.get("saturacion", 1.0))
    luz = float(p.get("luz", 1.0))
    mezcla_blanco = float(p.get("mezcla_blanco", 0.0))
    if saturacion != 1.0:
        img = ImageEnhance.Color(img).enhance(saturacion)
    if luz != 1.0:
        img = ImageEnhance.Brightness(img).enhance(luz)
    if mezcla_blanco > 0:
        img = Image.blend(img, Image.new("RGB", img.size, (255, 255, 255)), min(1.0, mezcla_blanco))

    W, H = img.size
    ref_all = np.asarray(img).astype(np.float32)
    papel = _a_rgb(p.get("papel", FONDO))
    lienzo = Image.new("RGB", (W * SS, H * SS), papel)
    trazos = []
    alfa_capa = float(p.get("alfa", 1.0))
    jitter_color = int(p.get("jitter_color", 0))
    jitter_rumbo = float(p.get("jitter_rumbo", 0.0))
    angulo_cruzado = p.get("angulo_cruzado")
    if angulo_cruzado is not None:
        angulo_cruzado = float(angulo_cruzado)

    def vista():  # el lienzo a tamaño de salida (reducido si hay supermuestreo)
        return lienzo if SS == 1 else lienzo.resize((W, H), Image.LANCZOS)

    for R, T, ML in zip(radios, umbrales, maxlen):
        ref = np.asarray(img.filter(ImageFilter.GaussianBlur(radius=max(1, R * 0.6)))).astype(np.float32)
        gy, gx = np.gradient(ref.mean(axis=2))
        err = np.abs(np.asarray(vista()).astype(np.float32) - ref).sum(axis=2)
        paso = max(2, R)
        celdas = []
        for y0 in range(0, H, paso):
            for x0 in range(0, W, paso):
                e = err[y0:y0 + paso, x0:x0 + paso]
                if e.size and e.mean() > T:
                    iy, ix = np.unravel_index(np.argmax(e), e.shape)
                    celdas.append((x0 + ix, y0 + iy))
        rnd.shuffle(celdas)
        # alfa < 1: la capa entera se pinta aparte (opaca) y se compone de una vez con su
        # alfa — así los trazos que se solapan DENTRO de la misma capa no se acumulan; es lo
        # que da la transparencia por capas de la acuarela/pastel/impresionista/carbón.
        capa_aparte = alfa_capa < 0.999
        capa = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0)) if capa_aparte else None
        d = ImageDraw.Draw(capa) if capa_aparte else ImageDraw.Draw(lienzo)
        for (x, y) in celdas:
            col = tuple(int(v) for v in ref[y, x])
            if jitter_color:
                col = tuple(max(0, min(255, c + rnd.randint(-jitter_color, jitter_color))) for c in col)
            col_np = np.array(ref[y, x], np.float32)
            cruzar = angulo_cruzado is not None and rnd.random() < 0.5  # carbon: tramado a 45°
            pts = [(float(x), float(y))]
            lx = ly = 0.0
            cx, cy = float(x), float(y)
            for i in range(ML):
                xi, yi = int(round(cx)), int(round(cy))
                if not (0 <= xi < W and 0 <= yi < H):
                    break
                if i > 0 and np.abs(ref[yi, xi] - col_np).sum() > 3 * T:
                    break  # el color de la referencia ya no es el de la pincelada
                g_x, g_y = gx[yi, xi], gy[yi, xi]
                mag = math.hypot(g_x, g_y)
                if mag < 0.5:
                    break
                dx, dy = -g_y / mag, g_x / mag  # perpendicular al gradiente: sigue el contorno
                if lx * dx + ly * dy < 0:
                    dx, dy = -dx, -dy
                if cruzar:
                    a = math.atan2(dy, dx) + angulo_cruzado
                    dx, dy = math.cos(a), math.sin(a)
                if jitter_rumbo:
                    a = math.atan2(dy, dx) + rnd.uniform(-jitter_rumbo, jitter_rumbo)
                    dx, dy = math.cos(a), math.sin(a)
                dx, dy = 0.6 * dx + 0.4 * lx, 0.6 * dy + 0.4 * ly  # curvatura suave
                n = math.hypot(dx, dy) or 1.0
                dx, dy = dx / n, dy / n
                cx, cy = cx + R * dx, cy + R * dy
                lx, ly = dx, dy
                pts.append((cx, cy))
            if len(pts) == 1:
                pts.append((x + 0.5, y + 0.5))
            RS = R * SS
            pts_s = [(px * SS, py * SS) for px, py in pts]
            relleno = col + (255,) if capa_aparte else col
            d.line(pts_s, fill=relleno, width=2 * RS, joint="curve")
            for pt in (pts_s[0], pts_s[-1]):
                d.ellipse([pt[0] - RS, pt[1] - RS, pt[0] + RS, pt[1] + RS], fill=relleno)
            trazos.append([int(R), "#%02x%02x%02x" % col, [round(float(v), 1) for pt in pts for v in pt]])
        if capa_aparte:
            a = capa.split()[3].point(lambda v: int(v * alfa_capa))
            capa.putalpha(a)
            lienzo = Image.alpha_composite(lienzo.convert("RGBA"), capa).convert("RGB")
        avisar(f"radio {R:2d}: {len(celdas):6d} pinceladas · error medio antes de la capa {err.mean():.1f}")

    difuminado_final = p.get("difuminado_final")
    if difuminado_final:  # carbon: esfumino sobre el lienzo entero, ya con todas las capas
        lienzo = lienzo.filter(ImageFilter.GaussianBlur(radius=float(difuminado_final) * SS))

    final = vista()
    png = os.path.join(salida, f"{base}_pintada.png")
    final.save(png)
    gz = os.path.join(salida, f"{base}_trazos.json.gz")
    with gzip.open(gz, "wt", encoding="utf-8") as fh:
        # "radios" lleva también estilo/papel/alfa (ver docstring): así video_pintura.py
        # reproduce el mismo papel de fondo y la misma composición por capas, sin tocar la
        # forma de las otras tres claves (W/H/trazos) de las que ya dependen otras pruebas.
        meta_radios = {"lista": radios, "estilo": estilo, "papel": "#%02x%02x%02x" % papel,
                       "alfa": round(alfa_capa, 3)}
        json.dump({"W": W, "H": H, "radios": meta_radios, "trazos": trazos}, fh, separators=(",", ":"))
    error = float(np.abs(np.asarray(final).astype(np.float32) - ref_all).sum(axis=2).mean())
    pagina = None
    if html:
        sel = [t for t in trazos if t[0] >= html_r_min]
        pagina = os.path.join(salida, f"{base}_pintor.html")
        with open(pagina, "w", encoding="utf-8") as fh:
            fh.write(_HTML % {"titulo": f"{base}, pintada", "W": W, "H": H,
                              "trazos": json.dumps(sel, separators=(",", ":")),
                              "papel": json.dumps("#%02x%02x%02x" % papel),
                              "alfa": round(alfa_capa, 3)})
        avisar(f"html: {pagina} ({len(sel)} pinceladas, pinceles >= {html_r_min} px)")
    avisar(f"pinceladas {len(trazos)} · error final medio {error:.1f} · {png}")
    return {"png": png, "trazos": gz, "html": pagina, "pinceladas": len(trazos),
            "error_medio": round(error, 2), "W": W, "H": H, "supermuestreo": SS, "acabado": bool(acabado),
            "estilo": estilo}


def _cli(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 1
    ruta = argv[0]
    opts = {"salida": None, "ancho": None, "alta": False, "html": False, "html_r_min": 2,
            "semilla": 7, "nombre": None, "supermuestreo": 1, "acabado": False, "estilo": "oleo"}
    ajustes = {}
    LISTAS_INT = {"radios", "longitud"}
    LISTAS_FLOAT = {"umbral"}
    FLOATS = {"alfa", "jitter_rumbo", "saturacion", "luz", "mezcla_blanco", "angulo_cruzado", "difuminado_final"}
    ENTEROS = {"jitter_color"}
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--alta":
            opts["alta"] = True
        elif a == "--html":
            opts["html"] = True
        elif a == "--acabado":
            opts["acabado"] = True
        elif a == "--suave":
            opts["supermuestreo"] = 2
            if i + 1 < len(argv) and argv[i + 1].isdigit():
                i += 1
                opts["supermuestreo"] = int(argv[i])
        elif a in ("--salida", "--ancho", "--html-r-min", "--semilla", "--nombre", "--estilo") and i + 1 < len(argv):
            i += 1
            v = argv[i]
            k = a[2:].replace("-", "_")
            opts[k] = int(v) if k in ("ancho", "html_r_min", "semilla") else v
        elif a.startswith("--") and a[2:].replace("-", "_") in _CLAVES_ESTILO and i + 1 < len(argv):
            i += 1
            v = argv[i]
            k = a[2:].replace("-", "_")
            if k in LISTAS_INT:
                ajustes[k] = [int(x) for x in v.split(",")]
            elif k in LISTAS_FLOAT:
                ajustes[k] = [float(x) for x in v.split(",")]
            elif k in FLOATS:
                ajustes[k] = float(v)
            elif k in ENTEROS:
                ajustes[k] = int(v)
            else:  # papel: "#rrggbb" tal cual
                ajustes[k] = v
        else:
            print("opción desconocida:", a)
            return 1
        i += 1
    try:
        r = pintar(ruta, **opts, **ajustes)
    except Exception as e:
        print(f"sin cuadro: {type(e).__name__} {e}")
        return 2
    print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:                       # la consola de Windows y la salida tienen que hablar
        from . import consola  # el mismo idioma: ver abyss/consola.py
    except ImportError:
        import consola
    consola.preparar()
    sys.exit(_cli(sys.argv[1:]))
