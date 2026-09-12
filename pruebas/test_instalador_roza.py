"""Cuatro comprobaciones puntuales de `instalar.py` (ver nombres de clase). Se
importa por ruta de fichero (no hace red ni `rutas.resolver()` a nivel de
módulo), con `PKG` en una carpeta temporal para no tocar el `abyss/` real."""
import os
import json
import tempfile
import importlib.util
from pathlib import Path
from unittest import mock
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


def _cargar_instalador():
    ruta = ay.RAIZ / 'instalar.py'
    spec = importlib.util.spec_from_file_location('abyss_instalador_bajo_prueba_roza', str(ruta))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CopiaFechadaNoPierdeColisiones(unittest.TestCase):
    def test_dos_copias_en_el_mismo_segundo_no_se_pisan(self):
        inst = _cargar_instalador()
        tmp = Path(tempfile.mkdtemp(prefix='abyss_copia_'))
        ruta = tmp / 'settings.json'
        ruta.write_text('{"a":1}', encoding='utf-8')

        with mock.patch.object(inst.time, 'strftime', return_value='20260906-215146'):
            d1 = inst._copia_fechada(str(ruta))
            ruta.write_text('{"a":2}', encoding='utf-8')  # cambia el contenido real antes de la 2ª copia
            d2 = inst._copia_fechada(str(ruta))

        self.assertIsNotNone(d1); self.assertIsNotNone(d2)
        self.assertNotEqual(d1, d2, 'dos copias en el mismo segundo deben quedar en ficheros distintos')
        self.assertEqual(Path(d1).read_text(encoding='utf-8'), '{"a":1}')
        self.assertEqual(Path(d2).read_text(encoding='utf-8'), '{"a":2}',
                          'la segunda copia no debe perderse por colisión de nombre de fichero')


class DatosGeneradosOmitirCuelgaDeSesiones(unittest.TestCase):
    def test_omitir_es_una_ruta_relativa_a_sesiones(self):
        inst = _cargar_instalador()
        esperado = os.path.join('sesiones', '.omitir')
        self.assertIn(esperado, inst.DATOS_GENERADOS,
                      'mem/sesiones/.omitir es donde continuidad.py lo escribe de verdad')
        self.assertNotIn('.omitir', inst.DATOS_GENERADOS,
                         '".omitir" suelto no existe como mem/.omitir: nunca lo encontraría --borrar-datos')


class EscribirJsonPreservaFinDeLineaLF(unittest.TestCase):
    """Un `settings.json` de partida en LF puro debe volver byte a byte tras
    un ciclo instalar→desinstalar (mismo JSON, sin CRLF de más)."""

    def test_ciclo_instalar_desinstalar_con_lf_de_partida_vuelve_byte_a_byte(self):
        inst = _cargar_instalador()
        pkg_temporal = Path(tempfile.mkdtemp(prefix='abyss_pkg_roza2_'))
        inst.PKG = str(pkg_temporal)

        tmp = Path(tempfile.mkdtemp(prefix='abyss_instalador_roza2_'))
        settings_ruta = tmp / 'settings.json'
        mem = tmp / 'proyecto' / 'memory'
        mem.mkdir(parents=True, exist_ok=True)

        # formato propio de `_escribir_json` (indent=2) en LF puro: el caso que
        # el README promete que vuelve exacto. Incluye ganchos ajenos y claves
        # sueltas para comprobar que también sobreviven intactos.
        datos_originales = {
            "permissions": {"allow": ["Bash(echo:*)"]},
            "otraClaveAjena": True,
            "hooks": {
                "SessionStart": [{"hooks": [{"type": "command", "command": "otro-programa --algo", "timeout": 10}]}],
                "PostToolUse": [{"hooks": [{"type": "command", "command": "otro-programa --post", "timeout": 10}]}],
                "Stop": [{"hooks": [{"type": "command", "command": "otro-programa --stop", "timeout": 10}]}],
            },
        }
        texto_original = json.dumps(datos_originales, ensure_ascii=False, indent=2) + '\n'
        with open(settings_ruta, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(texto_original)
        bytes_originales = settings_ruta.read_bytes()
        self.assertNotIn(b'\r\n', bytes_originales, 'el fixture de partida debe estar en LF puro')

        inst.instalar(['continuidad', 'preferencias'], settings_ruta=str(settings_ruta),
                       python_exe='python-de-prueba', mem=str(mem))
        inst.desinstalar(['continuidad', 'preferencias'], settings_ruta=str(settings_ruta), mem=str(mem))

        bytes_finales = settings_ruta.read_bytes()
        self.assertEqual(bytes_finales, bytes_originales,
                          'con un settings.json de partida en LF, ida y vuelta debe ser byte a byte')
        self.assertEqual(json.loads(bytes_finales), datos_originales)


class EstadoPermisosComparaLaReglaExacta(unittest.TestCase):
    def test_regla_ajena_no_cuenta_como_instalada_por_abyss(self):
        inst = _cargar_instalador()
        tmp = Path(tempfile.mkdtemp(prefix='abyss_permisos_'))
        settings_ruta = tmp / 'settings.json'
        otro_settings = tmp / 'otro' / 'settings.json'  # settings.json distinto al de esta prueba
        settings = {'permissions': {'allow': [f'Edit({otro_settings})']}}
        settings_ruta.write_text(json.dumps(settings), encoding='utf-8')

        mod_permisos = inst.MODULOS_POR_ID['permisos']
        st = inst.estado_modulo(settings, mod_permisos, str(settings_ruta))
        self.assertFalse(st, 'una regla Edit(...) sobre OTRO settings.json no es la que instala abyss')

    def test_regla_propia_si_cuenta_como_instalada(self):
        inst = _cargar_instalador()
        tmp = Path(tempfile.mkdtemp(prefix='abyss_permisos_'))
        settings_ruta = tmp / 'settings.json'
        settings = {'permissions': {'allow': [f'Edit({os.path.abspath(settings_ruta)})']}}
        settings_ruta.write_text(json.dumps(settings), encoding='utf-8')

        mod_permisos = inst.MODULOS_POR_ID['permisos']
        st = inst.estado_modulo(settings, mod_permisos, str(settings_ruta))
        self.assertTrue(st, 'la regla EXACTA que instalaría abyss sí debe leerse como instalada')


if __name__ == '__main__':
    unittest.main()
