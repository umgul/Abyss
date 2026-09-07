"""`varas.py --index` (fallo 6-sep, "engaña"): escribía MEMORY.md SIEMPRE, exista o
no. MEDIDO: en un proyecto virgen (memory/ vacío) el gancho SessionEnd (que dispara
en TODOS los proyectos, settings.json es global) dejaba un MEMORY.md de 147 bytes
con solo la leyenda — el fichero de memoria automática que Claude Code inyecta en
contexto, con una leyenda que no explica nada de ese proyecto. Efecto secundario:
además convertía el fichero a CRLF (medido con `cat -A`), así que un MEMORY.md con
finales LF cambiaba entero en cada cierre de sesión.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


class ProyectoVirgenNoCreaMemoryDeLaNada(unittest.TestCase):
    def test_sin_indice_ni_fichas_no_escribe_nada(self):
        proj = ay.nuevo_proyecto()
        mem = proj / 'memory'
        mem.mkdir(parents=True, exist_ok=True)  # memory/ existe pero está VACÍA (ni MEMORY.md ni fichas)
        env = ay.entorno(proj)

        r = ay.ejecutar(ay.script('varas.py'), ['--index'], env)

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('no se crea', r.stdout)
        self.assertFalse((mem / 'MEMORY.md').exists(),
                          'con el fallo, esto dejaba un MEMORY.md de la nada solo con la leyenda')

    def test_con_una_ficha_pero_sin_indice_si_puede_escribir(self):
        """Contraprueba: el guardián es "ni índice NI fichas" — si YA hay al menos
        una ficha, --index puede seguir actuando con normalidad (no se bloquea la
        primera vez que alguien arranca un índice sobre fichas ya existentes)."""
        proj = ay.nuevo_proyecto()
        mem = proj / 'memory'
        mem.mkdir(parents=True, exist_ok=True)
        (mem / 'una-ficha.md').write_text('---\ntype: reference\n---\ncontenido\n', encoding='utf-8')
        env = ay.entorno(proj)

        r = ay.ejecutar(ay.script('varas.py'), ['--index'], env)

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('no se crea', r.stdout)


class IndicePreservaFinalesDeLineaOriginales(unittest.TestCase):
    def test_no_convierte_lf_en_crlf(self):
        proj = ay.nuevo_proyecto()
        mem = proj / 'memory'
        mem.mkdir(parents=True, exist_ok=True)
        (mem / 'una-ficha.md').write_text('---\ntype: reference\n---\ncontenido\n', encoding='utf-8')
        contenido = '# Mi memoria\n> Varas: placeholder\n[una](una-ficha.md)\n'
        (mem / 'MEMORY.md').write_bytes(contenido.encode('utf-8'))  # LF puro, escrito en binario a propósito
        env = ay.entorno(proj)

        r = ay.ejecutar(ay.script('varas.py'), ['--index'], env)
        self.assertEqual(r.returncode, 0, r.stderr)

        crudo = (mem / 'MEMORY.md').read_bytes()
        self.assertNotIn(b'\r\n', crudo, 'un MEMORY.md con LF puro no debe convertirse a CRLF '
                          '(en Windows, el modo texto por defecto expande cada \\n a os.linesep '
                          'al escribir — con newline=\'\' no se traduce nada)')


if __name__ == '__main__':
    unittest.main()
