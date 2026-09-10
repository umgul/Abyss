"""`taller.py` (encargo directo): servidor local mínimo de
texto→imagen, boquilla A1111 (`POST /sdapi/v1/txt2img`, `GET /health`).

`diffusers` NO está instalado en esta máquina (comprobado): el caso "sin diffusers" se prueba
tal cual, sin tocar nada. El caso "con diffusers" inyecta un paquete `diffusers` FALSO por
`PYTHONPATH` (un `sitecustomize`-like: un directorio con su propio `diffusers/__init__.py`
antepuesto al `PYTHONPATH` del proceso hijo) que imita la única API que usa `taller.py`
(`StableDiffusionPipeline.from_pretrained(...).to(dispositivo)(prompt=...)` -> objeto con
`.images`) y devuelve una imagen sintética al instante — nunca se descarga ni se ejecuta un
modelo de verdad, y `torch` (SÍ instalado de verdad aquí, sin CUDA) se usa tal cual.

El servidor se lanza en segundo plano (`--puerto 0`: puerto libre elegido por el sistema
operativo, léase de la primera línea de stdout) y se mata al acabar cada prueba — nunca
queda escuchando, y nunca en otra interfaz que no sea 127.0.0.1 (lo fija el propio guion)."""
import json
import os
import queue
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / 'abyss' / 'taller.py'

# `taller.py` no toca `rutas.resolver()` ni stdin al importarse (no gestiona
# memoria/continuidad de Claude Code, ver su propio docstring) — se puede
# importar DIRECTAMENTE, sin subproceso, para comprobar `construir_servidor()`.
sys.path.insert(0, str(RAIZ))
from abyss import taller as tl  # noqa: E402


def _diffusers_falso():
    """Directorio temporal con un paquete `diffusers` de mentira: antepuesto al
    `PYTHONPATH` del proceso hijo, `import diffusers` lo encuentra a ÉL, no al real
    (que aquí ni siquiera está instalado)."""
    d = Path(tempfile.mkdtemp(prefix='abyss_diffusers_falso_'))
    paquete = d / 'diffusers'
    paquete.mkdir()
    (paquete / '__init__.py').write_text(textwrap.dedent('''
        class _ResultadoFalso:
            def __init__(self, images):
                self.images = images

        class StableDiffusionPipeline:
            def __init__(self, modelo):
                self.modelo = modelo
                self.device = "cpu"

            @classmethod
            def from_pretrained(cls, modelo, **kwargs):
                return cls(modelo)

            def to(self, device):
                self.device = device
                return self

            def __call__(self, prompt, negative_prompt=None, width=512, height=512,
                         num_inference_steps=20, guidance_scale=7.0, generator=None):
                from PIL import Image
                import random
                w, h = int(width), int(height)
                img = Image.new("RGB", (w, h))
                px = img.load()
                rnd = random.Random(1)
                for y in range(h):
                    for x in range(w):
                        px[x, y] = (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
                return _ResultadoFalso([img])
    '''), encoding='utf-8')
    return d


def _leer_linea_con_tope(stream, tope=20):
    """`stream.readline()` con un tope de espera: si el proceso no ha escrito nada en
    ese tiempo, devuelve `None` en vez de bloquear la prueba para siempre (mismo patrón
    que `rutas.leer_stdin()` usa para no colgarse esperando algo que no llega)."""
    q = queue.Queue()

    def _leer():
        try:
            q.put(stream.readline())
        except Exception:
            q.put('')

    threading.Thread(target=_leer, daemon=True).start()
    try:
        return q.get(timeout=tope)
    except queue.Empty:
        return None


class _TallerLevantado:
    """`with _TallerLevantado(env) as t:` lanza `taller.py --puerto 0` en segundo plano,
    espera a leer el puerto real de su primera línea de stdout, y lo mata al salir."""

    def __init__(self, env, args=()):
        self.env = env
        self.args = list(args)
        self.puerto = None

    def __enter__(self):
        self.proc = subprocess.Popen(
            [sys.executable, '-u', str(SCRIPT), '--puerto', '0', '--dispositivo', 'cpu',
             '--pasos', '1'] + self.args,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8',
            errors='replace', env=self.env)
        for _ in range(3):
            linea = _leer_linea_con_tope(self.proc.stdout, tope=20)
            if linea is None:
                break
            if 'escuchando en' in linea:
                self.puerto = int(linea.strip().rsplit(':', 1)[1].split(')')[0].split()[0])
                break
        return self

    def __exit__(self, *exc):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)
        finally:
            if self.proc.stdout:
                self.proc.stdout.close()


# Sin proxy explícito: la regla de la suite ("sin red") pone http_proxy/https_proxy
# apuntando a un puerto muerto, y urllib los respeta incluso para 127.0.0.1 si no se le
# dice lo contrario (mismo aviso que test_imagen_crear_vias.py) — este servidor SÍ es
# local de verdad, así que su tráfico nunca debe pasar por ningún proxy.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _get(url, tope=10):
    limite = time.time() + tope
    ultimo_error = None
    while time.time() < limite:
        try:
            with _OPENER.open(url, timeout=2) as r:
                return r.status, r.read()
        except Exception as e:
            ultimo_error = e
            time.sleep(0.2)
    raise RuntimeError(f'sin respuesta de {url} tras {tope}s: {ultimo_error}')


def _post_json(url, cuerpo_dict, tope=30):
    datos = json.dumps(cuerpo_dict).encode('utf-8')
    req = urllib.request.Request(url, data=datos, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with _OPENER.open(req, timeout=tope) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class TallerSinDiffusers(unittest.TestCase):
    def test_sale_con_2_y_el_mensaje_nombra_los_paquetes(self):
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)  # el entorno real de esta máquina: sin diffusers instalado
        r = subprocess.run([sys.executable, str(SCRIPT), '--puerto', '0'],
                            capture_output=True, text=True, encoding='utf-8', errors='replace',
                            env=env, timeout=15, input='')
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        for paquete in ('torch', 'diffusers', 'transformers', 'accelerate'):
            self.assertIn(paquete, r.stdout, f'el mensaje debe nombrar "{paquete}"')
        self.assertNotIn('Traceback', r.stdout)


class TallerSoloEscuchaEnLoopback(unittest.TestCase):
    """Fallo "roza": el docstring de la propia prueba afirmaba el límite
    ("nunca en otra interfaz que no sea 127.0.0.1") sin que ninguna prueba lo
    comprobara — medido por mutación (cambiar `('127.0.0.1', puerto)` por
    `('0.0.0.0', puerto)`), las 5 pruebas de antes seguían en verde. Se llama
    directamente a `construir_servidor()` (sin subproceso: no necesita
    `torch`/`diffusers`, `estado` solo se usa dentro de los manejadores) y se
    afirma el `server_address` real."""

    def test_construir_servidor_liga_a_127_0_0_1(self):
        srv = tl.construir_servidor(0, {})
        try:
            self.assertEqual(srv.server_address[0], '127.0.0.1')
        finally:
            srv.server_close()


class TallerConDiffusersSimulado(unittest.TestCase):
    def setUp(self):
        self.dir_falso = _diffusers_falso()
        self.env = dict(os.environ)
        self.env['PYTHONPATH'] = str(self.dir_falso) + os.pathsep + self.env.get('PYTHONPATH', '')

    def test_arranca_health_responde_y_txt2img_da_un_png_valido(self):
        with _TallerLevantado(self.env) as t:
            self.assertIsNotNone(t.puerto, 'no se leyó el puerto de la primera línea de stdout')

            cod, cuerpo = _get(f'http://127.0.0.1:{t.puerto}/health')
            self.assertEqual(cod, 200)
            salud = json.loads(cuerpo)
            self.assertTrue(salud['ok'])
            self.assertEqual(salud['dispositivo'], 'cpu')

            cod, cuerpo = _post_json(f'http://127.0.0.1:{t.puerto}/sdapi/v1/txt2img',
                                      {"prompt": "un gato de prueba", "width": 32, "height": 32,
                                       "steps": 1, "seed": 7})
            self.assertEqual(cod, 200, cuerpo)
            datos = json.loads(cuerpo)
            self.assertIn('images', datos)
            self.assertEqual(len(datos['images']), 1)
            import base64
            png = base64.b64decode(datos['images'][0])
            self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n', 'debe ser un PNG válido de verdad')

    def test_sin_prompt_da_400(self):
        with _TallerLevantado(self.env) as t:
            self.assertIsNotNone(t.puerto)
            cod, cuerpo = _post_json(f'http://127.0.0.1:{t.puerto}/sdapi/v1/txt2img', {})
            self.assertEqual(cod, 400)

    def test_ruta_desconocida_da_404(self):
        with _TallerLevantado(self.env) as t:
            self.assertIsNotNone(t.puerto)
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                _OPENER.open(f'http://127.0.0.1:{t.puerto}/no-existe', timeout=5)
            self.assertEqual(ctx.exception.code, 404)

    def test_argumento_desconocido_sale_con_1(self):
        r = subprocess.run([sys.executable, str(SCRIPT), '--no-existe', 'x'],
                            capture_output=True, text=True, encoding='utf-8', errors='replace',
                            env=self.env, timeout=15, input='')
        self.assertEqual(r.returncode, 1)


if __name__ == '__main__':
    unittest.main()
