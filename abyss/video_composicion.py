# -*- coding: utf-8 -*-
"""Vídeo del PROCESO para las composiciones de `lienzo.py` (`cubista`/`surrealista`) —
hermano de `video_pintura.py`, pero para efectos que NO son pinceladas: en vez de un
`.json.gz` de trazos, la entrada es una carpeta de fotogramas de PASOS ya renderizados
(`paso_000.png`, `paso_001.png`, ...) por `lienzo.py cubista --pasos N --pasos-dir DIR` o
`lienzo.py surrealista --pasos N --pasos-dir DIR`.

Por qué esto no reutiliza `video_pintura.py`: ese guion pesa el ritmo por el RADIO y la
CANTIDAD de pinceladas de cada capa (despacio con el pincel gordo, rápido en el relleno,
despacio otra vez en el detalle fino) — una métrica que solo existe porque cada paso ahí es
UNA pincelada. Aquí cada paso YA es una imagen entera compuesta por `cubista()`/
`surrealista()`: no hay pinceladas ni radios que pesar, así que el ritmo es sencillo —
reparto igual entre pasos, con un `hold` fijo al principio (se ve el primer paso quieto un
momento, para que el ojo llegue) y al final (el cuadro acabado, quieto, para que dé tiempo a
leerlo) — mismos parámetros de codificación de ffmpeg que `video_pintura.py`/`pintor.py`
(`libx264 -crf 18 -preset medium -pix_fmt yuv420p -movflags +faststart`), para que los tres
tipos de vídeo del paquete salgan con el mismo aspecto técnico.

Uso:
    python video_composicion.py <pasos_dir> <salida.mp4> [--segundos 8] [--fps 30]
                                [--hold-ini 0.6] [--hold-fin 1.6] [--ancho N]

Sin `--ancho`, se usa el ancho nativo del primer fotograma de `pasos_dir` (todos deben medir
igual: si no, RuntimeError con la ruta y la medida de cuál difiere, en vez de deformar
ninguno para que encaje).

Depende de Pillow e imageio_ffmpeg (las mismas dos de `video_pintura.py`; ver su docstring).
Si falta imageio_ffmpeg, o `pasos_dir` no tiene ningún `paso_*.png`, o los pasos no miden
todos igual, la CLI imprime «sin video: <motivo>» y sale con código 2 (no revienta con una
traza).
"""
import glob
import json
import os
import subprocess
import sys

from PIL import Image


def video(pasos_dir, salida, segundos=8.0, fps=30, hold_ini=0.6, hold_fin=1.6, ancho=None, avisar=print):
    """Escribe `salida` (mp4) a partir de los `paso_*.png` de `pasos_dir` (orden alfabético
    = orden de numeración, que es como los escribe `lienzo._escribir_pasos`). Devuelve
    {"mp4", "duracion", "W", "H", "frames", "pasos"}."""
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise RuntimeError(f"falta imageio_ffmpeg (pip install imageio-ffmpeg): {e}")

    rutas = sorted(glob.glob(os.path.join(pasos_dir, 'paso_*.png')))
    if not rutas:
        raise RuntimeError(f"sin pasos: ningún 'paso_*.png' en {pasos_dir}")

    imagenes = [Image.open(r).convert('RGB') for r in rutas]
    W0, H0 = imagenes[0].size
    for r, im in zip(rutas, imagenes):
        if im.size != (W0, H0):
            raise RuntimeError(f"{r} mide {im.size}, el primer paso {(W0, H0)}: todos los "
                                f"pasos deben medir igual (lienzo.py ya los escribe así)")

    if ancho:
        s = float(ancho) / W0
        W, H = int(ancho), int(round(H0 * s))
    else:
        W, H = W0, H0
    if W % 2:
        W += 1
    if H % 2:
        H += 1

    cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
           "-preset", "medium", "-movflags", "+faststart", os.path.abspath(salida)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def _fotograma(im):
        if im.size != (W, H):
            im = im.resize((W, H), Image.LANCZOS)
        proc.stdin.write(im.tobytes())

    n = len(imagenes)
    nf_paso = max(1, round(segundos * fps / n))
    frames = 0
    for _ in range(int(hold_ini * fps)):
        _fotograma(imagenes[0])
        frames += 1
    for im in imagenes:
        for _ in range(nf_paso):
            _fotograma(im)
            frames += 1
    for _ in range(int(hold_fin * fps)):
        _fotograma(imagenes[-1])
        frames += 1

    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg devolvió {proc.returncode}")
    duracion = round(frames / fps, 2)
    avisar(f"vídeo: {salida} · {duracion:.1f} s · {W}x{H} @ {fps} fps · {n} pasos")
    return {"mp4": os.path.abspath(salida), "duracion": duracion, "W": W, "H": H,
            "frames": frames, "pasos": n}


def _cli(argv):
    if len(argv) < 2 or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 1
    pasos_dir, salida = argv[0], argv[1]
    opts = {"segundos": 8.0, "fps": 30, "hold_ini": 0.6, "hold_fin": 1.6, "ancho": None}
    i = 2
    while i < len(argv):
        a = argv[i]
        if a in ("--segundos", "--fps", "--hold-ini", "--hold-fin", "--ancho") and i + 1 < len(argv):
            i += 1
            v = argv[i]
            k = a[2:].replace("-", "_")
            opts[k] = int(v) if k in ("fps", "ancho") else float(v)
        else:
            print("opción desconocida:", a)
            return 1
        i += 1
    try:
        r = video(pasos_dir, salida, **opts)
    except Exception as e:
        print(f"sin video: {type(e).__name__} {e}")
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
