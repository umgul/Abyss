"""`.claude-plugin/plugin.json` y `marketplace.json` (fallo 6-sep, "roza"): los dos
llevaban `author.name`/`owner.name` = `"<tu nombre>"` y su URL con `<tu-usuario>` —
placeholders sin rellenar, listos para publicarse tal cual. Se quitan esos campos
opcionales en vez de inventar un nombre real (regla dura 4 del encargo: nada de
datos personales en el repo).

TERCERA VUELTA (revisor Opus, "rompe"): a `marketplace.json` le faltaba la clave
`owner` (un objeto, no un texto suelto) y el validador oficial de la CLI
(`claude plugin validate`) lo rechaza con código de salida 1 — la vía de
instalación documentada (`/plugin marketplace add ... ` → `/plugin install
abyss@abyss`) no puede funcionar con un manifiesto inválido. Se añade
`"owner": {"name": "el usuario"}` (sin `url`: es opcional y un
`https://github.com/<tu-usuario>` sin rellenar reintroduciría justo el
placeholder que esta misma prueba ya prohíbe más abajo) y
`"metadata": {"description": ...}` con la MISMA descripción que ya lleva el
plugin, para que tampoco quede ni el aviso. `claude` no está instalado en esta
máquina de pruebas, así que aquí se falsa a nivel de esquema (tipo y presencia
de `owner`, JSON válido, sin BOM) en vez de invocar el binario."""
import json
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


class ManifiestosPluginSinPlaceholders(unittest.TestCase):
    def test_plugin_json_sin_placeholder(self):
        datos = json.loads((RAIZ / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8'))
        texto = json.dumps(datos)
        self.assertNotIn('<tu nombre>', texto)
        self.assertNotIn('<tu-usuario>', texto)
        self.assertIn('name', datos)

    def test_marketplace_json_sin_placeholder(self):
        datos = json.loads((RAIZ / '.claude-plugin' / 'marketplace.json').read_text(encoding='utf-8'))
        texto = json.dumps(datos)
        self.assertNotIn('<tu nombre>', texto)
        self.assertNotIn('<tu-usuario>', texto)
        self.assertIn('plugins', datos)
        self.assertTrue(all('name' in p and 'source' in p and 'description' in p for p in datos['plugins']))


class ManifiestoMarketplaceTieneOwnerValido(unittest.TestCase):
    """Falsador del fallo "rompe" (revisor 3): sin esta clave, `claude plugin
    validate` sale con `owner: Invalid input: expected object, received
    undefined` y código de salida 1 — la instalación documentada no funciona."""

    def test_marketplace_json_tiene_owner_objeto_con_name(self):
        datos = json.loads((RAIZ / '.claude-plugin' / 'marketplace.json').read_text(encoding='utf-8'))
        self.assertIn('owner', datos, 'sin `owner` el validador oficial de la CLI rechaza el manifiesto')
        self.assertIsInstance(datos['owner'], dict, '`owner` debe ser un objeto ({"name": ...}), no una cadena')
        self.assertIn('name', datos['owner'])
        self.assertTrue(datos['owner']['name'], '`owner.name` no puede estar vacío')

    def test_marketplace_json_metadata_description_coincide_con_el_plugin(self):
        datos = json.loads((RAIZ / '.claude-plugin' / 'marketplace.json').read_text(encoding='utf-8'))
        descripcion_plugin = datos['plugins'][0]['description']
        self.assertEqual(datos.get('metadata', {}).get('description'), descripcion_plugin)


class ManifiestosSonJsonValidoSinBom(unittest.TestCase):
    """Falsador adicional del fallo "rompe": `claude plugin validate` también
    falla (o falla de otra forma menos clara) si el fichero lleva BOM UTF-8 o no
    es JSON parseable. Se comprueba directo sobre los bytes del fichero."""

    def test_plugin_json_y_marketplace_json_sin_bom_y_parseables(self):
        for nombre in ('plugin.json', 'marketplace.json'):
            crudo = (RAIZ / '.claude-plugin' / nombre).read_bytes()
            self.assertFalse(crudo.startswith(b'\xef\xbb\xbf'), f'{nombre} lleva BOM UTF-8')
            try:
                json.loads(crudo.decode('utf-8'))
            except json.JSONDecodeError as e:
                self.fail(f'{nombre} no es JSON válido: {e}')


if __name__ == '__main__':
    unittest.main()
