"""Regla dura 4 del encargo 6-sep: nada de datos personales en el repo (ni el
nombre de pila del autor, ni el nombre de otro proyecto privado suyo, ni rutas
`C:/Users/<alguien>`, ni tokens, ni ids de chat) — el usuario se llama «el
usuario». Dos fallos ya medidos por el revisor entraban aquí:
`abyss/notify_telegram.ps1.plantilla` (una frase de ejemplo que citaba el nombre
de ese otro proyecto suyo, en un fichero que SÍ se distribuye) y
`ESPECIFICACION.md`/`ESPECIFICACION_TANDA2.md` (varias apariciones del nombre de
pila del autor).

SEGUNDA VUELTA (6-sep, revisor Opus, "roza"): el único fichero del repo con datos
personales de verdad era ESTE, porque su propio docstring citaba los nombres (para
contar la historia del fallo, sin necesitarlo) y `EXCLUIR_DIRS` saltaba `pruebas/`
ENTERA en vez de solo este fichero — cualquier dato personal que se colara en un
test futuro (una ruta real en un fixture, un id de chat) no se habría cazado. Ahora
el docstring ya no nombra a nadie, y se escanea TODO el repo, `pruebas/` incluida,
salvo ESTE fichero (que sí necesita las palabras, literalmente, en su propia
regex, para poder buscarlas) y `__pycache__`.

TERCERA VUELTA (revisor Opus, "roza"): `abyss/config.json` es el ÚNICO fichero que
el propio paquete instalado escribe dentro de la carpeta de código (ESPECIFICACION.md
§1/§4) — lleva la ruta absoluta del intérprete detectado, así que en cuanto alguien
ejecuta `instalar.py` una sola vez, esa ruta (con el nombre de pila de quien sea)
aparece ahí y esta prueba lo acusaba de dato personal publicado, cuando en realidad
es un artefacto de ejecución que `.gitignore:17` excluye explícitamente de lo que se
publica. `_ficheros_del_repo()` recorría por extensión sin mirar el `.gitignore`, así
que trataba un fichero ignorado como si estuviera en el repo. Ahora se lee el propio
`.gitignore` y se salta cualquier ruta que case con él (además de, como mínimo,
`abyss/config.json` por nombre, de propina, por si el `.gitignore` cambiase de forma
que dejase de cubrirlo) — el criterio de «qué se publica» vive en el `.gitignore`,
no duplicado a mano aquí.

CUARTA VUELTA (revisor Opus, "roza"): `ConfigJsonGeneradoNoEsPublicado` y
`UnFicheroNoIgnoradoSigueVigilado` ESCRIBÍAN sobre el repo real (`abyss/config.json`
y `docs/_decoy_prueba_datos_personales.md`) para poder probar los dos casos límite
— justo el tipo de mutación que `ESPECIFICACION_TANDA2.md` pide evitar («todo en
directorios temporales»). Medido por simulación de muerte dura (`os._exit(3)` justo
tras escribir el señuelo, equivalente a un corte de luz o un `taskkill /F`): el
señuelo sobrevivía en `docs/` (una ruta que `.gitignore` NO cubre, así que SÍ se
publicaría) y la siguiente corrida quedaba en rojo por su propia comprobación
`assertFalse(RUTA.exists(), ...)`; y correr la suite entera cambiaba el `mtime` de
`abyss/config.json` en el repo REAL. Ahora las dos pruebas trabajan sobre una COPIA
temporal del repo (`shutil.copytree` a un directorio bajo `tempfile`, borrado con
`addCleanup` — sobrevive incluso a un fallo a mitad de la prueba, aunque no a una
muerte dura del proceso, que ningún `finally`/`addCleanup` de Python puede
interceptar): nunca tocan un byte del repo real, así que una corrida interrumpida
no puede dejar nada personal publicable ni cambiar ningún fichero de verdad."""
import fnmatch
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ESTE_FICHERO_REL = Path(__file__).resolve().relative_to(RAIZ)
PROHIBIDAS = re.compile(r'\b(jordi|caela|vencejo)\b', re.IGNORECASE)
EXTENSIONES = {'.py', '.md', '.json', '.ps1', '.plantilla', '.txt', '.cfg', '.ini', '.js', '.html'}
EXCLUIR_DIRS = {'__pycache__', '.git'}
# Artefactos de ejecución gitignorados que NUNCA cuentan como «publicados» aunque
# `.gitignore` cambiara de forma o no se pudiera leer (ESPECIFICACION.md §1/§4):
# la única excepción documentada es este fichero, que escribe el propio instalador.
SIEMPRE_IGNORADOS = {'abyss/config.json'}
# Y los tres sitios donde el autor SE DECLARA, que es lo contrario de un dato personal
# colado: un paquete sin autor con nombre real es un hallazgo de su propio auditor
# (`auditar.py`, comprobación 1: «ningún manifiesto declara un autor con nombre real»),
# y la licencia Apache-2.0 pide un titular de copyright o no protege a nadie. La regla
# general no se toca: el nombre va AQUÍ y en ningún otro fichero del repositorio, y esta
# lista es corta a propósito para que ampliarla sea una decisión, no un descuido.
DONDE_SE_FIRMA = {'LICENSE', '.claude-plugin/plugin.json', '.claude-plugin/marketplace.json'}


def _patrones_gitignore(raiz):
    ruta = raiz / '.gitignore'
    if not ruta.exists():
        return []
    patrones = []
    for linea in ruta.read_text(encoding='utf-8').splitlines():
        linea = linea.strip()
        if not linea or linea.startswith('#') or linea.startswith('!'):
            continue  # sin negaciones en este .gitignore; no hacen falta aquí
        patrones.append(linea)
    return patrones


def _ignorado(ruta, patrones, raiz):
    """Replica el subconjunto de semántica de `.gitignore` que usan sus patrones
    (anclado a la raíz si lleva `/` que no sea solo el final, `**/` = cualquier
    profundidad, sin `/` = nombre en cualquier sitio, `/` final = directorio)."""
    rel = ruta.relative_to(raiz).as_posix()
    if rel in SIEMPRE_IGNORADOS or rel in DONDE_SE_FIRMA:
        return True
    partes = rel.split('/')
    for pat in patrones:
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
            if fnmatch.fnmatch(rel, p) or (es_dir and (rel == p or rel.startswith(p + '/'))):
                return True
        elif es_dir:
            if p in partes[:-1]:
                return True
        elif fnmatch.fnmatch(partes[-1], p):
            return True
    return False


def _ficheros_del_repo(raiz):
    """`raiz` es la raíz a escanear — el repo real (`RAIZ`, por defecto en
    `_todos_los_hallazgos()`) o una COPIA temporal (las dos pruebas que necesitan
    escribir un fichero para el caso límite). `ESTE_FICHERO_REL` se compara por
    ruta RELATIVA, no absoluta: así la copia de este mismo fichero de pruebas
    (que SÍ lleva las palabras prohibidas, literalmente, en su propia regex y en
    este docstring) también se salta correctamente dentro de una copia."""
    patrones = _patrones_gitignore(raiz)
    for dirpath, dirnames, filenames in os.walk(raiz):
        dirnames[:] = [d for d in dirnames if d not in EXCLUIR_DIRS]
        for nombre in filenames:
            ruta = Path(dirpath) / nombre
            if ruta.relative_to(raiz) == ESTE_FICHERO_REL:
                continue  # este SÍ necesita las palabras, literalmente, en su propia regex
            if ruta.suffix in EXTENSIONES or ruta.name.endswith('.plantilla'):
                if _ignorado(ruta, patrones, raiz):
                    continue  # artefacto de ejecución que el propio repo declara no publicable
                yield ruta


def _hallazgos_de(ruta, raiz):
    try:
        texto = ruta.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return []
    out = []
    for m in PROHIBIDAS.finditer(texto):
        linea = texto.count('\n', 0, m.start()) + 1
        out.append(f'{ruta.relative_to(raiz)}:{linea}: «{m.group(0)}»')
    return out


def _todos_los_hallazgos(raiz=RAIZ):
    hallazgos = []
    for ruta in _ficheros_del_repo(raiz):
        hallazgos.extend(_hallazgos_de(ruta, raiz))
    return hallazgos


def _copia_temporal_del_repo(caso):
    """COPIA completa del repo bajo un directorio temporal del sistema — para las
    pruebas que necesitan escribir un fichero de más para ejercitar un caso
    límite, sin tocar el repo real ni un instante (§ cuarta vuelta, arriba).
    `caso` es solo un prefijo legible en el nombre del directorio temporal."""
    tmp = Path(tempfile.mkdtemp(prefix=f'abyss_repo_copia_{caso}_'))
    copia = tmp / 'repo'
    shutil.copytree(RAIZ, copia, ignore=shutil.ignore_patterns(*EXCLUIR_DIRS))
    return tmp, copia


class RepoSinNombresPropiosPersonales(unittest.TestCase):
    def test_ningun_fichero_publicado_nombra_a_una_persona_o_proyecto_privado(self):
        hallazgos = _todos_los_hallazgos()
        self.assertEqual(hallazgos, [], 'datos personales encontrados en el repo:\n' + '\n'.join(hallazgos))


class ConfigJsonGeneradoNoEsPublicado(unittest.TestCase):
    """Falsador del fallo "roza" (revisor 3): `abyss/config.json` es un artefacto
    del instalador, gitignorado (§1/§4) — no debe tumbar esta prueba aunque lleve
    de verdad un nombre de pila dentro (la ruta absoluta del intérprete).

    Cuarta vuelta: sobre una COPIA temporal del repo (`_copia_temporal_del_repo`),
    nunca sobre el `abyss/config.json` real — así la prueba nunca cambia un
    fichero del repo de verdad, y sobrevive intacta a un fallo a mitad de la
    prueba (no hace falta ningún `finally` que restaure nada real)."""

    def test_config_json_con_nombre_de_pila_no_cuenta_como_publicado(self):
        tmp, copia = _copia_temporal_del_repo('config')
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (copia / 'abyss' / 'config.json').write_text(
            '{"python": "C:\\\\Users\\\\jordi\\\\AppData\\\\Local\\\\Programs\\\\Python\\\\python.exe", '
            '"actualizado": "2026-09-07"}',
            encoding='utf-8')
        hallazgos = _todos_los_hallazgos(copia)
        de_config = [h for h in hallazgos if h.startswith('abyss') and 'config.json' in h]
        self.assertEqual(de_config, [], 'abyss/config.json es un artefacto del instalador '
                          '(gitignorado, ESPECIFICACION.md §1/§4): no cuenta como publicado')


class UnFicheroNoIgnoradoSigueVigilado(unittest.TestCase):
    """Falsador en la otra dirección: un nombre prohibido en un fichero que
    `.gitignore` NO cubre (aquí, `docs/`) tiene que seguir cazándose — si no,
    la exclusión de arriba sería demasiado ancha y dejaría de medir nada.

    Cuarta vuelta: el señuelo se escribe dentro de una COPIA temporal del repo,
    nunca en `docs/` de verdad — medido por simulación de muerte dura
    (`os._exit` justo tras escribir el señuelo): con el fallo anterior, el
    señuelo sobrevivía en el repo real bajo una ruta que `.gitignore` NO cubre
    (SÍ se publicaría) y dejaba la siguiente corrida en rojo por su propia
    comprobación de partida; sobre una copia temporal, la muerte dura como
    mucho deja basura en `tempfile.gettempdir()`, nunca en el repo."""

    def test_un_fichero_normal_con_nombre_prohibido_se_sigue_cazando(self):
        tmp, copia = _copia_temporal_del_repo('decoy')
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        decoy = copia / 'docs' / '_decoy_prueba_datos_personales.md'
        decoy.write_text('nota de prueba que menciona a jordi de pasada', encoding='utf-8')
        hallazgos = _todos_los_hallazgos(copia)
        self.assertTrue(
            any(decoy.name in h for h in hallazgos),
            'un fichero NO ignorado con un nombre prohibido debe seguir cazándose')


if __name__ == '__main__':
    unittest.main()
