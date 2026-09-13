"""`estanteria.py` y `kinetico.py estanteria`: portadas por nombre, fichas solo con fuente,
rutas siempre dentro de la carpeta y una página que no pega texto de fuera en el HTML."""
import json
import os
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay

sys.path.insert(0, str(ay.PKG))
import estanteria  # noqa: E402

try:
    from PIL import Image
except ImportError:
    Image = None
try:
    import fitz
except ImportError:
    fitz = None


class PosterPorNombre(unittest.TestCase):
    def test_errata_de_una_letra_sigue_siendo_la_misma_obra(self):
        self.assertTrue(estanteria.es_su_poster("Blrade Runner 2019 The Final Cut.png",
                                                "2. Blade Runner 2019 The final cut.mkv"))

    def test_poster_de_serie_vale_para_cada_episodio_y_no_para_otra_serie(self):
        self.assertTrue(estanteria.es_su_poster("Serie X.png", "Serie X 3.mkv"))
        self.assertFalse(estanteria.es_su_poster("Serie X.png", "Serie Y 3.mkv"))

    def test_anios_distintos_no_se_confunden(self):
        self.assertFalse(estanteria.es_su_poster("Saga 2049.png", "Saga 2048 Otra.mp4"))
        self.assertFalse(estanteria.es_su_poster("Saga 2032.png", "Saga 2022.mp4"))

    def test_una_palabra_de_mas_en_la_imagen_no_casa(self):
        self.assertFalse(estanteria.es_su_poster("Saga(s) 2032.png", "7. Saga 2032.mp4"))


@unittest.skipIf(Image is None, "sin Pillow")
class MontarUnaColeccion(unittest.TestCase):
    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="abyss_estanteria_"))
        r = self.raiz
        Image.new("RGB", (500, 740), (200, 30, 30)).save(r / "Obra Alfa.png")
        Image.new("RGB", (500, 740), (30, 200, 30)).save(r / "Coleccion Beta.jpg")
        Image.new("RGB", (800, 600), (30, 30, 200)).save(r / "suelta.png")
        Image.new("RGB", (100, 100), (9, 9, 9)).save(r.parent / (r.name + "_fuera.png"))
        (r / "Coleccion Beta 1.txt").write_text("uno", encoding="utf-8")
        (r / "Coleccion Beta 2.txt").write_text("dos", encoding="utf-8")
        (r / "Coleccion Gamma 1.txt").write_text("tres", encoding="utf-8")
        (r / ".oculto.txt").write_text("no", encoding="utf-8")
        (r / "instalador.exe").write_bytes(b"MZ")
        (r / "atajo.lnk").write_bytes(b"L")
        (r / "sub").mkdir()
        with zipfile.ZipFile(r / "sub" / "nota.docx", "w") as z:
            z.writestr("word/document.xml", "<w/>")
        if fitz:
            doc = fitz.open()
            doc.new_page()
            doc.save(str(r / "Obra Alfa.pdf"))
            doc.close()
        else:
            (r / "Obra Alfa.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
        self.fichas = r.parent / (r.name + "_fichas.json")
        self.fichas.write_text(json.dumps({"titulo": "Mi colección", "etiqueta_autor": "autoría", "obras": [
            {"ficheros": ["Obra Alfa.pdf"], "titulo": "Alfa", "autor": "Autora", "anio": 1999,
             "sinopsis": "texto con fuente", "fuente": "https://example.org/alfa"},
            {"patron": "Coleccion Beta", "autor": "X", "sinopsis": "texto sin fuente"},
            {"ficheros": ["no_existe.mp4"]},
            {"ficheros": ["Coleccion Gamma 1.txt"], "portada": "../" + r.name + "_fuera.png"},
            {"ficheros": ["suelta.png"], "fuente": "javascript:alert(1)", "sinopsis": "x"},
        ]}), encoding="utf-8")
        self.avisos = []
        self.datos, self.portadas = estanteria.de_estanteria(str(r), fichas=str(self.fichas),
                                                             avisar=self.avisos.append)
        self.por_id = {it["id"]: it for it in self.datos["items"]}

    def test_las_obras_son_los_ficheros_visibles_menos_sus_posters(self):
        self.assertEqual(set(self.por_id), {"Obra Alfa.pdf", "Coleccion Beta 1.txt", "Coleccion Beta 2.txt",
                                            "Coleccion Gamma 1.txt", "suelta.png", "sub/nota.docx"})
        self.assertEqual(len(self.portadas), len(self.datos["items"]))

    def test_el_poster_por_nombre_gana_a_la_portada_del_propio_fichero(self):
        self.assertIn("Obra Alfa.png", self.por_id["Obra Alfa.pdf"]["aviso_portada"])
        for n in ("1", "2"):
            self.assertIn("Coleccion Beta.jpg", self.por_id["Coleccion Beta %s.txt" % n]["aviso_portada"])
        self.assertTrue(self.por_id["Coleccion Gamma 1.txt"]["aviso_portada"].startswith("portada dibujada"))
        self.assertEqual(self.por_id["suelta.png"]["aviso_portada"], "portada: la propia imagen")
        self.assertTrue(self.por_id["sub/nota.docx"]["aviso_portada"].startswith("portada dibujada"))

    def test_la_ficha_solo_se_ensena_con_fuente_http(self):
        alfa = self.por_id["Obra Alfa.pdf"]
        self.assertEqual((alfa["titulo"], alfa["autor"], alfa["sinopsis"], alfa["fuente"]),
                         ("Alfa", "Autora", "texto con fuente", "https://example.org/alfa"))
        self.assertTrue(alfa["datos"].startswith("1999"))
        for rel in ("Coleccion Beta 1.txt", "suelta.png"):
            it = self.por_id[rel]
            self.assertEqual((it["autor"], it["sinopsis"], it["fuente"]), ("", estanteria.SIN_DATO, ""))

    def test_lo_que_no_existe_o_sale_de_la_carpeta_se_dice_y_se_ignora(self):
        texto = "\n".join(self.avisos)
        self.assertIn("no_existe.mp4", texto)
        self.assertIn("fuera de la carpeta", texto)

    def test_montaje_sin_manos_y_sin_rutas_absolutas_en_las_obras(self):
        destino = Path(tempfile.mkdtemp(prefix="abyss_estanteria_montaje_"))
        self.assertTrue(estanteria.monta(self.datos, self.portadas, str(destino), manos=False,
                                         avisar=lambda *a: None))
        for f in ("index.html", "nodos.json", "gestos_comun.js", "three.min.js", "atlas/atlas_0.jpg"):
            self.assertTrue((destino / f).is_file(), f)
        self.assertFalse((destino / "mp").exists())
        self.assertEqual(Image.open(destino / "atlas" / "atlas_0.jpg").size,
                         (estanteria.CW * estanteria.REJ, estanteria.CH * estanteria.REJ))
        escena = json.loads((destino / "nodos.json").read_text(encoding="utf-8"))
        self.assertEqual(escena["titulo"], "Mi colección")
        self.assertEqual(os.path.normcase(escena["raiz"]), os.path.normcase(str(self.raiz)))
        for it in escena["items"]:
            self.assertFalse(os.path.isabs(it["id"]), it["id"])
            self.assertNotIn("\\", it["id"])


@unittest.skipIf(Image is None, "sin Pillow")
class MontajeQueNoRompeNada(unittest.TestCase):
    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="abyss_estanteria_prot_"))
        (self.raiz / "a.txt").write_text("a", encoding="utf-8")
        self.avisos = []
        self.datos, self.portadas = estanteria.de_estanteria(str(self.raiz), avisar=self.avisos.append)

    def test_no_monta_dentro_de_la_coleccion(self):
        (self.raiz / "atlas").mkdir()
        (self.raiz / "atlas" / "mio.jpg").write_bytes(b"x")
        ok = estanteria.monta(self.datos, self.portadas, str(self.raiz), manos=False, avisar=self.avisos.append)
        self.assertFalse(ok)
        self.assertTrue((self.raiz / "atlas" / "mio.jpg").is_file(), "no debe borrar nada del usuario")

    def test_no_monta_encima_de_una_carpeta_ajena_con_cosas(self):
        ajena = Path(tempfile.mkdtemp(prefix="abyss_estanteria_ajena_"))
        (ajena / "fondo.jpg").write_bytes(b"del usuario")
        ok = estanteria.monta(self.datos, self.portadas, str(ajena), manos=False, avisar=self.avisos.append)
        self.assertFalse(ok)
        self.assertEqual((ajena / "fondo.jpg").read_bytes(), b"del usuario")

    def test_remontar_encima_de_su_propio_montaje_si_vale(self):
        destino = Path(tempfile.mkdtemp(prefix="abyss_estanteria_propio_"))
        self.assertTrue(estanteria.monta(self.datos, self.portadas, str(destino), manos=False, avisar=lambda *a: None))
        self.assertTrue(estanteria.monta(self.datos, self.portadas, str(destino), manos=False, avisar=lambda *a: None))

    def test_fondo_en_otra_unidad_no_revienta(self):
        otra = "Q:\\fondo.png" if os.name == "nt" else "/fuera/fondo.png"
        datos, _ = estanteria.de_estanteria(str(self.raiz), fondo=otra, avisar=self.avisos.append)
        self.assertIsNotNone(datos)
        self.assertIn("fondo ignorado", "\n".join(self.avisos))


class PlantillaDeLaEstanteria(unittest.TestCase):
    TEXTO = (ay.PKG / "plantillas" / "estanteria.html").read_text(encoding="utf-8")

    def test_lee_la_escena_y_abre_por_la_lista_blanca_del_servidor(self):
        self.assertIn("fetch('nodos.json')", self.TEXTO)
        self.assertIn("fetch('abrir'", self.TEXTO)
        self.assertIn("destino:", self.TEXTO)
        self.assertIn("'atlas/atlas_'", self.TEXTO)

    def test_no_pega_texto_de_fuera_en_el_html(self):
        self.assertIsNone(re.search(r"\.(innerHTML|outerHTML)\s*[+]?=|insertAdjacentHTML|document\.write", self.TEXTO))

    def test_sin_mp_no_rompe_la_pagina(self):
        self.assertNotIn("from './mp/vision_bundle.mjs'", self.TEXTO)
        self.assertIn("import('./mp/vision_bundle.mjs')", self.TEXTO)


@unittest.skipIf(Image is None, "sin Pillow")
class CliEstanteria(unittest.TestCase):
    def test_solo_montar_sin_manos(self):
        raiz = Path(tempfile.mkdtemp(prefix="abyss_estanteria_cli_"))
        (raiz / "a.txt").write_text("a", encoding="utf-8")
        salida = Path(tempfile.mkdtemp(prefix="abyss_estanteria_cli_salida_"))
        r = ay.ejecutar(ay.script("kinetico.py"),
                        ["estanteria", str(raiz), "--solo-montar", "--sin-manos", "--salida", str(salida)],
                        dict(os.environ), timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("montado:", r.stdout)
        self.assertTrue((salida / "index.html").is_file())


if __name__ == "__main__":
    unittest.main()
