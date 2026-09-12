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
- Historial: 18 commit(s), primero 2026-09-07T09:42:44+02:00

## 2 · Comandos
- `instalar.py:708` llamada a subprocess/os.system/eval/exec: `r = subprocess.run([python_exe, '-c', f'import {nombre_import}'],`
- `instalar.py:763` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=5)`
- `instalar.py:806` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(comando, capture_output=True, text=True, timeout=600)`
- `abyss/auditar.py:40` descarga con tubería a un intérprete (curl/wget/iwr/irm | bash/sh/iex): `(`curl/wget/iwr/irm | bash/sh/iex`) — como EVIDENCIA (no todo uso de`
- `abyss/auditar.py:175` llamada a subprocess/os.system/eval/exec: `r'(subprocess\.\w+|os\.system\(|[^.\w]eval\(|[^.\w]exec\(|Invoke-Expression|(?<!\w)iex\s|powershell\s+-enc)', re.I)`
- `abyss/auditar.py:455` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['git', '-C', ruta, 'log', '--format=%cI'],`
- `abyss/auditar.py:460` llamada a subprocess/os.system/eval/exec: `except subprocess.TimeoutExpired:`
- `abyss/auditar.py:566` descarga con tubería a un intérprete (curl/wget/iwr/irm | bash/sh/iex): `'nota': 'descarga con tubería a un intérprete (curl/wget/iwr/irm | bash/sh/iex)',`
- `abyss/continuidad.py:342` llamada a subprocess/os.system/eval/exec: `r = subprocess.run([sys.executable, os.path.join(CODE, 'varas.py'), '--index'],`
- `abyss/continuidad.py:344` llamada a subprocess/os.system/eval/exec: `stdin=subprocess.DEVNULL)  # nunca heredar el stdin del propio gancho`
- `abyss/cuerpo.py:108` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(`
- `abyss/cuerpo.py:118` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['wmic', 'cpu', 'get', 'loadpercentage'], capture_output=True, text=True, timeout=5)`
- `abyss/cuerpo.py:187` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['vm_stat'], capture_output=True, text=True, timeout=5)`
- `abyss/cuerpo.py:221` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(`
- `abyss/cuerpo.py:242` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(`
- `abyss/cuerpo.py:275` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['pmset', '-g', 'batt'], capture_output=True, text=True, timeout=5)`
- `abyss/huella.py:240` llamada a subprocess/os.system/eval/exec: `proc = subprocess.Popen(['powershell', '-NoProfile', '-NonInteractive', '-Command', cmd],`
- `abyss/huella.py:241` llamada a subprocess/os.system/eval/exec: `stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)`
- `abyss/huella.py:246` llamada a subprocess/os.system/eval/exec: `except subprocess.TimeoutExpired:`
- `abyss/huella.py:340` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['ss', '-ltnp'], capture_output=True, text=True, timeout=5)`
- `abyss/huella.py:346` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['lsof', '-iTCP', '-sTCP:LISTEN', '-P', '-n'], capture_output=True, text=True, timeout=5)`
- `abyss/huella.py:359` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['ps', '-eo', 'pid,ppid,lstart,comm'], capture_output=True, text=True, timeout=5)`
- `abyss/huella.py:676` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True, text=True, timeout=8)`
- `abyss/kinetica.py:951` llamada a subprocess/os.system/eval/exec: `subprocess.Popen(['open', url], close_fds=True)`
- `abyss/kinetica.py:953` llamada a subprocess/os.system/eval/exec: `subprocess.Popen(['xdg-open', url], close_fds=True)`
- `abyss/kinetico_servidor.py:80` llamada a subprocess/os.system/eval/exec: `subprocess.Popen(["open", ruta], close_fds=True)`
- `abyss/kinetico_servidor.py:82` llamada a subprocess/os.system/eval/exec: `subprocess.Popen(["xdg-open", ruta], close_fds=True)`
- `abyss/lectura_visual.py:173` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass'] + args,`
- `abyss/lectura_visual.py:254` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)`
- `abyss/lectura_visual.py:354` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', '$input | Set-Clipboard'],`
- `abyss/lectura_visual.py:358` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['pbcopy'], input=texto_plano, text=True, encoding='utf-8', errors='replace', timeout=8)`
- `abyss/lectura_visual.py:361` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['xclip', '-selection', 'clipboard'], input=texto_plano, text=True,`
- `abyss/lectura_visual.py:652` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],`
- `abyss/navegador.py:160` llamada a subprocess/os.system/eval/exec: `subprocess.Popen(cmd, close_fds=True)`
- `abyss/navegador_cdp.py:160` llamada a subprocess/os.system/eval/exec: `proc = subprocess.Popen(`
- `abyss/navegador_cdp.py:165` llamada a subprocess/os.system/eval/exec: `stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)`
- `abyss/presenta.py:507` llamada a subprocess/os.system/eval/exec: `self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)`
- `abyss/presenta.py:539` llamada a subprocess/os.system/eval/exec: `r = subprocess.run(cmd, capture_output=True, timeout=120)`
- `abyss/presenta.py:618` llamada a subprocess/os.system/eval/exec: `"""`subprocess.run([python, abyss/<nombre_script>] + args)` con `ABYSS_PROYECTO=proyecto``
- `abyss/presenta.py:625` llamada a subprocess/os.system/eval/exec: `return subprocess.run([sys.executable, ruta] + list(args), input="", capture_output=True,`
- `abyss/render3d.py:1136` llamada a subprocess/os.system/eval/exec: `subprocess.run(cmd, capture_output=True, timeout=45)`
- `abyss/rutas.py:61` llamada a subprocess/os.system/eval/exec: ``varas.py --index` con `subprocess.run` heredando el stdin del propio gancho — si`
- `abyss/video_composicion.py:75` llamada a subprocess/os.system/eval/exec: `proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)`
- `abyss/video_pintura.py:108` llamada a subprocess/os.system/eval/exec: `proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)`
- `abyss/vigia.py:39` llamada a subprocess/os.system/eval/exec: ``Invoke-Expression`, `powershell -enc`) cuya fuente no esté en el turno. A`
- `abyss/vigia.py:41` descarga con tubería a un intérprete (curl/wget/iwr/irm | bash/sh/iex): `copias»), estos DOS tipos SÍ miran dentro de ellos: un `curl … | bash` suele`
- `abyss/vigia.py:150` llamada a subprocess/os.system/eval/exec: `r'|\b(?:iwr|invoke-webrequest|irm|invoke-restmethod)\b[^\n|]*\|\s*(?:iex|invoke-expression)\b'`
- `abyss/vigia.py:152` llamada a subprocess/os.system/eval/exec: `r'|\bwinget\s+install\b|\bchoco(?:latey)?\s+install\b|\bInvoke-Expression\b'`
- `abyss/vigia.py:318` descarga con tubería a un intérprete (curl/wget/iwr/irm | bash/sh/iex): `# `respuesta`, no `sin_codigo`) — un `curl … | bash` suele venir precisamente`

## 3 · Permisos
- Declara cómo deshacerlo en algún README: True
- `instalar.py:6`: `- Escribe ganchos en TU `settings.json` (por defecto `~/.claude/settings.json`,`
- `instalar.py:10`: `- Como ese `settings.json` es GLOBAL, los ganchos disparan en TODOS tus proyectos`
- `instalar.py:15`: `- Antes de tocar `settings.json` deja una COPIA FECHADA al lado`
- `instalar.py:16`: `(`settings.json.abyss-AAAAMMDD-HHMMSS.bak`).`
- `instalar.py:32`: `imprime todos con su estado real leído de `settings.json`.`
- `instalar.py:40`: `Comunes a instalar/desinstalar: `--settings <ruta>` (pruebas, o un settings.json`
- `instalar.py:53`: `está `~/.claude`, qué proyecto, qué `python`) se resuelve en tiempo de ejecución.`
- `instalar.py:151`: `SETTINGS_POR_DEFECTO = os.path.join(os.path.expanduser('~'), '.claude', 'settings.json')`
- `instalar.py:156`: `# carpeta de skills del usuario, igual que `~/.claude/settings.json` es la carpeta`
- `instalar.py:164`: `SKILLS_DIR_POR_DEFECTO = os.path.join(os.path.expanduser('~'), '.claude', 'skills')`
- `instalar.py:195`: `# `claves` son claves de nivel superior en settings.json que se fijan SOLO si el`
- `instalar.py:201`: `# en ningún `settings.json` real encontrado en esta máquina — se quitó el 6-sep tras`
- `instalar.py:301`: `'en el mismo paquete, sin módulo de instalación propio (sin gancho, no toca settings.json). '`
- `instalar.py:323`: `"no install module of its own (no hook, doesn't touch settings.json). Optional: "`
- `instalar.py:460`: `'cámara se enciende a petición explícita, nunca por gancho; no toca settings.json ni mem. '`
- `instalar.py:465`: `"touch settings.json or mem. Needs opencv-python, numpy and Pillow, and hands need "`
- `instalar.py:476`: `'a petición explícita, nunca por gancho; no toca settings.json ni mem',`
- `instalar.py:481`: `"turned on by explicit request, never by a hook; doesn't touch settings.json or mem"),`
- `instalar.py:488`: `toca='copia skills/esceptico/ a <skills-dir>/esceptico/ (por defecto ~/.claude/skills/esceptico/, '`
- `instalar.py:489`: `'ver --skills-dir); no es Python, no toca settings.json ni mem',`

## 4 · Qué sale de la máquina
- `...` — nombrado en el README: abyss/kinetica.py:596
- `aihorde.net` — nombrado en el README: abyss/imagen.py:225, abyss/imagen.py:307, plantillas/imagen_config.json:34
- `apache.org` — nombrado en el README: instalar.py:872, instalar.py:895, instalar.py:901, instalar.py:1093
- `api.artic.edu` — nombrado en el README: abyss/mundo.py:151
- `api.cloudflare.com` — nombrado en el README: abyss/imagen.py:175, abyss/imagen.py:306
- `api.open-meteo.com` — nombrado en el README: abyss/exterocepcion.py:197
- `api.openverse.org` — nombrado en el README: abyss/imagen.py:327
- `api.together.xyz` — nombrado en el README: abyss/imagen.py:200, abyss/imagen.py:306
- `api.windy.com` — nombrado en el README: abyss/mundo.py:285
- `artic.edu` — nombrado en el README: abyss/mundo.py:156, abyss/mundo.py:168
- `audi.com` — nombrado en el README: abyss/kinetica.py:456
- `cdn.jsdelivr.net` — nombrado en el README: instalar.py:659, instalar.py:662, instalar.py:665, instalar.py:668, instalar.py:671
- `collectionapi.metmuseum.org` — nombrado en el README: abyss/mundo.py:120, abyss/mundo.py:130
- `commons.wikimedia.org` — nombrado en el README: abyss/imagen.py:332, abyss/mundo.py:182
- `copia.ejemplo.com` — nombrado en el README: abyss/vigia.py:159
- `developers.cloudflare.com` — nombrado en el README: plantillas/imagen_config.json:46, plantillas/imagen_config.json:51
- `developers.google.com` — nombrado en el README: plantillas/imagen_config.json:69
- `discourse.threejs.org` — nombrado en el README: abyss/render3d.py:610
- `docs.together.ai` — nombrado en el README: plantillas/imagen_config.json:57
- `download.pytorch.org` — nombrado en el README: instalar.py:775, abyss/taller.py:83
- `enter.pollinations.ai` — nombrado en el README: plantillas/imagen_config.json:40
- `es.wikipedia.org` — nombrado en el README: abyss/mundo.py:334
- `fujifilm.com` — nombrado en el README: abyss/kinetica.py:455
- `gen.pollinations.ai` — nombrado en el README: abyss/imagen.py:163, abyss/imagen.py:305
- `geocoding-api.open-meteo.com` — nombrado en el README: abyss/exterocepcion.py:134
- `github.com` — nombrado en el README: abyss/fondo.py:63, abyss/lectura_visual.py:333
- `global.canon` — nombrado en el README: abyss/kinetica.py:453
- `google.com` — nombrado en el README: abyss/mundo.py:238
- `graph.mapillary.com` — nombrado en el README: abyss/mundo.py:256
- `hasselblad.com` — nombrado en el README: abyss/kinetica.py:451
- `huggingface.co` — nombrado en el README: plantillas/imagen_config.json:63
- `ipinfo.io` — nombrado en el README: abyss/exterocepcion.py:121
- `leica-camera.com` — nombrado en el README: abyss/kinetica.py:450
- `mapillary.com` — nombrado en el README: abyss/mundo.py:269, plantillas/imagen_config.json:75
- `maps.googleapis.com` — nombrado en el README: abyss/mundo.py:226, abyss/mundo.py:233
- `news.google.com` — nombrado en el README: abyss/noticias.py:163, abyss/noticias.py:184, abyss/noticias.py:219, abyss/noticias.py:231
- `nikon.com` — nombrado en el README: abyss/kinetica.py:454
- `nominatim.openstreetmap.org` — nombrado en el README: abyss/exterocepcion.py:141
- `router.huggingface.co` — nombrado en el README: abyss/imagen.py:212, abyss/imagen.py:307
- `sony.com` — nombrado en el README: abyss/kinetica.py:452
- `storage.googleapis.com` — nombrado en el README: instalar.py:674
- `threejs.org` — nombrado en el README: abyss/render3d.py:609
- `vivo.com` — nombrado en el README: abyss/kinetica.py:448
- `w3.org` — nombrado en el README: abyss/infografia.py:148, abyss/render3d.py:602
- `wikidata.org` — nombrado en el README: abyss/mundo.py:319, abyss/mundo.py:330
- `windy.com` — nombrado en el README: abyss/mundo.py:298
- `zeiss.com` — nombrado en el README: abyss/kinetica.py:449

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
