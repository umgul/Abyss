---
name: varas
description: >
  Recalcula el peso de uso ◆/◆◆/◆◆◆ de cada ficha de MEMORY.md a partir de citas y
  sesiones que la leyeron, por cuantiles de la distribución actual — nunca un
  umbral fijo. Úsala cuando el usuario pida reindexar la memoria, preguntar qué
  fichas se usan más, o recortar un MEMORY.md que se ha hecho grande: "reindexa la
  memoria", "qué fichas se citan más", "el índice se ha hecho muy largo,
  recórtalo", "recompute memory weights", "trim MEMORY.md". No la dispara ningún
  gancho por sí sola: la llama `continuidad.py --cierre` tras cada cierre de
  sesión, o se ejecuta a mano.
allowed-tools: Bash
---

# varas

## Qué hace

Dos varas separadas en el índice de memoria (`MEMORY.md`):

- **★ estrella-diario**: decreto del propio asistente al escribir la ficha
  (importancia que le dio ese día). `varas.py` no la toca.
- **◆ peso-uso medido**: citas `[[..]]` desde otras fichas más sesiones que
  leyeron esa ficha (solo lecturas explícitas — `Read`/`cat`; lo que el harness
  inyecta como memoria automática no deja huella, así que esto **subestima** el
  uso real). Cortes por decil y tramos de la distribución de uso medido, no por
  un número de citas fijo: ◆◆◆ decil alto, ◆◆ siguiente 20%, ◆ siguiente 30%.

`--index` reescribe esos glifos en `MEMORY.md`, de forma idempotente. Si el
fichero supera 24 KB tras reescribir, **avisa por stdout** que hace falta
recortar, pero no recorta nada por sí solo — ese aviso sale por el stdout de un
gancho y nadie lo lee ahí. Solo `--index --recortar`, explícito, corta las líneas
de más de 200 caracteres en su último separador ` · ` (nunca a medias de un
enlace, nunca borrando una línea entera), dejando antes una copia fechada
`MEMORY.md.abyss-AAAAMMDD-HHMMSS.bak`.

## Cómo se ejecuta

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/varas.py" --proyecto "$(pwd)"                    # informe, sin tocar nada
python "${CLAUDE_PLUGIN_ROOT}/abyss/varas.py" --index --proyecto "$(pwd)"            # reescribe los ◆
python "${CLAUDE_PLUGIN_ROOT}/abyss/varas.py" --index --recortar --proyecto "$(pwd)" # además recorta si supera 24 KB
```

`--proyecto <cwd>` (o `ABYSS_PROYECTO`) hace falta al ejecutarlo a mano, igual que
el resto del paquete (ver la skill de `continuidad`).

## Qué devuelve

Texto por stdout: sin argumentos, un informe de pesos; con `--index`, confirma la
reescritura y, si aplica, el aviso de tamaño; con `--recortar`, además cuántas
líneas se cortaron y dónde quedó la copia `.bak`.

## Qué sale de la máquina

Nada. Todo local: lee y escribe `MEMORY.md` y las sesiones dentro de `memory/`.

## Límites honestos

- "Leída" solo cuenta `Read`/`cat` explícitos — la memoria automática que Claude
  Code inyecta no deja huella, así que el uso medido siempre está por debajo del
  real, sin forma de saber cuánto.
- El recorte automático **no existe**: solo avisa. Recortar de verdad es una
  acción manual (`--index --recortar`), y nunca borra contenido, solo lo parte en
  su separador.

## Reglas SGICP de esta pieza

- **Cortes por cuantiles, nunca umbrales fijos**: los ◆ salen del decil y los
  tramos de la distribución de uso *actual*, que rota cada vez que hay datos
  nuevos — nunca de "más de N citas = ◆◆◆".
- **Arranque en frío**: con menos de 8 sesiones archivadas (`propiocepcion.UMBRAL_FRIO`)
  no hay distribución que valga — no se pone **ningún** ◆, aunque el uso medido
  sea mayor que cero; con tan poco corpus el ranking por cuantiles no significa
  nada. Si el guion dice "sin vara todavía", no le pongas un ◆ a mano para
  compensar.
