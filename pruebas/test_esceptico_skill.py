"""`esceptico` es una skill de Claude Code (`skills/esceptico/SKILL.md`), no un guion
Python: comprueba que `instalar.py` la copia, que su frontmatter parsea y que el
desinstalador solo la retira si lleva nuestra marca. El destino de la copia va siempre a una carpeta temporal, nunca a `~/.claude/skills/` real."""
import os
import re
import importlib.util
from pathlib import Path
import tempfile
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


def _colapsar(texto):
    """Colapsa espacios/saltos de línea a uno solo: el frontmatter YAML pliega
    (`description: >`) frases largas en varias líneas del fichero."""
    return re.sub(r'\s+', ' ', texto)


def _cargar_instalador():
    ruta = ay.RAIZ / 'instalar.py'
    spec = importlib.util.spec_from_file_location('abyss_instalador_bajo_prueba_esceptico', str(ruta))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TodaSkillQueCopiaElInstaladorLlevaLaMarca(unittest.TestCase):
    """Sin la marca en el frontmatter, `--desinstalar` no se atreve a borrar la copia y la deja."""

    def test_cada_modulo_skill_tiene_la_marca_en_su_frontmatter(self):
        inst = _cargar_instalador()
        for mod in inst.MODULOS:
            if mod.get('especial') != 'skill':
                continue
            carpeta = mod.get('carpeta_skill') or mod['id']
            ruta = ay.RAIZ / 'skills' / carpeta / 'SKILL.md'
            bloque = inst._frontmatter_bloque(str(ruta))
            self.assertTrue(bloque and any(l.strip() == inst.MARCA_SKILL_LINEA for l in bloque.splitlines()),
                            '%s: falta «%s» en el frontmatter' % (carpeta, inst.MARCA_SKILL_LINEA))


class SkillEscepticoExisteYSuFrontmatterParsea(unittest.TestCase):
    def test_el_fichero_fuente_existe_con_nombre_y_marca(self):
        ruta = ay.RAIZ / 'skills' / 'esceptico' / 'SKILL.md'
        self.assertTrue(ruta.is_file(), 'skills/esceptico/SKILL.md debe existir en el repo')
        texto = ruta.read_text(encoding='utf-8')
        lineas = texto.splitlines()
        self.assertEqual(lineas[0].strip(), '---', 'el fichero debe empezar con frontmatter YAML')
        fin = next(i for i in range(1, len(lineas)) if lineas[i].strip() == '---')
        bloque = '\n'.join(lineas[1:fin])
        self.assertIn('name: esceptico', bloque)
        self.assertIn('abyss-managed: true', bloque, 'la marca debe vivir en el FRONTMATTER, no en el cuerpo')

    def test_disparadores_estan_en_la_descripcion(self):
        texto = _colapsar((ay.RAIZ / 'skills' / 'esceptico' / 'SKILL.md').read_text(encoding='utf-8'))
        for disparador in ('/esceptico', 'tumba este plan', 'revisa antes de construir',
                           'try to refute this plan'):
            self.assertIn(disparador, texto, f'falta el disparador «{disparador}» en la descripción')


class InstaladorCopiaLaSkill(unittest.TestCase):
    def setUp(self):
        self.inst = _cargar_instalador()
        self.pkg_temporal = Path(tempfile.mkdtemp(prefix='abyss_pkg_esc_'))
        self.inst.PKG = str(self.pkg_temporal)  # nunca tocar el abyss/ real (config.json)
        self.tmp = Path(tempfile.mkdtemp(prefix='abyss_esceptico_'))
        self.settings_ruta = self.tmp / 'settings.json'
        self.skills_dir = self.tmp / 'skills'  # NUNCA ~/.claude/skills real
        self.mem = self.tmp / 'proyecto' / 'memory'
        self.mem.mkdir(parents=True, exist_ok=True)

    def test_instalar_copia_skill_con_su_marca(self):
        msjs = self.inst.instalar(
            ['esceptico'], settings_ruta=str(self.settings_ruta), python_exe='python-de-prueba',
            mem=str(self.mem), skills_dir=str(self.skills_dir))
        self.assertTrue(any('esceptico' in m and 'copiada' in m for m in msjs), msjs)

        destino = self.skills_dir / 'esceptico' / 'SKILL.md'
        self.assertTrue(destino.is_file(), 'debe haber copiado SKILL.md a <skills-dir>/esceptico/')
        texto = destino.read_text(encoding='utf-8')
        self.assertIn('abyss-managed: true', texto)
        # copiada fuera del sistema de plugins, la skill no puede depender de CLAUDE_PLUGIN_ROOT
        self.assertNotIn('${CLAUDE_PLUGIN_ROOT}', texto)
        self.assertIn(self.inst.RAIZ.replace(os.sep, '/') + '/abyss/', texto)

        # no debe haber tocado settings.json: esceptico no lleva gancho ni clave
        self.assertFalse(self.settings_ruta.exists())

    def test_estado_modulo_ve_la_skill_instalada(self):
        self.inst.instalar(
            ['esceptico'], settings_ruta=str(self.settings_ruta), python_exe='python-de-prueba',
            mem=str(self.mem), skills_dir=str(self.skills_dir))
        mod = self.inst.MODULOS_POR_ID['esceptico']
        st = self.inst.estado_modulo({}, mod, str(self.settings_ruta), str(self.skills_dir))
        self.assertTrue(st, 'tras instalar, estado_modulo debe ver la skill como instalada')


class DesinstaladorSoloRetiraLaSkillMarcada(unittest.TestCase):
    def setUp(self):
        self.inst = _cargar_instalador()
        self.pkg_temporal = Path(tempfile.mkdtemp(prefix='abyss_pkg_esc2_'))
        self.inst.PKG = str(self.pkg_temporal)
        self.tmp = Path(tempfile.mkdtemp(prefix='abyss_esceptico2_'))
        self.settings_ruta = self.tmp / 'settings.json'
        self.skills_dir = self.tmp / 'skills'
        self.mem = self.tmp / 'proyecto' / 'memory'
        self.mem.mkdir(parents=True, exist_ok=True)

    def test_desinstalar_retira_la_skill_que_instalamos(self):
        self.inst.instalar(
            ['esceptico'], settings_ruta=str(self.settings_ruta), python_exe='python-de-prueba',
            mem=str(self.mem), skills_dir=str(self.skills_dir))
        destino = self.skills_dir / 'esceptico'
        self.assertTrue(destino.is_dir())

        msjs = self.inst.desinstalar(
            ['esceptico'], settings_ruta=str(self.settings_ruta), mem=str(self.mem),
            skills_dir=str(self.skills_dir))
        self.assertTrue(any('retirada' in m for m in msjs), msjs)
        self.assertFalse(destino.exists(), 'la skill que SÍ instalamos nosotros debe desaparecer')

    def test_desinstalar_no_toca_una_skill_ajena_con_el_mismo_nombre(self):
        """Una skill con el mismo nombre puesta por el usuario (sin nuestra marca) no
        debe borrarse al desinstalar."""
        destino = self.skills_dir / 'esceptico'
        destino.mkdir(parents=True)
        (destino / 'SKILL.md').write_text(
            '---\nname: esceptico\ndescription: mi propia skill, nada que ver con abyss\n---\n# la mía\n',
            encoding='utf-8')

        msjs = self.inst.desinstalar(
            ['esceptico'], settings_ruta=str(self.settings_ruta), mem=str(self.mem),
            skills_dir=str(self.skills_dir))
        self.assertTrue(any('no lleva la marca' in m for m in msjs), msjs)
        self.assertTrue(destino.is_dir(), 'una skill ajena con el mismo nombre NO debe borrarse')
        self.assertTrue((destino / 'SKILL.md').exists())


if __name__ == '__main__':
    unittest.main()
