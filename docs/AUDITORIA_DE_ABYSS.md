# Abyss sobre Abyss

*[English version](AUDITORIA_DE_ABYSS.en.md)*

Informe de `abyss/auditar.py` sobre el propio repositorio, generado con:

```
python abyss/auditar.py . --markdown docs/AUDITORIA_DE_ABYSS.md
```

Todo lo que sigue, a partir del título `# Auditoría de …`, es la salida tal cual
del guion, con una sustitución a mano: el nombre del autor, que ya firma en
`.claude-plugin/plugin.json`, aparece como `<autor declarado en plugin.json>`. El
paquete se auditó desde su raíz (`.`) para que la comprobación 1 alcance el
manifiesto.

«Sin hallazgos» significa «hasta donde mira esta vara, no encontró nada»; la
sección 6 dice qué no lee. No es un certificado de que el paquete sea bueno.

---

# Auditoría de `abyss`

**Veredicto**: sin hallazgos

## Hallazgos

Sin hallazgos **en lo que esta vara mira**, en las cuatro comprobaciones con veredicto (procedencia, comandos, permisos, red) — no es "no hay nada": es "hasta donde mira esta vara, no lo vio". Ver la sección 6 para qué no leyó.

## 1 · Procedencia
- Manifiestos encontrados: ['.claude-plugin/plugin.json', '.claude-plugin/marketplace.json']
  - `.claude-plugin/plugin.json`: autor = <autor declarado en plugin.json>
  - `.claude-plugin/marketplace.json`: autor = <autor declarado en plugin.json>
- Historial: 19 commit(s), primero 2026-09-07T09:42:44+02:00

## 2 · Comandos
- `instalar.py:687` llamada a subprocess/os.system/eval/exec: `r = subprocess.run([python_exe, '-c', f'import {nombre_import}'],`
- `instalar.py:742` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=5)`
- `instalar.py:785` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(comando, capture_output=True, text=True, timeout=600)`
- `abyss/auditar.py:100` llamada a subprocess/os.system/eval/exec: `r'(subprocess\.\w+|os\.system\(|[^.\w]eval\(|[^.\w]exec\(|Invoke-Expression|(?<!\w)iex\s|powershell\s+-enc)', re.I)`
- `abyss/auditar.py:373` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['git', '-C', ruta, 'log', '--format=%cI'],`
- `abyss/auditar.py:378` llamada a subprocess/os.system/eval/exec: `except subprocess.TimeoutExpired:`
- `abyss/auditar.py:482` descarga con tubería a un intérprete (curl/wget/iwr/irm | bash/sh/iex): `'nota': 'descarga con tubería a un intérprete (curl/wget/iwr/irm | bash/sh/iex)',`
- `abyss/continuidad.py:340` llamada a subprocess/os.system/eval/exec: `r = subprocess.run([sys.executable, os.path.join(CODE, 'varas.py'), '--index'],`
- `abyss/continuidad.py:342` llamada a subprocess/os.system/eval/exec: `stdin=subprocess.DEVNULL)  # nunca heredar el stdin del propio gancho:`
- `abyss/cuerpo.py:65` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(`
- `abyss/cuerpo.py:75` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['wmic', 'cpu', 'get', 'loadpercentage'], capture_output=True, text=True, timeout=5)`
- `abyss/cuerpo.py:142` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['vm_stat'], capture_output=True, text=True, timeout=5)`
- `abyss/cuerpo.py:174` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(`
- `abyss/cuerpo.py:193` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(`
- `abyss/cuerpo.py:226` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['pmset', '-g', 'batt'], capture_output=True, text=True, timeout=5)`
- `abyss/huella.py:165` llamada a subprocess/os.system/eval/exec: `proc = subprocess.Popen(['powershell', '-NoProfile', '-NonInteractive', '-Command', cmd],`
- `abyss/huella.py:166` llamada a subprocess/os.system/eval/exec: `stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)`
- `abyss/huella.py:171` llamada a subprocess/os.system/eval/exec: `except subprocess.TimeoutExpired:`
- `abyss/huella.py:265` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['ss', '-ltnp'], capture_output=True, text=True, timeout=5)`
- `abyss/huella.py:271` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['lsof', '-iTCP', '-sTCP:LISTEN', '-P', '-n'], capture_output=True, text=True, timeout=5)`
- `abyss/huella.py:284` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['ps', '-eo', 'pid,ppid,lstart,comm'], capture_output=True, text=True, timeout=5)`
- `abyss/huella.py:601` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True, text=True, timeout=8)`
- `abyss/kinetica.py:832` llamada a subprocess/os.system/eval/exec: `subprocess.Popen(['open', url], close_fds=True)`
- `abyss/kinetica.py:834` llamada a subprocess/os.system/eval/exec: `subprocess.Popen(['xdg-open', url], close_fds=True)`
- `abyss/kinetico_servidor.py:67` llamada a subprocess/os.system/eval/exec: `subprocess.Popen(["open", ruta], close_fds=True)`
- `abyss/kinetico_servidor.py:69` llamada a subprocess/os.system/eval/exec: `subprocess.Popen(["xdg-open", ruta], close_fds=True)`
- `abyss/lectura_visual.py:158` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass'] + args,`
- `abyss/lectura_visual.py:236` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)`
- `abyss/lectura_visual.py:328` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', '$input | Set-Clipboard'],`
- `abyss/lectura_visual.py:332` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['pbcopy'], input=texto_plano, text=True, encoding='utf-8', errors='replace', timeout=8)`
- `abyss/lectura_visual.py:335` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['xclip', '-selection', 'clipboard'], input=texto_plano, text=True,`
- `abyss/lectura_visual.py:604` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],`
- `abyss/navegador.py:157` llamada a subprocess/os.system/eval/exec: `subprocess.Popen(cmd, close_fds=True)`
- `abyss/navegador_cdp.py:148` llamada a subprocess/os.system/eval/exec: `proc = subprocess.Popen(`
- `abyss/navegador_cdp.py:153` llamada a subprocess/os.system/eval/exec: `stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)`
- `abyss/presenta.py:455` llamada a subprocess/os.system/eval/exec: `self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)`
- `abyss/presenta.py:487` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(cmd, capture_output=True, timeout=120)`
- `abyss/presenta.py:566` llamada a subprocess/os.system/eval/exec: `"""`subprocess.run([python, abyss/<nombre_script>] + args)` con `ABYSS_PROYECTO=proyecto``
- `abyss/presenta.py:573` llamada a subprocess/os.system/eval/exec: `return subprocess.run([sys.executable, ruta] + list(args), input="", capture_output=True,`
- `abyss/render3d.py:1101` llamada a subprocess/os.system/eval/exec: `subprocess.run(cmd, capture_output=True, timeout=45)`
- `abyss/rutas.py:59` llamada a subprocess/os.system/eval/exec: `(p. ej. `subprocess.run` heredando el stdin del propio gancho si Claude Code no lo`
- `abyss/video_composicion.py:75` llamada a subprocess/os.system/eval/exec: `proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)`
- `abyss/video_pintura.py:108` llamada a subprocess/os.system/eval/exec: `proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)`
- `abyss/vigia.py:110` llamada a subprocess/os.system/eval/exec: `r'|\b(?:iwr|invoke-webrequest|irm|invoke-restmethod)\b[^\n|]*\|\s*(?:iex|invoke-expression)\b'`
- `abyss/vigia.py:112` llamada a subprocess/os.system/eval/exec: `r'|\bwinget\s+install\b|\bchoco(?:latey)?\s+install\b|\bInvoke-Expression\b'`
- `abyss/vigia.py:271` descarga con tubería a un intérprete (curl/wget/iwr/irm | bash/sh/iex): `# `respuesta`, no `sin_codigo`) — un `curl … | bash` suele venir precisamente`

## 3 · Permisos
- Declara cómo deshacerlo en algún README: True
- `instalar.py:5`: `Escribe ganchos en TU `settings.json` (por defecto `~/.claude/settings.json`,`
- `instalar.py:8`: `AÑADE una entrada nueva en cada evento. Como `settings.json` es GLOBAL, los ganchos`
- `instalar.py:11`: `sin mezclar memoria entre proyectos. Antes de tocar `settings.json` deja una copia`
- `instalar.py:12`: `fechada al lado (`settings.json.abyss-AAAAMMDD-HHMMSS.bak`); apunta todo lo añadido`
- `instalar.py:19`: `excepción). Sin rutas de usuario en el código: dónde está `~/.claude`, qué proyecto`
- `instalar.py:23`: `imprime todos con su estado real leído de `settings.json`.`
- `instalar.py:31`: `Comunes a instalar/desinstalar: `--settings <ruta>` (pruebas, o un settings.json`
- `instalar.py:133`: `SETTINGS_POR_DEFECTO = os.path.join(os.path.expanduser('~'), '.claude', 'settings.json')`
- `instalar.py:138`: `# carpeta de skills del usuario, igual que `~/.claude/settings.json` es la carpeta`
- `instalar.py:146`: `SKILLS_DIR_POR_DEFECTO = os.path.join(os.path.expanduser('~'), '.claude', 'skills')`
- `instalar.py:177`: `# `claves` son claves de nivel superior en settings.json que se fijan SOLO si el`
- `instalar.py:183`: `# en ningún `settings.json` real — sin poder verificarla contra ninguna fuente, no se`
- `instalar.py:282`: `'en el mismo paquete, sin módulo de instalación propio (sin gancho, no toca settings.json). '`
- `instalar.py:304`: `"no install module of its own (no hook, doesn't touch settings.json). Optional: "`
- `instalar.py:441`: `'cámara se enciende a petición explícita, nunca por gancho; no toca settings.json ni mem. '`
- `instalar.py:446`: `"touch settings.json or mem. Needs opencv-python, numpy and Pillow, and hands need "`
- `instalar.py:457`: `'a petición explícita, nunca por gancho; no toca settings.json ni mem',`
- `instalar.py:462`: `"turned on by explicit request, never by a hook; doesn't touch settings.json or mem"),`
- `instalar.py:469`: `toca='copia skills/esceptico/ a <skills-dir>/esceptico/ (por defecto ~/.claude/skills/esceptico/, '`
- `instalar.py:470`: `'ver --skills-dir); no es Python, no toca settings.json ni mem',`

## 4 · Qué sale de la máquina
- `...` — nombrado en el README: abyss/kinetica.py:494
- `aihorde.net` — nombrado en el README: abyss/imagen.py:201, abyss/imagen.py:283, plantillas/imagen_config.json:34
- `apache.org` — nombrado en el README: instalar.py:851, instalar.py:873, instalar.py:879, instalar.py:1071
- `api.artic.edu` — nombrado en el README: abyss/mundo.py:147
- `api.cloudflare.com` — nombrado en el README: abyss/imagen.py:151, abyss/imagen.py:282
- `api.open-meteo.com` — nombrado en el README: abyss/exterocepcion.py:194
- `api.openverse.org` — nombrado en el README: abyss/imagen.py:303
- `api.together.xyz` — nombrado en el README: abyss/imagen.py:176, abyss/imagen.py:282
- `api.windy.com` — nombrado en el README: abyss/mundo.py:277
- `artic.edu` — nombrado en el README: abyss/mundo.py:152, abyss/mundo.py:164
- `audi.com` — nombrado en el README: abyss/kinetica.py:365
- `cdn.jsdelivr.net` — nombrado en el README: instalar.py:638, instalar.py:641, instalar.py:644, instalar.py:647, instalar.py:650
- `collectionapi.metmuseum.org` — nombrado en el README: abyss/mundo.py:116, abyss/mundo.py:126
- `commons.wikimedia.org` — nombrado en el README: abyss/imagen.py:308, abyss/mundo.py:177
- `copia.ejemplo.com` — nombrado en el README: abyss/vigia.py:119
- `developers.cloudflare.com` — nombrado en el README: plantillas/imagen_config.json:46, plantillas/imagen_config.json:51
- `developers.google.com` — nombrado en el README: plantillas/imagen_config.json:69
- `discourse.threejs.org` — nombrado en el README: abyss/render3d.py:579
- `docs.together.ai` — nombrado en el README: plantillas/imagen_config.json:57
- `download.pytorch.org` — nombrado en el README: instalar.py:754, abyss/taller.py:83
- `enter.pollinations.ai` — nombrado en el README: plantillas/imagen_config.json:40
- `es.wikipedia.org` — nombrado en el README: abyss/mundo.py:324
- `fujifilm.com` — nombrado en el README: abyss/kinetica.py:364
- `gen.pollinations.ai` — nombrado en el README: abyss/imagen.py:139, abyss/imagen.py:281
- `geocoding-api.open-meteo.com` — nombrado en el README: abyss/exterocepcion.py:131
- `github.com` — nombrado en el README: abyss/fondo.py:60, abyss/lectura_visual.py:307
- `global.canon` — nombrado en el README: abyss/kinetica.py:362
- `google.com` — nombrado en el README: abyss/mundo.py:232
- `graph.mapillary.com` — nombrado en el README: abyss/mundo.py:249
- `hasselblad.com` — nombrado en el README: abyss/kinetica.py:360
- `huggingface.co` — nombrado en el README: plantillas/imagen_config.json:63
- `ipinfo.io` — nombrado en el README: abyss/exterocepcion.py:118
- `leica-camera.com` — nombrado en el README: abyss/kinetica.py:359
- `mapillary.com` — nombrado en el README: abyss/mundo.py:262, plantillas/imagen_config.json:75
- `maps.googleapis.com` — nombrado en el README: abyss/mundo.py:220, abyss/mundo.py:227
- `news.google.com` — nombrado en el README: abyss/noticias.py:161, abyss/noticias.py:182, abyss/noticias.py:217, abyss/noticias.py:229
- `nikon.com` — nombrado en el README: abyss/kinetica.py:363
- `nominatim.openstreetmap.org` — nombrado en el README: abyss/exterocepcion.py:138
- `router.huggingface.co` — nombrado en el README: abyss/imagen.py:188, abyss/imagen.py:283
- `sony.com` — nombrado en el README: abyss/kinetica.py:361
- `storage.googleapis.com` — nombrado en el README: instalar.py:653
- `threejs.org` — nombrado en el README: abyss/render3d.py:578
- `vivo.com` — nombrado en el README: abyss/kinetica.py:357
- `w3.org` — nombrado en el README: abyss/infografia.py:147, abyss/render3d.py:572
- `wikidata.org` — nombrado en el README: abyss/mundo.py:309, abyss/mundo.py:320
- `windy.com` — nombrado en el README: abyss/mundo.py:290
- `zeiss.com` — nombrado en el README: abyss/kinetica.py:358

Terceros embebidos bajo `vendor/`, `dist/` o `build/` — leídos APARTE, nunca contra el README de este paquete (no son código propio):
- `apache.org`: abyss/vendor/modelos/LICENSE-u2netp.txt:60, abyss/vendor/modelos/LICENSE-u2netp.txt:252, abyss/vendor/mp/LICENSE-mediapipe.txt:17, abyss/vendor/mp/LICENSE-mediapipe.txt:23, abyss/vendor/mp/LICENSE-mediapipe.txt:215
- `cdnjs.cloudflare.com`: abyss/vendor/LICENSE-three.txt:8
- `discourse.threejs.org`: abyss/vendor/three.min.js:7
- `github.com`: abyss/vendor/LICENSE-three.txt:10, abyss/vendor/modelos/LICENSE-u2netp.txt:5
- `raw.githubusercontent.com`: abyss/vendor/LICENSE-three.txt:11, abyss/vendor/modelos/LICENSE-u2netp.txt:12, abyss/vendor/modelos/LICENSE-u2netp.txt:19
- `threejs.org`: abyss/vendor/three.min.js:1
- `w3.org`: abyss/vendor/three.min.js:7

## 5 · Dominio (lectura manual)
- este guion NO dice si un dominio es legítimo; solo los reúne para lectura carácter a carácter — contra eso solo vale leer, no un regex.

`download.pytorch.org`, `github.com`, `pytorch.org`

## 6 · Qué no leyó esta vara (declarado, no medido)
- solo estas extensiones, en código y datos: .bat, .cfg, .cjs, .cmd, .env, .go, .ini, .js, .json, .jsx, .mjs, .ps1, .py, .rb, .sh, .toml, .ts, .tsx, .txt, .yaml, .yml — cualquier otra (compilados, binarios, formatos propios de otra herramienta...) no se lee
- carpetas nunca leídas, ni siquiera como terceros: .git, .hg, .svn, .venv, __pycache__, node_modules, site-packages, venv
- vendor/dist/build: 7 host(s) ahí dentro, leídos APARTE como terceros embebidos (nunca contra el README de este paquete): apache.org, cdnjs.cloudflare.com, discourse.threejs.org, github.com, raw.githubusercontent.com, threejs.org, w3.org
- una URL partida en dos líneas por concatenación de cadenas no se reconoce: es un regex sobre texto, no un parser
