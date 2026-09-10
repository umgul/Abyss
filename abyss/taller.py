# -*- coding: utf-8 -*-
"""Taller: servidor local mínimo de texto→imagen, con la boquilla de A1111/Forge, sin
FastAPI (solo `http.server` de la biblioteca estándar).

    python taller.py [--puerto 7860] [--modelo Lykon/dreamshaper-8] [--cache-dir RUTA]
                      [--dispositivo auto|cuda|mps|cpu] [--pasos 20]

Sirve, SOLO en 127.0.0.1 (nunca en 0.0.0.0: esto es un taller de casa, no un servicio):

    GET  /health              -> {"ok": true, "modelo": "...", "dispositivo": "..."}
    POST /sdapi/v1/txt2img    -> cuerpo {"prompt" (obligatorio), "width", "height", "steps",
                                  "cfg_scale", "seed", "negative_prompt"} (el resto, opcionales)
                               -> {"images": ["<PNG en base64>"]}

Es la misma forma que espera `imagen.py crear --via local` de un servidor A1111/Forge de
verdad — este taller puede ser ese servidor.

El modelo se carga con `diffusers` (`StableDiffusionPipeline`) la PRIMERA vez que llega un
`txt2img`, no al arrancar: así `/health` responde al instante, y el coste de cargar el modelo
(segundos a minutos, según disco y dispositivo) lo paga solo la primera imagen. Se descarga de
Hugging Face a la caché que le digas con `--cache-dir` (por defecto, la caché propia de
Hugging Face en tu perfil de usuario, `~/.cache/huggingface`) — NUNCA dentro de este repositorio.

Dispositivo (`--dispositivo auto`, por defecto): `cuda` si `torch.cuda.is_available()`; si no,
`mps` si `torch.backends.mps.is_available()` (Apple Silicon); si no, `cpu` — y lo dice por
stdout al arrancar. En `cpu` la generación tarda MINUTOS, no segundos: se avisa antes de que
llegue la primera petición, no después de que alguien se quede esperando.

Precisión: `torch.float16` solo en `cuda` (lo que pide la tarea); `float32` en `mps`/`cpu`,
porque fp16 en esos dos suele fallar o no acelerar nada con esta familia de modelos — no es
una elección estética, es lo que hace falta para que cargue.

VRAM: no medido en esta máquina (sin GPU CUDA disponible aquí). No se afirma una cifra de
memoria sin haberla medido de verdad o poder citarla como dato ya publicado del propio modelo.

Un único `threading.Lock` serializa las generaciones: mientras una imagen se está generando,
una segunda petición a `/sdapi/v1/txt2img` espera su turno (nunca se descartan, nunca se
generan dos a la vez — un modelo de difusión en una sola GPU no da para más). `/health` no
pasa por ese cerrojo: sigue respondiendo mientras tanto.

Si `torch` o `diffusers` no están instalados, lo dice por stdout con el `pip install` exacto
de cada paquete (la línea de `torch` cambia según haya o no una tarjeta NVIDIA) y sale con
código 2 — no instala nada por su cuenta.

Sin gancho. No escribe en `mem`: es un servidor que sirve mientras vive, no una pieza de
memoria/continuidad de Claude Code — no resuelve ningún proyecto (`rutas.py` no interviene
aquí). El prompt que le mandes no sale de esta máquina: es, precisamente, la vía `local` de
`imagen.py`, y el `POST /sdapi/v1/img2img` con máscara que usa `lienzo.py borrar --metodo
taller` (esa ruta de inpainting NO la implementa este `taller.py`; hace falta un servidor
A1111/Forge de verdad, o ampliar este mismo servidor — no está hecho aquí).
"""
import base64
import io
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODELO_POR_DEFECTO = "Lykon/dreamshaper-8"
PUERTO_POR_DEFECTO = 7860
PASOS_POR_DEFECTO = 20

try:
    import torch
except ImportError:
    torch = None

try:
    from diffusers import StableDiffusionPipeline
except ImportError:
    StableDiffusionPipeline = None


def _tiene_cuda():
    try:
        return torch is not None and torch.cuda.is_available()
    except Exception:
        return False


def mensaje_dependencias():
    if _tiene_cuda():
        linea_torch = ("pip install torch --index-url https://download.pytorch.org/whl/cu121  "
                        "(ajusta cu121 al CUDA de tu tarjeta si hace falta)")
    else:
        linea_torch = ("pip install torch  (no se detecta GPU NVIDIA aquí; con AMD/Intel/Apple "
                        "consulta pytorch.org para el comando exacto de tu sistema)")
    return (
        "[taller] faltan dependencias para generar imágenes en esta máquina. Instala:\n"
        f"  - {linea_torch}\n"
        "  - pip install diffusers transformers accelerate\n"
        "No se instala nada automáticamente."
    )


def elegir_dispositivo(pedido='auto'):
    if pedido and pedido != 'auto':
        return pedido
    if _tiene_cuda():
        return 'cuda'
    try:
        if torch is not None and torch.backends.mps.is_available():
            return 'mps'
    except Exception:
        pass
    return 'cpu'


def _pipe_cargado(estado):
    if estado['pipe'] is None:
        dtype = torch.float16 if estado['dispositivo'] == 'cuda' else torch.float32
        kwargs = {"torch_dtype": dtype}
        if estado.get('cache_dir'):
            kwargs['cache_dir'] = estado['cache_dir']
        pipe = StableDiffusionPipeline.from_pretrained(estado['modelo'], **kwargs)
        estado['pipe'] = pipe.to(estado['dispositivo'])
    return estado['pipe']


def construir_servidor(puerto, estado):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, cuerpo_dict, codigo=200):
            cuerpo = json.dumps(cuerpo_dict).encode('utf-8')
            self.send_response(codigo)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):
            if self.path == '/health':
                self._json({"ok": True, "modelo": estado['modelo'], "dispositivo": estado['dispositivo']})
            else:
                self._json({"error": "ruta desconocida"}, 404)

        def do_POST(self):
            if self.path != '/sdapi/v1/txt2img':
                self._json({"error": "ruta desconocida (este taller solo sirve /sdapi/v1/txt2img)"}, 404)
                return
            largo = int(self.headers.get('Content-Length', 0) or 0)
            crudo = self.rfile.read(largo) if largo else b'{}'
            try:
                carga = json.loads(crudo or b'{}')
            except Exception:
                self._json({"error": "cuerpo no es JSON válido"}, 400)
                return
            prompt = (carga.get('prompt') or '').strip()
            if not prompt:
                self._json({"error": "falta 'prompt'"}, 400)
                return
            try:
                ancho = int(carga.get('width') or 512)
                alto = int(carga.get('height') or 512)
                pasos = int(carga.get('steps') or estado['pasos'])
                cfg = float(carga.get('cfg_scale') or 7.0)
                semilla = carga.get('seed')
                with estado['lock']:
                    pipe = _pipe_cargado(estado)
                    generador = None
                    if semilla is not None:
                        dispositivo_gen = 'cpu' if estado['dispositivo'] == 'mps' else estado['dispositivo']
                        generador = torch.Generator(device=dispositivo_gen).manual_seed(int(semilla))
                    salida = pipe(prompt=prompt, negative_prompt=(carga.get('negative_prompt') or None),
                                  width=ancho, height=alto, num_inference_steps=pasos,
                                  guidance_scale=cfg, generator=generador)
                imagen = salida.images[0]
                buf = io.BytesIO()
                imagen.save(buf, format='PNG')
                b64 = base64.b64encode(buf.getvalue()).decode('ascii')
            except Exception as e:
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)
                return
            self._json({"images": [b64]})

        def log_message(self, *a):
            pass  # silencio: no ensuciar stdout (ahí va el aviso de arranque, que sí importa)

    return ThreadingHTTPServer(('127.0.0.1', puerto), Handler)


def main(opts):
    if torch is None or StableDiffusionPipeline is None:
        print(mensaje_dependencias())
        return 2
    dispositivo = elegir_dispositivo(opts['dispositivo'])
    estado = {"pipe": None, "lock": threading.Lock(), "modelo": opts['modelo'],
              "dispositivo": dispositivo, "cache_dir": opts['cache_dir'], "pasos": opts['pasos']}
    if dispositivo == 'cpu':
        print('[taller] dispositivo: cpu (sin GPU disponible) — cada imagen tardará minutos, no segundos')
    else:
        print(f'[taller] dispositivo: {dispositivo}')
    servidor = construir_servidor(opts['puerto'], estado)
    puerto_real = servidor.server_address[1]
    print(f'[taller] escuchando en http://127.0.0.1:{puerto_real} (modelo {opts["modelo"]})')
    sys.stdout.flush()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
    return 0


def _cli(argv):
    if argv and argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    opts = {"puerto": PUERTO_POR_DEFECTO, "modelo": MODELO_POR_DEFECTO, "cache_dir": None,
            "dispositivo": "auto", "pasos": PASOS_POR_DEFECTO}
    con_valor = {"--puerto": "puerto", "--modelo": "modelo", "--cache-dir": "cache_dir",
                 "--dispositivo": "dispositivo", "--pasos": "pasos"}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in con_valor and i + 1 < len(argv) and not argv[i + 1].startswith('--'):
            i += 1
            v = argv[i]
            clave = con_valor[a]
            if clave in ('puerto', 'pasos'):
                try:
                    opts[clave] = int(v)
                except ValueError:
                    print(f'--{clave.replace("_", "-")} necesita un número, no "{v}"')
                    return 1
            else:
                opts[clave] = v
        else:
            print(f'argumento no reconocido: {a} (usa --puerto/--modelo/--cache-dir/--dispositivo/--pasos)')
            return 1
        i += 1
    return main(opts)


if __name__ == '__main__':
    try:                       # la consola de Windows y la salida tienen que hablar
        from . import consola  # el mismo idioma: ver abyss/consola.py
    except ImportError:
        import consola
    consola.preparar()
    sys.exit(_cli(sys.argv[1:]))
