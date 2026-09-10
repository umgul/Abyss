"""`esceptico` no es un guion Python — es una
skill de Claude Code (`skills/esceptico/SKILL.md`) que `instalar.py` copia a la
carpeta de skills del usuario (`--skills-dir`, por defecto `~/.claude/skills`).
"la prueba comprueba que el instalador la copia, que el frontmatter parsea y que
el desinstalador la retira solo si lleva nuestra marca."

Import directo por ruta de fichero, igual que `test_instalador.py` (sin red ni
`rutas.resolver()` a nivel de módulo). `RAIZ_SKILLS` de `instalar.py` apunta al
`skills/` REAL del repo (no hay por qué fingirlo: es contenido versionado, no un
artefacto de ejecución) — solo el DESTINO de la copia va a una carpeta temporal,
nunca al `~/.claude/skills/` real de quien corra la prueba (regla dura 1/2)."""
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
    """Espacios/saltos de línea a un solo espacio — el frontmatter YAML pliega
    (`description: >`) una frase larga en varias líneas del FICHERO; buscar la
    frase disparadora tal cual (sin colapsar) fallaría por un salto de línea que
    no significa nada para quien lee la skill renderizada."""
    return re.sub(r'\s+', ' ', texto)


def _cargar_instalador():
    ruta = ay.RAIZ / 'instalar.py'
    spec = importlib.util.spec_from_file_location('abyss_instalador_bajo_prueba_esceptico', str(ruta))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
        self.assertIn('abyss-managed: true', destino.read_text(encoding='utf-8'))

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
        """Falsador directo de que `desinstalar()` solo retira la skill copiada si
        lleva nuestra marca: una carpeta `esceptico/SKILL.md` que
        el usuario ya tuviera puesta por su cuenta (sin nuestra marca) no debe
        borrarse solo porque `--desinstalar esceptico` se ejecute."""
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
