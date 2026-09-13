# -*- coding: utf-8 -*-
"""`navegador.conceder_camara()`: concede SOLO la cámara para un origen, nunca el
micrófono, y si un perfil viejo (de una versión anterior de la función) tenía el
micrófono concedido para ese mismo origen, lo retira al volver a escribir.

`navegador.py` no usa `rutas.resolver()` (sin CWD ni stdin de por medio, a diferencia
de otros guiones del paquete), así que se importa directamente en el proceso, igual
que `test_render3d.py` hace con `render3d.py`. Nada de esto abre un navegador: solo
lee y escribe el `Preferences` de un perfil en un directorio temporal."""
import sys
import os
import json
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay  # noqa: E402

sys.path.insert(0, str(ay.PKG))
import navegador  # noqa: E402


def _perfil_con_permisos_previos(origenes):
    """Perfil nuevo en un directorio temporal con `Default/Preferences` ya escrito:
    cámara Y micrófono concedidos para cada uno de `origenes` (como los dejaba la
    versión anterior de `conceder_camara`). Devuelve la ruta del perfil."""
    perfil = tempfile.mkdtemp(prefix="abyss_perfil_prueba_")
    os.makedirs(os.path.join(perfil, "Default"), exist_ok=True)
    marca = "13300000000000000"
    exc_camara, exc_mic = {}, {}
    for origen in origenes:
        clave = origen + ",*"
        exc_camara[clave] = {"last_modified": marca, "setting": 1}
        exc_mic[clave] = {"last_modified": marca, "setting": 1}
    prefs = {"profile": {"content_settings": {"exceptions": {
        "media_stream_camera": exc_camara,
        "media_stream_mic": exc_mic,
    }}}}
    with open(os.path.join(perfil, "Default", "Preferences"), "w", encoding="utf-8") as fh:
        json.dump(prefs, fh)
    return perfil


class ConcederCamaraNuncaMicrofono(unittest.TestCase):
    ORIGEN = "http://127.0.0.1:8850"
    OTRO_ORIGEN = "http://127.0.0.1:8811"

    def test_concede_camara_retira_mic_del_origen_y_no_toca_el_otro(self):
        perfil = _perfil_con_permisos_previos([self.ORIGEN, self.OTRO_ORIGEN])
        self.addCleanup(shutil.rmtree, perfil, ignore_errors=True)
        ruta_preferences = os.path.join(perfil, "Default", "Preferences")

        ruta_devuelta = navegador.conceder_camara(perfil, self.ORIGEN)
        self.assertEqual(os.path.abspath(ruta_devuelta), os.path.abspath(ruta_preferences))

        with open(ruta_preferences, encoding="utf-8") as fh:
            texto = fh.read()
        prefs = json.loads(texto)  # si el fichero hubiera quedado con JSON roto, esto ya lo revienta

        exc = prefs["profile"]["content_settings"]["exceptions"]
        clave, otra_clave = self.ORIGEN + ",*", self.OTRO_ORIGEN + ",*"

        self.assertEqual(exc["media_stream_camera"].get(clave, {}).get("setting"), 1,
                          "la cámara debe quedar concedida para el origen pedido")
        self.assertNotIn(clave, exc.get("media_stream_mic", {}),
                          "el micrófono de ESE origen debe quedar retirado")
        self.assertEqual(exc["media_stream_camera"].get(otra_clave, {}).get("setting"), 1,
                          "el otro origen no debe perder su cámara")
        self.assertEqual(exc["media_stream_mic"].get(otra_clave, {}).get("setting"), 1,
                          "el otro origen no debe perder su micrófono: solo se retira el del origen pedido")

    def test_perfil_nuevo_no_recibe_microfono(self):
        """El bug original: un perfil SIN excepciones previas terminaba con el
        micrófono concedido igual que la cámara, sin que nada lo pidiera."""
        perfil = tempfile.mkdtemp(prefix="abyss_perfil_prueba_")
        self.addCleanup(shutil.rmtree, perfil, ignore_errors=True)

        navegador.conceder_camara(perfil, self.ORIGEN)

        with open(os.path.join(perfil, "Default", "Preferences"), encoding="utf-8") as fh:
            prefs = json.load(fh)
        exc = prefs["profile"]["content_settings"]["exceptions"]
        self.assertEqual(exc["media_stream_camera"][self.ORIGEN + ",*"]["setting"], 1)
        self.assertNotIn("media_stream_mic", exc, "un perfil nuevo no debe recibir nunca el micrófono")

class ElUltimoRecursoNoSigueArboles(unittest.TestCase):
    TEXTO = (ay.PKG / 'navegador_cdp.py').read_text(encoding='utf-8')

    def test_para_proceso_a_proceso_y_se_excluye_a_si_mismo(self):
        self.assertNotIn('taskkill', self.TEXTO)
        self.assertIn('$_.ProcessId -ne $PID', self.TEXTO)
        self.assertIn('Stop-Process -Id $_.ProcessId', self.TEXTO)


if __name__ == "__main__":
    unittest.main()
