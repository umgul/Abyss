"""`instalar.py` (ESPECIFICACION.md §4 y §6): fusiona ganchos en `settings.json`
SIN perder uno ajeno, y `desinstalar()` devuelve el mismo CONTENIDO original (salvo
lo que puso abyss) — no el mismo fichero byte a byte: `_escribir_json()` siempre
reescribe con su propio `indent=2`, así que si el `settings.json` de partida usaba
otro formato (otro indent, arrays en una línea, otro orden de claves…) el texto
final difiere aunque el JSON cargado sea idéntico. El fixture de abajo usa a
propósito un formato AJENO al de `_escribir_json` para no dar por buena una
igualdad que solo se cumpliría porque el fixture ya viniera en NUESTRO formato.

`instalar.py` no hace ninguna llamada de red ni ningún `rutas.resolver()` a nivel
de módulo (eso vive dentro de `_resolver_mem()`, que solo se usa desde su CLI), así
que aquí se importa DIRECTAMENTE por ruta de fichero — a diferencia de los guiones
de gancho (`continuidad.py`, `vigia.py`, `varas.py`, `propiocepcion.py`), que
siempre se prueban por subprocess (ver `ayudas.py`).

Se sobreescribe `PKG` del módulo cargado para que `_escribir_config_codigo()` (el
único fichero que el instalador escribe en la carpeta del código) NO toque el
`abyss/` real del repositorio, sino una carpeta temporal propia de la prueba.
"""
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

        # Formato deliberadamente AJENO al de `_escribir_json` (indent=2, un elemento
        # por línea): indent de 4, arrays compactos en una sola línea, orden de
        # claves distinto (showThinkingSummaries antes que hooks). El gancho ajeno usa
        # el esquema REAL de Claude Code — {type, command, timeout}, la línea de
        # órdenes ENTERA dentro de `command`, SIN campo `args` (medido 6-sep contra
        # hooks/hooks.json:8: un fixture con `args` medía su propio error, no el del
        # instalador, porque las dos formas eran igual de inválidas)."""
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
        """Falsador directo del fallo 6-sep: el esquema real de un gancho de
        settings.json de Claude Code es {type, command, timeout} con la línea de
        órdenes ENTERA en `command`; no existe un campo `args`. Antes el instalador
        escribía {"command": "<python.exe>", "args": ["<script>", "--bandera"]},
        que ejecutaría python.exe pelado, sin guion."""
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
        """Fallo 6-sep, "roza": `statusMessage` no aparece en el esquema de gancho
        documentado (skill oficial `hook-development`: {type, command, timeout} para
        un gancho `command`) ni en ningún `settings.json` real de esta máquina — se
        quitó de `hooks/hooks.json`, `docs/ganchos_settings_ejemplo.json` y de aquí,
        `_anadir_hook`."""
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


if __name__ == '__main__':
    unittest.main()
