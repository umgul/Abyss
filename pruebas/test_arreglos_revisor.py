"""Falsadores de los cinco fallos señalados el 6-sep sobre la versión viva:

(nota 6-sep, fallo "la suite no es independiente de la red"): `ArranqueEnFrioNoRompeElJSON`
lanza `continuidad.py --arranque`, que llama a `exterocepcion.py`/`noticias.py` como
librerías — sin `ABYSS_SIN_RED=1` esto haría peticiones reales (ipinfo.io,
news.google.com), violando la regla dura 2 del encargo ("sin red en la suite").
`ABYSS_SIN_RED=1` corta esas llamadas al instante, sin tocar la red ni depender de
si la máquina que corre la prueba tiene conexión.

(a) `continuidad.py --arranque`: `cerrar()` imprimía sus avisos por su cuenta
    (arranque en frío, índice que pide recorte) ANTES del único JSON que debe
    salir por el stdout del gancho SessionStart — lo rompía. Ahora `cerrar()`
    devuelve los avisos y `--arranque` los mete DENTRO de `additionalContext`,
    antes de `json.dumps`.
(d) `continuidad.py --cierre` tiraba el código de salida y el stderr de
    `varas.py --index`: si varas.py revienta con una excepción sin capturar
    (MEMORY.md convertido en directorio, por ejemplo) no queda ningún rastro.
    Ahora un `returncode != 0` deja una línea fechada en `mem/varas.log` con la
    última línea de stderr.

(b) y (c) — el positional que se cuela como `transcript_path` en `modelo.py`,
`exterocepcion.py` y `noticias.py` — tienen su propio fichero,
`test_validacion_posicionales.py`.
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


class ArranqueEnFrioNoRompeElJSON(unittest.TestCase):
    def test_arranque_bajo_umbral_sigue_siendo_json_valido(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-arranque-frio-1'
        tp = proj / f'{sid}.jsonl'
        ay.sesion_simple(tp, ['hola, primer mensaje de esta sesión que arranca en frío'])
        # Una ficha .md YA existente (6-sep: varas.py --index ya no escribe NADA en un
        # proyecto sin ninguna ficha — otro fallo, ver test_varas_no_crea_de_la_nada.py
        # — así que aquí hace falta al menos una para que llegue al aviso que este
        # falsador quiere ejercitar).
        mem = proj / 'memory'; mem.mkdir(parents=True, exist_ok=True)
        (mem / 'una-ficha.md').write_text('---\ntype: reference\n---\ncontenido\n', encoding='utf-8')
        # NINGUNA sesión archivada todavía en memory/sesiones/ (la propia no cuenta:
        # --arranque cosecha las de OTROS hilos, nunca la que está empezando) → varas.py
        # dirá «sin vara todavía» por SU stdout, que es justo el aviso que antes se
        # colaba crudo delante del JSON.
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        env = ay.entorno(proj, ABYSS_SIN_RED='1')  # sin esto, --arranque llamaría a ipinfo/news.google real
        r = ay.ejecutar(ay.script('continuidad.py'), ['--arranque'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip(), 'debería imprimir algo en --arranque')

        # con el fallo (a), esto lanza json.decoder.JSONDecodeError: el aviso de
        # varas.py salía impreso ANTES de esta línea, no dentro de ella.
        payload = json.loads(r.stdout)
        contexto = payload['hookSpecificOutput']['additionalContext']
        self.assertIn('sin vara', contexto)


class VarasQueRevientaDejaRastro(unittest.TestCase):
    def test_cierre_con_memory_md_como_directorio_deja_linea_en_varas_log(self):
        proj = ay.nuevo_proyecto()
        mem = proj / 'memory'
        mem.mkdir(parents=True, exist_ok=True)
        (mem / 'MEMORY.md').mkdir()  # MEMORY.md convertido en directorio: varas.py
        # revienta con una excepción sin capturar nada más abrirlo (open() sobre un
        # directorio) y sale con código != 0 y traza en stderr.

        sid = 'ses-cierre-revienta-1'
        tp = proj / f'{sid}.jsonl'
        ay.sesion_simple(tp, ['hola, esto es una sesión de prueba para el cierre'])
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        env = ay.entorno(proj)

        log = mem / 'varas.log'
        self.assertFalse(log.exists())

        r = ay.ejecutar(ay.script('continuidad.py'), ['--cierre'], env, entrada=entrada)
        # el gancho en sí no debe reventar aunque varas.py sí lo haga por dentro
        self.assertEqual(r.returncode, 0, r.stderr)

        # con el fallo (d) esto falla: rc y stderr de varas.py se tiraban en silencio
        # y no quedaba ningún rastro del reventón.
        self.assertTrue(log.exists(), 'debe quedar rastro del fallo de varas.py en varas.log')
        contenido = log.read_text(encoding='utf-8')
        self.assertTrue(contenido.strip(), 'el log no debe quedar vacío')
        self.assertIn('varas', contenido)


if __name__ == '__main__':
    unittest.main()
