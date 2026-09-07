---
name: vigia
description: >
  Vigía anti-confabulación: contrasta la última respuesta del asistente contra
  la evidencia real de la sesión (lo dicho por el usuario, lo devuelto por
  herramientas) y bloquea el cierre del turno una vez si encuentra números, rutas
  o citas sin fuente. Corre sola en el gancho Stop; esta skill es para cuando el
  usuario pide revisar su precisión o descargar una caza falsa: "descarga esa
  caza, era un cálculo que sí mostré", "cuál es la precisión del vigía",
  "dismiss that catch, I showed my work", "how accurate is the watchdog". Nunca
  la invoques para silenciar una caza real: el descargo es para cazas
  ilegítimas, medidas después con --precision.
allowed-tools: Bash
---

# vigia

## Qué hace

No detecta "mentiras": detecta ausencia de fuente. Tras cada respuesta
(`Stop`), busca en el texto de esa respuesta números, rutas de fichero y citas
entre «»; si no aparecen ni en lo dicho por el usuario ni en lo devuelto por una
herramienta en toda la sesión, los apunta en `memory/confabulaciones.jsonl` y
**bloquea el cierre del turno una vez** para que se reescriba
(`stop_hook_active=True` ⇒ deja pasar y solo apunta "reincidente" — no hay
segundo intento en el mismo turno). Un número suelto sin fuente solo avisa
(puede ser aritmética propia); dos o más números, o cualquier ruta o cita,
bloquean. Las citas entre «» se dividen en `cita` (hay un verbo de atribución
cerca: alguien la habría dicho así) y `parafrasis` (uso estilístico, más
benigno, contado aparte). Frases en primera persona sobre el propio estado
("me alegra", "tengo ganas") no bloquean — se cuentan como "estados sin vara".

## Cómo se ejecuta

El gancho `Stop` ya corre solo. Comandos manuales:

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/vigia.py" --presion <sid> --proyecto "$(pwd)"
python "${CLAUDE_PLUGIN_ROOT}/abyss/vigia.py" --descargo <sid> "<caza>" "<motivo>" --proyecto "$(pwd)"
python "${CLAUDE_PLUGIN_ROOT}/abyss/vigia.py" --precision --proyecto "$(pwd)"
python "${CLAUDE_PLUGIN_ROOT}/abyss/vigia.py" --estados-baseline --proyecto "$(pwd)"
```

`--descargo` es el que el propio asistente debería usar cuando el texto de
bloqueo señala una caza que en realidad tenía fuente (un cálculo mostrado, una
cita exacta): así se mide la precisión real de la vara con el tiempo, en vez de
dejar la caza como si hubiera sido un acierto sin más.

## Qué devuelve

`--precision` compara cazas totales contra descargos: con cero descargos dice
explícitamente **"sin vara"** en vez de imprimir un 1.00 que solo significaría
que nadie ha mirado. `--presion` da las cazas de una sesión contra la
distribución. `--estados-baseline` cuenta estados sin vara en todas las sesiones
guardadas.

## Qué sale de la máquina

Nada. Todo local: lee el transcript y escribe `confabulaciones.jsonl`.

## Límites honestos

- No juzga afirmaciones sin número ni cita — ahí no llega.
- Un número calculado a partir de otros sale cazado correctamente (hay que
  enseñar el cálculo); un número presente por casualidad en cualquier salida de
  herramienta se da por cubierto aunque no tenga relación real — falso negativo
  conocido.
- Bloquea como mucho una vez por turno; si el asistente insiste tras el primer
  bloqueo, pasa y solo queda anotado como "reincidente".

## Reglas SGICP de esta pieza

- **Cazar lo que no salió de ninguna parte**: la comparación es solo con la
  evidencia real de la sesión (usuario + herramientas), nunca con los propios
  textos anteriores del asistente ni con "parece razonable".
- **Una vara sin varianza no mide**: sin ningún descargo todavía, `--precision`
  dice "sin vara" — un acierto del 100% sin nadie que lo haya puesto a prueba no
  significa que la vara sea perfecta, significa que nadie ha mirado si se
  equivoca.
