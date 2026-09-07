"""`modelo.py` (ronda 2 de arreglos, 7-sep): fallo "engaña" medido sobre la versión
viva — `recorrer(tp)` leía el transcript VIVO sin mirar el tramo de `parentesis.py`
en absoluto, así que `texto(tp)` (librería de `continuidad.py --despertar`, llamada
en CADA prompt) podía reinyectar hasta 70/90 caracteres LITERALES de un turno dicho
DENTRO de un paréntesis abierto en el aviso `[modelo · revisión]` — que
`continuidad.py --despertar` mete en `additionalContext`, así que ese fragmento
VUELVE A VIAJAR a la API en el siguiente prompt. Es la misma familia de fallo que
ya se cerró en `vigia.leer_turno()` (`pruebas/test_parentesis.py::IntegracionConVigia`),
pero peor: aquí el texto no solo queda registrado en local, vuelve al PROMPT.

Con un transcript de 4 líneas donde el turno respondido por otro modelo (`claude-
opus-99`, con un "secreto" en su respuesta) cae DENTRO de un tramo cerrado y el
turno siguiente ya responde con el modelo preferido (`claude-fable-5-1`, el valor
por defecto de `modelo.preferido()` sin `modelo_preferido.json`): sin tramo (caso de
control) el aviso `[modelo · revisión]` reinyecta el texto secreto; con el tramo
marcado, `--despertar` no debe mencionarlo en absoluto — igual que exige
`ESPECIFICACION_TANDA2.md` T2.1 ("lo que el propio asistente vuelve a leer en hilos
futuros").
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


def _transcript_con_downgrade(tp):
    ay.escribir_jsonl(tp, [
        ay.usuario('esto es secretisimo rododendro y no debe volver a leerse jamas', '2026-01-01T10:05:00Z'),
        ay.asistente_texto('respondo con el dato secretisimo 987654 y la ruta C:/secreto/rododendro.txt',
                            '2026-01-01T10:05:05Z', modelo='claude-opus-99'),
        ay.usuario('sigamos charlando', '2026-01-01T10:06:00Z'),
        ay.asistente_texto('vale, ya vuelvo a fable', '2026-01-01T10:06:05Z', modelo='claude-fable-5-1'),
    ])


class ParentesisNoViajaAlAvisoDeRevision(unittest.TestCase):
    def test_sin_tramo_el_turno_ajeno_si_se_reinyecta(self):
        """Control: sin ningún paréntesis marcado, el mecanismo de revisión sigue
        funcionando como siempre — el filtro no apaga la función en general."""
        proj = ay.nuevo_proyecto()
        sid = 'ses-modelo-control'
        tp = proj / f'{sid}.jsonl'
        _transcript_con_downgrade(tp)
        env = ay.entorno(proj)
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj), 'prompt': 'sigamos'})
        r = ay.ejecutar(ay.script('continuidad.py'), ['--despertar'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('secretisimo', r.stdout, 'sin tramo, el aviso de revisión sí debe citar el turno ajeno')
        self.assertIn('987654', r.stdout)

    def test_con_tramo_el_turno_ajeno_no_se_reinyecta(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-modelo-tramo'
        tp = proj / f'{sid}.jsonl'
        _transcript_con_downgrade(tp)
        mem = proj / 'memory'
        mem.mkdir(parents=True, exist_ok=True)
        # el tramo cubre EXACTAMENTE el turno respondido por el otro modelo (10:05:00
        # a 10:05:05), y se cierra antes del turno siguiente (10:06:00) que ya
        # responde con el modelo preferido.
        (mem / 'parentesis.json').write_text(json.dumps({
            sid: [{'inicio': '2026-01-01T10:04:00+00:00', 'fin': '2026-01-01T10:05:30+00:00', 'motivo': 'prueba'}]
        }), encoding='utf-8')
        env = ay.entorno(proj)
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj), 'prompt': 'sigamos'})
        r = ay.ejecutar(ay.script('continuidad.py'), ['--despertar'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('secretisimo', r.stdout, 'nada dicho DENTRO del tramo debe volver a viajar al prompt')
        self.assertNotIn('987654', r.stdout)
        self.assertNotIn('rododendro', r.stdout)
        # con el único turno ajeno oculto, no queda nada que revisar: sin aviso
        self.assertNotIn('[modelo', r.stdout)

    def test_tramo_abierto_sin_cerrar_tambien_oculta(self):
        """Un tramo `--abrir` sin `--cerrar` (`fin: None`) se trata como abierto
        hasta ahora mismo (`parentesis.en_parentesis()`): el turno ajeno, dicho
        DESPUÉS del `--abrir` y nunca cerrado, tampoco debe reinyectarse."""
        proj = ay.nuevo_proyecto()
        sid = 'ses-modelo-abierto'
        tp = proj / f'{sid}.jsonl'
        _transcript_con_downgrade(tp)
        mem = proj / 'memory'
        mem.mkdir(parents=True, exist_ok=True)
        (mem / 'parentesis.json').write_text(json.dumps({
            sid: [{'inicio': '2026-01-01T10:04:00+00:00', 'fin': None, 'motivo': 'prueba'}]
        }), encoding='utf-8')
        env = ay.entorno(proj)
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj), 'prompt': 'sigamos'})
        r = ay.ejecutar(ay.script('continuidad.py'), ['--despertar'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('secretisimo', r.stdout)
        self.assertNotIn('vale, ya vuelvo a fable', r.stdout)


if __name__ == '__main__':
    unittest.main()
