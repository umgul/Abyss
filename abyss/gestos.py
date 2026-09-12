# -*- coding: utf-8 -*-
"""Gestos: la mano manda en el holograma — MediaPipe lee 21 puntos por mano y este guion
los convierte en dedos extendidos, apertura de pellizco, pose de la palma y distancia
entre dos manos, servidos por HTTP local para que otra pieza reaccione.

Uso:
    python gestos.py [--camara 0] [--puerto 8799] [--escena f.json] [--holograma]
                      [--vocabulario f.json]

DEPENDENCIA declarada: `mediapipe`. Ausente o roto, `main()`/la CLI dicen EXACTAMENTE qué
instalar y salen con código 2 ANTES de abrir la cámara o levantar el servidor. "Roto" no es
teórico: `mediapipe` puede importar sin error y aun así no traer `mediapipe.solutions`, así
que la comprobación mira el atributo, no solo el `import` (`_mediapipe_utilizable()`). El
módulo en sí SÍ se puede importar sin `mediapipe` (las funciones puras no lo necesitan):
solo `main()`/la CLI comprueban la dependencia y cortan ahí.
La copia que MANDA del vocabulario es `abyss/plantillas/gestos_comun.js`; `kinetica.html`
la importa y este fichero es su ESPEJO en Python, para quien quiera el estado de la mano
desde fuera del navegador (hay que mantenerlo a mano: nada comprueba todavía que los dos
digan lo mismo). El estado sigue igual: este servidor HTTP no lo consume nadie — los
visores kinéticos leen la mano en el navegador con MediaPipe; esto está para el día que
haga falta desde otro proceso.
De una referencia externa (el post de Jhon Jairo Torres sobre gestos con MediaPipe) se toman
TÉCNICAS, nunca su diseño: está PROHIBIDO su vocabulario
de figuritas (una flor, un aguacate...). El de este paquete es PROPIO (tabla abajo) y la
mano no invoca objetos: MANEJA la escena de despiece que ya sabe abrir `render3d.py`.
- Dedo extendido: distancia(punta, muñeca) > `ratio_dedo_extendido` (1,7 por defecto,
  heredado tal cual, no una medida propia todavía). Pose de la palma: `cv2.solvePnP`
  contra un modelo plano NOMINAL; `None` si falta `cv2`, algún punto, o si no converge.
- Pellizco y distancia entre manos: normalizados por los percentiles 10/90 de TODAS las
  lecturas de ESTA sesión (`NormalizadorPercentil`); con menos de `muestras_para_vara`
  lecturas (30 por defecto) el campo `vara_*` dice «sin vara todavía (n=…)» y el valor se
  queda en 0,5 en vez de fingir un corte sobre pocas muestras. Calibración
  (`segundos_calibracion_inicial`, 5 por defecto de mano libre): sugerencia en pantalla,
  no una puerta — la puerta real es el conteo de muestras.
- Suavizado: filtro One Euro (Casiez, Roussel y Vogel 2012) por coordenada de cada uno de los
  21 puntos, antes de calcular
  dedos/pellizco/pose/distancia. Nada se muestra hasta que el gesto está completo: un
  fotograma sin una mano con exactamente 21 puntos se descarta ENTERO; el estado se queda
  en su último valor bueno.
Vocabulario PROPIO, cambiable por fichero (`--vocabulario f.json`; este guion no lo busca
solo, se le pasa la ruta):

| gesto de la mano                | qué mueve en la escena                | campo en `/estado`   |
|-----------------------------------|-----------------------------------------|-------------------------|
| nº de dedos extendidos            | aísla capas: 0 todas, 1 la primera…      | `capas_visibles`        |
| pellizco (pulgar-índice)          | desliza la explosión                    | `pellizco`/`explosion`  |
| pose de la palma (`solvePnP`)     | orbita la cámara (giro/inclinación)     | `orbita`                |
| mano abierta y quieta ≥1 s        | captura PNG de lo que se ve             | `gesto_completado`      |
| dos manos                         | escala por la distancia entre ellas     | `escala`                |

`capas_visibles`/`escala`/`orbita` solo se actualizan con un fotograma completo, y
`gesto_completado` solo vale `"captura"` durante el fotograma que dispara — nunca queda
pegado avisando de una captura vieja.
Servidor SOLO en `127.0.0.1` (nunca `0.0.0.0`): `GET /estado` (ver `ESTADO_INICIAL` para la
forma completa) y `GET /health` -> `{"ok": true}`. Con `--escena f.json`, lee sus grupos
(mismo `escena.json` de `render3d.py`/`volumen.py`) y arranca con `capas_visibles`=TODAS.
`--holograma` solo viaja como un campo más del estado; ESTE guion no dibuja nada.
Límite declarado: este paquete no hace que la página de `render3d.py` lea este `/estado` y
reaccione (mover cámara/capas/zoom) — sirve el JSON correcto y probado, con el vocabulario
ya resuelto en cada campo; conectarlo a la página es trabajo pendiente, declarado, no
prometido como hecho. Sin gancho: no escribe en `mem`, no resuelve un proyecto de Claude
Code, la cámara se abre porque este guion se invoca a mano, nunca desde un hook.
"""
import json
import math
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    import mediapipe as mp
except ImportError:
    mp = None

PUERTO_POR_DEFECTO = 8799
WRIST = 0
# (nombre, índice de nudillo/MCP, índice de la punta) — numeración estándar de MediaPipe Hands
# (0=muñeca; pulgar 1-4; índice 5-8; corazón 9-12; anular 13-16; meñique 17-20).
DEDOS = (
    ('pulgar', 2, 4),
    ('indice', 5, 8),
    ('corazon', 9, 12),
    ('anular', 13, 16),
    ('menique', 17, 20),
)
RATIO_EXTENDIDO_HEREDADO = 1.7  # de una referencia externa (ver docstring), no medido aquí todavía
MUESTRAS_PARA_VARA = 30         # por debajo de esto, «sin vara todavía (n=…)»

VOCABULARIO_POR_DEFECTO = {
    'ratio_dedo_extendido': RATIO_EXTENDIDO_HEREDADO,
    'percentil_bajo': 10,
    'percentil_alto': 90,
    'muestras_para_vara': MUESTRAS_PARA_VARA,
    'segundos_calibracion_inicial': 5.0,
    'segundos_captura_quieta': 1.0,
    'umbral_movimiento_quieta': 0.04,  # unidades normalizadas de MediaPipe (0..1 del ancho/alto)
}

ESTADO_INICIAL = {
    'dedos': None, 'dedos_extendidos': None,
    'pellizco_bruto': None, 'pellizco': None, 'explosion': None, 'vara_pellizco': None,
    'pose': None, 'orbita': None,
    'manos': 0, 'escala': None, 'vara_escala': None,
    'grupos': None, 'capas_visibles': None, 'gesto_completado': None,
    'holograma': False, 'muestras': 0,
}


def _mediapipe_utilizable():
    """`import mediapipe` puede tener éxito y aun así dejar un módulo inservible (sin
    `mediapipe.solutions`, `AttributeError` dentro de `crear_detector()`): comprobar solo
    `mp is None` no basta. `main()` trata este caso igual que "falta mediapipe" y corta
    ANTES de abrir la cámara o levantar el servidor, nunca a mitad de fotograma."""
    return mp is not None and hasattr(mp, 'solutions') and hasattr(mp.solutions, 'hands')


def mensaje_dependencias():
    faltan = []
    if mp is None:
        faltan.append('  - pip install mediapipe')
    elif not _mediapipe_utilizable():
        faltan.append('  - pip install --upgrade --force-reinstall mediapipe  '
                       '(mediapipe está instalado pero sin mediapipe.solutions: versión rota en esta máquina)')
    if cv2 is None:
        faltan.append('  - pip install opencv-python')
    return ('gestos.py necesita paquetes que no están instalados en esta máquina:\n'
            + '\n'.join(faltan) + '\nNo se instala nada por su cuenta.')


# ───────────────────────────────── vocabulario propio, cambiable por fichero ─────────────────────────────────

def cargar_vocabulario(ruta=None):
    """Vocabulario PROPIO de este paquete (tabla completa en el docstring del módulo),
    partiendo de `VOCABULARIO_POR_DEFECTO`. Con `ruta`, MEZCLA sobre esos valores solo las
    claves que el fichero declare (JSON plano `clave: número`) — las que no toque se
    quedan con su valor por defecto. Fichero inexistente o JSON inválido/no-objeto:
    `ValueError` con el motivo (fail-closed: lo atrapa la CLI y sale con código 2, nunca
    sigue con un vocabulario a medio cargar)."""
    vocab = dict(VOCABULARIO_POR_DEFECTO)
    if not ruta:
        return vocab
    try:
        with open(ruta, encoding='utf-8') as fh:
            propio = json.load(fh)
    except (OSError, ValueError) as e:
        raise ValueError(f'no se pudo leer "{ruta}" ({type(e).__name__}: {e})') from e
    if not isinstance(propio, dict):
        raise ValueError(f'"{ruta}" debe ser un objeto JSON de clave: número, no {type(propio).__name__}')
    vocab.update(propio)
    return vocab


# ───────────────────────────────── geometría de la mano (puras, sin mediapipe) ─────────────────────────────────

def _dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(min(len(a), len(b)))))


def dedos_extendidos(puntos, ratio=RATIO_EXTENDIDO_HEREDADO):
    """{'pulgar': bool, 'indice': bool, 'corazon': bool, 'anular': bool, 'menique': bool}:
    extendido si distancia(punta, muñeca) > `ratio` × distancia(nudillo, muñeca) — una
    RAZÓN, invariante a lo grande que salga la mano en el encuadre (ver docstring del
    módulo). `puntos` son 21 (x, y[, z]), en el orden de MediaPipe Hands."""
    wrist = puntos[WRIST]
    salida = {}
    for nombre, nudillo, punta in DEDOS:
        d_nudillo = _dist(puntos[nudillo], wrist)
        d_punta = _dist(puntos[punta], wrist)
        salida[nombre] = bool(d_nudillo > 0 and (d_punta / d_nudillo) > ratio)
    return salida


def apertura_pellizco_bruta(puntos):
    """Distancia pulgar(4)-índice(8), SIN normalizar (eso lo hace `NormalizadorPercentil`
    con los percentiles de la sesión: cada mano y cada cámara dan una escala distinta, un
    umbral fijo en esta función sería un número inventado)."""
    return _dist(puntos[4], puntos[8])


def distancia_entre_manos(manos_puntos):
    """Distancia entre las muñecas (punto 0) de las DOS primeras manos de
    `manos_puntos` — "dos manos = escala". `None` con menos de dos manos."""
    if len(manos_puntos) < 2:
        return None
    return _dist(manos_puntos[0][WRIST], manos_puntos[1][WRIST])


def capas_visibles_por_dedos(grupos, n_dedos):
    """"número de dedos = qué capa del despiece se aísla": 0 dedos → TODAS las
    capas; 1 → solo la primera; 2 → las dos primeras… hasta el total de `grupos` (pedir
    más dedos que capas no revienta: satura al total, nunca inventa una capa de más).
    `None` si no hay ninguna escena cargada (`grupos` es `None`)."""
    if grupos is None:
        return None
    if not n_dedos:
        return list(grupos)
    return list(grupos[:min(n_dedos, len(grupos))])


def orbita_de_pose(pose):
    """"pose de la palma = órbita de la cámara": el MISMO número que da
    `pose_palma()`, con los dos nombres que usa una órbita de cámara (`giro`=yaw,
    `inclinacion`=pitch) en vez de los de una IMU (roll/pitch/yaw) — ningún cálculo
    nuevo, un vocabulario propio sobre el mismo dato. `None` si no hay pose."""
    if pose is None:
        return None
    return {'giro': pose['yaw'], 'inclinacion': pose['pitch']}


class NormalizadorPercentil:
    """Normaliza un valor en vivo contra los percentiles 10/90 de TODO lo visto hasta ahora
    en esta sesión (mismo patrón de cortes propios por percentil que `propiocepcion.py`/
    `vigia.py`, aplicado aquí a una señal continua en vez de a un conteo por sesión): 0,0 en
    el percentil 10 o por debajo, 1,0 en el percentil 90 o por encima, lineal entre medias.

    Arranque en frío: con menos de `minimo` muestras (30 por defecto, vocabulario
    `muestras_para_vara`) no hay distribución que valga — `normalizar()` devuelve 0,5 (ni
    un extremo ni el otro) en vez de fingir un corte sobre un puñado de lecturas, y
    `descripcion()` lo dice: «sin vara todavía (n=…)» (mismo patrón de aviso que
    `propiocepcion.UMBRAL_FRIO`)."""

    def __init__(self, minimo=MUESTRAS_PARA_VARA):
        self.valores = []
        self.minimo = minimo

    def actualizar(self, valor):
        self.valores.append(float(valor))

    @staticmethod
    def _percentil(valores_ordenados, p):
        n = len(valores_ordenados)
        if n == 1:
            return valores_ordenados[0]
        k = (p / 100.0) * (n - 1)
        f, c = math.floor(k), math.ceil(k)
        if f == c:
            return valores_ordenados[int(k)]
        return valores_ordenados[f] + (valores_ordenados[c] - valores_ordenados[f]) * (k - f)

    def normalizar(self, valor, percentil_bajo=10, percentil_alto=90):
        if len(self.valores) < self.minimo:
            return 0.5
        ordenados = sorted(self.valores)
        p_bajo = self._percentil(ordenados, percentil_bajo)
        p_alto = self._percentil(ordenados, percentil_alto)
        if p_alto <= p_bajo:
            return 0.5
        return max(0.0, min(1.0, (valor - p_bajo) / (p_alto - p_bajo)))

    def descripcion(self):
        """`None` si ya hay vara (≥ `self.minimo` muestras); si no, "sin vara todavía
        (n=N)" — para mostrar en pantalla o en el estado servido, nunca en silencio."""
        n = len(self.valores)
        if n >= self.minimo:
            return None
        return f'sin vara todavía (n={n})'


class FiltroUnaEuro:
    """Filtro One Euro (Casiez, Roussel y Vogel, 2012): poco retraso en movimientos rápidos,
    mucho suavizado en los lentos — el temblor de la mano quieta desaparece sin que un
    gesto rápido llegue perceptiblemente tarde. Un filtro por CANAL (una coordenada x/y/z
    de un punto de UNA mano): `gestos.py` mantiene uno por (mano, índice de punto, eje)."""

    def __init__(self, mincutoff=1.0, beta=0.0, dcutoff=1.0):
        self.mincutoff = mincutoff
        self.beta = beta
        self.dcutoff = dcutoff
        self._x_prev = None
        self._dx_prev = 0.0
        self._t_prev = None

    @staticmethod
    def _alfa(corte, dt):
        tau = 1.0 / (2 * math.pi * corte)
        return 1.0 / (1.0 + tau / dt)

    def filtrar(self, x, t=None):
        t = t if t is not None else time.time()
        if self._t_prev is None:
            self._x_prev, self._dx_prev, self._t_prev = x, 0.0, t
            return x
        dt = max(1e-6, t - self._t_prev)
        dx = (x - self._x_prev) / dt
        a_d = self._alfa(self.dcutoff, dt)
        dx_hat = a_d * dx + (1 - a_d) * self._dx_prev
        corte = self.mincutoff + self.beta * abs(dx_hat)
        a = self._alfa(corte, dt)
        x_hat = a * x + (1 - a) * self._x_prev
        self._x_prev, self._dx_prev, self._t_prev = x_hat, dx_hat, t
        return x_hat


class DetectorCapturaPorQuietud:
    """"Mano abierta y quieta un segundo = capturar PNG": sigue, fotograma a
    fotograma, si los 5 dedos están extendidos Y la muñeca apenas se mueve; cuando eso
    dura ≥ `segundos` (parámetro del vocabulario `segundos_captura_quieta`) declara el
    gesto `"captura"` UNA sola vez — mientras la mano se mantenga abierta y quieta no
    vuelve a dispararse, para no repetir la captura en cada fotograma siguiente (nada en
    pantalla se adelanta a un gesto sin terminar, y una captura repetida cada fotograma
    tampoco sería honesta con "un gesto completado")."""

    def __init__(self, segundos=1.0, umbral_movimiento=0.04):
        self.segundos = segundos
        self.umbral_movimiento = umbral_movimiento
        self._inicio = None
        self._pos_inicio = None
        self._disparado = False

    def actualizar(self, dedos_extendidos_n, muneca_xy, t):
        """`dedos_extendidos_n` (0-5), `muneca_xy` (x, y) del punto 0 de la mano
        PRINCIPAL de este fotograma, `t` el instante (segundos, `time.time()`).
        Devuelve `"captura"` exactamente en el fotograma que dispara, si no `None`."""
        if dedos_extendidos_n != 5:
            self._inicio = None
            self._pos_inicio = None
            self._disparado = False
            return None
        if self._inicio is None:
            self._inicio, self._pos_inicio, self._disparado = t, muneca_xy, False
            return None
        dx = muneca_xy[0] - self._pos_inicio[0]
        dy = muneca_xy[1] - self._pos_inicio[1]
        if math.hypot(dx, dy) > self.umbral_movimiento:
            # se movió más de la cuenta: la quietud empieza a contar de nuevo desde aquí
            self._inicio, self._pos_inicio, self._disparado = t, muneca_xy, False
            return None
        if not self._disparado and (t - self._inicio) >= self.segundos:
            self._disparado = True
            return 'captura'
        return None


# ───────────────────────────────── pose de la palma (cv2.solvePnP) ─────────────────────────────────

_IDX_MODELO_PALMA = (0, 5, 9, 17)  # muñeca, nudillo índice, nudillo corazón, nudillo meñique


def _modelo_palma():
    # Proporciones relativas NOMINALES entre esos 4 puntos (no es una medida de ninguna
    # mano real: solo fija una forma plausible para que solvePnP tenga qué resolver).
    return np.array([
        [0.0, 0.0, 0.0],
        [-1.0, 2.0, 0.0],
        [0.2, 2.3, 0.0],
        [1.5, 1.6, 0.0],
    ], dtype=np.float64)


def pose_palma(puntos, ancho, alto):
    """Orientación aproximada de la palma (`cv2.solvePnP`), o `None` si falta `cv2`/`numpy`,
    si `puntos` no trae los 21, o si `solvePnP` no converge. Cámara sin calibrar (focal ≈
    ancho del fotograma, centro óptico en el centro): ver límites en el docstring del
    módulo — es una orientación aproximada, no una medida angular calibrada."""
    if cv2 is None or np is None or puntos is None or len(puntos) < 21:
        return None
    try:
        img_pts = np.array([[puntos[i][0] * ancho, puntos[i][1] * alto] for i in _IDX_MODELO_PALMA], dtype=np.float64)
        foco = float(ancho)
        camara = np.array([[foco, 0.0, ancho / 2.0], [0.0, foco, alto / 2.0], [0.0, 0.0, 1.0]])
        ok, rvec, _tvec = cv2.solvePnP(_modelo_palma(), img_pts, camara, np.zeros((4, 1)))
        if not ok:
            return None
        rot, _ = cv2.Rodrigues(rvec)
        sy = math.sqrt(rot[0, 0] ** 2 + rot[1, 0] ** 2)
        if sy < 1e-6:
            x = math.atan2(-rot[1, 2], rot[1, 1])
            y = math.atan2(-rot[2, 0], sy)
            z = 0.0
        else:
            x = math.atan2(rot[2, 1], rot[2, 2])
            y = math.atan2(-rot[2, 0], sy)
            z = math.atan2(rot[1, 0], rot[0, 0])
        return {'roll': round(math.degrees(x), 1), 'pitch': round(math.degrees(y), 1), 'yaw': round(math.degrees(z), 1)}
    except Exception:
        return None


# ───────────────────────────────── MediaPipe: extracción de puntos ─────────────────────────────────

def crear_detector(max_manos=2, confianza_deteccion=0.6, confianza_seguimiento=0.6):
    return mp.solutions.hands.Hands(static_image_mode=False, max_num_hands=max_manos,
                                     min_detection_confidence=confianza_deteccion,
                                     min_tracking_confidence=confianza_seguimiento)


def manos_de_resultado(resultado, maximo=2):
    """Lista de hasta `maximo` manos, cada una sus 21 puntos (x, y, z) normalizados, de
    `resultado` (`mediapipe.solutions.hands.Hands().process(...)`). Una mano con un
    número de puntos distinto de 21 se DESCARTA individualmente — no se rellena ni se
    adivina (ver "nada se muestra hasta que el gesto está completo" en el docstring del
    módulo); las demás manos válidas del mismo fotograma sí cuentan. Lista vacía si no
    hay ninguna mano, o ninguna es válida."""
    manos = getattr(resultado, 'multi_hand_landmarks', None) or []
    salida = []
    for mano in manos[:maximo]:
        landmarks = getattr(mano, 'landmark', None)
        if landmarks and len(landmarks) == 21:
            salida.append([(p.x, p.y, getattr(p, 'z', 0.0)) for p in landmarks])
    return salida


def puntos_de_resultado(resultado):
    """Los 21 puntos de la PRIMERA mano válida de `resultado`, o `None` si no hay ninguna
    (sin mano, o ninguna con exactamente 21 puntos) — ver `manos_de_resultado()`."""
    manos = manos_de_resultado(resultado, maximo=1)
    return manos[0] if manos else None


def procesar_puntos(puntos, ancho, alto, normalizador_pellizco, ratio=RATIO_EXTENDIDO_HEREDADO):
    """A partir de 21 puntos YA completos de la mano PRINCIPAL (y ya suavizados por quien
    llama, ver `main()`): dedos extendidos, apertura de pellizco (bruta y normalizada,
    con su alias `explosion` — vocabulario propio, ver docstring del módulo), pose de la
    palma y su alias `orbita`."""
    dedos = dedos_extendidos(puntos, ratio=ratio)
    bruto = apertura_pellizco_bruta(puntos)
    normalizador_pellizco.actualizar(bruto)
    pellizco = round(normalizador_pellizco.normalizar(bruto), 4)
    pose = pose_palma(puntos, ancho, alto)
    return {
        'dedos': dedos,
        'dedos_extendidos': sum(1 for v in dedos.values() if v),
        'pellizco_bruto': round(bruto, 5),
        'pellizco': pellizco,
        'explosion': pellizco,  # alias: "pellizco = deslizador de explosión"
        'vara_pellizco': normalizador_pellizco.descripcion(),
        'pose': pose,
        'orbita': orbita_de_pose(pose),
    }


def procesar_fotograma(manos_puntos, ancho, alto, normalizador_pellizco, normalizador_escala,
                        ratio=RATIO_EXTENDIDO_HEREDADO):
    """Un fotograma YA reducido a 0-2 manos (`manos_de_resultado()`), con el vocabulario
    propio de este paquete ya resuelto (tabla del docstring del módulo). Devuelve `None`
    si NO hay ninguna mano completa — quien llama debe entonces dejar el estado servido
    TAL COMO ESTABA, nunca sobreescribirlo con este `None` ("nada se muestra hasta que el
    gesto está completo"). Con al menos una mano, la PRIMERA es la principal (dedos,
    pellizco, pose/órbita); con dos, además calcula `escala` por la distancia entre
    ambas muñecas."""
    if not manos_puntos:
        return None
    info = procesar_puntos(manos_puntos[0], ancho, alto, normalizador_pellizco, ratio=ratio)
    info['manos'] = len(manos_puntos)
    dist = distancia_entre_manos(manos_puntos)
    if dist is None:
        info['escala'] = None
        info['vara_escala'] = None
    else:
        normalizador_escala.actualizar(dist)
        info['escala'] = round(normalizador_escala.normalizar(dist), 4)
        info['vara_escala'] = normalizador_escala.descripcion()
    return info


def _grupos_de_escena(ruta):
    with open(ruta, encoding='utf-8') as fh:
        datos = json.load(fh)
    grupos = []
    for p in (datos.get('piezas') or []):
        g = p.get('grupo') or p.get('nombre')
        if g and g not in grupos:
            grupos.append(g)
    return grupos


# ───────────────────────────────── servidor HTTP (SOLO 127.0.0.1) ─────────────────────────────────

def construir_servidor(puerto, estado, cerrojo):
    """`ThreadingHTTPServer` ligado a `127.0.0.1` — NUNCA `0.0.0.0` (ver docstring del
    módulo). `estado` es el dict COMPARTIDO que el bucle de `main()` va actualizando bajo
    `cerrojo`; el manejador solo lee, con el mismo cerrojo, para no servir un estado a
    medio escribir."""
    class Handler(BaseHTTPRequestHandler):
        def _json(self, cuerpo, codigo=200):
            datos = json.dumps(cuerpo, ensure_ascii=False).encode('utf-8')
            self.send_response(codigo)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def do_GET(self):
            if self.path in ('/estado', '/'):
                with cerrojo:
                    self._json(dict(estado))
            elif self.path == '/health':
                self._json({'ok': True})
            else:
                self._json({'error': 'ruta desconocida'}, 404)

        def log_message(self, *a):
            pass  # silencio: por stdout solo va el aviso de arranque

    return ThreadingHTTPServer(('127.0.0.1', puerto), Handler)


# ───────────────────────────────── bucle principal ─────────────────────────────────

def _abrir_camara(indice):
    if os.name == 'nt':
        cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
        if cap.isOpened():
            return cap
    return cv2.VideoCapture(indice)


def main(opts):
    if not _mediapipe_utilizable() or cv2 is None or np is None:
        # Cortar AQUÍ, antes de tocar cámara o servidor: un mediapipe ausente o roto
        # (ver `_mediapipe_utilizable()`) no debe dejar encender la webcam ni levantar el
        # HTTP para luego reventar a mitad de fotograma en `crear_detector()`.
        print(mensaje_dependencias())
        return 2

    try:
        vocabulario = cargar_vocabulario(opts.get('vocabulario'))
    except ValueError as e:
        print(f'sin dato: {e}')
        return 2

    grupos = None
    if opts.get('escena'):
        try:
            grupos = _grupos_de_escena(opts['escena'])
        except (OSError, ValueError) as e:
            print(f'sin dato: no se pudo leer la escena ({type(e).__name__}: {e})')
            return 2

    cap = _abrir_camara(opts['camara'])
    if not cap.isOpened():
        print(f'cámara {opts["camara"]} no disponible')
        return 2

    cerrojo = threading.Lock()
    estado = dict(ESTADO_INICIAL)
    estado['holograma'] = bool(opts.get('holograma'))
    if grupos:
        estado['grupos'] = grupos
        estado['capas_visibles'] = list(grupos)  # 0 dedos todavía: todas visibles

    servidor = construir_servidor(opts['puerto'], estado, cerrojo)
    puerto_real = servidor.server_address[1]
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    print(f'[gestos] escuchando en http://127.0.0.1:{puerto_real}')
    print(f'[gestos] calibrando ~{vocabulario["segundos_calibracion_inicial"]:.0f}s: mueve '
          f'los dedos y el pellizco libremente para medir tu propia vara '
          f'(sin vara todavía hasta {vocabulario["muestras_para_vara"]} muestras)')
    sys.stdout.flush()

    detector = crear_detector(max_manos=2)
    normalizador_pellizco = NormalizadorPercentil(minimo=vocabulario['muestras_para_vara'])
    normalizador_escala = NormalizadorPercentil(minimo=vocabulario['muestras_para_vara'])
    detector_captura = DetectorCapturaPorQuietud(
        segundos=vocabulario['segundos_captura_quieta'],
        umbral_movimiento=vocabulario['umbral_movimiento_quieta'])
    filtros = {}

    def suavizar_mano(mano_idx, puntos, t):
        salida = []
        for i, p in enumerate(puntos):
            fila = []
            for eje, valor in enumerate(p):
                clave = (mano_idx, i, eje)
                if clave not in filtros:
                    filtros[clave] = FiltroUnaEuro()
                fila.append(filtros[clave].filtrar(valor, t))
            salida.append(tuple(fila))
        return salida

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            alto, ancho = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            resultado = detector.process(rgb)
            manos = manos_de_resultado(resultado)
            if not manos:
                continue  # gesto incompleto: se queda con el último estado bueno
            t = time.time()
            manos_suaves = [suavizar_mano(i, m, t) for i, m in enumerate(manos)]
            info = procesar_fotograma(manos_suaves, ancho, alto, normalizador_pellizco,
                                       normalizador_escala, ratio=vocabulario['ratio_dedo_extendido'])
            if info is None:
                continue
            gesto = detector_captura.actualizar(info['dedos_extendidos'], manos_suaves[0][WRIST][:2], t)
            with cerrojo:
                estado.update(info)
                estado['gesto_completado'] = gesto
                estado['muestras'] = estado.get('muestras', 0) + 1
                if grupos:
                    estado['capas_visibles'] = capas_visibles_por_dedos(grupos, info['dedos_extendidos'])
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        servidor.shutdown()
        servidor.server_close()
    return 0


def _parsear_argv(argv):
    """(opts, error_o_None). Solo interpreta banderas — no toca cámara ni `mediapipe`, así
    se puede probar sin ninguna de las dos (`main()` sí las necesita, esto no)."""
    opts = {'camara': 0, 'puerto': PUERTO_POR_DEFECTO, 'escena': None, 'holograma': False, 'vocabulario': None}
    con_valor = {'--camara': 'camara', '--puerto': 'puerto', '--escena': 'escena', '--vocabulario': 'vocabulario'}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in con_valor and i + 1 < len(argv):
            i += 1
            clave = con_valor[a]
            if clave in ('camara', 'puerto'):
                try:
                    opts[clave] = int(argv[i])
                except ValueError:
                    return None, f'--{clave} necesita un número, no "{argv[i]}"'
            else:
                opts[clave] = argv[i]
        elif a == '--holograma':
            opts['holograma'] = True
        else:
            return None, f'argumento no reconocido: {a} (usa --camara/--puerto/--escena/--holograma/--vocabulario)'
        i += 1
    return opts, None


def _cli(argv):
    if argv and argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    opts, error = _parsear_argv(argv)
    if error:
        print(error)
        return 1
    return main(opts)


if __name__ == '__main__':
    try:                       # la consola de Windows y la salida tienen que hablar
        from . import consola  # el mismo idioma: ver abyss/consola.py
    except ImportError:
        import consola
    consola.preparar()
    sys.exit(_cli(sys.argv[1:]))
