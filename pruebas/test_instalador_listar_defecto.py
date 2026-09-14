"""`instalar.py --listar` corto con el detalle a petición, `--instalar defecto`, y que instalar una skill nunca borre
una del usuario con el mismo nombre. La orden real de instalar corre por subprocess sobre una COPIA del paquete
(instalar escribe `abyss/config.json` junto al código); lo que solo lista o valida, sobre el repo, con home, settings
y proyecto temporales."""
import sys
import os
import re
import json
import shutil
import tempfile
import importlib.util
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay

# Lo que `defecto` no puede traer: los apagados, la clave de settings del usuario y las tres skills que se copian.
FUERA_DE_DEFECTO = {'huella', 'taller', 'telegram', 'permisos', 'preferencias', 'kinetica', 'kinetico', 'esceptico'}


def _cargar_instalador():
    spec = importlib.util.spec_from_file_location('abyss_instalador_listar_defecto', str(ay.RAIZ / 'instalar.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


INST = _cargar_instalador()
IDS = [m['id'] for m in INST.MODULOS]
DEFECTO = [i for i in IDS if i not in FUERA_DE_DEFECTO]


def _entorno(tmp, **extra):
    env = dict(os.environ, USERPROFILE=str(tmp), HOME=str(tmp), **extra)
    env.pop('ABYSS_PROYECTO', None)
    return env


def _cli(*args, columnas=None):
    """Con home, settings y proyecto temporales: si algo llegara a instalar o a resolver proyecto, nada cae en el
    `~/.claude` real ni en el `abyss/` del repo."""
    tmp = Path(tempfile.mkdtemp(prefix='abyss_listar_'))
    env = _entorno(tmp, ABYSS_PROYECTO=str(tmp / 'proyecto'), **({'COLUMNS': str(columnas)} if columnas else {}))
    return ay.ejecutar(ay.RAIZ / 'instalar.py', [*args, '--settings', str(tmp / 'settings.json')], env, cwd=str(tmp))


def _filas(stdout):
    """{id: fila} de las filas de módulo, por su primera columna (dos espacios, id, espacios, `[estado]`)."""
    return {m.group(1): m.group(0) for m in re.finditer(r'^  (\S+)\s+\[.*$', stdout, re.M)}


def _ids_en_orden(stdout):
    return re.findall(r'^  (\S+)\s+\[', stdout, re.M)


class ListarCorto(unittest.TestCase):
    def test_una_fila_por_modulo_en_orden_y_sin_detalle(self):
        for idioma, etiquetas, palabras in (('es', ('toca:', 'aviso:'), ('--listar todos', '--instalar defecto')),
                                            ('en', ('touches:', 'note:'), ('--listar all', '--instalar default'))):
            with self.subTest(idioma=idioma):
                r = _cli('--listar', '--idioma', idioma)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(_ids_en_orden(r.stdout), IDS)
                for etiqueta in etiquetas:
                    self.assertNotIn(etiqueta, r.stdout)
                texto = ' '.join(r.stdout.split())
                for palabra in palabras:
                    self.assertIn(palabra, texto)

    def test_cada_fila_cabe_en_el_ancho_sin_perder_sus_marcas(self):
        r = _cli('--listar', '--idioma', 'es', columnas=100)
        filas = _filas(r.stdout)
        self.assertEqual(len(filas), len(IDS))
        for mod in INST.MODULOS:
            fila = filas[mod['id']]
            self.assertLessEqual(len(fila), 99, mod['id'])
            self.assertEqual('⚠' in fila, bool(mod.get('aviso')), mod['id'])
            self.assertEqual(fila.endswith('· apagado por defecto'), not mod.get('defecto', True), mod['id'])

    def test_el_pie_nombra_las_skills_que_defecto_deja_fuera(self):
        texto = ' '.join(_cli('--listar', '--idioma', 'es').stdout.split())
        for mod in INST.MODULOS:
            if mod.get('especial') == 'skill':
                self.assertIn(mod['id'], texto.split('--instalar defecto', 1)[1])

    def test_continuidad_avisa_de_la_red_y_de_como_cortarla(self):
        self.assertIn('⚠', _filas(_cli('--listar', '--idioma', 'es').stdout)['continuidad'])
        detalle = _cli('--listar', 'continuidad', '--idioma', 'en').stdout
        for trozo in ('ipinfo.io', 'news.google.com', 'ABYSS_SIN_RED=1'):
            self.assertIn(trozo, detalle)

    def test_sin_ventana_es_la_lista_corta(self):
        r = _cli('--sin-ventana', '--idioma', 'es')
        self.assertEqual(_ids_en_orden(r.stdout), IDS)
        self.assertNotIn('toca:', r.stdout)


class ListarDetalle(unittest.TestCase):
    def test_un_modulo_con_lo_que_toca_su_aviso_y_como_encenderlo(self):
        for idioma, etiquetas in (('es', ('toca:', 'aviso:', 'apagado por defecto; para encenderlo:')),
                                  ('en', ('touches:', 'note:', 'off by default; to turn it on:'))):
            with self.subTest(idioma=idioma):
                r = _cli('--listar', 'huella', '--idioma', idioma)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(_ids_en_orden(r.stdout), ['huella'])
                for etiqueta in etiquetas:
                    self.assertIn(etiqueta, r.stdout)
                self.assertIn('python instalar.py --instalar huella', r.stdout)

    def test_varios_en_el_orden_pedido_y_sin_repetir(self):
        self.assertEqual(_ids_en_orden(_cli('--listar', 'vigia,continuidad,vigia').stdout), ['vigia', 'continuidad'])

    def test_defecto_da_el_detalle_de_lo_que_instalaria(self):
        for palabra in ('defecto', 'default'):
            r = _cli('--listar', palabra, '--idioma', 'es')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_ids_en_orden(r.stdout), DEFECTO, palabra)
            self.assertEqual(len(re.findall(r'^\s+toca: ', r.stdout, re.M)), len(DEFECTO))

    def test_todos_trae_el_detalle_de_cada_modulo(self):
        for palabra in ('todos', 'all'):
            r = _cli('--listar', palabra, '--idioma', 'es')
            self.assertEqual(_ids_en_orden(r.stdout), IDS, palabra)
            self.assertEqual(len(re.findall(r'^\s+toca: ', r.stdout, re.M)), len(IDS))

    def test_un_id_desconocido_sale_con_2(self):
        r = _cli('--listar', 'vigia,no-existe')
        self.assertEqual(r.returncode, 2)
        self.assertIn('no-existe', r.stderr)

    def test_listar_admite_otra_bandera_detras_o_un_valor(self):
        self.assertIsNone(INST._argumento_no_reconocido(['--listar', '--idioma', 'en']))
        self.assertIsNone(INST._argumento_no_reconocido(['--listar', 'todos']))


class InstalarDefecto(unittest.TestCase):
    def test_se_expande_sin_apagados_sin_clave_de_settings_y_sin_skills_copiadas(self):
        self.assertEqual(INST._expandir_defecto(['defecto']), DEFECTO)
        self.assertEqual(INST._expandir_defecto(['default']), DEFECTO)

    def test_combina_con_ids_escritos_a_mano_sin_repetir(self):
        exp = INST._expandir_defecto(['huella', 'defecto', 'vigia', 'preferencias'])
        self.assertEqual(exp[0], 'huella')
        self.assertEqual(exp[-1], 'preferencias', 'lo escrito a mano sí entra')
        self.assertEqual(len(exp), len(set(exp)))

    def test_ningun_modulo_se_llama_como_las_palabras_reservadas(self):
        for palabra in INST.PALABRAS_DEFECTO + INST.PALABRAS_TODOS:
            self.assertNotIn(palabra, IDS)

    def test_defecto_solo_vale_en_instalar_y_listar(self):
        r = _cli('--desinstalar', 'defecto')
        self.assertEqual(r.returncode, 2)
        self.assertIn('defecto', r.stderr)
        r = _cli('--instalar', 'defecto,no-existe')
        self.assertEqual(r.returncode, 2)
        self.assertIn('no-existe', r.stderr)
        self.assertNotIn('defecto', r.stderr)


class LaOrdenRealDeInstalarDefecto(unittest.TestCase):
    """`python instalar.py --instalar defecto` de verdad, dos veces, sobre una copia del paquete."""

    @classmethod
    def setUpClass(cls):
        cls.copia = Path(tempfile.mkdtemp(prefix='abyss_copia_'))
        shutil.copy2(ay.RAIZ / 'instalar.py', cls.copia)
        shutil.copytree(ay.RAIZ / 'abyss', cls.copia / 'abyss',
                        ignore=shutil.ignore_patterns('vendor', '__pycache__', 'config.json'))
        shutil.copytree(ay.RAIZ / 'skills', cls.copia / 'skills')
        shutil.copytree(ay.RAIZ / 'plantillas', cls.copia / 'plantillas')

    def instalar(self, tmp, settings):
        args = ['--instalar', 'defecto', '--settings', str(settings), '--skills-dir', str(tmp / 'skills'),
                '--proyecto', str(tmp / 'proyecto')]
        r = ay.ejecutar(self.copia / 'instalar.py', args, _entorno(tmp), cwd=str(tmp), timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def test_dos_veces_no_pisa_nada_y_devuelve_lo_quitado_a_mano(self):
        tmp = Path(tempfile.mkdtemp(prefix='abyss_defecto_cli_'))
        settings = tmp / 'settings.json'
        settings.write_text(json.dumps({'showThinkingSummaries': False}), encoding='utf-8')
        r = self.instalar(tmp, settings)
        self.assertIn(', '.join(DEFECTO), r.stdout)
        primero = json.loads(settings.read_text(encoding='utf-8'))
        self.assertIs(primero['showThinkingSummaries'], False, 'defecto no toca la clave del usuario')
        self.assertIn('Stop', primero['hooks'])
        manifiestos = list(tmp.glob('.claude/projects/*/memory/abyss_manifiesto.json'))
        self.assertEqual(len(manifiestos), 1)
        self.assertEqual(set(json.loads(manifiestos[0].read_text(encoding='utf-8'))['modulos_instalados']), set(DEFECTO))
        self.assertFalse((tmp / 'skills').exists(), 'defecto no copia skills')

        sin_stop = dict(primero, hooks={k: v for k, v in primero['hooks'].items() if k != 'Stop'})
        settings.write_text(json.dumps(sin_stop), encoding='utf-8')
        self.instalar(tmp, settings)
        self.assertEqual(json.loads(settings.read_text(encoding='utf-8')), primero,
                         'repetirlo devuelve el gancho quitado, sin duplicar ninguno ni tocar la clave')


class InstalarNoBorraUnaSkillDelUsuario(unittest.TestCase):
    def setUp(self):
        self.inst = _cargar_instalador()
        self.tmp = Path(tempfile.mkdtemp(prefix='abyss_skill_ajena_'))
        self.inst.PKG = str(self.tmp / 'pkg')
        os.makedirs(self.inst.PKG)
        self.mem = self.tmp / 'memory'
        self.mem.mkdir()
        self.skills = self.tmp / 'skills'

    def instalar(self):
        return self.inst.instalar(['esceptico'], settings_ruta=str(self.tmp / 'settings.json'), python_exe='py',
                                  mem=str(self.mem), skills_dir=str(self.skills))

    def instalados(self):
        return json.loads((self.mem / 'abyss_manifiesto.json').read_text(encoding='utf-8'))['modulos_instalados']

    def poner_ajena(self):
        ajena = self.skills / 'esceptico'
        shutil.rmtree(ajena, ignore_errors=True)
        ajena.mkdir(parents=True)
        (ajena / 'SKILL.md').write_text('---\nname: esceptico\ndescription: la mía\n---\n', encoding='utf-8')
        (ajena / 'notas_mias.txt').write_text('no me borres', encoding='utf-8')
        return ajena

    def test_una_carpeta_sin_la_marca_no_se_toca_ni_cuenta_como_instalada(self):
        ajena = self.poner_ajena()
        mensajes = self.instalar()
        self.assertTrue((ajena / 'notas_mias.txt').exists())
        self.assertTrue(any('no lleva la marca' in m and 'bórrala a mano' in m for m in mensajes), mensajes)
        self.assertNotIn('esceptico', self.instalados())

    def test_si_estaba_en_el_manifiesto_sale_de_el(self):
        self.instalar()
        self.assertIn('esceptico', self.instalados())
        self.poner_ajena()
        self.instalar()
        self.assertNotIn('esceptico', self.instalados())

    def test_la_copia_nuestra_si_se_sustituye(self):
        self.instalar()
        sobrante = self.skills / 'esceptico' / 'sobrante.txt'
        sobrante.write_text('de una copia vieja', encoding='utf-8')
        self.instalar()
        self.assertFalse(sobrante.exists(), 'reinstalar deja la copia buena, no dos mezcladas')
        self.assertIn('esceptico', self.instalados())


if __name__ == '__main__':
    unittest.main()
