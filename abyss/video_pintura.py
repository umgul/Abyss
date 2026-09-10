# -*- coding: utf-8 -*-
"""Vídeo de la pintura pincelada a pincelada, con ritmo variable: despacio al principio (se ve
nacer la imagen con los pinceles gruesos), rápido en el medio (las capas de relleno) y despacio al
final (los detalles se acaban los últimos). Codifica H.264 con el ffmpeg de imageio_ffmpeg.

Uso:
    python video_pintura.py <trazos.json.gz> <salida.mp4> [--segundos 9] [--ancho 1080] [--fps 30]
                            [--foco x,y[;x,y]] [--retrato] [--suave [2]]

--foco: puntos (fracción del ancho y del alto, 0-1) que se pintan LOS ÚLTIMOS en la capa fina.
--retrato: atajo para dos ojos de un retrato centrado (0.37,0.33 y 0.63,0.33).
Sin foco, la capa fina se pinta en el orden en que se pintó.

Estilos (`pintor.py`): el `.json.gz` guarda el papel de fondo y el alfa de capa dentro de
`"radios"` (`{"lista", "estilo", "papel", "alfa"}` — ver el docstring de `pintor.py`). Este guion
los lee: pinta sobre ESE papel (no un negro fijo) y, si el estilo pinta con alfa < 1 (acuarela,
impresionista, pastel, carbón), compone cada capa (grupo de radio) de una vez con su alfa sobre lo
ya pintado, igual que hace `pintor.pintar()` — así el vídeo no oscurece de más donde los trazos de
una misma capa se solapan. Con alfa = 1 (óleo, tinta) pinta directo, como siempre: más rápido y
sin componer nada. Un `.json.gz` viejo (sin ese dict) se sigue leyendo: sin él, se
asume óleo (papel oscuro de siempre, alfa 1).

Depende de Pillow e imageio_ffmpeg (pip install imageio-ffmpeg). Todo en local. Si falta
imageio_ffmpeg o algo falla, la CLI imprime «sin video: <motivo>» y sale con código 2.
"""
import gzip
import json
import math
import os
import subprocess
import sys

from PIL import Image, ImageDraw

RETRATO = [(0.37, 0.33), (0.63, 0.33)]
FONDO = (8, 6, 7)  # papel por defecto de "oleo" (pintor.FONDO) — igual sin metadatos de estilo


def _rgb_de_hex(v, defecto=FONDO):
    """`"#rrggbb"` -> (r,g,b); cualquier otra cosa (ausente, formato viejo) -> `defecto`."""
    if isinstance(v, str) and len(v) == 7 and v.startswith("#"):
        try:
            return tuple(int(v[i:i + 2], 16) for i in (1, 3, 5))
        except ValueError:
            pass
    return defecto


def video(trazos_gz, salida, segundos=9.0, ancho=1080, fps=30, foco=None, hold_ini=0.4, hold_fin=2.0,
          supermuestreo=1, avisar=print):
    """Escribe `salida` (mp4) y devuelve {"mp4", "duracion", "W", "H", "frames"}.

    supermuestreo=2: cada fotograma se pinta a doble tamaño y se reduce antes de codificar
    (pinceladas suaves; cuesta ~4x en el dibujo y una reducción por fotograma)."""
    SS = max(1, int(supermuestreo))
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise RuntimeError(f"falta imageio_ffmpeg (pip install imageio-ffmpeg): {e}")

    d = json.load(gzip.open(trazos_gz, "rt", encoding="utf-8"))
    W0, H0, T = d["W"], d["H"], d["trazos"]
    meta = d.get("radios")
    meta = meta if isinstance(meta, dict) else {}  # .json.gz viejo: "radios" era una lista
    papel = _rgb_de_hex(meta.get("papel"))
    alfa_estilo = float(meta.get("alfa", 1.0))
    s = ancho / W0
    W, H = int(ancho), int(round(H0 * s))
    if H % 2:
        H += 1  # yuv420p exige pares
    if W % 2:
        W += 1

    radios = sorted({t[0] for t in T}, reverse=True)
    cuenta = {r: sum(1 for t in T if t[0] == r) for r in radios}
    peso = {r: (3.0 if r >= 10 else 1.4 if r >= 5 else 0.55 if r >= 2 else 1.0) for r in radios}
    base = {r: cuenta[r] ** 0.5 * peso[r] for r in radios}  # raíz: que las capas enormes no se lo coman todo
    tot = sum(base.values()) or 1.0
    segs = {r: segundos * base[r] / tot for r in radios}
    por_capa = {r: [t for t in T if t[0] == r] for r in radios}
    rf = radios[-1]
    if foco:
        puntos = [(fx * W0, fy * H0) for fx, fy in foco]

        def lejos(t):
            p = t[2]
            return min(math.hypot(p[0] - ex, p[1] - ey) for ex, ey in puntos)
        por_capa[rf].sort(key=lejos, reverse=True)  # lejos del foco primero; el foco, al final

    plan = []
    for r in radios:
        n = cuenta[r]
        nf = max(1, int(round(segs[r] * fps)))
        if r == rf:  # última capa: constante y frenada en el último 20 % de pinceladas
            n_lento = int(n * 0.2)
            n_rap = n - n_lento
            nf_lento = max(1, int(round(nf * 0.45)))
            nf_rap = max(1, nf - nf_lento)
            plan += [(r, n_rap / nf_rap)] * nf_rap + [(r, n_lento / nf_lento)] * nf_lento
        else:
            plan += [(r, n / nf)] * nf
    avisar(f"{W}x{H} · capas {[(r, cuenta[r], round(segs[r], 2)) for r in radios]} · frames {len(plan)}")

    cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
           "-preset", "medium", "-movflags", "+faststart", os.path.abspath(salida)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    sS = s * SS
    capa_alfa = alfa_estilo < 0.999  # alfa=1 (óleo/tinta): dibuja directo, como siempre

    if capa_alfa:
        # cada grupo de radio es SU capa: se dibuja aparte a opacidad plena y se compone de
        # una vez con `alfa_estilo` sobre lo ya fijado — igual que pintor.pintar(), para que los
        # trazos que se solapan dentro de una misma capa no se oscurezcan entre sí.
        fijo = Image.new("RGBA", (W * SS, H * SS), papel + (255,))
        capa = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
        dr = ImageDraw.Draw(capa)
        radio_de_capa = [None]

        def _fija_capa():
            nonlocal fijo, capa, dr
            a = capa.split()[3].point(lambda v: int(v * alfa_estilo))
            capa.putalpha(a)
            fijo = Image.alpha_composite(fijo, capa)
            capa = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
            dr = ImageDraw.Draw(capa)

        def pinta(t):
            r0 = t[0]
            if radio_de_capa[0] is not None and r0 != radio_de_capa[0]:
                _fija_capa()
            radio_de_capa[0] = r0
            r = max(1.0, r0 * sS)
            col = t[1]
            p = t[2]
            pts = [(p[k] * sS, p[k + 1] * sS) for k in range(0, len(p), 2)]
            dr.line(pts, fill=col, width=max(1, int(round(2 * r))), joint="curve")
            if r >= 1.5:
                for q in (pts[0], pts[-1]):
                    dr.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=col)

        def frame():
            # la capa en curso se ve YA compuesta con su alfa (entrando sobre lo fijado),
            # aunque solo se fije de verdad al cambiar de radio (ver _fija_capa)
            a = capa.split()[3].point(lambda v: int(v * alfa_estilo))
            vista = capa.copy()
            vista.putalpha(a)
            cuadro = Image.alpha_composite(fijo, vista).convert("RGB")
            if SS != 1:
                cuadro = cuadro.resize((W, H), Image.LANCZOS)
            proc.stdin.write(cuadro.tobytes())
    else:
        lienzo = Image.new("RGB", (W * SS, H * SS), papel)
        dr = ImageDraw.Draw(lienzo)

        def pinta(t):
            r = max(1.0, t[0] * sS)
            col = t[1]
            p = t[2]
            pts = [(p[k] * sS, p[k + 1] * sS) for k in range(0, len(p), 2)]
            dr.line(pts, fill=col, width=max(1, int(round(2 * r))), joint="curve")
            if r >= 1.5:
                for q in (pts[0], pts[-1]):
                    dr.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=col)

        def frame():
            cuadro = lienzo if SS == 1 else lienzo.resize((W, H), Image.LANCZOS)
            proc.stdin.write(cuadro.tobytes())

    for _ in range(int(hold_ini * fps)):
        frame()
    idx = {r: 0 for r in radios}
    acum = {r: 0.0 for r in radios}
    for (r, k) in plan:
        acum[r] += k
        capa_r = por_capa[r]
        tope = min(int(acum[r]), len(capa_r))
        while idx[r] < tope:
            pinta(capa_r[idx[r]])
            idx[r] += 1
        frame()
    for r in radios:  # lo que quede por redondeo
        while idx[r] < len(por_capa[r]):
            pinta(por_capa[r][idx[r]])
            idx[r] += 1
    if capa_alfa:
        _fija_capa()  # la última capa también se fija, para los fotogramas de cierre
    for _ in range(int(hold_fin * fps)):
        frame()
    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg devolvió {proc.returncode}")
    dur = hold_ini + len(plan) / fps + hold_fin
    avisar(f"vídeo: {salida} · {dur:.1f} s · {W}x{H} @ {fps} fps")
    return {"mp4": os.path.abspath(salida), "duracion": round(dur, 2), "W": W, "H": H,
            "frames": len(plan) + int(hold_ini * fps) + int(hold_fin * fps)}


def _cli(argv):
    if len(argv) < 2 or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 1
    src, out = argv[0], argv[1]
    opts = {"segundos": 9.0, "ancho": 1080, "fps": 30, "foco": None, "supermuestreo": 1}
    i = 2
    while i < len(argv):
        a = argv[i]
        if a == "--retrato":
            opts["foco"] = RETRATO
        elif a == "--suave":
            opts["supermuestreo"] = 2
            if i + 1 < len(argv) and argv[i + 1].isdigit():
                i += 1
                opts["supermuestreo"] = int(argv[i])
        elif a in ("--segundos", "--ancho", "--fps", "--foco") and i + 1 < len(argv):
            i += 1
            v = argv[i]
            if a == "--segundos":
                opts["segundos"] = float(v)
            elif a == "--ancho":
                opts["ancho"] = int(v)
            elif a == "--fps":
                opts["fps"] = int(v)
            else:
                opts["foco"] = [tuple(float(c) for c in par.split(",")) for par in v.split(";") if par.strip()]
        else:
            print("opción desconocida:", a)
            return 1
        i += 1
    try:
        r = video(src, out, **opts)
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
