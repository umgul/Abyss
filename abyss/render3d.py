# -*- coding: utf-8 -*-
"""render3d: escenas 3D con three.js, embebidas en una página autocontenida.

Uso:
    python render3d.py <modelo.glb|.gltf|.obj|.stl|escena.json> [--html [salida.html]]
                        [--png [salida.png]] [--explosion 0.5] [--camara x,y,z] [--mirar x,y,z]
                        [--fondo #rrggbb] [--luz calida|fria|neutra] [--ancho 1600] [--alto 900]
                        [--holograma] [--acabado mate|estudio]

`--acabado` (por defecto `mate`, para no cambiarle el resultado a nadie que ya use este guion):
`mate` es el material plano de siempre (roughness 0.85/metalness 0.05, tres luces planas,
rejilla debajo). `estudio` reproduce, en un guion GENÉRICO (no sabe qué es un tornillo), la
receta que trae embebida `pintor_demo/tornillo/tornillo.html` (verificada leyendo ese fichero,
no de memoria): tono ACES (`toneMappingExposure=1.05`), sombras suaves (`PCFSoftShadowMap`),
un entorno de reflejo PROCEDURAL (un cubo con dos caras que llevan "ventanas" claras, dos
`<canvas>` 2D generados en la propia página — cero texturas cargadas de fuera), material
metálico (`metalness:1.0`), un suelo oscuro que recibe sombra, y SIN rejilla (se sigue
creando pero arranca oculta — el control de la página la puede volver a encender).

Las posiciones/tamaños de luces y suelo de esa receta están pensadas para SU tornillo, que
mide RADIO≈24,1538 (mismo CENTRO/RADIO que calcula `_bbox_escena()` de este propio guion,
aplicado a mano a los vértices que decodifiqué del `PIEZAS` embebido en ese HTML, con las
mismas transformaciones que aplica su guion: `grupo.position.z=-16.350` y
`tumbado.rotation.{y,z}`). Por eso aquí NO se copian esos números a pelo: se guarda cada
posición como `(posición_vieja − CENTRO_viejo) / RADIO_viejo` y, al renderizar, se multiplica
por el RADIO de la escena que se cargue — así una luz direccional (sin atenuación: lo único
que le importa es su DIRECCIÓN, que un reescalado uniforme no toca) queda en el mismo ángulo
sin importar el tamaño del modelo. El roughness 0,34/0,27 por pieza (plana/curva) del original
no se replica pieza a pieza: ese dato (qué grupo es una cara plana) no existe en el esquema
genérico de `render3d.py` — aquí todas las piezas del acabado `estudio` llevan un único
roughness intermedio (0,30); el aspecto facetado o liso de cada grupo lo sigue dando, igual
que en `mate`, el propio normal que trae el fichero de entrada, no el material.

`--html` es el modo normal (SIEMPRE se escribe la página, con o sin la bandera; ésta solo
sirve para elegir la ruta — a diferencia de `pintor.py`, aquí la página no es un extra
opcional: es el propio resultado que pide T3.1). Sin ruta explícita:
`<carpeta_de_la_entrada>/<base>_render3d.html`.

`--holograma` (T4.4): la MISMA escena, la MISMA cámara, en cuatro cuadrantes cuadrados
alrededor del centro de la pantalla (arriba/abajo/izquierda/derecha), cada uno con la
imagen espejada horizontalmente y girada 0°/180°/90°/-90° respectivamente — lo que pide
una pirámide de metacrilato apoyada en el centro de la pantalla (Pepper's ghost): cada cara
de la pirámide refleja el cuadrante que tiene delante hacia el centro, y la reflexión
espeja la imagen, de ahí el espejado. Es una CONVENCIÓN de composición 2D declarada aquí,
no verificada contra una pirámide física de verdad (no hay una en la máquina de
desarrollo): si la orientación no coincide con la tuya, cambia el signo de los ángulos, es
el único ajuste que hace falta. El fondo se fuerza a negro puro (`#000000`, ignora
`--fondo`) porque el efecto exige negro de verdad, no un gris oscuro. Sin dependencias
nuevas: los cuatro cuadrantes son cuatro copias 2D (`CanvasRenderingContext2D.drawImage`)
del MISMO fotograma que ya pinta el `<canvas>` WebGL de siempre (que se queda montado pero
oculto, como fuente); no se crean más contextos WebGL ni se vuelve a recorrer la escena
cuatro veces.

`--png [salida.png]`: además de la página, la abre en un navegador sin cabeza (Chrome o
Edge; se busca en las rutas habituales de Windows — `msedge.exe`/`chrome.exe` — y en el
PATH en Linux/macOS: `google-chrome`/`chromium`) y guarda una captura. Sin navegador
encontrado: «sin dato: no hay navegador sin cabeza», código 2 — la página HTML igualmente
se ha escrito (no depende del navegador). WebGL renderiza con aceleración si el navegador
la tiene; sin ella el navegador sin cabeza cae a SwiftShader (software) y tarda más — no
hay «fallback a WebGL» porque WebGL YA es el camino normal en la propia página.

Formatos de entrada:
  - `escena.json` (diagramas sin CAD, sin geometría real): `{"unidades": "m", "piezas":
    [{"nombre", "tipo": "caja|cilindro|esfera|texto|plano", "pos":[x,y,z], "tam":[...],
    "color":"#rrggbb", "grupo":"..."}], "camara": {"pos":[...], "mirar":[...], "fov":50}}`.
    `tam` según tipo: caja=[ancho,alto,fondo]; esfera=[radio]; cilindro=[radio_arriba,
    radio_abajo,altura] (con 2 valores, cilindro recto: [radio,altura]); plano=[ancho,alto];
    texto=[tamaño] (el texto mostrado es el propio `nombre`).
  - `.stl` (binario o ASCII; multi-solid ASCII → una pieza por bloque `solid/endsolid`,
    cada una es su propio grupo). Un STL de una sola malla, por tanto, es una sola pieza:
    la explosión no tiene nada de qué separarla (límite declarado a propósito,
    no un caso especial en el código: sale solo de que solo hay un grupo).
  - `.obj` (+ `.mtl` si hay `mtllib`/`usemtl`, solo se lee `Kd` como color): cada `o`/`g`
    es una pieza; caras con más de 3 vértices se trianguladan en abanico.
  - `.glb`/`.gltf` (+ buffers externos o en `data:` URI): cada nodo con malla es una pieza
    (posiciones y normales ya transformadas por la jerarquía de nodos a coordenadas del
    mundo); el color sale de `baseColorFactor` del material. Solo primitivas en modo
    TRIÁNGULOS (4, el valor por defecto); accessors normalizados o `sparse` no están
    soportados (caso raro en exportaciones simples) y se saltan con un aviso, no revientan.

Vista explosionada: cada pieza guarda su CENTROIDE; las piezas se agrupan por `grupo` (si
no lo declaran, cada una es su propio grupo — así una `.stl`/`.obj` sin grupos no explosiona
nada, y una `escena.json` con `grupo` repetido mueve esas piezas juntas). El deslizador de
la página desplaza cada grupo, como bloque rígido, en la dirección desde el centro de TODA
la escena hacia el centroide de ese grupo, escalado por el radio de la escena — así el
efecto se ve igual de bien sin importar las unidades del modelo.

Tres controles más en la página, todos en vivo (no son banderas de la CLI, que solo fija
el estado INICIAL): casilla de rejilla, casilla de alambre, y tres pares casilla+deslizador
de plano de corte (uno por eje). Y el botón «Capturar PNG», que descarga el fotograma
actual del `<canvas>` (con `preserveDrawingBuffer` a propósito: sin él, `toDataURL()` puede
devolver un lienzo vacío).

Tres es el número de reintentos de `--png`, no una promesa de que el primero vaya a fallar:
el primer fotograma se pinta de forma SÍNCRONA, antes de arrancar el bucle de
`requestAnimationFrame` (para que ya esté dibujado cuando el navegador sin cabeza dispara
la captura al terminar de cargar), y el guion, tras cada intento, comprueba que el PNG
resultante pesa por lo menos 10 KB (medido: un fotograma realmente en blanco de estas
dimensiones comprime muchísimo más pequeño que uno con luces, rejilla y geometría) — si no,
borra el intento y prueba otra vez, hasta 3 veces con 1,5 s
de espera entre cada una, avisando en cada reintento. Si las tres fallan, se queda con el
último PNG (puede llevar un aviso: «PNG de N bytes, por debajo de 10000») en vez de reventar
teniendo ya algo que mostrar — solo lanza si NINGÚN intento deja fichero.

Medido el 7-sep-2026 en la máquina de desarrollo (Windows, msedge.exe headless,
SwiftShader por software con --disable-gpu): `--png` sobre `pruebas/datos/escena_prueba.json`
(3 piezas, 1600×900) acertó al PRIMER intento las 3 veces que se repitió seguido, entre
1,05 y 2,02 s (PNG de 70.801 bytes, por encima del umbral de 10 KB con margen de sobra).

Dependencias: NINGUNA fuera de la biblioteca estándar (a propósito: la página que se genera
no necesita más que `abyss/vendor/three.min.js` y `abyss/vendor/orbita_minima.js`, embebidos
tal cual — ver sus docstrings/LICENSE-three.txt — así que tampoco este guion necesita nada
más para construirla). `--png` lanza un proceso de navegador con `subprocess`, nunca instala
nada.

Límites honestos: esto es un visor y editor de vistas, no un modelador (no repara mallas,
no simplifica, no exporta). La vista explosionada exige piezas YA separadas en el fichero de
entrada (grupos distintos en `escena.json`, objetos/grupos distintos en `.obj`, nodos
distintos en `.glb`/`.gltf`); no parte una malla única. La página pesa lo que pesa three.js
embebido (~650 KB) más lo que pese la geometría de la entrada — para modelos grandes eso
puede ser mucho: no hay compresión ni LOD.

No sale nada de la máquina: todo lo que hace este guion es leer el fichero de entrada,
escribir el HTML y (con `--png`) lanzar un navegador LOCAL contra ese mismo fichero por
`file://`; la página no pide nada por red — las dos URLs de aviso que trae three.js se
incrustan sin esquema (`https://` recortado) y la única `http://` que queda es el espacio
de nombres XHTML de `document.createElementNS(...)`, que nunca se descarga — ver
`_texto_three_embebido()`.
"""
import base64
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.parse

VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
TIPOS_PRIMITIVA = {"caja", "cilindro", "esfera", "texto", "plano"}
UMBRAL_PNG_OK = 10_000  # bytes: por debajo, se sospecha un fotograma en blanco (medido, ver docstring)


class SinNavegador(RuntimeError):
    """Ningún navegador sin cabeza (msedge.exe/chrome.exe/google-chrome/chromium) encontrado."""


# ───────────────────────── geometría: matrices 4x4 (columna-mayor, como glTF) ─────────────────────────

def _mat4_identidad():
    return [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]


def _mat4_mul(a, b):
    r = [0.0] * 16
    for col in range(4):
        for fil in range(4):
            s = 0.0
            for k in range(4):
                s += a[k * 4 + fil] * b[col * 4 + k]
            r[col * 4 + fil] = s
    return r


def _mat4_de_trs(t, q, esc):
    x, y, z, w = q
    x2, y2, z2 = x + x, y + y, z + z
    xx, xy, xz = x * x2, x * y2, x * z2
    yy, yz, zz = y * y2, y * z2, z * z2
    wx, wy, wz = w * x2, w * y2, w * z2
    sx, sy, sz = esc
    m = [0.0] * 16
    m[0] = (1 - (yy + zz)) * sx; m[1] = (xy + wz) * sx; m[2] = (xz - wy) * sx; m[3] = 0.0
    m[4] = (xy - wz) * sy; m[5] = (1 - (xx + zz)) * sy; m[6] = (yz + wx) * sy; m[7] = 0.0
    m[8] = (xz + wy) * sz; m[9] = (yz - wx) * sz; m[10] = (1 - (xx + yy)) * sz; m[11] = 0.0
    m[12] = t[0]; m[13] = t[1]; m[14] = t[2]; m[15] = 1.0
    return m


def _mat4_punto(m, p):
    x, y, z = p
    return (m[0] * x + m[4] * y + m[8] * z + m[12],
            m[1] * x + m[5] * y + m[9] * z + m[13],
            m[2] * x + m[6] * y + m[10] * z + m[14])


def _mat4_vector(m, v):
    x, y, z = v
    return (m[0] * x + m[4] * y + m[8] * z,
            m[1] * x + m[5] * y + m[9] * z,
            m[2] * x + m[6] * y + m[10] * z)


# ───────────────────────────────── cargadores por formato ─────────────────────────────────

def _cargar_escena_json(ruta):
    with open(ruta, encoding="utf-8") as fh:
        datos = json.load(fh)
    piezas_in = datos.get("piezas") or []
    if not piezas_in:
        raise ValueError("escena.json sin piezas")
    piezas = []
    for i, p in enumerate(piezas_in):
        tipo = p.get("tipo")
        if tipo not in TIPOS_PRIMITIVA:
            raise ValueError(f'pieza {i}: tipo desconocido {tipo!r} (usa caja/cilindro/esfera/texto/plano)')
        pos = [float(v) for v in (p.get("pos") or [0, 0, 0])]
        piezas.append({
            "nombre": p.get("nombre") or f"pieza_{i}",
            "tipo": tipo,
            "pos": pos,
            "tam": [float(v) for v in (p.get("tam") or [1, 1, 1])],
            "color": p.get("color") or "#8899aa",
            "grupo": p.get("grupo") or None,
            "centro": pos,
        })
    return piezas, datos.get("camara"), datos.get("unidades")


def _es_stl_binario(datos):
    if len(datos) < 84:
        return False
    n = struct.unpack_from("<I", datos, 80)[0]
    return len(datos) == 84 + n * 50


def _leer_stl_binario(datos):
    n = struct.unpack_from("<I", datos, 80)[0]
    verts = []
    off = 84
    for _ in range(n):
        vals = struct.unpack_from("<12fH", datos, off)  # normal(3) + v0(3) + v1(3) + v2(3) + attr(uint16)
        verts.append(vals[3:6]); verts.append(vals[6:9]); verts.append(vals[9:12])
        off += 50
    return verts


_RE_STL_SOLID = re.compile(r"solid\s*(\S*)(.*?)endsolid", re.S | re.I)
_RE_STL_VERTEX = re.compile(r"vertex\s+([\-0-9.eE]+)\s+([\-0-9.eE]+)\s+([\-0-9.eE]+)")


def _leer_stl_ascii(texto):
    bloques = _RE_STL_SOLID.findall(texto)
    if not bloques:
        raise ValueError("STL en texto sin bloques solid/endsolid reconocibles")
    grupos = []
    for i, (nombre, cuerpo) in enumerate(bloques):
        verts = [tuple(float(x) for x in m) for m in _RE_STL_VERTEX.findall(cuerpo)]
        if verts:
            grupos.append((nombre or f"solido_{i}", verts))
    return grupos


def _cargar_stl(ruta):
    with open(ruta, "rb") as fh:
        datos = fh.read()
    if _es_stl_binario(datos):
        grupos = [("malla", _leer_stl_binario(datos))]
    else:
        grupos = _leer_stl_ascii(datos.decode("utf-8", errors="ignore"))
    piezas = []
    for nombre, verts in grupos:
        if not verts:
            continue
        cx = sum(v[0] for v in verts) / len(verts)
        cy = sum(v[1] for v in verts) / len(verts)
        cz = sum(v[2] for v in verts) / len(verts)
        piezas.append({"nombre": nombre, "tipo": "malla", "color": "#b7b7b7", "grupo": nombre,
                       "centro": [cx, cy, cz], "vertices": verts, "normales": None, "indices": None})
    if not piezas:
        raise ValueError("STL sin triángulos que leer")
    return piezas


def _cargar_mtl(ruta):
    colores = {}
    actual = None
    try:
        with open(ruta, encoding="utf-8", errors="ignore") as fh:
            for linea in fh:
                p = linea.split()
                if not p:
                    continue
                if p[0] == "newmtl" and len(p) > 1:
                    actual = p[1]
                elif p[0] == "Kd" and actual and len(p) >= 4:
                    r, g, b = (float(x) for x in p[1:4])
                    colores[actual] = "#%02x%02x%02x" % tuple(min(255, max(0, round(c * 255))) for c in (r, g, b))
    except OSError:
        pass
    return colores


def _idx_obj(i, n):
    """Índices de OBJ: 1-based; negativos, relativos al final de la lista ACTUAL."""
    return i - 1 if i > 0 else n + i


def _cargar_obj(ruta):
    vs, vns = [], []
    colores = {}
    grupos, orden = {}, []
    actual, color_actual = None, "#9a9a9a"
    with open(ruta, encoding="utf-8", errors="ignore") as fh:
        for linea in fh:
            p = linea.split()
            if not p:
                continue
            c = p[0]
            if c == "v" and len(p) >= 4:
                vs.append((float(p[1]), float(p[2]), float(p[3])))
            elif c == "vn" and len(p) >= 4:
                vns.append((float(p[1]), float(p[2]), float(p[3])))
            elif c == "mtllib" and len(p) > 1:
                colores.update(_cargar_mtl(os.path.join(os.path.dirname(ruta), p[1])))
            elif c == "usemtl" and len(p) > 1:
                color_actual = colores.get(p[1], color_actual)
            elif c in ("o", "g"):
                actual = " ".join(p[1:]) or None
            elif c == "f" and len(p) >= 4:
                if actual is None:
                    actual = "objeto"
                if actual not in grupos:
                    grupos[actual] = {"tris": [], "color": color_actual}
                    orden.append(actual)
                idxs = []
                for tok in p[1:]:
                    partes = tok.split("/")
                    vi = _idx_obj(int(partes[0]), len(vs))
                    ni = None
                    if len(partes) >= 3 and partes[2]:
                        ni = _idx_obj(int(partes[2]), len(vns))
                    idxs.append((vi, ni))
                for k in range(1, len(idxs) - 1):  # triangulación en abanico (polígonos > 3 lados)
                    grupos[actual]["tris"].append((idxs[0], idxs[k], idxs[k + 1]))

    piezas = []
    for nombre in orden:
        g = grupos[nombre]
        verts, norms, ok_norm = [], [], True
        for tri in g["tris"]:
            for (vi, ni) in tri:
                if not (0 <= vi < len(vs)):
                    ok_norm = False
                    continue
                verts.append(vs[vi])
                if ni is not None and 0 <= ni < len(vns):
                    norms.append(vns[ni])
                else:
                    ok_norm = False
        if not verts:
            continue
        cx = sum(v[0] for v in verts) / len(verts)
        cy = sum(v[1] for v in verts) / len(verts)
        cz = sum(v[2] for v in verts) / len(verts)
        piezas.append({
            "nombre": nombre, "tipo": "malla", "color": g["color"], "grupo": nombre,
            "centro": [cx, cy, cz], "vertices": verts,
            "normales": norms if (ok_norm and len(norms) == len(verts)) else None,
            "indices": None,
        })
    if not piezas:
        raise ValueError("OBJ sin caras que leer")
    return piezas


_COMPONENTE = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
_NUMCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}


def _gltf_leer_accessor(gltf, buffers, idx):
    """Solo el caso común: accessor con `bufferView`, sin `sparse`, sin normalizar
    (POSITION/NORMAL en float32, índices en uint16/uint32 — lo que exportan Blender y
    la mayoría de herramientas para mallas simples). Un accessor `sparse` o normalizado
    se lee igual pero SIN aplicar esas dos correcciones (aviso, no excepción, para no
    tirar todo el modelo por una sola primitiva rara)."""
    acc = gltf["accessors"][idx]
    n = _NUMCOMP[acc["type"]]
    fmt, sz = _COMPONENTE[acc["componentType"]]
    count = acc["count"]
    bv_idx = acc.get("bufferView")
    if bv_idx is None:
        return [(0.0,) * n for _ in range(count)]
    bv = gltf["bufferViews"][bv_idx]
    buf = buffers[bv["buffer"]]
    base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    paso = bv.get("byteStride") or (n * sz)
    out = []
    for i in range(count):
        out.append(struct.unpack_from("<" + fmt * n, buf, base + i * paso))
    return out


def _gltf_materiales(gltf):
    colores = []
    for m in gltf.get("materials", []):
        bcf = (m.get("pbrMetallicRoughness") or {}).get("baseColorFactor") or [0.7, 0.7, 0.7, 1]
        colores.append("#%02x%02x%02x" % tuple(min(255, max(0, round(c * 255))) for c in bcf[:3]))
    return colores


def _gltf_buffers(gltf, chunk_bin, ruta_base):
    buffers = []
    for b in gltf.get("buffers", []):
        uri = b.get("uri")
        if uri is None:
            if chunk_bin is None:
                raise ValueError("buffer sin uri y sin chunk binario (GLB incompleto)")
            buffers.append(chunk_bin)
        elif uri.startswith("data:"):
            buffers.append(base64.b64decode(uri.split(",", 1)[1]))
        else:
            ruta = os.path.join(os.path.dirname(ruta_base), urllib.parse.unquote(uri))
            with open(ruta, "rb") as fh:
                buffers.append(fh.read())
    return buffers


def _gltf_nodos(gltf, buffers, materiales, avisar):
    nodos = gltf.get("nodes", [])
    mallas = gltf.get("meshes", [])
    piezas = []

    def matriz_local(nodo):
        if "matrix" in nodo:
            return [float(v) for v in nodo["matrix"]]
        return _mat4_de_trs(nodo.get("translation", [0, 0, 0]), nodo.get("rotation", [0, 0, 0, 1]),
                            nodo.get("scale", [1, 1, 1]))

    def visitar(idx, mundo_padre):
        nodo = nodos[idx]
        mundo = _mat4_mul(mundo_padre, matriz_local(nodo))
        if "mesh" in nodo:
            malla = mallas[nodo["mesh"]]
            prims = malla.get("primitives", [])
            for pi, prim in enumerate(prims):
                if prim.get("mode", 4) != 4:
                    avisar(f'  aviso: nodo {idx} primitiva {pi}: modo {prim.get("mode")} no soportado (solo TRIANGLES), se salta')
                    continue
                attrs = prim.get("attributes", {})
                if "POSITION" not in attrs:
                    continue
                pos_local = _gltf_leer_accessor(gltf, buffers, attrs["POSITION"])
                pos_mundo = [_mat4_punto(mundo, p) for p in pos_local]
                normales = None
                if "NORMAL" in attrs:
                    normales = [_mat4_vector(mundo, v) for v in _gltf_leer_accessor(gltf, buffers, attrs["NORMAL"])]
                indices = None
                if "indices" in prim:
                    indices = [v[0] for v in _gltf_leer_accessor(gltf, buffers, prim["indices"])]
                color = "#b0b0b0"
                mat_idx = prim.get("material")
                if mat_idx is not None and mat_idx < len(materiales):
                    color = materiales[mat_idx]
                nombre = nodo.get("name") or f"nodo_{idx}"
                if len(prims) > 1:
                    nombre = f"{nombre}_{pi}"
                cx = sum(p[0] for p in pos_mundo) / len(pos_mundo)
                cy = sum(p[1] for p in pos_mundo) / len(pos_mundo)
                cz = sum(p[2] for p in pos_mundo) / len(pos_mundo)
                piezas.append({"nombre": nombre, "tipo": "malla", "color": color, "grupo": nombre,
                               "centro": [cx, cy, cz], "vertices": pos_mundo, "normales": normales,
                               "indices": indices})
        for hijo in nodo.get("children", []):
            visitar(hijo, mundo)

    escenas = gltf.get("scenes")
    raices = escenas[gltf.get("scene", 0)].get("nodes", []) if escenas else list(range(len(nodos)))
    for r in raices:
        visitar(r, _mat4_identidad())
    return piezas


def _leer_glb(datos):
    magia, _version, longitud = struct.unpack_from("<III", datos, 0)
    if magia != 0x46546C67:
        raise ValueError("no es un GLB válido (cabecera incorrecta)")
    off, gltf, chunk_bin = 12, None, None
    while off < longitud:
        clen, ctype = struct.unpack_from("<II", datos, off)
        off += 8
        cdatos = datos[off:off + clen]
        off += clen
        if ctype == 0x4E4F534A:  # 'JSON'
            gltf = json.loads(cdatos.decode("utf-8"))
        elif ctype == 0x004E4942:  # 'BIN\0'
            chunk_bin = cdatos
    if gltf is None:
        raise ValueError("GLB sin chunk JSON")
    return gltf, chunk_bin


def _cargar_gltf(ruta, avisar):
    with open(ruta, "rb") as fh:
        datos = fh.read()
    if datos[:4] == b"glTF":
        gltf, chunk_bin = _leer_glb(datos)
    else:
        gltf = json.loads(datos.decode("utf-8"))
        chunk_bin = None
    buffers = _gltf_buffers(gltf, chunk_bin, ruta)
    piezas = _gltf_nodos(gltf, buffers, _gltf_materiales(gltf), avisar)
    if not piezas:
        raise ValueError("sin mallas de triángulos legibles en este glTF/GLB")
    return piezas


def cargar_entrada(ruta, avisar=print):
    """(piezas, camara_json_o_None, unidades_o_None) — `piezas` ya en el formato común
    (primitivas con pos/tam, o mallas con vertices/normales/indices), sin `centro` de la
    ESCENA todavía (eso lo calcula `_bbox_escena`)."""
    ruta = os.path.abspath(ruta)
    if not os.path.isfile(ruta):
        raise FileNotFoundError(f"no existe: {ruta}")
    ext = os.path.splitext(ruta)[1].lower()
    if ext == ".json":
        return _cargar_escena_json(ruta)
    if ext == ".stl":
        return _cargar_stl(ruta), None, None
    if ext == ".obj":
        return _cargar_obj(ruta), None, None
    if ext in (".glb", ".gltf"):
        return _cargar_gltf(ruta, avisar), None, None
    raise ValueError(f"extensión no soportada: {ext!r} (usa .glb/.gltf/.obj/.stl/.json)")


# ───────────────────────────────── caja de la escena entera ─────────────────────────────────

def _tam3(tam):
    tam = list(tam) if tam else [1.0]
    if len(tam) == 1:
        return tam[0], tam[0], tam[0]
    if len(tam) == 2:
        return tam[0], tam[1], tam[0]
    return tam[0], tam[1], tam[2]


def _extension_primitiva(tipo, tam):
    """Semiejes (hx,hy,hz) de una caja que SÍ contiene la primitiva, para el cálculo del
    centro/radio de la escena entera — no necesita ser exacta, solo no quedarse corta."""
    if tipo == "caja":
        w, h, d = _tam3(tam)
        return w / 2, h / 2, d / 2
    if tipo == "esfera":
        r = tam[0] if tam else 0.5
        return r, r, r
    if tipo == "cilindro":
        r = max(tam[0] if tam else 0.5, tam[1] if len(tam) >= 3 else (tam[0] if tam else 0.5))
        h = (tam[-1] if tam else 1.0) / 2
        return r, h, r
    if tipo == "plano":
        w, h, _ = _tam3(tam)
        return w / 2, h / 2, 0.01
    return 0.3, 0.3, 0.3  # texto: una etiqueta, tamaño nominal


def _bbox_escena(piezas):
    minv, maxv = [math.inf, math.inf, math.inf], [-math.inf, -math.inf, -math.inf]

    def marca(x, y, z):
        for i, v in enumerate((x, y, z)):
            if v < minv[i]:
                minv[i] = v
            if v > maxv[i]:
                maxv[i] = v

    for p in piezas:
        if p["tipo"] == "malla":
            for (x, y, z) in p["vertices"]:
                marca(x, y, z)
        else:
            cx, cy, cz = p["pos"]
            hx, hy, hz = _extension_primitiva(p["tipo"], p.get("tam") or [1, 1, 1])
            marca(cx - hx, cy - hy, cz - hz)
            marca(cx + hx, cy + hy, cz + hz)

    if minv[0] == math.inf:  # no debería pasar (cargar_entrada ya exige >=1 pieza), fail-safe
        return [0.0, 0.0, 0.0], 1.0
    centro = [(minv[i] + maxv[i]) / 2 for i in range(3)]
    diagonal = math.dist(minv, maxv)
    radio = max(0.25, diagonal / 2)
    return centro, radio


# ───────────────────────────────── incrustado en la página ─────────────────────────────────

def _leer_vendor(nombre):
    with open(os.path.join(VENDOR, nombre), encoding="utf-8") as fh:
        return fh.read()


def _texto_three_embebido():
    """El vendor tal cual (ver LICENSE-three.txt), con sus DOS únicas URLs (una en el aviso
    de obsolescencia del build UMD, otra repetida dos veces en un aviso sobre gestión de
    color) recortadas al vuelo a "threejs.org/..." / "discourse.threejs.org/..." (se les
    quita solo el esquema `https://`, dentro de textos de `console.warn` que nadie llega a
    fetch-ear) — así la página generada no lleva ninguna URL externa de verdad.

    OJO: la ÚNICA otra cadena `http` del fichero es `"http://www.w3.org/1999/xhtml"`, el
    espacio de nombres XHTML que usa internamente `document.createElementNS(...)` para
    crear el `<canvas>` — esa NO se toca (recortarle el esquema la convertiría en un
    espacio de nombres distinto y `createElementNS` dejaría de darte un `HTMLCanvasElement`
    de verdad: es un identificador, nunca se descarga). El fichero en `vendor/` no se toca;
    esto solo afecta a la copia que se escribe en cada HTML."""
    texto = _leer_vendor("three.min.js")
    texto = texto.replace("https://threejs.org", "threejs.org")
    texto = texto.replace("https://discourse.threejs.org", "discourse.threejs.org")
    return texto


def _b64_floats(valores):
    if not valores:
        return None
    return base64.b64encode(struct.pack(f"<{len(valores)}f", *valores)).decode("ascii")


def _b64_uint32(valores):
    if not valores:
        return None
    return base64.b64encode(struct.pack(f"<{len(valores)}I", *(int(v) for v in valores))).decode("ascii")


def _pieza_embebible(p):
    if p["tipo"] == "malla":
        verts = p["vertices"]
        d = {
            "nombre": p["nombre"], "tipo": "malla", "color": p["color"], "grupo": p["grupo"],
            "centro": [round(c, 6) for c in p["centro"]],
            "vertices_b64": _b64_floats([c for v in verts for c in v]),
        }
        if p.get("normales"):
            d["normales_b64"] = _b64_floats([c for v in p["normales"] for c in v])
        if p.get("indices"):
            d["indices_b64"] = _b64_uint32(p["indices"])
        return d
    return {
        "nombre": p["nombre"], "tipo": p["tipo"], "pos": p["pos"], "tam": p["tam"],
        "color": p["color"], "grupo": p["grupo"], "centro": [round(c, 6) for c in p["centro"]],
    }


_MAIN_JS = r"""
function b64ToFloat32(b64) {
  const bin = atob(b64); const buf = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
  return new Float32Array(buf.buffer);
}
function b64ToUint32(b64) {
  const bin = atob(b64); const buf = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
  return new Uint32Array(buf.buffer);
}
function crearEtiqueta(texto, tam, color) {
  const cv = document.createElement('canvas');
  cv.width = 512; cv.height = 128;
  const ctx = cv.getContext('2d');
  ctx.font = 'bold 64px system-ui, sans-serif';
  ctx.fillStyle = color || '#ffffff';
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(String(texto), 256, 64);
  const tex = new THREE.CanvasTexture(cv);
  tex.needsUpdate = true;
  const spr = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true }));
  const t = tam || 0.4;
  spr.scale.set(t * 4, t, 1);
  return spr;
}
function crearMaterial(color) {
  // acabado "estudio": metal pulido (metalness 1.0) que ademas recibe el entorno de reflejo
  // procedural montado en principal() -- receta calcada de tornillo.html. El original
  // distinguia roughness 0.34 (pieza plana) / 0.27 (pieza curva) con un dato de pieza que
  // este guion GENERICO no declara (no sabe que un grupo es una cara plana): aqui se usa un
  // unico roughness intermedio (0.30) para todas las piezas del acabado "estudio". El
  // aspecto facetado o liso de cada grupo sigue viniendo, igual que en "mate", del propio
  // normal que trae el fichero de entrada (o de computeVertexNormals si no trae ninguno) --
  // no de este material.
  if (ESCENA.acabado === 'estudio') {
    return new THREE.MeshStandardMaterial({ color: color, side: THREE.DoubleSide, metalness: 1.0, roughness: 0.30, envMapIntensity: 1.15 });
  }
  return new THREE.MeshStandardMaterial({ color: color, side: THREE.DoubleSide, roughness: 0.85, metalness: 0.05 });
}
function construirPieza(p) {
  let obj;
  const tam = p.tam || [1, 1, 1];
  if (p.tipo === 'malla') {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(b64ToFloat32(p.vertices_b64), 3));
    if (p.normales_b64) geo.setAttribute('normal', new THREE.BufferAttribute(b64ToFloat32(p.normales_b64), 3));
    if (p.indices_b64) geo.setIndex(new THREE.BufferAttribute(b64ToUint32(p.indices_b64), 1));
    if (!p.normales_b64) geo.computeVertexNormals();
    obj = new THREE.Mesh(geo, crearMaterial(p.color));
    obj.castShadow = true; obj.receiveShadow = true;  // sin efecto si shadowMap va apagado (acabado "mate")
    obj.userData.basePos = new THREE.Vector3(0, 0, 0);
  } else if (p.tipo === 'texto') {
    obj = crearEtiqueta(p.nombre, tam[0], p.color);
    obj.position.set(p.pos[0], p.pos[1], p.pos[2]);
    obj.userData.basePos = obj.position.clone();
  } else {
    let geo;
    if (p.tipo === 'caja') {
      geo = new THREE.BoxGeometry(tam[0] || 1, tam[1] != null ? tam[1] : (tam[0] || 1), tam[2] != null ? tam[2] : (tam[0] || 1));
    } else if (p.tipo === 'esfera') {
      geo = new THREE.SphereGeometry(tam[0] != null ? tam[0] : 0.5, 24, 16);
    } else if (p.tipo === 'cilindro') {
      const rt = tam[0] != null ? tam[0] : 0.5;
      const rb = tam.length >= 3 ? tam[1] : rt;
      const h = tam[tam.length - 1] != null ? tam[tam.length - 1] : 1;
      geo = new THREE.CylinderGeometry(rt, rb, h, 32);
    } else {
      geo = new THREE.PlaneGeometry(tam[0] || 1, tam[1] != null ? tam[1] : (tam[0] || 1));
    }
    obj = new THREE.Mesh(geo, crearMaterial(p.color));
    obj.castShadow = true; obj.receiveShadow = true;  // sin efecto si shadowMap va apagado (acabado "mate")
    obj.position.set(p.pos[0], p.pos[1], p.pos[2]);
    obj.userData.basePos = obj.position.clone();
  }
  obj.name = p.nombre;
  obj.userData.grupo = p.grupo;
  obj.userData.centro = p.centro;
  return obj;
}
function calcularDirecciones(piezasObjs, centroV) {
  const sumas = {}, cuentas = {};
  for (const o of piezasObjs) {
    const g = o.userData.grupo;
    if (!sumas[g]) { sumas[g] = new THREE.Vector3(); cuentas[g] = 0; }
    sumas[g].add(new THREE.Vector3(o.userData.centro[0], o.userData.centro[1], o.userData.centro[2]));
    cuentas[g]++;
  }
  const dir = {};
  for (const g in sumas) {
    const centroide = sumas[g].clone().divideScalar(cuentas[g]);
    const d = centroide.clone().sub(centroV);
    dir[g] = d.lengthSq() > 1e-9 ? d.normalize() : new THREE.Vector3(0, 1, 0);
  }
  return dir;
}
(function principal() {
  const CENTRO = ESCENA.centro, RADIO = Math.max(ESCENA.radio, 0.01);
  const escena3d = new THREE.Scene();
  escena3d.background = new THREE.Color(ESCENA.fondo);

  const camDatos = ESCENA.camara || {};
  const objetivo = new THREE.Vector3(...(camDatos.mirar || CENTRO));
  const posCam = camDatos.pos || [CENTRO[0] + RADIO * 1.8, CENTRO[1] + RADIO * 1.3, CENTRO[2] + RADIO * 1.8];
  const camera = new THREE.PerspectiveCamera(camDatos.fov || 50, ESCENA.ancho / ESCENA.alto, Math.max(0.005, RADIO / 1000), RADIO * 80 + 20);
  camera.position.set(posCam[0], posCam[1], posCam[2]);
  camera.lookAt(objetivo);

  const canvas = document.createElement('canvas');
  document.body.appendChild(canvas);
  const renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(ESCENA.ancho, ESCENA.alto);
  if ('outputColorSpace' in renderer) renderer.outputColorSpace = THREE.SRGBColorSpace;
  if (ESCENA.acabado === 'estudio') {
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  }

  if (ESCENA.acabado === 'estudio') {
    // Entorno de reflejo PROCEDURAL (receta de tornillo.html): un cubo con dos caras que
    // llevan "ventanas" claras -> el metal pulido refleja luz de estudio en vez de un gris
    // plano. Dos <canvas> 2D generados aqui mismo, nada cargado de fuera.
    const caraEstudio = function (esVentana) {
      const c = document.createElement('canvas'); c.width = c.height = 256;
      const x = c.getContext('2d');
      const g = x.createLinearGradient(0, 0, 0, 256);
      g.addColorStop(0, '#3a4048'); g.addColorStop(1, '#0e1013');
      x.fillStyle = g; x.fillRect(0, 0, 256, 256);
      if (esVentana) {
        x.fillStyle = '#ffffff'; x.fillRect(30, 40, 196, 60);
        x.fillStyle = '#cfd6dd'; x.fillRect(60, 150, 140, 40);
      }
      return c;
    };
    const cubo = new THREE.CubeTexture([caraEstudio(false), caraEstudio(false), caraEstudio(true),
      caraEstudio(false), caraEstudio(false), caraEstudio(false)]);
    cubo.needsUpdate = true;
    cubo.mapping = THREE.CubeReflectionMapping;
    cubo.colorSpace = THREE.SRGBColorSpace;
    escena3d.environment = cubo;
  }

  if (ESCENA.acabado === 'estudio') {
    // Tres luces + ambiente, calcadas de tornillo.html, en vez de las dos planas de "mate"
    // (--luz calida/fria/neutra no se usa aqui: este acabado trae su propia luz fija, la de
    // la receta). Las POSICIONES no son las del viejo a pelo: son (posicion_vieja menos su
    // CENTRO) dividido por su RADIO (~24,1538, calculado con la MISMA formula de
    // _bbox_escena aplicada a mano a los vertices que decodifique de tornillo.html -- ver el
    // docstring del modulo), multiplicadas aqui por el RADIO de ESTA escena: una luz
    // direccional no se atenua con la distancia, asi que lo unico que le importa es su
    // DIRECCION, y un reescalado uniforme de su posicion no la toca.
    escena3d.add(new THREE.AmbientLight(0xffffff, 0.22));
    const key = new THREE.DirectionalLight(0xffffff, 3.1);
    key.position.set(CENTRO[0] + RADIO * 1.1679, CENTRO[1] + RADIO * 1.7311, CENTRO[2] + RADIO * 1.0764);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    const extSombra = RADIO * 1.6561;
    key.shadow.camera.left = -extSombra; key.shadow.camera.right = extSombra;
    key.shadow.camera.top = extSombra; key.shadow.camera.bottom = -extSombra;
    key.shadow.bias = -0.0008 * (RADIO / 24.1538);
    escena3d.add(key);
    const fill = new THREE.DirectionalLight(0x9fb6d0, 1.0);
    fill.position.set(CENTRO[0] - RADIO * 1.2334, CENTRO[1] + RADIO * 0.4890, CENTRO[2] - RADIO * 0.7452);
    escena3d.add(fill);
    const rim = new THREE.DirectionalLight(0xdfe8f5, 1.6);
    rim.position.set(CENTRO[0] - RADIO * 0.6538, CENTRO[1] + RADIO * 0.6546, CENTRO[2] + RADIO * 1.7389);
    escena3d.add(rim);
  } else {
    const LUCES = {
      calida: { ambiente: 0x40332a, dir: 0xffdcae },
      fria: { ambiente: 0x222a33, dir: 0xcfe6ff },
      neutra: { ambiente: 0x333333, dir: 0xffffff },
    };
    const lp = LUCES[ESCENA.luz] || LUCES.neutra;
    escena3d.add(new THREE.AmbientLight(lp.ambiente, 1.0));
    const luzClave = new THREE.DirectionalLight(lp.dir, 1.2);
    luzClave.position.set(CENTRO[0] + RADIO * 1.5, CENTRO[1] + RADIO * 2.2, CENTRO[2] + RADIO * 1.1);
    escena3d.add(luzClave);
    const luzRelleno = new THREE.DirectionalLight(0xffffff, 0.35);
    luzRelleno.position.set(CENTRO[0] - RADIO * 1.5, CENTRO[1] + RADIO * 0.6, CENTRO[2] - RADIO * 1.5);
    escena3d.add(luzRelleno);
  }

  const grid = new THREE.GridHelper(Math.max(2, RADIO * 4), 24, 0x555a5f, 0x33383c);
  grid.position.set(CENTRO[0], CENTRO[1] - RADIO * 1.05, CENTRO[2]);
  grid.visible = (ESCENA.acabado !== 'estudio');  // "estudio" pide NADA de rejilla al arrancar; el control de la pagina la puede volver a encender
  escena3d.add(grid);

  if (ESCENA.acabado === 'estudio') {
    // Suelo oscuro que RECIBE sombra (receta: PlaneGeometry(400,400), y=-9.0, sobre una
    // escena de RADIO~24,1538 -- ver el comentario de las luces, arriba, para de donde sale
    // ese numero). Aqui, escalado: lado = RADIO*16,5605, y = CENTRO.y - RADIO*0,2976.
    const suelo = new THREE.Mesh(new THREE.PlaneGeometry(RADIO * 16.5605, RADIO * 16.5605),
      new THREE.MeshStandardMaterial({ color: 0x111318, roughness: 0.55, metalness: 0.0 }));
    suelo.rotation.x = -Math.PI / 2;
    suelo.position.set(CENTRO[0], CENTRO[1] - RADIO * 0.2976, CENTRO[2]);
    suelo.receiveShadow = true;
    escena3d.add(suelo);
  }

  const piezasObjs = ESCENA.piezas.map(construirPieza);
  for (const o of piezasObjs) escena3d.add(o);
  const direcciones = calcularDirecciones(piezasObjs, new THREE.Vector3(CENTRO[0], CENTRO[1], CENTRO[2]));

  function aplicarExplosion(valor) {
    for (const o of piezasObjs) {
      const d = direcciones[o.userData.grupo] || new THREE.Vector3(0, 1, 0);
      const off = d.clone().multiplyScalar(valor * RADIO * 0.6);
      o.position.copy(o.userData.basePos).add(off);
    }
  }

  const sldExplosion = document.getElementById('sldExplosion');
  const valExplosion = document.getElementById('valExplosion');
  function refrescarExplosion() {
    valExplosion.textContent = parseFloat(sldExplosion.value).toFixed(2);
    aplicarExplosion(parseFloat(sldExplosion.value));
  }
  sldExplosion.addEventListener('input', refrescarExplosion);

  document.getElementById('chkRejilla').addEventListener('change', function () { grid.visible = this.checked; });
  document.getElementById('chkAlambre').addEventListener('change', function () {
    for (const o of piezasObjs) { if (o.material && 'wireframe' in o.material) o.material.wireframe = this.checked; }
  });

  const ejes = [
    { chk: 'chkX', sld: 'sldX', i: 0, normal: new THREE.Vector3(-1, 0, 0) },
    { chk: 'chkY', sld: 'sldY', i: 1, normal: new THREE.Vector3(0, -1, 0) },
    { chk: 'chkZ', sld: 'sldZ', i: 2, normal: new THREE.Vector3(0, 0, -1) },
  ];
  const planos = ejes.map(e => new THREE.Plane(e.normal, 0));
  renderer.localClippingEnabled = true;
  function actualizarRecorte() {
    const activos = [];
    ejes.forEach((e, k) => {
      const chk = document.getElementById(e.chk), sld = document.getElementById(e.sld);
      planos[k].constant = parseFloat(sld.value);
      if (chk.checked) activos.push(planos[k]);
    });
    for (const o of piezasObjs) { if (o.material) o.material.clippingPlanes = activos; }
  }
  ejes.forEach((e) => {
    const sld = document.getElementById(e.sld);
    sld.min = CENTRO[e.i] - RADIO * 1.3; sld.max = CENTRO[e.i] + RADIO * 1.3;
    sld.step = Math.max(RADIO / 200, 0.001); sld.value = CENTRO[e.i] + RADIO * 1.3;
    document.getElementById(e.chk).addEventListener('change', actualizarRecorte);
    sld.addEventListener('input', actualizarRecorte);
  });

  document.getElementById('btnCapturar').addEventListener('click', function () {
    renderer.render(escena3d, camera);
    const a = document.createElement('a');
    a.href = renderer.domElement.toDataURL('image/png');
    a.download = (ESCENA.nombre_base || 'render3d') + '.png';
    document.body.appendChild(a); a.click(); a.remove();
  });

  try {
    if (new URLSearchParams(location.search).has('captura')) document.getElementById('panel').classList.add('oculto');
  } catch (e) { /* location.search puede fallar en file:// muy antiguos: sin drama, se ve el panel */ }

  const controles = new OrbitaMinima(camera, renderer.domElement, objetivo);

  // T4.4 --holograma: cuatro cuadrantes 2D espejados sobre negro (Pepper's ghost). El
  // <canvas> WebGL de siempre sigue existiendo y pintando (es la FUENTE, con `drawImage`);
  // solo se oculta como tal. Ver la convención de ángulos/espejado en el docstring de
  // `renderizar()` — sin dependencias nuevas: dos llamadas de Canvas2D de toda la vida.
  function iniciarHolograma() {
    const cont = document.getElementById('holograma');
    cont.style.display = 'block';
    canvas.style.display = 'none';
    const cuadrantes = [
      { el: document.getElementById('cuadArriba'), angulo: 180 },
      { el: document.getElementById('cuadAbajo'), angulo: 0 },
      { el: document.getElementById('cuadIzquierda'), angulo: 90 },
      { el: document.getElementById('cuadDerecha'), angulo: -90 },
    ];
    function colocar() {
      const lado = Math.max(1, Math.floor(Math.min(window.innerWidth, window.innerHeight) * 0.5));
      const vw = window.innerWidth, vh = window.innerHeight;
      const posiciones = {
        cuadArriba: [(vw - lado) / 2, vh / 2 - lado],
        cuadAbajo: [(vw - lado) / 2, vh / 2],
        cuadIzquierda: [vw / 2 - lado, (vh - lado) / 2],
        cuadDerecha: [vw / 2, (vh - lado) / 2],
      };
      for (const c of cuadrantes) {
        c.el.width = lado; c.el.height = lado;
        const pos = posiciones[c.el.id];
        c.el.style.left = pos[0] + 'px'; c.el.style.top = pos[1] + 'px';
      }
    }
    window.addEventListener('resize', colocar);
    colocar();
    return function dibujarHolograma() {
      const sw = canvas.width, sh = canvas.height;
      if (!sw || !sh) return;
      for (const c of cuadrantes) {
        const ctx = c.el.getContext('2d');
        const lado = c.el.width;
        ctx.save();
        ctx.clearRect(0, 0, lado, lado);
        ctx.translate(lado / 2, lado / 2);
        ctx.rotate(c.angulo * Math.PI / 180);
        ctx.scale(-1, 1);  // espejado: la reflexión de la pirámide invierte la imagen
        const escala = Math.max(lado / sw, lado / sh);
        ctx.drawImage(canvas, -sw * escala / 2, -sh * escala / 2, sw * escala, sh * escala);
        ctx.restore();
      }
    };
  }
  const dibujarHolograma = ESCENA.holograma ? iniciarHolograma() : null;

  refrescarExplosion();
  renderer.render(escena3d, camera);  // síncrono, antes de animar(): ya hay un fotograma pintado
  if (dibujarHolograma) dibujarHolograma();

  function animar() {
    requestAnimationFrame(animar);
    controles.update();
    renderer.render(escena3d, camera);
    if (dibujarHolograma) dibujarHolograma();
  }
  animar();
})();
"""

_PLANTILLA_HTML = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>__TITULO__</title>
<style>
html,body{margin:0;width:100%;height:100%;overflow:hidden;background:__FONDO__;font:12px/1.4 system-ui,sans-serif;color:#eee}
canvas{display:block}
#panel{position:fixed;top:8px;left:8px;z-index:5;background:#000000b0;padding:10px 12px;border-radius:8px;min-width:210px}
#panel.oculto{display:none}
#panel h1{font-size:13px;margin:0 0 8px;font-weight:600}
#panel label{display:block;margin:6px 0 2px;opacity:.85}
#panel input[type=range]{width:100%;vertical-align:middle}
#panel .fila{display:flex;align-items:center;gap:6px;margin:2px 0}
#panel button{background:#3a3a44;color:#eee;border:0;border-radius:6px;padding:7px 10px;margin-top:10px;cursor:pointer;width:100%;font:inherit}
#panel button:hover{background:#4a4a56}
#holograma{position:fixed;inset:0;background:#000;display:none}
#holograma canvas{position:absolute;background:#000}
</style>
</head>
<body>
<div id="panel">
  <h1>__TITULO_PANEL__</h1>
  <label>vista explosionada <span id="valExplosion"></span></label>
  <input id="sldExplosion" type="range" min="0" max="2" step="0.01" value="__EXPLOSION__">
  <div class="fila"><input id="chkRejilla" type="checkbox" __REJILLA_CHECKED__> <label for="chkRejilla" style="margin:0">rejilla</label></div>
  <div class="fila"><input id="chkAlambre" type="checkbox"> <label for="chkAlambre" style="margin:0">alambre</label></div>
  <label>recorte X</label>
  <div class="fila"><input id="chkX" type="checkbox"><input id="sldX" type="range" style="flex:1"></div>
  <label>recorte Y</label>
  <div class="fila"><input id="chkY" type="checkbox"><input id="sldY" type="range" style="flex:1"></div>
  <label>recorte Z</label>
  <div class="fila"><input id="chkZ" type="checkbox"><input id="sldZ" type="range" style="flex:1"></div>
  <button id="btnCapturar" type="button">Capturar PNG</button>
</div>
<!-- T4.4 --holograma: cuatro cuadrantes 2D (drawImage del <canvas> WebGL de siempre,
     que sigue existiendo pero oculto) — ver ESCENA.holograma en __MAIN_JS__. -->
<div id="holograma">
  <canvas id="cuadArriba"></canvas>
  <canvas id="cuadAbajo"></canvas>
  <canvas id="cuadIzquierda"></canvas>
  <canvas id="cuadDerecha"></canvas>
</div>
<script>
/* three.js r160 (0.160.0), licencia MIT: abyss/vendor/LICENSE-three.txt */
__THREE_JS__
</script>
<script>
__ORBITA_JS__
</script>
<script>
const ESCENA = __ESCENA_JSON__;
__MAIN_JS__
</script>
</body>
</html>
"""


def _construir_html(escena_embebida, titulo, explosion_inicial):
    html = _PLANTILLA_HTML
    html = html.replace("__TITULO__", f"{titulo}, render 3D")
    html = html.replace("__TITULO_PANEL__", titulo)
    html = html.replace("__FONDO__", escena_embebida["fondo"])
    html = html.replace("__EXPLOSION__", repr(float(explosion_inicial)))
    # el acabado "estudio" arranca SIN rejilla (ver docstring del módulo); la casilla del
    # panel arranca a juego con eso, no siempre marcada, para no mentirle al que la mira.
    html = html.replace("__REJILLA_CHECKED__", "" if escena_embebida["acabado"] == "estudio" else "checked")
    html = html.replace("__THREE_JS__", _texto_three_embebido())
    html = html.replace("__ORBITA_JS__", _leer_vendor("orbita_minima.js"))
    html = html.replace("__ESCENA_JSON__", json.dumps(escena_embebida, ensure_ascii=False))
    html = html.replace("__MAIN_JS__", _MAIN_JS)
    return html


# ───────────────────────────────── navegador sin cabeza ─────────────────────────────────

def _buscar_navegador():
    """Ruta a un ejecutable de Chrome/Edge sin cabeza, o `None` si no se encuentra ninguno.

    `ABYSS_RENDER3D_NAVEGADOR` (si está puesta, aunque sea vacía) MANDA sobre la búsqueda
    real: existe solo para las pruebas de este paquete (poder forzar tanto "aquí está" como
    "aquí no hay nada" sin depender de qué navegadores tenga instalados la máquina que
    ejecuta la suite) — en uso normal nunca se define, igual que `ABYSS_OPENVERSE_URL` en
    `imagen.py`."""
    forzado = os.environ.get("ABYSS_RENDER3D_NAVEGADOR")
    if forzado is not None:
        return forzado if (forzado and os.path.isfile(forzado)) else None

    if os.name == "nt":
        candidatos = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        for c in candidatos:
            if c and os.path.isfile(c):
                return c
        for nombre in ("msedge", "chrome"):
            p = shutil.which(nombre)
            if p:
                return p
        return None

    for nombre in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "msedge"):
        p = shutil.which(nombre)
        if p:
            return p
    for c in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
              "/Applications/Chromium.app/Contents/MacOS/Chromium"):
        if os.path.isfile(c):
            return c
    return None


def _capturar_png(ruta_html, ruta_png, ancho, alto, avisar=print, navegador=None):
    exe = navegador if navegador is not None else _buscar_navegador()
    if not exe or not os.path.isfile(exe):
        raise SinNavegador("no hay navegador sin cabeza")
    url = "file:///" + os.path.abspath(ruta_html).replace("\\", "/") + "?captura=1"
    ruta_png = os.path.abspath(ruta_png)
    ultimo_aviso = None
    t0 = time.time()

    # ── primero, por el protocolo del navegador ─────────────────────────────
    # La bandera `--screenshot` dejó de servir para esta página. Medido el 9-sep-2026 con
    # Edge 152.0.4191.66: sobre la escena WebGL da 0 bytes en `--headless`, `--headless=old`
    # y `--headless=new`, con y sin `--disable-gpu` y con SwiftShader — tres intentos, todos
    # vacíos; y sobre una página trivial alterna 0 y 1.981 bytes entre intentos, que es una
    # carrera, no una avería. Por el protocolo, la misma escena sale a la primera.
    # La bandera se conserva DEBAJO como respaldo: en otra máquina o con otra versión puede
    # seguir siendo el camino bueno, y quitarla sería cambiar una suposición por otra.
    try:
        from navegador_cdp import captura as _captura_cdp
    except ImportError:
        try:
            from abyss.navegador_cdp import captura as _captura_cdp
        except ImportError:
            _captura_cdp = None
    if _captura_cdp is not None:
        datos = _captura_cdp(exe, url, ruta_png, ancho, alto, avisar=avisar)
        if datos and len(datos) >= UMBRAL_PNG_OK:
            return {"segundos": round(time.time() - t0, 2), "intentos": 1,
                    "bytes": len(datos), "via": "protocolo del navegador"}
        ultimo_aviso = ("por el protocolo salió un PNG de %d bytes"
                        % (len(datos) if datos else 0))
        avisar("  %s; probando con la bandera de siempre" % ultimo_aviso)

    for intento in range(1, 4):
        if os.path.exists(ruta_png):
            try:
                os.remove(ruta_png)
            except OSError:
                pass
        cmd = [exe, "--headless", "--disable-gpu", f"--window-size={int(ancho)},{int(alto)}",
               f"--screenshot={ruta_png}", url]
        try:
            subprocess.run(cmd, capture_output=True, timeout=45)
        except Exception as e:
            ultimo_aviso = f"{type(e).__name__} {e}"
            avisar(f"  intento {intento}/3: {ultimo_aviso}")
            if intento < 3:
                time.sleep(1.5)
            continue
        tam = os.path.getsize(ruta_png) if os.path.exists(ruta_png) else 0
        if tam >= UMBRAL_PNG_OK:
            return {"segundos": round(time.time() - t0, 2), "intentos": intento,
                "bytes": tam, "via": "bandera --screenshot"}
        ultimo_aviso = f"PNG de {tam} bytes (por debajo de {UMBRAL_PNG_OK}: puede estar en blanco)"
        avisar(f"  intento {intento}/3: {ultimo_aviso}")
        if intento < 3:
            time.sleep(1.5)
    tam = os.path.getsize(ruta_png) if os.path.exists(ruta_png) else 0
    if tam <= 0:
        raise RuntimeError(f"no se obtuvo ningún PNG tras 3 intentos ({ultimo_aviso})")
    return {"segundos": round(time.time() - t0, 2), "intentos": 3, "bytes": tam, "aviso": ultimo_aviso}


# ───────────────────────────────── API pública ─────────────────────────────────

def renderizar(entrada, html=None, png=None, explosion=0.0, ancho=1600, alto=900,
               camara=None, mirar=None, fondo=None, luz="neutra", holograma=False,
               acabado="mate", avisar=print, navegador=None):
    """Lee `entrada` (glb/gltf/obj/stl/escena.json), escribe SIEMPRE una página HTML
    autocontenida (`html`: ruta exacta si es una cadena; si no — `None` o `True`, para la
    bandera `--html` sin valor — `<carpeta_de_entrada>/<base>_render3d.html`) y, si `png`
    no es `None`, además una captura vía navegador sin cabeza (mismo criterio de ruta con
    `_render3d.png`; lanza `SinNavegador` si no se encuentra ninguno).

    `camara`/`mirar`: `"x,y,z"` o `[x,y,z]`; si no se dan, se usa la `camara` de
    `escena.json` (si la trae) y si tampoco, un encuadre automático a 3/4 sobre el centro
    de toda la escena. `fondo`: `"#rrggbb"` (por defecto `#15151a`; ignorado, forzado a
    `#000000`, si `holograma=True` — ver docstring del módulo). `luz`: calida/fria/neutra.
    `holograma`: cuatro cuadrantes espejados sobre negro (Pepper's ghost, T4.4). `acabado`:
    `mate` (por defecto) o `estudio` (metal con reflejos, entorno procedural, sombras suaves,
    suelo oscuro, sin rejilla al arrancar — ver docstring del módulo).

    Devuelve un dict con `html`, `png` (o `None`), `piezas`, `grupos`, `centro`, `radio`, y
    -si hubo `--png`- `segundos_png`/`intentos_png`/`bytes_png` (y `aviso` si el PNG final
    quedó por debajo del umbral tras los 3 intentos)."""
    ruta_entrada = os.path.abspath(entrada)
    piezas, camara_json, unidades = cargar_entrada(ruta_entrada, avisar=avisar)

    for p in piezas:
        if not p.get("grupo"):
            p["grupo"] = p["nombre"]  # sin grupo declarado: cada pieza es su propio grupo (no explosiona con nada)

    centro, radio = _bbox_escena(piezas)

    def _vec(v):
        if v is None:
            return None
        if isinstance(v, str):
            return [float(x) for x in v.split(",")]
        return [float(x) for x in v]

    pos_cam = _vec(camara) or (camara_json or {}).get("pos")
    mirar_v = _vec(mirar) or (camara_json or {}).get("mirar")
    fov = (camara_json or {}).get("fov", 50)
    fondo_final = "#000000" if holograma else (fondo or "#15151a")
    luz_final = luz if luz in ("calida", "fria", "neutra") else "neutra"
    acabado_final = acabado if acabado in ("mate", "estudio") else "mate"

    base = os.path.splitext(os.path.basename(ruta_entrada))[0]
    carpeta = os.path.dirname(ruta_entrada) or "."
    ruta_html = html if isinstance(html, str) else os.path.join(carpeta, f"{base}_render3d.html")

    escena_embebida = {
        "ancho": int(ancho), "alto": int(alto), "fondo": fondo_final, "luz": luz_final,
        "acabado": acabado_final,
        "centro": centro, "radio": radio, "holograma": bool(holograma),
        "camara": {"pos": pos_cam, "mirar": mirar_v, "fov": fov} if (pos_cam or mirar_v) else None,
        "piezas": [_pieza_embebible(p) for p in piezas],
        "nombre_base": base,
    }
    os.makedirs(os.path.dirname(os.path.abspath(ruta_html)) or ".", exist_ok=True)
    with open(ruta_html, "w", encoding="utf-8") as fh:
        fh.write(_construir_html(escena_embebida, base, float(explosion)))
    avisar(f"html: {ruta_html} ({len(piezas)} piezas)")

    resultado = {
        "html": ruta_html, "png": None, "piezas": len(piezas),
        "grupos": len({p["grupo"] for p in piezas}), "centro": [round(c, 4) for c in centro],
        "radio": round(radio, 4), "unidades": unidades,
    }
    if png is not None:
        ruta_png = png if isinstance(png, str) else os.path.join(carpeta, f"{base}_render3d.png")
        info = _capturar_png(ruta_html, ruta_png, ancho, alto, avisar=avisar, navegador=navegador)
        resultado["png"] = os.path.abspath(ruta_png)
        resultado["segundos_png"] = info["segundos"]
        resultado["intentos_png"] = info["intentos"]
        resultado["bytes_png"] = info["bytes"]
        if "aviso" in info:
            resultado["aviso"] = info["aviso"]
        avisar(f"png: {resultado['png']} ({info['bytes']} bytes, {info['intentos']} intento(s), {info['segundos']} s)")
    return resultado


# ───────────────────────────────── CLI ─────────────────────────────────

def _cli(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 1
    entrada = argv[0]
    opts = {"html": None, "png": None, "explosion": 0.0, "ancho": 1600, "alto": 900,
            "camara": None, "mirar": None, "fondo": None, "luz": "neutra", "holograma": False,
            "acabado": "mate"}
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--holograma":
            opts["holograma"] = True
        elif a == "--html":
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                i += 1
                opts["html"] = argv[i]
        elif a == "--png":
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                i += 1
                opts["png"] = argv[i]
            else:
                opts["png"] = True
        elif a in ("--explosion", "--ancho", "--alto") and i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            i += 1
            clave = a[2:]
            try:
                opts[clave] = float(argv[i]) if clave == "explosion" else int(argv[i])
            except ValueError:
                print(f'--{clave} necesita un número, no "{argv[i]}"')
                return 1
        elif a in ("--camara", "--mirar", "--fondo") and i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            i += 1
            opts[a[2:]] = argv[i]
        elif a == "--luz" and i + 1 < len(argv):
            i += 1
            if argv[i] not in ("calida", "fria", "neutra"):
                print(f'--luz debe ser calida/fria/neutra, no "{argv[i]}"')
                return 1
            opts["luz"] = argv[i]
        elif a == "--acabado" and i + 1 < len(argv):
            i += 1
            if argv[i] not in ("mate", "estudio"):
                print(f'--acabado debe ser mate/estudio, no "{argv[i]}"')
                return 1
            opts["acabado"] = argv[i]
        else:
            print("argumento no reconocido:", a)
            return 1
        i += 1
    try:
        r = renderizar(entrada, **opts)
    except SinNavegador as e:
        print(f"sin dato: {e}")
        return 2
    except Exception as e:
        print(f"sin render: {type(e).__name__} {e}")
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
