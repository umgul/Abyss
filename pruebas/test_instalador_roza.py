"""Cuatro fallos «roza» de `instalar.py` señalados sobre la versión viva:

(1) `_copia_fechada`: si dos copias caen en el MISMO segundo (instalar y
    desinstalar seguidos), el nombre ya está tomado y la segunda se saltaba
    entera — se perdía la copia de seguridad justo antes del desinstalado.
(2) `DATOS_GENERADOS` incluía `'.omitir'` como si colgara directamente de `mem`,
    cuando el fichero real es `mem/sesiones/.omitir` (`continuidad.py` lo escribe
    ahí, y así lo dice la tabla del README).
(3) `estado_modulo` para «permisos» decía "instalado" con CUALQUIER regla
    `Edit(...)` que mencionara la palabra "settings", así que una regla que el
    usuario ya tenía por su cuenta se leía como si la hubiera puesto abyss.
(4) `_escribir_json` no fijaba `newline='\n'`: en Windows, un `settings.json`
    de partida en LF volvía en CRLF tras instalar/desinstalar — mismo
    contenido JSON, fichero entero marcado como modificado en cualquier diff.

Igual que `test_instalador.py`: se importa `instalar.py` DIRECTAMENTE por ruta de
fichero (no hace red ni `rutas.resolver()` a nivel de módulo), con `PKG` apuntado a
una carpeta temporal para no tocar el `abyss/` real.
"""
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
        # con el fallo, d2 == d1 (mismo nombre) y la copia de la 2ª llamada se saltaba
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
    """Fallo "roza" medido 7-sep: `_escribir_json()` abría el fichero temporal
    con `open(..., 'w')` SIN `newline='\\n'`, así que en Windows cada `\\n` del
    texto se traducía a `\\r\\n` al escribir. Con un `settings.json` de
    partida YA en el formato propio de `_escribir_json` (indent=2, un
    elemento por línea — lo que escriben tanto los editores como el propio
    Claude Code) y en LF, un ciclo instalar→desinstalar debía volver BYTE A
    BYTE y no lo hacía: 41 líneas LF entraban, 41 líneas CRLF salían — mismo
    CONTENIDO (`json.loads` igual) pero el fichero ENTERO aparecía como
    modificado en cualquier diff o git."""

    def test_ciclo_instalar_desinstalar_con_lf_de_partida_vuelve_byte_a_byte(self):
        inst = _cargar_instalador()
        pkg_temporal = Path(tempfile.mkdtemp(prefix='abyss_pkg_roza2_'))
        inst.PKG = str(pkg_temporal)

        tmp = Path(tempfile.mkdtemp(prefix='abyss_instalador_roza2_'))
        settings_ruta = tmp / 'settings.json'
        mem = tmp / 'proyecto' / 'memory'
        mem.mkdir(parents=True, exist_ok=True)

        # YA en el formato propio de `_escribir_json` (indent=2) y en LF puro —
        # el caso "común" que el README promete que sí vuelve exacto. Ganchos
        # ajenos en tres eventos que abyss no toca, más una clave suelta y
        # permissions.allow, para comprobar que también sobreviven intactos.
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
        # con el fallo, esto tenía MÁS bytes (\r\n en vez de \n) aunque el
        # contenido JSON fuera idéntico
        self.assertEqual(bytes_finales, bytes_originales,
                          'con un settings.json de partida en LF, ida y vuelta debe ser byte a byte')
        self.assertEqual(json.loads(bytes_finales), datos_originales)


class EstadoPermisosComparaLaReglaExacta(unittest.TestCase):
    def test_regla_ajena_no_cuenta_como_instalada_por_abyss(self):
        inst = _cargar_instalador()
        tmp = Path(tempfile.mkdtemp(prefix='abyss_permisos_'))
        settings_ruta = tmp / 'settings.json'
        otro_settings = tmp / 'otro' / 'settings.json'  # un settings.json DISTINTO del que usamos aquí
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
