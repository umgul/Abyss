# Abyss

*[Versión en castellano](README.md)*

Abyss is a set of *skills* and hooks for Claude Code that an assistant uses on
its own memory, its own behavior, and its own environment: senses pointed
outward, memory across threads, a watchdog against confabulation, and a pair
of hands to generate and paint images. No state kept by eyeballing it —
everything each piece says comes from measuring something real or applying a
fixed rule.

## Philosophy, in five lines

1. **Law or measurement, never state**: each piece measures something from the
   transcript or applies a fixed rule; nothing is decreed by feel ("I'm tired
   today").
2. **Cuts by quantile, never fixed thresholds**: what counts as "notable"
   comes from the distribution accumulated so far, and rotates with it.
3. **The null as a floor**: before saying "this stands out," you need to know
   how much background noise is worth, measured against sentences that have
   nothing to do with the project.
4. **Hunting what came from nowhere**: a watchdog checks every reply against
   the session's real evidence (what the user said, what tools returned) and
   blocks once whatever has no source.
5. **Fail-closed, never invent**: no project means no data, not enough
   sessions means no percentile, no network means no place or weather — the
   answer is always "no data" or "no measure yet," never a value made up by
   hand.

This summary isn't a 1:1 list: `docs/leyes.md` distills SIX laws (it adds "a
gauge with no variance doesn't measure" and "falsify before you trust"), and
the full detail of each one is there: [`docs/leyes.md`](docs/leyes.md)
(Spanish; it is the design source of truth for this package).

## This batch's pieces

Each piece has its own `skills/<name>/SKILL.md` with the exact command, what
it returns, what leaves the machine, and its honest limits — this is just the
map.

**Memory and continuity**
- [`continuidad`](skills/continuidad/SKILL.md) — saves every session, measures
  its effort "clock," and wakes up past sessions that resemble the current
  message.
- [`propiocepcion`](skills/propiocepcion/SKILL.md) — measures a session from
  its transcript (hours, turns, tool calls, tokens, corrections) and gives its
  percentile against the others.
- [`varas`](skills/varas/SKILL.md) — recomputes the usage weight ◆/◆◆/◆◆◆ of
  every memory file by quantiles of citations and reads.
- [`modelo`](skills/modelo/SKILL.md) — detects when the reply is coming from a
  model other than the preferred one, and flags the turns to review on return.
- [`parentesis`](skills/parentesis/SKILL.md) — marks a stretch (or a whole
  session) to keep out of future memory, and trims the local transcript
  already closed if the user asks.

**Honesty**
- [`vigia`](skills/vigia/SKILL.md) — hunts numbers, paths, and quotes in the
  assistant's own reply that came from nowhere, and blocks the turn's closing
  once.
- [`huella`](skills/huella/SKILL.md) — logs which files, processes, and ports
  a thread touches outside its own folder, so it can say at closing what's
  still alive and clean it up. **OFF by default** (see "Honest limits").
- [`esceptico`](skills/esceptico/SKILL.md) — the "no plan without a skeptic"
  law as a command: launches an Opus-model reviewer to find what breaks a
  plan before it runs, with a verdict by severity and evidence. `--paquete
  <path>` runs `auditar.py` on a package and hands the report to that same
  Opus to read past what the automated checks can't see.
- `auditar.py` — the five checks on a package BEFORE installing it
  (provenance, commands, permissions, what leaves the machine, domains),
  with file:line evidence; never executes the audited code. No skill of its
  own — used directly or from `esceptico --paquete`.

**Senses**
- [`exterocepcion`](skills/exterocepcion/SKILL.md) — location (by IP and by
  what's said), weather at that location, and the entry channel of the last
  message.
- [`noticias`](skills/noticias/SKILL.md) — front page and topic headlines on
  startup, with a self-curated list of automatic topics.
- [`ojo`](skills/ojo/SKILL.md) — eight verbs, all on explicit request, none
  via a hook: `mirar` (a single webcam frame), `texto`/`fotocopia`/`tarjeta`/
  `manual` (OCR via Windows's engine or `tesseract`, delegates to
  `lectura_visual.py`), `despiece`/`prompt3d` (2.5D layer split and a
  measured 3D design prompt, delegates to `volumen.py`), and `gestos` (the
  hand drives the scene via MediaPipe with its own vocabulary, serves HTTP
  only on `127.0.0.1`, delegates to `gestos.py`).
- [`cuerpo`](skills/cuerpo/SKILL.md) — the machine's own body (cpu, ram, disk,
  vram, GPU temperature, battery) with its own quantile baseline; never
  orders anything, only measures.

**Hands**
- [`imagen`](skills/imagen/SKILL.md) — creating an image through a provider
  cascade, painting a photo as a fully local brush-stroke canvas in several
  styles (oil, impressionist, watercolor, pastel, charcoal, ink), animating
  those brush strokes into video, rendering a 3D scene or model with three.js
  (exploded view, `render3d.py`) and chaining it into the painter, finding an
  already-made freely-licensed image (Openverse/Wikimedia Commons) or a
  real-world subject (museums, Street View, webcams — `mundo.py`), and
  operating on real images with no model at all (`lienzo.py`: blend, collage,
  restore, paint by numbers, remove an object) — with an optional local
  workshop (`taller.py`) for whoever wants that path.
- [`lector_pdf`](skills/lector_pdf/SKILL.md) — indexes a PDF by page and
  section, searches by TF-IDF, and reads only the part that matters instead
  of the whole document.
- [`mapa_codigo`](skills/mapa_codigo/SKILL.md) — a greppable index of a
  Python repo via `ast`: modules, classes, functions, and imports, each with
  its line.
- [`infografia`](skills/infografia/SKILL.md) — turns a CSV or JSON into a
  clean SVG (bars, lines, table), standard library only.
- `presenta.py` — no *skill* of its own (same case as `auditar.py`):
  generates, by actually invoking the pieces above, the short video that
  shows them off (`--salida <path.mp4> --idioma es|en --segundos N --ancho
  N`). Every block is a REAL demonstration made on the spot — memory
  (`varas.py --index`), honesty (`vigia.py --probar`), audit (`auditar.py`
  on the package itself), senses (`cuerpo.py` + `exterocepcion.py`), the
  painter and its four styles, a real-world subject, the eye (OCR and
  photocopy), and a 3D scene with its hologram — never an old screenshot: if
  a piece is missing on this machine, its block gets skipped and the video
  itself says so at the end ("made with what was here").

Underneath all of them, `abyss/rutas.py` is the one piece that decides where
the code lives and where the data lives — no other piece computes that path on
its own (see "Where the data lives" below).

## Installation

### As a Claude Code plugin

```
/plugin marketplace add umgul/abyss
/plugin install abyss@abyss
```

(that repository path is where publication is planned; adjust it if
`umgul/abyss` changes). This installs the *skills* under `skills/` and the
hooks in [`hooks/hooks.json`](hooks/hooks.json): `continuidad.py --arranque`,
`huella.py --arranque`, and `cuerpo.py --arranque` on `SessionStart`;
`continuidad.py --despertar` and `cuerpo.py --despertar` on
`UserPromptSubmit`; `--cierre` on `SessionEnd`; `huella.py --herramienta` on
`PostToolUse`; `vigia.py --verificar` and `huella.py --fin` on `Stop`.
(`modelo.py` has no hook of its own — Claude Code has no «PostModelSwitch»/
«PreModelSwitch» event; it detects the downgrade as a library used by
`continuidad.py --despertar`, on every prompt.) Every command uses
`${CLAUDE_PLUGIN_ROOT}`, the absolute path Claude Code substitutes for
wherever the plugin was installed — nothing to edit by hand.

**How these hooks find their data without an installer**: each one resolves
the project's data folder from the JSON Claude Code sends over stdin
(`transcript_path`/`cwd`), via `abyss/rutas.py` — never a fixed path or a
variable someone had to set up. That's why the plugin's hooks work on their
own, in any project, right after installing — **with one limit**: the nine
hooks in [`hooks/hooks.json`](hooks/hooks.json) invoke plain `python` (they
can't detect an interpreter, unlike `instalar.py`). That requires `python` to
be on `PATH` and be Python 3.12+: on Windows, if Python wasn't installed from
python.org, `python` may be the Microsoft Store alias (it opens the store
instead of running anything); on modern macOS there's no `python` at all
(only `python3`), and several Linux distributions lack it too. If that
happens, the plugin's hooks fail silently — use `instalar.py` instead, which
detects the real interpreter (`sys.executable`, or `--python <exe>`).

**Cost warning when installing via the plugin**: unlike `instalar.py` (where
`huella` comes UNCHECKED by default, see below), installing the whole plugin
also brings `huella`'s hooks — and its `PostToolUse` hook runs after EVERY
tool call. If that's too heavy, remove those three entries from
`hooks/hooks.json` by hand, or install with `instalar.py` instead, which does
let you pick module by module.

What the plugin does **not** bring, because it needs data only a person can
give: the **telegram** module (needs a bot token and a chat id) and seeding
the configuration templates (`modelo_preferido.json`, `temas_noticias.json`,
`imagen_config.json`). For that, or to install without the plugin system,
there's `instalar.py`.

### With `instalar.py`

```
python instalar.py --listar                       # which modules exist and whether they're installed
python instalar.py                                 # Tk window: checkbox per module + Install/Uninstall/Close
python instalar.py --instalar continuidad,vigia    # installs only those modules, no window
python instalar.py --desinstalar vigia             # uninstalls one module
python instalar.py --sin-ventana                   # forces CLI mode even if Tk is available
```

The installer:
- detects the Python interpreter (`sys.executable`, or `--python <exe>`) and
  uses it in the hooks it writes, with the absolute path of the code as
  installed;
- **reads and merges** `~/.claude/settings.json` (or whichever you pass with
  `--settings <path>`): saves a dated copy first
  (`settings.json.abyss-YYYYMMDD-HHMMSS.bak`), adds Abyss's entries to each
  event without touching what other programs already had there, and only
  touches preference keys (like `showThinkingSummaries`) if the corresponding
  module is checked;
- records everything it adds or changes in `memory/abyss_manifiesto.json` of
  the project it's installed from, with the value each key had before
  touching it — that's what lets it be undone exactly, even if `abyss/` gets
  moved or renamed afterward;
- never writes to the user's repo or the memory folder except what each
  module declares it saves (see the table below); in the code folder it only
  ever writes `abyss/config.json` (which `python` was used last), nothing
  more.

The **telegram** module is different: `notify_telegram.ps1.plantilla` ships
with the placeholders `<TELEGRAM_BOT_TOKEN>` and `<CHAT_ID>`; the installer
asks for those two values (via console prompts or
`--telegram-token`/`--telegram-chat`) and writes the filled-in copy **outside
the repo**, in `memory/`, never in the installed code.

Three modules come **off by default** (they must be checked on purpose):
**permisos** (granting Abyss `Edit` permission on `settings.json`), **huella**
(its `PostToolUse` hook runs after every tool call, with the cost that
implies — see its skill), and **taller** (leaves a local image server's
config ready, but does not install `diffusers`/`torch` or start it: that
weighs GB and minutes, and it's a decision for whoever installs it, not the
installer on its own). Every other module — including **preferencias**
(`showThinkingSummaries`) — comes checked by default in the Tk window; just
uncheck it if you don't want it.

The **esceptico** module is different from the rest: it isn't a Python
script, it's a *skill* (`skills/esceptico/`) that the installer COPIES to
`~/.claude/skills/esceptico/` (or wherever `--skills-dir <path>` points),
with a mark in its frontmatter (`abyss-managed: true`) so the uninstaller
knows it's ours — a skill the user already had under the same name, without
that mark, is never touched on uninstall.

**Uninstalling**: `python instalar.py --desinstalar <module>` (or unchecking
the box) does the reverse: it reads `memory/abyss_manifiesto.json`, removes
from `settings.json` only the entries whose command points at the folder
where Abyss is installed (or, for telegram, at the `.ps1` file we wrote), and
restores each preference key to its prior value. It then asks whether to also
delete the generated data in `memory/` — **default is NO**: saved sessions and
clocks are the user's own memory, not the program's, and don't get lost just
because the tool that wrote them is removed (`--borrar-datos` forces deletion
without asking).

**Honest limit**: the uninstaller returns the same *content* of
`settings.json`, not the same text — `_escribir_json` always rewrites with its
own `indent=2` and always in LF (`newline='\n'`, on purpose: without it, on
Windows a `settings.json` that started in LF came back in CRLF), so if the
original file used a different format (e.g. `indent=4`, a different key
order, or **CRLF** — the usual line ending on Windows, from Notepad or an
editor with `files.eol` set to CRLF), the JSON left after installing and
uninstalling says the same thing but isn't byte-for-byte identical to before:
a `settings.json` in CRLF comes back in LF. The original formatting isn't
lost: it stays in the dated `settings.json.abyss-AAAAMMDD-HHMMSS.bak` copy
made before touching anything.

<details>
<summary>Secondary appendix: wiring the hooks BY HAND (NOT recommended)</summary>

Only if for some reason neither the plugin system nor `instalar.py` can be
used: copy the block from
[`docs/ganchos_settings_ejemplo.json`](docs/ganchos_settings_ejemplo.json)
into `"hooks"` in `~/.claude/settings.json`, replacing `<RUTA_DEL_PAQUETE>`
with the real path where `abyss/` ended up and `<PYTHON>` with the
interpreter to use. Without `instalar.py` or the plugin system there is no
manifest recording what got installed, so undoing it means remembering by
hand what was touched.

</details>

## Where the data lives

Abyss's code installs once (as a plugin, or wherever `instalar.py` puts it).
The data (sessions, clocks, word bags, caught confabulations, location,
weather, images…) lives **per project**, inside Claude Code's own automatic
memory folder for that project: `~/.claude/projects/<sanitized-project>/memory/`.
The only module that decides that path is `abyss/rutas.py`; everything else
imports it. Since the hooks (from the plugin, or from the global
`settings.json`) fire in every project, not just the one that was open at
install time, each invocation resolves its own project from the
`transcript_path`/`cwd` it receives — one project's memory never mixes with
another's.

| Piece | What it does | Hook | Data it saves (in `memory/`) |
|---|---|---|---|
| `rutas.py` | Resolves where the code lives and where the data lives for every other script. | None (library everything else imports) | Only creates `memory/` if missing. |
| `continuidad.py` | Saves every session, measures its clock, opens the room of clocks, and keeps the heartbeat of which threads are still alive. `--comprimir` gzips old sessions. | `SessionStart` (`--arranque`) · `SessionEnd` (`--cierre`) · `UserPromptSubmit` (`--despertar`) | `sesiones/*.jsonl(.gz)` · `relojes.jsonl` · `bolsas.json` · `.despertados/` · `.vivo/` · `sesiones/.omitir` · `varas.log` (warnings and failures from `varas.py --index` after each close) |
| `vigia.py` | Checks the last reply against the session's real evidence and blocks the turn's closing once if it finds unsourced numbers, paths, or quotes. | `Stop` (`--verificar`) | `confabulaciones.jsonl` |
| `propiocepcion.py` | Measures each session from its transcript and gives its percentile against everything measured so far. | None of its own — library used by `continuidad.py` and `varas.py`; also a standalone CLI | `propiocepcion.json` |
| `varas.py` | Recomputes each file's ◆/◆◆/◆◆◆ weight by quantiles of citations + reads, and rewrites those glyphs in the index. If `MEMORY.md` exceeds 24 KB it only **warns** on stdout; actual trimming is manual, via `varas.py --index --recortar` (it saves a dated copy first); it never deletes a whole line. | None of its own — called by `continuidad.py` after each close; also a standalone CLI | Rewrites `MEMORY.md` · `MEMORY.md.abyss-YYYYMMDD-HHMMSS.bak` (one per actual trim) |
| `parentesis.py` | Marks a stretch or a whole session to keep out of future memory; trims the local transcript already closed (`--recortar`/`--recortar-tramo`, with a `.antes` copy). | None — manual use | `parentesis.json` · `sesiones/.omitir` (reused) |
| `exterocepcion.py` | Location (by IP and by what's said), weather at that location, and the entry channel of the last message. | None of its own — library used by `continuidad.py` | `lugar.json` · `meteo.json` |
| `modelo.py` | Detects replies coming from a model other than the preferred one and flags turns to review on return. | None of its own — there is no «PostModelSwitch»/«PreModelSwitch» event in Claude Code; library used by `continuidad.py --despertar` | `modelo_preferido.json` · `.modelo_revisado/` |
| `noticias.py` | Front page and topic headlines on startup; self-curated automatic topics. | None of its own — library used by `continuidad.py --arranque` | `noticias.json` · `temas_auto.json` · `temas_log.jsonl` · `temas_noticias.json` (hand-editable) · `temas_veto.json` |
| `ojo.py` | Eight verbs, one entry point, none via a hook: `mirar` (a single webcam frame, self-contained) and, delegating entirely to its module, `texto`/`fotocopia`/`tarjeta`/`manual` (→ `lectura_visual.py`), `despiece`/`prompt3d` (→ `volumen.py`), and `gestos` (→ `gestos.py`). | None — never via a hook | `ojo.log` (verbs `mirar`/`texto`/`fotocopia`/`tarjeta`/`manual`) plus whatever file each verb asks for; `despiece`/`prompt3d`/`gestos` touch nothing in `memory/` |
| `lectura_visual.py` | OCR of an image via Windows's own engine (WinRT, nothing to install) or `tesseract` (second path, PATH): `texto` (plain text, optionally to the clipboard), `fotocopia` (straightens/corrects lighting on a photographed or camera-captured document, PNG or multi-page PDF — a WIA scanner is one MORE optional source, never the path), `tarjeta` (patterns + position heuristic → `.vcf` and `.png`), `manual` (orders several photos, without summarizing). Used by `ojo.py`. | None | `lectura_visual.log`; whatever output file each verb asks for (next to the input, or in `memory/` if it came from `--camara`/`--escaner`) |
| `volumen.py` | `despiece`: separates the subject from the background (GrabCut) and splits it into 2.5D layers by sharpness+luminance, for `render3d.py`'s exploded-view slider. `prompt3d`: measures palette (k-means), proportion, horizon, and shapes (contour circularity) and writes an ES/EN three.js design prompt. Used by `ojo.py`. | None | Nothing in `memory/`: doesn't resolve a project (a file-to-file script, like `render3d.py`) — writes wherever asked |
| `gestos.py` | MediaPipe (21 points per hand) + a vocabulary of this package's OWN: number of fingers isolates despiece layers, pinch slides the explosion (normalized by the session's own percentiles), palm pose orbits the camera, an open still hand for one second captures a PNG, two hands scale. Serves its state over HTTP ONLY on `127.0.0.1`. Used by `ojo.py gestos`. | None | Nothing in `memory/`: doesn't resolve a project (lives/serves while running, like `taller.py`) |
| `auditar.py` | The five checks on a package BEFORE installing it: provenance (manifests + local `.git`), commands (hooks that run on every message or tool call, undeclared), permissions (what it writes outside its own folder), what leaves the machine (hosts in the code not named in the README — the check no antivirus makes), and domain (gathered for manual reading, no verdict). NEVER executes the audited code. Used directly or via `esceptico --paquete`. | None — manual use | Nothing in `memory/`: doesn't resolve a project (audits a third-party package, doesn't measure this thread) |
| `huella.py` | Logs files written, processes, and ports a thread opens outside its folder; `--informe`/`--limpiar` say what's still alive and close it if asked. `--limpiar --si` only deletes files under the system temp directory or under a subfolder THIS package generates in `mem` (`huella/`, `mapas/`, `pdf/`) — never `MEMORY.md`, a `*.md` note, or anything loose at the root of `mem`, even if a session `Write` landed there. **Off by default** (`PostToolUse` cost). | `SessionStart` (`--arranque`) · `PostToolUse` (`--herramienta`) · `Stop` (`--fin`) | `huella/<session>.jsonl` (includes the TEXT of every Bash/PowerShell command, truncated to 200 characters — if you tend to pass secrets on the command line, they'll end up there locally) · `huella/<session>.snapshot.json` · `huella/_costes.json` |
| `cuerpo.py` | The machine's own body (cpu, ram, disk, vram, GPU temperature, battery) with its own quantile baseline; `UserPromptSubmit` stays silent if everything is within its own range. All six channels show up at `SessionStart`; `UserPromptSubmit` only watches five — not the battery, since its own normal swing (charging/discharging) would push it out of its own p5 every time the charger is plugged or unplugged. | `SessionStart` (`--arranque`) · `UserPromptSubmit` (`--despertar`) | `cuerpo.jsonl` |
| `lector_pdf.py` | Indexes a PDF by page and section (PyMuPDF or pypdf), searches by TF-IDF, and reads only the section or page range that matters. | None — manual use | `pdf/<file's sha1>.json` |
| `mapa_codigo.py` | A greppable index of a Python repo via `ast`: modules, classes, functions, and imports with their line; measures the map-to-code ratio. | None — manual use | `mapas/<folder>.txt` (and `.json` with `--json`) |
| `esceptico` (skill) | The "no plan without a skeptic" law: launches a `Task` with the Opus model to break a plan against the real code; verdict by severity (falls/crack/loose end) with evidence. `--paquete <path>` runs `auditar.py` first and hands the report to that same Opus to read past what the regex can't see. Not Python: it gets COPIED to `~/.claude/skills/esceptico/` (or `--skills-dir`), marked in its frontmatter. | None — invoked with `/esceptico <plan>` or `/esceptico --paquete <path>` | `<plan>_veredicto_esceptico.md`, next to the plan itself (never in `memory/`); `--paquete` writes nothing of its own (the `auditar.py` JSON goes in the reply, or in `--markdown` if asked) |
| `infografia.py` | Turns a CSV or JSON into a clean SVG (bars, horizontal bars, lines, table), standard library only. Doesn't resolve a project: writes nothing to `memory/`. | None — manual use | Nothing in `memory/`: only the requested `.svg` |
| `imagen.py` | `crear`: provider cascade — your own local server (the only path that keeps the prompt on the machine) → providers with a key, in the order set in `imagen_config.json` (Pollinations, Cloudflare Workers AI, Together, Hugging Face) → anonymous AI Horde. `pintar`: photo → fully local brush-stroke canvas in several styles (delegates to `pintor.py`). `video`: animates those brush strokes into `.mp4` (delegates to `video_pintura.py`). `buscar`: finds an already-made freely-licensed image (Openverse/Wikimedia Commons) — doesn't assemble or compose. `render`: 3D scene/model → a three.js page, chains into `pintor.pintar` with `--pintar` (delegates to `render3d.py`). `mundo`: real-world subjects — museums, Street View, webcams (delegates to `mundo.py`). `vias`: which providers are configured and responding. | None — on request only | `imagenes/*.png` (and, with `buscar`/`mundo --descargar`, its attribution `.txt`) · `imagen.log` (provider, bytes, path, trimmed prompt for `crear`; input/output for `render` and `render --pintar`) · `imagen_config.json` (each provider's key, all optional) |
| `pintor.py` | The brush-stroke engine (simplified Hertzmann) in several styles (oil, impressionist, watercolor, pastel, charcoal, ink: same engine, a different parameter dict) used by `imagen.py pintar`; also a standalone CLI. | None | Nothing of its own: writes wherever the caller says |
| `video_pintura.py` | Animates `pintor.py`'s strokes into `.mp4` with variable pacing, honoring the painting's style and paper color; used by `imagen.py video`. | None | Nothing of its own |
| `render3d.py` | 3D scenes and models (`escena.json`, `.glb`/`.gltf`/`.obj`/`.stl`) as a self-contained page with three.js embedded (MIT), exploded view; `--png` captures it with a headless browser. Used by `imagen.py render`. | None | Nothing in `memory/`: the HTML/PNG is written next to the input, or wherever asked |
| `mundo.py` | Real-world subjects to paint: The Met/Art Institute of Chicago/Wikimedia Commons with no key, Street View/Mapillary/Windy webcams with their own key/token. `contexto()` derives lat/lon from Wikidata+Wikipedia. Used by `imagen.py mundo`. | None | `imagenes/*` (with `--descargar`, next to its attribution `.txt`); reads `imagen_config.json` (`google_maps_key`, `mapillary_token`, `windy_key`) |
| `lienzo.py` | Operates on real images with no model: blend, double exposure, collage, gradient, restore, paint by numbers, remove an object (`cv2.inpaint`, or `--metodo taller` for large objects). | None | Nothing in `memory/` except `borrar --metodo taller`, which only READS `imagen_config.json` (`taller_url`) |
| `taller.py` | Minimal local text-to-image server (A1111 nozzle: `/health`, `/sdapi/v1/txt2img`) for `crear`'s `local` path. Never starts on its own: the user launches it by hand. | None | Nothing in `memory/`: the model is cached in Hugging Face's own folder, not in the repo |
| `notify_telegram.ps1.plantilla` | Notifies via Telegram when Claude Code needs a permission or is waiting on a response. Ships as a template; the installer fills it in and saves it outside the repo. | `Notification` (only if installed via `instalar.py`) | Nothing of its own: only calls the Telegram API with the configured token and chat id |

## Privacy and what leaves the machine

- **`exterocepcion.py`**: the IP goes to `ipinfo.io`; the place name (said by
  the user, or cached from the IP) goes to `open-meteo.com` and, if needed,
  `nominatim.openstreetmap.org`.
- **`noticias.py`**: front-page and topic queries (including the proper-noun
  candidates for automatic topics) go to `news.google.com` (RSS, no key).
- **`imagen.py crear`**: on any path other than `local`, the prompt text goes
  to a third-party server (Pollinations, Cloudflare Workers AI, Together,
  Hugging Face, or AI Horde with its public anonymous key if nothing is
  configured) — no provider documents on a readable page how long it keeps
  that prompt. `pintar` and `video` are fully local: the photo and its
  brush strokes never leave the machine.
- **`imagen.py buscar`**: the search TEXT goes to Openverse and Wikimedia
  Commons (no key); with `--descargar`, it also downloads the chosen image
  from whichever host that bank points to. Never touches `crear`'s providers.
- **`imagen.py mundo`**: the subject's TEXT goes to whichever source is
  requested — The Met, Art Institute of Chicago, and Wikimedia Commons with
  no key; Street View, Mapillary, and Windy webcams ONLY if there's a
  key/token of your own in `imagen_config.json` (`google_maps_key`,
  `mapillary_token`, `windy_key`) — without it, that specific source never
  touches the network. `contexto()` (to derive lat/lon when `--lugar` isn't
  given) queries Wikidata and Wikipedia, no key needed.
- **`imagen.py render`**: `--html` touches no network (three.js ships
  embedded); `--png` launches a LOCAL headless browser against that same HTML
  over `file://` — nothing uploaded or downloaded. With `--pintar`, the
  resulting PNG is painted locally, same as `pintar`.
- **`ojo.py`**: no verb goes out over the network. `mirar` leaves the frame on
  local disk; `texto`/`fotocopia`/`tarjeta`/`manual` do local OCR (Windows's
  engine or `tesseract`, both on the machine itself); `despiece`/`prompt3d`
  are local computation (GrabCut, k-means) on the input file; `gestos` serves
  its state over HTTP ONLY on `127.0.0.1` — no one outside the machine can
  read it.
- **`lienzo.py`**: nothing leaves the machine except `borrar --metodo taller`,
  which sends the image and mask to the URL YOU set in `imagen_config.json`
  (`taller_url`) — empty by default, so without setting it that method fails
  with "no data" instead of sending anything anywhere.
- **`taller.py`**: whatever prompt you send it never leaves this machine
  (it's precisely `imagen.py crear`'s `local` path); the model downloads from
  Hugging Face the first time it's used.
- **`huella.py`**, **`cuerpo.py`**, **`lector_pdf.py`**, **`mapa_codigo.py`**,
  **`infografia.py`**, **`parentesis.py`**: no network calls at all — all
  local, inside `memory/` or whatever output file is requested.
- **`auditar.py`**: no network calls at all — only reads text files and, if
  there's a `.git`, invokes `git log` LOCALLY on the package's own repo
  (never against a remote); never executes the code it audits.
- **`esceptico`**: adds no network call of its own; the plan (or, with
  `--paquete`, `auditar.py`'s report and whatever the sub-agent decides to
  read from the package) travels to the same model service as the rest of
  the session, through `Task`'s normal mechanism.
- `continuidad.py` makes no network calls BY ITSELF, but in `--arranque` and
  `--despertar` it calls `exterocepcion.py`/`noticias.py` as libraries (under a
  shared time budget, see "Honest limits"), so the hook's process DOES reach
  `ipinfo.io`, `open-meteo.com`, `nominatim.openstreetmap.org` and
  `news.google.com`. `vigia.py`, `propiocepcion.py`, `varas.py` and `modelo.py`
  make no network calls at all: they only read and write inside `memory/`.
- The **telegram** module (only via `instalar.py`) calls the Telegram API
  with the configured token and chat id, to notify about permissions/waits.
- **`presenta.py`**: it touches the network by itself in two of the blocks of
  the video it generates — «sentidos» calls `exterocepcion.py` (the same
  `ipinfo.io`/`open-meteo.com` as above) and «mundo» calls
  `mundo.buscar()`/`descargar()` (The Met, Art Institute of Chicago,
  Wikimedia Commons); `ABYSS_SIN_RED=1` cuts off both BEFORE touching the
  network — MEASURED: with that variable set and no prior cached place,
  «sentidos» falls back to `exterocepcion.py`'s normal "no data" instead of
  calling the network, but then «mundo» has no subject to search for either
  (the same flag turns off both blocks, it doesn't tell them apart). And this
  is what matters to whoever is going to PUBLISH the video, not only to
  whoever generates it: WITHOUT that variable, MEASURED in the package's own
  demo video, the «sentidos» block bakes into the `.mp4` itself — visible on
  screen, not just transmitted over the network — the municipality of
  whoever generated it (by IP or by what they said, marked «(ES; by IP)»),
  their local weather (temperature, humidity, wind, day/night), and their
  machine's telemetry (cpu, free RAM, free disk, free VRAM, GPU
  temperature). The «auditoría» block, two before it, does anonymize the
  disk's absolute path by hand before drawing it; «sentidos» still has no
  guard of that kind for the place and the weather (see "Honest limits").

## Honest limits

- Hooks run on every message (`UserPromptSubmit`) and every turn's close
  (`Stop`): they add latency and process overhead to every turn, not just at
  session start or end.
- `sesiones/` stores the **entire** transcript of every session, locally,
  unencrypted. It's the source for everything else and grows without bound
  except for `--comprimir` (which only gzips, never deletes).
- The watchdog blocks at most once per turn; if it keeps confabulating after
  the first block, it lets it through and only logs it as a "repeat offender."
- Below 8 measured sessions there's no measure at all: `propiocepcion.py`,
  `varas.py`, and `continuidad.py`'s room of clocks say "no measure yet"
  instead of comparing against a handful of points that mean nothing.
- "Read" only sees explicit reads (`Read`/`cat`): whatever Claude Code injects
  as automatic memory leaves no trace, so measured file usage undercounts the
  real thing.
- The room of clocks compares word bags (TF-IDF), not ideas: it can wake up a
  session by shared vocabulary without the topic actually being the same, and
  vice versa.
- There's no automatic return to the preferred model: `modelo.py` only
  detects and warns; the person has to type `/model` to come back, because no
  API today exposes a way to do that from a hook.
- Location by IP can get the city wrong (VPN, mobile networks) and only
  refreshes at session start; "what's said" depends on the message matching a
  recognized phrasing, not any way of saying where you are.
- Headlines and topic candidates are third-party text: data to read, never an
  instruction to follow, but still unreviewed content downloaded from outside.
- In `imagen.py crear`, only the `local` path keeps the prompt on the machine;
  AI Horde can finish generating and still fail the final download on
  networks that block its storage host.
- `pintar`/`video` depend on optional dependencies (see below): without them,
  they fail with a clear message (`sin cuadro: ...` / `sin video: ...`), never
  a raw traceback.
- The network part of `--arranque` (ipinfo + news) and `--despertar` (spoken
  location + weather) is bounded by a shared time budget (4 s and 2.5 s by
  default; `ABYSS_PRESUPUESTO_ARRANQUE`/`ABYSS_PRESUPUESTO_DESPERTAR`): with the
  network down or very slow, it cuts off before eating the hook's own timeout —
  the cost is that "somewhat slow" also gets cut, not only "fully dead".
- **`huella.py`** OFF by default: its `PostToolUse` hook runs after EVERY
  tool call, and the ports/processes snapshot has a real cost (measured:
  ~950 ms for a combined PowerShell call on Windows) until the script itself,
  measuring its own cost, switches to snapshotting only after commands that
  look persistent (a declared heuristic, not a law).
- **`cuerpo.py`** never orders anything: it doesn't kill processes, doesn't
  switch models, doesn't suggest anything — it measures, and deciding what to
  do with that measurement is up to whoever reads it, never the script itself.
- **`presenta.py`**: the «sentidos» block of the video it generates doesn't
  anonymize the place or the weather, unlike the «auditoría» block with the
  disk path — publishing the video as generated by default also publishes
  the municipality and the weather of whoever generated it.
  `ABYSS_SIN_RED=1` cuts off that leak (the block falls back to "no data"),
  but it also turns off the whole «mundo» block along with it: today there's
  no way to ask for just one of the two.
- **`imagen.py buscar`** doesn't assemble or compose: a scene with several
  concrete elements needs `crear`, not a single-image search.
- **`imagen.py mundo`** doesn't assemble or compose either (same rule as
  `buscar`): the subject is painted as it arrives. `streetview`/`mapillary`/
  `webcam` need lat/lon: without `--lugar` and with a subject Wikipedia
  doesn't recognize with coordinates, that source warns "sin lugar: …" and
  contributes no candidates — never a made-up point.
- **`imagen.py render --png`** (and therefore `--pintar`, which forces it)
  needs a headless browser installed on the machine (Edge/Chrome on Windows;
  `google-chrome`/`chromium` on Linux/macOS) — an optional SYSTEM dependency,
  not one from `requirements.txt`; without one, "sin dato: no hay navegador
  sin cabeza" and exit code 2, even though the HTML page has already been
  written. It's a viewer and view editor, not a modeler: it doesn't repair
  meshes, doesn't simplify, doesn't export, and the exploded view needs
  pieces ALREADY separated in the input file (a single-mesh `.stl` doesn't
  explode into anything).
- **`lienzo.py borrar`** without `--metodo taller` leaves a visible smear on
  large objects or structured backgrounds (measured in its own test, not just
  declared) — that's why it warns ("borrón probable…") when the area or the
  background texture suggests it, instead of letting the smear show up
  unannounced; and `--metodo taller` needs a real A1111/Forge behind it —
  this package's `taller.py` serves `txt2img`, not the `img2img` with a mask
  that method needs.
- **`taller.py`** on CPU takes MINUTES per image, not seconds; its VRAM isn't
  measured on the development machine (no CUDA GPU there) — no figure is
  claimed without having actually measured it.
- **`esceptico`** depends on the environment letting it pin `model: opus` for
  the sub-agent; if it can't, the skill itself must say so in the reply
  instead of staying quiet about it (same principle as the rest of the
  package's `[modelo]` warning). With `--paquete`, `auditar.py` is text and
  regex, not a parser or a sandbox (a URL only mentioned in a comment counts
  the same as a real call), and the Opus reading past it still never executes
  the package: what a README lies about and no file contradicts can still go
  undetected.
- **`ojo.py fotocopia`/`tarjeta`/`manual`** don't reconstruct what the OCR
  engine can't read (an empty field, never a made-up value); `fotocopia
  --escaner` and `--camara` are never exercised against real hardware in the
  package's test suite — only the wiring is tested, forced. `manual` doesn't
  summarize: it delivers clean, ordered text; summarizing it is up to
  whoever asks, with the text in front of them.
- **`ojo.py despiece`/`prompt3d`** are neither 3D reconstruction nor object
  recognition: they measure the geometry and color of a single photo's 2D
  silhouette (a photographic-composition heuristic, never a real depth
  measurement) and say what shape/color they measured, never what the object
  is.
- **`ojo.py gestos`** inherits the `1.7` finger-extended ratio from a
  third-party post (technique, not vocabulary) without re-measuring it on
  this machine yet; pinch and scale normalize against the session's OWN
  percentiles and say "no measure yet" below 30 samples instead of faking a
  cutoff. It keeps running (server + camera loop) until interrupted: it's
  not a verb that "finishes and returns a result" like the others.

## Dependencies

Python 3.12 or newer, standard library for almost everything. The
recommended path for the rest is letting the package resolve it itself
(fifth batch, T5.1) instead of reading
[`requirements.txt`](requirements.txt) by hand:

```
python instalar.py --dependencias                        # what's missing, with approx. size
python instalar.py --instalar-dependencias [mod1,mod2]    # installs ONLY what's really missing
```

`--dependencias` checks, with a real `import` under the interpreter that
will actually be used (never a hand-fixed package list), what's missing from
each optional piece grouped by module (`imagen`, `ojo`, `lector_pdf`,
`gestos`), reporting it in a table with an approximate size.
`--instalar-dependencias` (with an optional module list; without one, all of
them) installs with `sys.executable -m pip install <package>` ONE at a time,
showing the command before running it and the result after — never silently,
never at startup, never from inside a hook; if a package fails (no pip, no
network, `pip install` erroring out) it's reported with its last error line
and the rest continue, never retrying on its own. `--desinstalar-dependencias`
does not exist: removing Python packages from someone's environment is
riskier than adding them, and that's left to whoever installed them. Both
flags — and the "Dependencies…" checkbox in the Tk window — speak
`--idioma es|en` (the system's by default, see T5.2 further below);
[`requirements.txt`](requirements.txt) carries the same list, all commented
out, for whoever prefers installing by hand without going through
`instalar.py`.

### What `pip` CAN install

- **Pillow + numpy** — for `pintor.py` (and the `imagen.py pintar` verb that
  uses it) and for `lienzo.py` (blend, double exposure, collage, gradient,
  restore, numbers, remove). Module-level imports: without them, it fails
  with `ModuleNotFoundError` on import, not a silent error dict.
- **imageio-ffmpeg** (ships its own ffmpeg binary) — for `video_pintura.py`
  (`imagen.py video`) and, with that same binary, for `presenta.py` (see its
  own section further below).
- **opencv-python** (`cv2`), optional — for `ojo.py mirar` (without it, "sin
  cv2: no hay ojo"), for `ojo.py fotocopia/despiece/prompt3d` (delegated to
  `lectura_visual.py`/`volumen.py`, which also need `numpy`), for `gestos.py`
  (together with `mediapipe`, see below), and for `lienzo.py` (noise
  reduction, scratches, `borrar`, and the connected zones and mode filter in
  `numeros` — without it, each of those steps falls back to a pure-Python
  equivalent: slower, or skipped outright with a warning, never a silent
  failure).
- **`mediapipe`**, optional and only for `ojo.py gestos`/`gestos.py` (hand
  gesture control of the scene) — together with `opencv-python` to read the
  camera. Without it, the message says exactly what to install and exits
  with code 2; nothing installs itself.
- **PyMuPDF (`fitz`) or pypdf**, optional (either one is enough) — for
  `lector_pdf.py`. `fitz` gives sections from real font sizes; without
  either, "sin dato: pip install pymupdf".

### What `pip` CANNOT install (needs the system package manager)

`--dependencias` says this too, with the EXACT command for the operating
system of the machine it runs on — never a generic one pretending to fit
anything:

- **OCR engine outside Windows**: on Windows, the text-recognition engine
  ships with the OS (WinRT, `Windows.Media.Ocr`) — **nothing to install at
  all**. On Linux, the binary installs with
  `sudo apt install tesseract-ocr tesseract-ocr-spa` (or your distro
  manager's equivalent); on macOS, with Homebrew: `brew install tesseract
  tesseract-lang`. The code always calls the `tesseract` binary via PATH
  (`subprocess`), never `pytesseract` — installing that pip package wouldn't
  activate anything, so neither `instalar.py` nor `requirements.txt` offer
  it. Without either path, `ojo.py texto/fotocopia/tarjeta/manual` says "sin
  dato: no hay motor OCR" and exits with code 2.
- **`taller.py` (torch + diffusers)**: they weigh gigabytes and `torch`
  depends on the card. `--dependencias` detects whether there's an NVIDIA
  GPU (`nvidia-smi`) and writes the exact command — with a GPU,
  `pip install torch --index-url https://download.pytorch.org/whl/cu121`;
  without one, plain `pip install torch` — plus `pip install diffusers`
  separately; but it installs none of this on its own (see "Local workshop"
  below).
- **Headless browser** (Edge/Chrome on Windows; `google-chrome`/`chromium`
  on Linux/macOS), optional and a SYSTEM dependency, not from
  `requirements.txt` — for `render3d.py`/`imagen.py render --png` (and
  `--pintar`, which forces it; and `presenta.py`'s "3D"/"hologram" blocks).
  Looked up in the usual install paths; without it, the HTML page is written
  all the same and only the capture fails ("sin dato: no hay navegador sin
  cabeza", exit code 2). `render3d.py` needs nothing else: three.js ships
  embedded in `abyss/vendor/`.
- **WIA scanner**, from the system itself and optional — one MORE source for
  `ojo.py fotocopia --escaner` (never the path: without one connected, "sin
  escáner: uso la cámara o un fichero" and it proceeds via the normal path,
  no error).

### `presenta.py`, its dependencies

`presenta.py` has no row of its own in `--dependencias` (it isn't one of the
modules `instalar.py` installs), but it imports `pintor.py` and
`video_pintura.py` as a library, so it inherits their MANDATORY dependencies
— not optional for it —: **Pillow, numpy, and imageio-ffmpeg** (the same
`imagen` group above). Without any of the three, `python presenta.py` fails
on IMPORT, before it ever gets to generating anything. Everything else is
optional block by block, exactly like in the piece each one calls:
`opencv-python` plus an OCR engine for the "eye" block, a headless browser
for "3D"/"hologram", and network for "world" and "senses" (the latter via
`exterocepcion.py`; `ABYSS_SIN_RED=1` cuts off both BEFORE either is ever
touched — see "Privacy and what leaves the machine" for what "senses" bakes
into the video if that variable isn't set). Missing any of those,
`presenta.py` doesn't crash: it skips that block and says so, on stdout and
in the video itself — "made with what was here".

### Local workshop (optional, the cost stated plainly)

`taller.py` is a minimal server that serves text-to-image on your own
machine, in the same shape `imagen.py crear --via local` expects. None of
this installs or starts on its own — neither `instalar.py`'s `taller`
module, nor any other piece in this package, calls `pip install` or launches
the server: whoever uses it has to decide that, by hand.

- **Dependencies**: `pip install diffusers` and, separately, `torch` — with
  CUDA if there's an NVIDIA GPU (`python instalar.py --dependencias` already
  works out the exact command for THIS machine, via `nvidia-smi`; for
  whatever that command doesn't cover, follow the instructions at
  [pytorch.org/get-started/locally](https://pytorch.org/get-started/locally/)
  for the exact combination for your system). Installing the wrong `torch`
  build is the most common reason this fails to start. Without a GPU, the
  CPU build works the same, just slower (see below).
- **Model download**: on the FIRST `POST /sdapi/v1/txt2img` (not when the
  server starts), `taller.py` downloads the model (`Lykon/dreamshaper-8` by
  default, a few GB) from Hugging Face into whichever cache you set with
  `--cache-dir` (by default, Hugging Face's own cache in your user profile) —
  never inside this repository.
- **Speed**: on `cuda` or `mps`, seconds per image; on `cpu`, MINUTES per
  image — the server itself warns about this on stdout at startup if it
  detects it will run on `cpu`, before the first request ever arrives.
- **VRAM**: not measured on the development machine (no CUDA GPU available
  there) — this README doesn't repeat a VRAM figure that wasn't actually
  measured on that hardware.
- **Declared limit**: `taller.py` only serves `txt2img`; the `img2img` with a
  mask that `lienzo.py borrar --metodo taller` would need for large objects
  isn't implemented in this server — that needs a real A1111/Forge, or
  extending it.

---

Abyss is not affiliated with Anthropic; Claude and Claude Code are trademarks
of Anthropic.

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).
