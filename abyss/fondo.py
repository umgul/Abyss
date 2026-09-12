# -*- coding: utf-8 -*-
"""Fondo: quitar el fondo de una foto y dejar el objeto recortado, en local y sin subir
nada a ninguna parte.

Uso:
    python fondo.py <imagen> [--salida f.png] [--motor auto|sistema|modelo|grabcut]
                    [--sobre blanco|negro|alfa] [--umbral 0.5] [--listar-motores]

Existe porque `kinetica.py` recorta mejor cuando la foto viene sin fondo: con un fondo de
un solo color la silueta del objeto es exacta y no hay pixeles del objeto que estimar ni
inventar por relleno.

## Tres motores, y cada uno dice quien es

- `sistema` (solo macOS 14 o posterior): el recorte del propio sistema, el mismo que usan
  Vista Previa y Fotos al «levantar el sujeto». Se pide por la biblioteca Vision con
  `VNGenerateForegroundInstanceMaskRequest`, a traves de PyObjC. No baja ningun modelo:
  ya viene con el sistema.
  NO PROBADO: este paquete se ha escrito en Windows. El camino esta completo y falla con
  un mensaje claro si PyObjC no esta o si el sistema es anterior, pero NADIE lo ha visto
  funcionar todavia. Esta declarado asi a proposito y no se presenta como medido.

- `modelo`: una red pequena en formato ONNX (U^2-Net «p») que corre con `onnxruntime` en
  la CPU. Funciona igual en Windows, Linux y macOS. Es el unico camino que hay en
  Windows: el boton «Quitar fondo» de la aplicacion Fotos de Windows no se puede llamar
  desde fuera — no expone ninguna interfaz publica — y la segmentacion que si trae el
  sistema (Windows App SDK) esta reservada a equipos con NPU. Asi que aqui NO se usa nada
  del sistema: se usa este modelo, y se dice.

- `grabcut`: sin descargas y sin modelo, solo OpenCV. Es notablemente peor: separa por
  color y contraste desde un rectangulo, se come los bordes finos y se escapa por los
  reflejos. Esta para que la herramienta nunca se quede sin respuesta, y siempre avisa de
  que el resultado es tosco.

`auto` prueba `sistema`, luego `modelo`, luego `grabcut`, y SIEMPRE imprime cual uso. Nunca
cambia de motor en silencio: un recorte de `grabcut` presentado como si fuera del sistema
seria justo el tipo de engano que este paquete persigue.

Dependencias: numpy y Pillow siempre; `onnxruntime` para el motor `modelo`; `opencv-python`
para `grabcut`; `pyobjc-framework-Vision` para `sistema`. Si falta lo que hace falta, se
dice el comando exacto y se sale con codigo 2, sin traza cruda.
"""
import os
import sys

try:                       # la consola de Windows y la salida tienen que hablar
    from . import consola  # el mismo idioma: ver abyss/consola.py
except ImportError:
    import consola
consola.preparar()
try:
    import numpy as np
    from PIL import Image
except ImportError as e:
    print("sin dato: faltan dependencias basicas (pip install numpy pillow) — %s" % e)
    raise SystemExit(2)

AQUI = os.path.dirname(os.path.abspath(__file__))
MODELO = os.path.join(AQUI, "vendor", "modelos", "u2netp.onnx")
URL_MODELO = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"
LADO = 320  # entrada de U^2-Net p


# ---------------------------------------------------------------- motor: sistema (macOS)
def disponible_sistema():
    if sys.platform != "darwin":
        return False, "el recorte del sistema solo existe en macOS 14 o posterior"
    try:
        import Vision  # noqa: F401
    except ImportError:
        return False, "falta PyObjC (pip install pyobjc-framework-Vision pyobjc-framework-Quartz)"
    try:
        import Vision
        if not hasattr(Vision, "VNGenerateForegroundInstanceMaskRequest"):
            return False, "este macOS no trae VNGenerateForegroundInstanceMaskRequest (hace falta 14+)"
    except Exception as e:
        return False, "PyObjC no responde: %s" % e
    return True, "Vision del sistema (macOS)"


def alfa_sistema(ruta):
    """Mascara 0..1 con el recorte del sistema (ver docstring del modulo)."""
    import Vision
    from Foundation import NSURL
    import Quartz

    url = NSURL.fileURLWithPath_(os.path.abspath(ruta))
    manejador = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, {})
    peticion = Vision.VNGenerateForegroundInstanceMaskRequest.alloc().init()
    ok, err = manejador.performRequests_error_([peticion], None)
    if not ok:
        raise RuntimeError("Vision no pudo procesar la imagen: %s" % err)
    res = peticion.results()
    if not res:
        raise RuntimeError("Vision no encontro ningun sujeto en la imagen")
    obs = res[0]
    buf, err = obs.generateScaledMaskForImageForInstances_fromRequestHandler_error_(
        obs.allInstances(), manejador, None)
    if buf is None:
        raise RuntimeError("Vision devolvio una mascara vacia: %s" % err)
    Quartz.CVPixelBufferLockBaseAddress(buf, 1)
    try:
        w = Quartz.CVPixelBufferGetWidth(buf)
        h = Quartz.CVPixelBufferGetHeight(buf)
        paso = Quartz.CVPixelBufferGetBytesPerRow(buf)
        base = Quartz.CVPixelBufferGetBaseAddress(buf)
        crudo = np.frombuffer(base.as_buffer(paso * h), dtype=np.float32)
        m = crudo.reshape(h, paso // 4)[:, :w]
    finally:
        Quartz.CVPixelBufferUnlockBaseAddress(buf, 1)
    orig = Image.open(ruta).convert("RGB").size
    return np.asarray(Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8))
                      .resize(orig, Image.BILINEAR)).astype(np.float32) / 255.0


# ------------------------------------------------------------------- motor: modelo (ONNX)
def disponible_modelo():
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return False, "falta onnxruntime (pip install onnxruntime)"
    if not os.path.exists(MODELO):
        return False, ("falta el modelo. Bájalo una vez, con red, de %s "
                       "y guárdalo en %s" % (URL_MODELO, MODELO))
    return True, "modelo local U^2-Net p (%d bytes)" % os.path.getsize(MODELO)


def alfa_modelo(ruta):
    """Mascara 0..1 con el modelo ONNX. Este camino SI esta medido en este paquete."""
    import onnxruntime as ort

    im = Image.open(ruta).convert("RGB")
    x = np.asarray(im.resize((LADO, LADO), Image.BILINEAR)).astype(np.float32) / 255.0
    x = (x - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)
    x = x.transpose(2, 0, 1)[None]
    ses = ort.InferenceSession(MODELO, providers=["CPUExecutionProvider"])
    salida = ses.run(None, {ses.get_inputs()[0].name: x})[0]
    m = salida[0, 0]
    m = (m - m.min()) / (m.max() - m.min() + 1e-8)
    return np.asarray(Image.fromarray((m * 255).astype(np.uint8))
                      .resize(im.size, Image.BILINEAR)).astype(np.float32) / 255.0


# ---------------------------------------------------------------------- motor: grabcut
def disponible_grabcut():
    try:
        import cv2  # noqa: F401
    except ImportError:
        return False, "falta OpenCV (pip install opencv-python)"
    return True, "GrabCut de OpenCV (tosco, sin modelo)"


def alfa_grabcut(ruta, iteraciones=5, margen=0.06):
    import cv2

    img = cv2.imread(ruta)
    if img is None:
        raise RuntimeError("no puedo leer %s" % ruta)
    alto, ancho = img.shape[:2]
    mx, my = int(ancho * margen), int(alto * margen)
    mask = np.zeros((alto, ancho), np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(img, mask, (mx, my, ancho - 2 * mx, alto - 2 * my), bgd, fgd,
                iteraciones, cv2.GC_INIT_WITH_RECT)
    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    return cv2.GaussianBlur(fg, (5, 5), 0).astype(np.float32) / 255.0


MOTORES = [("sistema", disponible_sistema, alfa_sistema),
           ("modelo", disponible_modelo, alfa_modelo),
           ("grabcut", disponible_grabcut, alfa_grabcut)]


def listar():
    """[(nombre, disponible, explicacion)] — para decir por que NO se puede usar cada uno."""
    return [(n, ) + d() for n, d, _ in MOTORES]


def quitar(ruta, salida=None, motor="auto", sobre="blanco", umbral=0.5, avisar=print):
    """Escribe `salida` y devuelve {"salida", "motor", "explicacion", "cobertura"}.

    `cobertura` es la fraccion del cuadro que el motor da por objeto: sirve para oler un
    recorte malo (cerca de 0 no encontro nada, cerca de 1 se quedo con todo)."""
    candidatos = MOTORES if motor == "auto" else [m for m in MOTORES if m[0] == motor]
    if not candidatos:
        raise SystemExit("motor desconocido: %s (usa auto/sistema/modelo/grabcut)" % motor)
    for nombre, disponible, funcion in candidatos:
        ok, por_que = disponible()
        if not ok:
            avisar("  %-8s no: %s" % (nombre, por_que))
            continue
        avisar("  %-8s si: %s" % (nombre, por_que))
        m = funcion(ruta)
        break
    else:
        raise SystemExit("sin dato: ningun motor disponible; mira las lineas de arriba, "
                         "cada una dice que le falta")

    im = Image.open(ruta).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    dura = (m >= umbral).astype(np.float32)
    cobertura = float(dura.mean())
    if sobre == "alfa":
        rgba = np.dstack([a, np.clip(m, 0, 1) * 255]).astype(np.uint8)
        img = Image.fromarray(rgba, "RGBA")
        ext = ".png"
    else:
        base = 255.0 if sobre == "blanco" else 0.0
        mez = m[:, :, None]
        img = Image.fromarray((a * mez + base * (1 - mez)).astype(np.uint8), "RGB")
        ext = ".png"
    if salida is None:
        raiz, _ = os.path.splitext(ruta)
        salida = raiz + "_sin_fondo" + ext
    img.save(salida)
    return {"salida": salida, "motor": nombre, "explicacion": por_que,
            "cobertura": round(cobertura, 4)}


def _cli(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 1
    if argv[0] == "--listar-motores":
        for n, ok, por_que in listar():
            print("%-8s %-3s %s" % (n, "si" if ok else "no", por_que))
        return 0
    ruta = argv[0]
    opts = {"salida": None, "motor": "auto", "sobre": "blanco", "umbral": 0.5}
    i = 1
    while i < len(argv):
        a = argv[i]
        for bandera, clave in (("--salida", "salida"), ("--motor", "motor"),
                               ("--sobre", "sobre"), ("--umbral", "umbral")):
            if a == bandera and i + 1 < len(argv):
                opts[clave] = argv[i + 1]
                i += 1
        i += 1
    opts["umbral"] = float(opts["umbral"])
    if not os.path.exists(ruta):
        print("sin dato: no existe %s" % ruta)
        return 2
    print("quitando el fondo de %s" % os.path.basename(ruta))
    try:
        r = quitar(ruta, **opts)
    except SystemExit as e:
        print(e)
        return 2
    print("recorte: %s · motor %s · el objeto ocupa el %.1f%% del cuadro"
          % (r["salida"], r["motor"], 100 * r["cobertura"]))
    if r["motor"] == "grabcut":
        print("aviso: recorte TOSCO (sin modelo). Para uno bueno, baja el modelo "
              "de %s a %s" % (URL_MODELO, MODELO))
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
