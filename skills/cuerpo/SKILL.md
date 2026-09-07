---
name: cuerpo
description: >
  El cuerpo de la máquina donde corre el asistente (cpu, ram, disco, vram,
  temperatura de GPU, batería) con su propia normal por cuantiles. Corre sola
  por ganchos (SessionStart/UserPromptSubmit); esta skill es para cuando el
  usuario pregunta por el estado de la máquina o su historial: "cómo va la
  máquina", "cuánta vram libre tengo", "how's the machine doing", "how much
  free vram do I have", "show me the history of the machine's stats". No
  ordena nada (no cierra procesos, no baja modelos): mide, y quien lo lea
  decide.
allowed-tools: Bash
---

# cuerpo

## Qué hace

Seis canales, cada uno con su propio instrumento: cpu (% de uso), ram libre
(GB), disco libre del disco que contiene `memory/` (GB), vram libre y
temperatura de GPU (`nvidia-smi`, una sola llamada), batería (% y si carga).
Sin instrumento (sin GPU NVIDIA, equipo de sobremesa sin batería…): «sin
dato», nunca un 0 que parecería una medida real.

Cada medida se apunta en `memory/cuerpo.jsonl`. Con al menos 8 medidas
previas CON DATO en un canal, ese canal se lee contra sus propios cuantiles
(p5, p50, p95); con menos, «sin vara todavía (n=…)».

- **`SessionStart`**: una línea `[cuerpo] cpu … · ram libre … · disco libre …
  · vram libre … (p50 tuyo …) · temp gpu … · batería …`.
- **`UserPromptSubmit`**: SOLO imprime algo si algún canal de la medida de
  AHORA cae fuera de su p5–p95 propio (`«[cuerpo] vram libre 1,2 GiB: por
  debajo de tu p5 (3,4)»`); si todo está dentro de lo suyo, silencio total.

## Cómo se ejecuta

Los dos ganchos ya corren solos si el módulo está instalado. A mano:

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/cuerpo.py" --proyecto "$(pwd)"                    # una medida, se guarda, se imprime
python "${CLAUDE_PLUGIN_ROOT}/abyss/cuerpo.py" --historial [n] --proyecto "$(pwd)"     # últimas n medidas (20 por defecto)
python "${CLAUDE_PLUGIN_ROOT}/abyss/cuerpo.py" --historial --json --proyecto "$(pwd)"  # como JSON
```

## Qué devuelve

Texto plano por stdout con un valor por canal (y su cuantil p50 propio cuando
ya hay vara); `--json` da la medida y los cuantiles actuales como JSON.

## Qué sale de la máquina

Nada. Todo local: comandos del propio sistema (PowerShell/`wmic` en Windows;
`/proc`, `os.getloadavg()`, `vm_stat`, `pmset` en Linux/macOS) y
`memory/cuerpo.jsonl`.

## Límites honestos

- `leer_cpu()` en Linux/macOS es carga media a 1 minuto entre núcleos, no un
  % de uso instantáneo tal cual — aproximación declarada, no medida exacta.
- La batería nunca compara contra su propio p5–p95 en `UserPromptSubmit`: baja
  de p5 cada vez que se desconecta el cargador, y eso es normal, no una
  anomalía — se muestra en el arranque, no se vigila en cada prompt.
- Con menos de 8 medidas previas en un canal, ese canal no puede "salirse de
  su vara": no hay vara todavía, y la línea lo dice tal cual, sin aproximarlo.

## Reglas SGICP de esta pieza

- **Ley o medida, nunca estado**: nunca dice "la máquina va mal" — dice el
  valor de cada canal y, cuando ya hay vara, en qué cuantil cae.
- **Fail-closed, nunca inventar**: un instrumento sin dato es `None`, nunca
  un 0 que sería indistinguible de una medida real de cero.
- **Nunca ordena**: no cierra procesos, no baja de modelo, no sugiere nada —
  mide, y la decisión queda para quien lo lea.
