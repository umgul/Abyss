"""`instalar.py` (ESPECIFICACION.md §4 y §6): fusiona ganchos en `settings.json`
sin perder uno ajeno, y `desinstalar()` restaura el mismo CONTENIDO original (no
el mismo fichero byte a byte: `_escribir_json()` siempre reescribe con su propio indent)."""
import sys
import os
import json
import glob
import tempfile
import importlib.util
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


# instalar.py no hace red ni `rutas.resolver()` a nivel de módulo (vive dentro de
# _resolver_mem(), solo usado por su CLI): se importa aquí directamente por ruta,
# a diferencia de los guiones de gancho, que se prueban por subprocess.
def _cargar_instalador():
    ruta = ay.RAIZ / 'instalar.py'
    spec = importlib.util.spec_from_file_location('abyss_instalador_bajo_prueba', str(ruta))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class InstaladorFusionaYRestauraElContenido(unittest.TestCase):
    def setUp(self):
        self.inst = _cargar_instalador()
        # nunca tocar el abyss/ real: config.json va a una carpeta propia de la prueba
        self.pkg_temporal = Path(tempfile.mkdtemp(prefix='abyss_pkg_'))
        self.inst.PKG = str(self.pkg_temporal)

        self.tmp = Path(tempfile.mkdtemp(prefix='abyss_instalador_'))
        self.settings_ruta = self.tmp / 'settings.json'
        self.mem = self.tmp / 'proyecto' / 'memory'
        self.mem.mkdir(parents=True, exist_ok=True)

        # formato deliberadamente AJENO al de `_escribir_json` (si el fixture ya viniera
        # en NUESTRO formato, la comparación de contenido no mediría nada). El gancho ajeno
        # usa el esquema REAL de Claude Code: {type, command, timeout}, sin campo `args`.
        self.texto_original = (
            '{\n'
            '    "showThinkingSummaries": false,\n'
            '    "hooks": {\n'
            '        "SessionStart": [\n'
            '            {"hooks": [{"type": "command", "command": "otro-programa --algo", '
            '"timeout": 10, "statusMessage": "Ajeno"}]}\n'
            '        ]\n'
            '    }\n'
            '}\n'
        )
        self.original = json.loads(self.texto_original)  # el mismo contenido, para comparar por JSON
        self.settings_ruta.write_text(self.texto_original, encoding='utf-8')

    def test_instala_sin_perder_gancho_ajeno(self):
        msjs = self.inst.instalar(
            ['continuidad', 'preferencias'],
            settings_ruta=str(self.settings_ruta), python_exe='python-de-prueba',
            mem=str(self.mem))
        self.assertTrue(any('continuidad' in m for m in msjs))

        settings = json.loads(self.settings_ruta.read_text(encoding='utf-8'))
        comandos = [h['command'] for g in settings['hooks']['SessionStart'] for h in g['hooks']]
        self.assertTrue(all('args' not in h for g in settings['hooks']['SessionStart'] for h in g['hooks']),
                         'el esquema real de Claude Code no lleva un campo "args" aparte')
        self.assertTrue(any('otro-programa' in c for c in comandos), 'el gancho ajeno debe seguir ahí')
        self.assertTrue(any('python-de-prueba' in c and '--arranque' in c for c in comandos),
                         'y el nuestro se añade, no lo sustituye, con python+guion+bandera en UNA cadena')
        self.assertEqual(len(settings['hooks']['SessionStart']), 2)
        self.assertIn('SessionEnd', settings['hooks'])
        self.assertIn('UserPromptSubmit', settings['hooks'])
        self.assertTrue(settings['showThinkingSummaries'])

        backups = glob.glob(str(self.settings_ruta) + '.abyss-*.bak')
        self.assertEqual(len(backups), 1, 'debe quedar UNA copia fechada del settings.json original')
        self.assertEqual(Path(backups[0]).read_text(encoding='utf-8'), self.texto_original)

    def test_gancho_escrito_en_un_solo_command_sin_args(self):
        """El esquema real de un gancho de `settings.json` de Claude Code es
        {type, command, timeout}: la línea de órdenes ENTERA va dentro de `command`,
        sin un campo `args` aparte."""
        self.inst.instalar(
            ['vigia'], settings_ruta=str(self.settings_ruta),
            python_exe='C:\\Py\\python.exe', mem=str(self.mem))
        settings = json.loads(self.settings_ruta.read_text(encoding='utf-8'))
        stop = settings['hooks']['Stop']
        entradas = [h for g in stop for h in g['hooks']]
        nuestra = next(h for h in entradas if 'vigia.py' in h['command'])
        self.assertNotIn('args', nuestra, 'el esquema real no lleva un campo "args" aparte de "command"')
        self.assertIn('C:\\Py\\python.exe', nuestra['command'])
        self.assertIn('vigia.py', nuestra['command'])
        self.assertIn('--verificar', nuestra['command'])

    def test_gancho_escrito_sin_statusmessage(self):
        """`statusMessage` no forma parte del esquema de gancho documentado
        ({type, command, timeout}) ni de ningún `settings.json` real: abyss no debe escribirlo."""
        self.inst.instalar(
            ['continuidad', 'vigia'], settings_ruta=str(self.settings_ruta),
            python_exe='python-de-prueba', mem=str(self.mem))
        settings = json.loads(self.settings_ruta.read_text(encoding='utf-8'))
        for evento in ('SessionStart', 'SessionEnd', 'UserPromptSubmit', 'Stop'):
            for g in settings['hooks'][evento]:
                for h in g['hooks']:
                    if 'python-de-prueba' in h.get('command', ''):
                        self.assertNotIn('statusMessage', h,
                                         f'{evento}: abyss no debe escribir statusMessage (sin verificar contra el esquema real)')

    def test_desinstalar_devuelve_el_mismo_contenido_no_el_mismo_formato(self):
        self.inst.instalar(
            ['continuidad', 'preferencias'],
            settings_ruta=str(self.settings_ruta), python_exe='python-de-prueba',
            mem=str(self.mem))

        self.inst.desinstalar(
            ['continuidad', 'preferencias'],
            settings_ruta=str(self.settings_ruta), mem=str(self.mem))

        texto_final = self.settings_ruta.read_text(encoding='utf-8')
        contenido_final = json.loads(texto_final)
        self.assertEqual(contenido_final, self.original,
                          'tras instalar y desinstalar, settings.json debe tener el mismo CONTENIDO '
                          'que el original (el instalador siempre reescribe con su propio indent, '
                          'no restaura el formato byte a byte)')
        # el formato SÍ cambia (es _escribir_json quien reescribió el fichero): si esto
        # fallara, sería porque el fixture ya venía en nuestro propio formato y la
        # prueba de arriba no mediría nada de verdad.
        self.assertNotEqual(texto_final, self.texto_original)

        manifiesto = json.loads((self.mem / 'abyss_manifiesto.json').read_text(encoding='utf-8'))
        self.assertEqual(manifiesto['modulos_instalados'], [])


class ModuloDesconocidoEnLaCli(unittest.TestCase):
    def test_instalar_un_id_inexistente_sale_con_2_sin_tocar_nada(self):
        proj = ay.nuevo_proyecto()
        settings = proj / 'settings.json'
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.RAIZ / 'instalar.py', ['--instalar', 'noexiste', '--settings', str(settings)], env)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn('noexiste', r.stderr)
        self.assertFalse(settings.exists(), 'un id desconocido no debe escribir settings.json')


if __name__ == '__main__':
    unittest.main()
