# Laws of the self-built SGICP

*[Versión en castellano](leyes.md)*

Distilled from the original design notes, which are not published because
they are the author's personal notes (dated, in first person). Here only the
laws, dry, and which piece of the package measures each one. These are not
generic best practices: they are the concrete rules this code follows or,
when it can't, says it doesn't measure instead of making something up.

## 1 · Law or measurement, never state

No piece declares how the thread "feels" (tired, happy, in a hurry). Either
there is an instrument that measures something from the transcript, or there
is a fixed rule that applies the same way every time (a law), or there is
nothing to say. There is no third option decreed by feel.

- `propiocepcion.py` doesn't say "you're tired": it says how many hours,
  turns, tools, and tokens the session had, and what percentile that falls
  into against the other sessions.
- `vigia.py` doesn't judge "this is a lie": it hunts numbers, paths, and
  quotes that don't appear in the evidence (what the user said or what a
  tool returned) and leaves the correction to whoever wrote the reply.
- First-person sentences about one's own state ("I'm glad", "I feel like
  it") count as *gaugeless states* — they aren't forbidden (they are speech
  acts), but they aren't taken as a measurement of anything either.

## 2 · Cuts by quantile, never fixed thresholds

No piece compares against a number set by hand. Every cut comes from the
distribution accumulated so far, and gets recalculated every time there is
new data ("normals that rotate").

- `varas.py` distributes ◆/◆◆/◆◆◆ by the decile and bands of the measured-use
  distribution of the files — never by a fixed citation count.
- `propiocepcion.py` gives the current session's percentile against every
  session measured up to today, never against a frozen reference value.
- `continuidad.py` (the room of clocks) only wakes a clock if its similarity
  is above the mean + 1 standard deviation *of that specific prompt*, never
  an absolute number.

## 3 · The null as a floor

Before a gauge can say "this stands out," it has to know how much background
noise is worth: what score sentences that have nothing to do with the
project reach. That noise ceiling (the "null") is the floor below which
nothing ever fires, and it gets recalculated with the corpus — it is not a
constant written once and forgotten.

- `continuidad.py` keeps a fixed list of sentences unrelated to the project
  (recipes, football, mortgages…) and uses 1.5× the maximum similarity they
  reach against the saved sessions as the floor for the room of clocks. It
  gets recalculated on every harvest (`hacer_bolsas`).
- `noticias.py` requires an automatic topic to clear that same floor before
  admitting it: its headlines have to resemble real conversations, not just
  exist.

## 4 · Hunting what came from nowhere

The watchdog doesn't detect lies: it detects absence of source. A number, a
path, or a quote between «» that doesn't appear either in what the user said
or in what a tool returned anywhere in the session is, by definition,
something that didn't come from any verifiable place — whether it was made
up or calculated without showing the calculation.

- `vigia.py --verificar` (the `Stop` hook) makes exactly that comparison and
  blocks the turn from closing the first time it finds something like that,
  so it gets rewritten.
- Quotes between «» split into two kinds because they don't carry the same
  weight: `cita` (there's an attribution verb nearby — someone would really
  have said it that way) and `parafrasis` (stylistic or translation quotes,
  without that exact text in the evidence).
- Declared limit: this doesn't judge claims with no number or quote — it
  doesn't reach that far — and a number that happens to appear in any tool
  output by coincidence is counted as covered even with no real relation (a
  known false negative).

## 5 · A gauge with no variance doesn't measure

A gauge that has never been put to the test doesn't have precision: it has
silence. If no one has ever used the override mechanism, saying "100%
accurate" doesn't mean the gauge is perfect — it means no one has checked
whether it's wrong.

- `vigia.py --precision` compares total catches against overrides
  (`--descargo`); with zero overrides it explicitly says "no gauge" instead
  of printing a misleading 1.00.
- Corollary of the cold start (§2.2 of `ESPECIFICACION.md`): with fewer than
  `propiocepcion.UMBRAL_FRIO` (8) measured sessions there is no corpus to
  compare against, so `propiocepcion.percentiles()` returns `None`,
  `varas.py --index` sets no ◆ at all, and the room of clocks wakes nothing.
  Fail-closed: a percentile is never invented over a distribution that
  barely exists.

## 6 · Falsify before you trust

No new gauge goes live without being tested first against real data and
against the null.

- The room of clocks was tested with leave-one-out (`continuidad.py
  --falsar`): each session's first sentence against the bags without that
  sentence, and against unrelated new sentences that should never wake
  anything.
- `noticias.py`'s automatic topics went through five successive
  measurements before going live (each one uncovered a different kind of
  noise: internal jargon, fragments of Windows paths, compaction-summary
  headers) and final relevance requires clearing the null's floor, not just
  "giving two headlines."

## What each piece measures (summary)

| Piece | What it measures or watches | With what gauge |
|---|---|---|
| `propiocepcion.py` | A session's effort (hours, turns, tools, tokens, corrections) | Percentile against the other sessions; `None` when cold |
| `varas.py` | Real usage weight of each memory file (citations + reads) | Quantiles of the current usage distribution |
| `continuidad.py` (room) | Similarity between the prompt and past sessions | TF-IDF cosine over the null's floor + the prompt's own mean/σ |
| `vigia.py` | Numbers/paths/quotes in the reply itself with no verifiable source | Presence in the evidence (user + tools); precision via overrides |
| `modelo.py` | Whether the reply is running outside the preferred model | Exact comparison against `modelo_preferido.json`, no inference |
| `noticias.py` (auto topics) | Whether a recurring proper name deserves to become a press topic | Frequency per session + similarity of its headlines over the null's floor |

## Pieces from the second batch

Not all of them measure against a gauge with quantiles — some apply a fixed
rule (a law) or transform without measuring anything (a hand tool). The
table says which is which, and what each one does NOT promise — the same
honesty as above, said from the side of what doesn't quite become a gauge.

| Piece | What it does | Measures or applies | What it does NOT promise |
|---|---|---|---|
| `parentesis.py` | Marks a span (or a whole session) so it doesn't enter future memory | Law: filters by timestamp, never deletes what was already sent | Doesn't undo what already travelled to the API within a turn |
| `huella.py` | Logs files/processes/ports a thread touches outside its own folder | Measures the cost (ms) of its own snapshot and decides its own heuristic for when to repeat it against ITS OWN median, never a fixed number | Doesn't see what another program (not this thread) left open; stores the TEXT of every Bash/PowerShell command (trimmed to 200 characters, locally) — if you tend to pass secrets on the command line, they'll stay there; `--limpiar --si` only deletes under temp/ or under a subfolder it generates itself in `mem` (`huella/`, `mapas/`, `pdf/`) — never `MEMORY.md` nor any `*.md` file; OFF by default except via `instalar.py`, on if the whole plugin is installed |
| `cuerpo.py` | The machine's body (cpu/ram/disk/vram/temp/battery) | p5/p50/p95 quantiles of its own history, cold start with `UMBRAL_FRIO`=8 same as `propiocepcion.py` | Never orders anything (doesn't kill processes, doesn't downgrade the model): it measures, it doesn't decide; the six channels show up on `SessionStart`, but `UserPromptSubmit` only watches five — not the battery, because its own normal swing when (un)plugging would knock it out of its p5 every time |
| `lector_pdf.py` | Indexes a PDF by page/section and searches by TF-IDF | Measures characters read vs. the whole PDF (`--ahorro`), no quantile gauge | The saving is in READING, not in answer quality — that needs an A/B test that hasn't been done |
| `mapa_codigo.py` | Greppable index of a Python repo via `ast` | Measures map lines vs. code lines (ratio), no quantile gauge | Doesn't measure whether the map is ENOUGH to understand the code — only how much it weighs against the code |
| `esceptico` (skill) | Law "no plan without a skeptic": an Opus reviewer looks for what breaks a plan | Law: verdict by severity (falls/crack/loose end) with cited evidence, never a summary or praise | Doesn't execute the plan; if the environment doesn't set `model: opus`, it has to say so, not stay quiet |
| `infografia.py` | CSV/JSON to clean SVG | Transforms without measuring: 1-2-5 ticks from the data's own scale | Doesn't choose the chart type or rasterize to PNG |
| `lienzo.py` | Operating on real images (merge, collage, restore, paint-by-numbers, erase) | Measures contrast/noise before-after in `restaurar`; the limit of `borrar` without the workshop is measured in its own test (error under half the initial one) | Doesn't generate anything new and doesn't understand the scene — these are deterministic operations on the given pixels |
| `taller.py` | Minimal local text-to-image server (A1111 mouthpiece) | Applies: serves `txt2img`, nothing else | Doesn't measure VRAM without a real GPU to measure; doesn't implement `img2img` with a mask yet |

## Pieces from the fourth batch

The eye stops being a single photo, and the watchdog starts looking at what
gets installed. Same table, same criterion: what each piece measures or what
law it applies, and what it does NOT promise.

| Piece | What it does | Measures or applies | What it does NOT promise |
|---|---|---|---|
| `vigia.py` (domain/command) | Extends the provenance hunt to hosts/URLs and to install-or-remote-execute lines | Provenance law (§4 above), applied to whatever could lead to another machine: normalized host present or absent from the evidence | Checks WHERE a domain came from, never whether it's trustworthy — a domain with real provenance can still be a copycat; a bare TLD outside the declared list is a known false negative |
| `auditar.py` | The five checks on a package before installing it (provenance, commands, permissions, what leaves the machine, domain) | Law: file:line evidence for every check; verdict breaks/deceives/grazes = the worst finding, never a filler one | NEVER executes or imports the audited code; it's text and regex, not a parser or a sandbox — a URL just mentioned in a comment counts the same as a real call; the domain check never issues a finding on purpose (read it character by character) |
| `lectura_visual.py` | OCR (text/photocopy/card/manual) via the Windows engine or `tesseract` | Applies: real engine measured on the development machine (443 ms, es-ES); declared position/size heuristic for name-title-company | Doesn't invent what the engine doesn't recognize (empty field, never a faked value); `manual` doesn't summarize, it delivers clean, ordered text; `--escaner` is never exercised against real hardware in the test battery |
| `volumen.py` | 2.5D layer breakdown (GrabCut + sharpness/luminance) and `prompt3d` (measured palette/proportion/horizon/shapes) | DECLARED photographic-composition heuristic, never real depth; k-means for palette, contour circularity for shapes | Not 3D reconstruction or object recognition: it says what shapes/colors it measured, never what the object is |
| `gestos.py` | The hand drives the scene (fingers → layers, pinch → explosion, palm pose → orbit, still hand → capture, two hands → scale) | 10th/90th percentiles of the SESSION'S OWN data for pinch/scale (cold start: "no gauge yet" under 30 samples); inherited 1.7 ratio, not yet measured on this machine | Its OWN vocabulary, never any outside tutorial's; nothing on screen jumps ahead of an unfinished gesture; serves HTTP only on 127.0.0.1 |
| `ojo.py` (verbs) | A single entry point (`mirar`/`texto`/`fotocopia`/`tarjeta`/`manual`/`despiece`/`prompt3d`/`gestos`) | Law: delegates entirely to the module that implements each verb (same argv, same exit code) — only `mirar` is self-contained | No verb fires from a hook; `ojo.py` doesn't repeat or weaken the limit of whatever it delegates to |
| `fondo.py` | Removes a photo's background locally (three engines: `sistema` on macOS 14+, `modelo` — an ONNX network of 4,574,861 bytes MEASURED, on `onnxruntime` — and `grabcut` from OpenCV), so that `kinetica.py --quitar-fondo` can MEASURE the silhouette instead of estimating it | Provenance rule for the engine: `auto` tries them in that order and ALWAYS prints which one it used, never switching engines silently; the effect is MEASURED with the same photo in both versions (78,947 pixels invented by inpainting with the background, 55 without it) | The `sistema` engine is WRITTEN BUT NOT TESTED (this package has been measured on Windows) and is declared that way, never as tested; on Windows there is no system path at all (the Photos app's «Remove background» button exposes no public interface, and the Windows App SDK's segmentation requires an NPU); `grabcut` is crude and says so every time, never presented as the good one |
| `kinetica.py` | Turns a photo into a folder with `piezas.json` + `piezas/<clave>.png` for its REAL components (with `--regiones`: hand-drawn polygon + `cv2.grabCut`, overlaps resolved by priority with the real masks; without regions, automatic connected components, flagged as worse) and a three.js viewer served on `127.0.0.1` that the hand drives through the camera | Provenance law: with `--regiones`, WHAT piece exists and WHERE it is comes from whoever looks at the photo, in a readable file — the edge itself is measured by GrabCut; without regions, it warns the result is automatic, has no real names, and is worse — never presented as recognition. The same rule applied to the LINK: the official site can only come from what is read or seen IN THE PHOTO (`--reconocer`, OCR over the pieces; or `--reconocimiento f.json`, signed by whoever looked at it and rejected if it doesn't say what was seen), never from the `titulo` a person typed — no recognition, no link, and the viewer writes down why | Not 3D reconstruction and no real depth measurement; `--rellenar` reconstructs what's covered via `cv2.inpaint` (invented, counted in `relleno_px`); without `abyss/vendor/mp/` (downloaded separately with `instalar.py --manos`, not shipped in the repo) the viewer serves with no hands, with an on-screen warning, never a faked hand; the "hologram" the still palm opens is not a hologram (the assembled object composited over the video and anchored to the palm, and the screen says so); `--reconocer` never gets to run the OCR (MEASURED on 8-Sep: `_reconocer()` uses `AQUI`, a name the module doesn't define, and its own `except` returns it as `como: ninguno`) |
| `esceptico --paquete` | The same skeptic, on a package: `auditar.py` first, then an Opus to read past it | Law: the automatic pass doesn't repeat what a regex already knows how to do; the Opus looks for what the regex can't see (a README that lies, a host built from parts) | The Opus doesn't execute the package either — what no file disproves can still go undetected |
