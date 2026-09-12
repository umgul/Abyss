"""`varas.py --index`: una lectura de ficha (`"name":"Read"`) hecha dentro de
un tramo de `parentesis.py` no debe subirle el ◆ (peso de uso) a esa ficha en
`MEMORY.md` — justo lo que el asistente relee al empezar cada hilo."""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay

N_SESIONES_ARCHIVADAS = 8  # == propiocepcion.UMBRAL_FRIO: justo para salir del arranque en frío
FICHAS = ('ficha-secreta.md', 'ficha-b.md', 'ficha-c.md', 'ficha-d.md')


def _linea_read(ruta_ficha, ts):
    """Una línea de transcript que `varas.py` reconoce como lectura de ficha:
    debe contener literalmente `"name":"Read"` (JSON compacto, sin espacio
    tras los dos puntos, como serializa el harness real) y `memory` en la ruta."""
    d = {'type': 'assistant', 'timestamp': ts,
         'message': {'content': [{'type': 'tool_use', 'name': 'Read', 'input': {'file_path': ruta_ficha}}]}}
    return json.dumps(d, separators=(',', ':'), ensure_ascii=False)


def _preparar_proyecto():
    proj = ay.nuevo_proyecto()
    mem = proj / 'memory'
    mem.mkdir(parents=True, exist_ok=True)
    ses = mem / 'sesiones'
    ses.mkdir(parents=True, exist_ok=True)
    for i in range(N_SESIONES_ARCHIVADAS):
        (ses / f'archivada-{i}.jsonl').write_text('{}\n', encoding='utf-8')
    for f in FICHAS:
        (mem / f).write_text(f'# {f}\n', encoding='utf-8')
    lineas = ['# Mi memoria', ''] + [f'- [{f[:-3]}]({f})' for f in FICHAS]
    (mem / 'MEMORY.md').write_text('\n'.join(lineas) + '\n', encoding='utf-8')
    return proj, mem


class LecturaDentroDelTramoNoCuentaComoUso(unittest.TestCase):
    def test_sin_tramo_la_lectura_si_sube_el_glifo(self):
        """Control: sin ningún paréntesis marcado, una lectura real de la ficha
        SÍ le sube el ◆ — el filtro no apaga la medida en general."""
        proj, mem = _preparar_proyecto()
        sid = 'ses-varas-control'
        tp = proj / f'{sid}.jsonl'
        ruta_ficha = str(mem / 'ficha-secreta.md')
        tp.write_text(_linea_read(ruta_ficha, '2026-01-01T10:05:05Z') + '\n', encoding='utf-8')

        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('varas.py'), ['--index'], env)
        self.assertEqual(r.returncode, 0, r.stderr)

        indice = (mem / 'MEMORY.md').read_text(encoding='utf-8')
        self.assertIn('[ficha-secreta](ficha-secreta.md) ◆', indice,
                       'sin tramo, la lectura real de la ficha debe subirle el ◆')

    def test_con_tramo_la_lectura_no_sube_el_glifo(self):
        proj, mem = _preparar_proyecto()
        sid = 'ses-varas-tramo'
        tp = proj / f'{sid}.jsonl'
        ruta_ficha = str(mem / 'ficha-secreta.md')
        ts = '2026-01-01T10:05:05Z'
        tp.write_text(_linea_read(ruta_ficha, ts) + '\n', encoding='utf-8')
        # el tramo cubre EXACTAMENTE el instante de esa lectura
        (mem / 'parentesis.json').write_text(json.dumps({
            sid: [{'inicio': '2026-01-01T10:04:00+00:00', 'fin': '2026-01-01T10:06:00+00:00', 'motivo': 'prueba'}]
        }), encoding='utf-8')

        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('varas.py'), ['--index'], env)
        self.assertEqual(r.returncode, 0, r.stderr)

        indice = (mem / 'MEMORY.md').read_text(encoding='utf-8')
        self.assertIn('[ficha-secreta](ficha-secreta.md)', indice, 'el enlace en sí no debe desaparecer')
        self.assertNotIn('[ficha-secreta](ficha-secreta.md) ◆', indice,
                          'una lectura hecha DENTRO del tramo no debe subirle el ◆ a la ficha')


if __name__ == '__main__':
    unittest.main()
