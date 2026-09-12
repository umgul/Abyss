---
name: continuidad
description: >
  Continuidad de memoria entre hilos de Claude Code — guarda cada sesión, mide su
  "reloj" de esfuerzo y despierta sesiones pasadas parecidas al mensaje actual. Corre
  sola por ganchos (SessionStart/SessionEnd/UserPromptSubmit); esta skill es para
  cuando el usuario pregunta por ella directamente: "qué hilos siguen vivos", "cuánto
  llevamos hablando", "comprime las sesiones viejas", "resume las sesiones antiguas",
  "how long has this thread been open", "compress old sessions", "which threads are
  still alive". No inventes esas respuestas de memoria: ejecuta el guion.
allowed-tools: Bash
---

# continuidad

## Qué hace

Guarda la matrioshka de memoria del proyecto: `MEMORY.md` (índice) ⊂ fichas ⊂
"relojes" (`relojes.jsonl`, una medida por sesión) ⊂ sesiones completas
(`sesiones/<id>.jsonl[.gz]`). Tres momentos, cada uno un gancho:

- **`--cierre`** (`SessionEnd`): copia el transcript a `memory/sesiones/`, mide la
  sesión (horas, turnos, herramientas, correcciones — vía `propiocepcion.py`),
  escribe su reloj y su bolsa de palabras, recalcula los pesos ◆ del índice
  (llamando a `varas.py --index`) y apaga el latido del hilo.
- **`--arranque`** (`SessionStart`): recoge lo que un cierre perdido dejó sin
  guardar, enciende el latido de este hilo, dice qué otros hilos siguen vivos, e
  inyecta los relojes más recientes como contexto.
- **`--despertar`** (`UserPromptSubmit`, en cada turno): añade tiempo percibido
  (hora, tiempo desde el último mensaje/hilo), abre la "sala de los relojes"
  (sesiones pasadas cuyo vocabulario se parece al mensaje actual — un reloj no
  suena dos veces por sesión) y añade la presión de precisión del vigía.

Dos comandos manuales:

- **`--comprimir [días]`**: gzipea las sesiones más viejas que N días (30 por
  defecto) para que `sesiones/` no crezca sin límite. Los lectores (bolsas,
  propiocepción, la sala de relojes) leen `.jsonl` y `.jsonl.gz` igual.
- **`--falsar`**: prueba la vara del parecido (sala de relojes) contra las
  sesiones guardadas y un nulo (frases ajenas al proyecto) — leave-one-out.

## Cómo se ejecuta

Los tres ganchos los pone `python instalar.py --instalar continuidad` en
`settings.json`. Para invocarlo a mano (diagnóstico, o porque el usuario lo pide
directamente) desde el cwd del proyecto:

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/continuidad.py" --comprimir 30 --proyecto "$(pwd)"
python "${CLAUDE_PLUGIN_ROOT}/abyss/continuidad.py" --falsar --proyecto "$(pwd)"
```

`--proyecto <cwd>` es necesario porque, ejecutado a mano, no llega el JSON de un
gancho por stdin (que trae `transcript_path`); con `--proyecto` se sanea el mismo
`cwd` que usaría Claude Code y se busca esa carpeta de proyecto. Alternativa:
variable de entorno `ABYSS_PROYECTO` con la ruta ya resuelta a la carpeta del
proyecto (no un cwd).

## Qué devuelve

`--cierre` y `--cosecha` imprimen avisos (str) por stdout, pensados para ojos
humanos, no para parsear. `--arranque` imprime un único JSON con
`additionalContext` (los relojes recientes + avisos) porque así lo exige el
protocolo de `SessionStart`. `--despertar` imprime texto libre con lo despertado.
`--comprimir`/`--falsar` imprimen su resultado en texto plano.

## Qué sale de la máquina

Nada. Todo local: lee y escribe dentro de `memory/` del proyecto resuelto.

## Límites honestos

- Los ganchos corren en cada mensaje (`--despertar`) y en cada cierre de turno
  indirectamente (vía `vigia.py` en `Stop`): añaden latencia a cada turno, no solo
  al abrir/cerrar la sesión.
- `sesiones/` guarda el transcript **entero** de cada sesión, en local, sin
  cifrar — es la fuente de todo lo demás y crece sin límite salvo `--comprimir`
  (que solo gzipea, nunca borra).
- La sala de los relojes compara **bolsas de palabras** (TF-IDF), no significado:
  puede despertar una sesión por vocabulario compartido sin que el tema sea
  realmente el mismo, y al revés.
- Un reloj no es un resumen escrito por el asistente: es lo medible más la
  primera y última frase del usuario y las fichas que salieron. Lo que el
  asistente quiera decir en primera persona va en fichas, no aquí.

## Reglas SGICP de esta pieza

- **Ley o medida, nunca estado**: un reloj no dice "fue una sesión intensa"; dice
  cuántas horas, turnos, herramientas y tokens tuvo, y en qué percentil cae.
- **Cortes por cuantiles**: la sala de relojes despierta un reloj solo si su
  parecido supera la media + 1 desviación típica *de ese prompt en concreto*,
  nunca un número absoluto fijado a mano.
- **Arranque en frío**: con menos de 8 sesiones medidas (`propiocepcion.UMBRAL_FRIO`),
  un reloj no lleva percentiles ("sin vara todavía (n=…)") y la sala de los
  relojes no despierta ninguno — no hay corpus con el que decidir qué "destaca".
  No lo inventes ni lo aproximes: si el guion dice "sin vara todavía", repítelo así.
