"""Ningún fichero publicado del repo nombra a una persona ni lleva rutas de usuario
o secretos: el usuario es «el usuario». Lo que `.gitignore` excluye no cuenta como
publicado; el nombre del autor solo puede aparecer donde firma (`DONDE_SE_FIRMA`)."""
import fnmatch
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ESTE_FICHERO_REL = Path(__file__).resolve().relative_to(RAIZ)
PROHIBIDAS = re.compile(
    r'\b(jordi|caela|vencejo)\b'
    r'|[A-Za-z]:[\\/]+Users[\\/]+(?!<|\.\.\.)[A-Za-z0-9_.-]{3,}'   # C:/Users/<alguien> real; marcadores (<x>, x, ...) no
    r'|MLY\|'                                             # token de Mapillary
    r'|\b(?:sk-|hf_|ghp_|gho_)[A-Za-z0-9]{20,}'           # claves de API con prefijo conocido
    r'|\b\d{8,10}:[A-Za-z0-9_-]{35}\b',                   # token de bot de Telegram
    re.IGNORECASE)
EXTENSIONES = {'.py', '.md', '.json', '.jsonl', '.ps1', '.plantilla', '.txt', '.cfg', '.ini',
               '.js', '.html', '.yaml', '.yml', '.toml'}
EXCLUIR_DIRS = {'__pycache__', '.git'}
SIEMPRE_IGNORADOS = {'abyss/config.json'}   # lo escribe el instalador; .gitignore ya lo excluye
# Los tres sitios donde el autor SE DECLARA: se escanean igual, pero sin su nombre tal
# como lo firma `plugin.json` (`author.name`). Cualquier otro dato personal ahí cuenta.
DONDE_SE_FIRMA = {'LICENSE', '.claude-plugin/plugin.json', '.claude-plugin/marketplace.json'}


def _firma(raiz):
    try:
        m = json.loads((raiz / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8'))
        return (m.get('author') or {}).get('name') or ''
    except Exception:
        return ''


def _patrones_gitignore(raiz):
    ruta = raiz / '.gitignore'
    if not ruta.exists():
        return []
    patrones = []
    for linea in ruta.read_text(encoding='utf-8').splitlines():
        linea = linea.strip()
        if not linea or linea.startswith('#'):
            continue
        negado = linea.startswith('!')
        patrones.append((negado, linea[1:] if negado else linea))
    return patrones


def _casa(rel, partes, pat):
    p = pat
    es_dir = p.endswith('/')
    if es_dir:
        p = p[:-1]
    if p.startswith('**/'):
        p = p[3:]
        anclado = False
    elif p.startswith('/'):
        p = p[1:]
        anclado = True
    else:
        anclado = '/' in p
    if anclado:
        return fnmatch.fnmatch(rel, p) or (es_dir and (rel == p or rel.startswith(p + '/')))
    if es_dir:
        return p in partes[:-1]
    return fnmatch.fnmatch(partes[-1], p)


def _ignorado(ruta, patrones, raiz):
    """Semántica de `.gitignore` reducida a lo que usa el del repo: anclado si lleva
    `/` en medio, `**/` = cualquier profundidad, `/` final = directorio, y `!`
    reincluye (gana el último patrón que casa)."""
    rel = ruta.relative_to(raiz).as_posix()
    if rel in SIEMPRE_IGNORADOS:
        return True
    partes = rel.split('/')
    ignorado = False
    for negado, pat in patrones:
        if _casa(rel, partes, pat):
            ignorado = not negado
    return ignorado


def _ficheros_del_repo(raiz):
    """Ficheros de texto publicables bajo `raiz` (el repo real o una copia temporal).
    Este fichero se salta por ruta relativa: lleva las palabras en su propia regex."""
    patrones = _patrones_gitignore(raiz)
    for dirpath, dirnames, filenames in os.walk(raiz):
        dirnames[:] = [d for d in dirnames if d not in EXCLUIR_DIRS]
        for nombre in filenames:
            ruta = Path(dirpath) / nombre
            if ruta.relative_to(raiz) == ESTE_FICHERO_REL:
                continue
            if ruta.suffix in EXTENSIONES or ruta.suffix == '' or ruta.name.endswith('.plantilla'):
                if not _ignorado(ruta, patrones, raiz):
                    yield ruta


def _hallazgos_de(ruta, raiz, firma):
    try:
        texto = ruta.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return []
    rel = ruta.relative_to(raiz).as_posix()
    if rel in DONDE_SE_FIRMA and firma:
        texto = texto.replace(firma, '')
    out = []
    for m in PROHIBIDAS.finditer(texto):
        linea = texto.count('\n', 0, m.start()) + 1
        out.append(f'{rel}:{linea}: «{m.group(0)}»')
    return out


def _todos_los_hallazgos(raiz=RAIZ):
    firma = _firma(raiz)
    hallazgos = []
    for ruta in _ficheros_del_repo(raiz):
        hallazgos.extend(_hallazgos_de(ruta, raiz, firma))
    return hallazgos


def _copia_temporal_del_repo(caso):
    """Copia del repo bajo un directorio temporal, para las pruebas que necesitan
    escribir un fichero de más sin tocar el repo real."""
    tmp = Path(tempfile.mkdtemp(prefix=f'abyss_repo_copia_{caso}_'))
    copia = tmp / 'repo'
    shutil.copytree(RAIZ, copia, ignore=shutil.ignore_patterns(*EXCLUIR_DIRS))
    return tmp, copia


class RepoSinNombresPropiosPersonales(unittest.TestCase):
    def test_ningun_fichero_publicado_nombra_a_una_persona_o_proyecto_privado(self):
        hallazgos = _todos_los_hallazgos()
        self.assertEqual(hallazgos, [], 'datos personales encontrados en el repo:\n' + '\n'.join(hallazgos))


class SobreUnaCopiaTemporal(unittest.TestCase):
    def _copia(self, caso):
        tmp, copia = _copia_temporal_del_repo(caso)
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        return copia

    def test_config_json_del_instalador_no_cuenta_como_publicado(self):
        copia = self._copia('config')
        (copia / 'abyss' / 'config.json').write_text(
            '{"python": "C:\\\\Users\\\\jordi\\\\AppData\\\\Local\\\\Programs\\\\Python\\\\python.exe"}',
            encoding='utf-8')
        de_config = [h for h in _todos_los_hallazgos(copia) if 'config.json' in h]
        self.assertEqual(de_config, [])

    def test_un_fichero_no_ignorado_se_sigue_cazando(self):
        copia = self._copia('decoy')
        decoy = copia / 'docs' / '_decoy_prueba_datos_personales.md'
        decoy.write_text('nota de prueba que menciona a jordi de pasada', encoding='utf-8')
        self.assertTrue(any(decoy.name in h for h in _todos_los_hallazgos(copia)))

    def test_los_ficheros_firmados_se_escanean_salvo_la_firma(self):
        copia = self._copia('firma')
        ruta = copia / '.claude-plugin' / 'plugin.json'
        m = json.loads(ruta.read_text(encoding='utf-8'))
        m['description'] = 'nota que menciona a jordi'
        ruta.write_text(json.dumps(m), encoding='utf-8')
        hallazgos = _todos_los_hallazgos(copia)
        self.assertTrue(any('plugin.json' in h for h in hallazgos), hallazgos)

    def test_una_negacion_del_gitignore_reincluye(self):
        copia = self._copia('negacion')
        mp = copia / 'abyss' / 'vendor' / 'mp'
        mp.mkdir(parents=True, exist_ok=True)
        (mp / 'LICENSE-prueba.txt').write_text('licencia que menciona a jordi', encoding='utf-8')
        (mp / 'otro.txt').write_text('binario ignorado que menciona a jordi', encoding='utf-8')
        hallazgos = _todos_los_hallazgos(copia)
        self.assertTrue(any('LICENSE-prueba.txt' in h for h in hallazgos), hallazgos)
        self.assertFalse(any('otro.txt' in h for h in hallazgos), hallazgos)

    def test_una_ruta_de_usuario_real_o_un_token_se_cazan(self):
        copia = self._copia('token')
        f = copia / 'docs' / '_decoy_token.md'
        f.write_text('ruta C:/Users/alguien/x y clave MLY|123|abc y sk-' + 'a' * 24, encoding='utf-8')
        hallazgos = [h for h in _todos_los_hallazgos(copia) if '_decoy_token.md' in h]
        self.assertEqual(len(hallazgos), 3, hallazgos)


if __name__ == '__main__':
    unittest.main()
