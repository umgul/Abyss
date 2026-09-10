---
name: huella
description: >
  Todo lo que este hilo toca FUERA de su propia carpeta de código: ficheros
  escritos, procesos y puertos que arrancó y que siguen vivos. Úsala cuando el
  usuario pregunte qué dejó abierto el hilo o pida limpiarlo: "qué tocaste
  fuera del proyecto", "qué procesos dejaste corriendo", "limpia lo que hayas
  dejado abierto", "what did this thread leave running", "clean up whatever
  you left open". Corre sola por ganchos SOLO si el módulo `huella` está
  instalado (APAGADO por defecto: ver "Límites honestos").
allowed-tools: Bash
---

# huella

## Qué hace

Con el módulo instalado, tres ganchos registran en
`memory/huella/<sesión>.jsonl`:

- **`SessionStart`**: una foto inicial de puertos en escucha y procesos con su
  hora de arranque (nada se imprime).
- **`PostToolUse`**: si la herramienta es `Write`/`Edit`/`NotebookEdit`,
  apunta la ruta escrita; si es `Bash`/`PowerShell`, apunta el comando
  (recortado a 200 caracteres) y la DIFERENCIA de puertos/procesos contra la
  foto anterior — puertos nuevos en escucha, procesos nuevos.
- **`Stop`**: una línea `[huella] N proceso(s) y M puerto(s) abiertos por este
  hilo siguen vivos: --informe` — solo si de verdad queda algo vivo; si no,
  silencio total.

## Cómo se ejecuta

Diagnóstico y limpieza, a mano:

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/huella.py" --informe [id] --proyecto "$(pwd)"
python "${CLAUDE_PLUGIN_ROOT}/abyss/huella.py" --limpiar [id] --proyecto "$(pwd)"          # simula, no toca nada
python "${CLAUDE_PLUGIN_ROOT}/abyss/huella.py" --limpiar [id] --si --proyecto "$(pwd)"      # limpia de verdad
```

`--informe` lista ficheros escritos (agrupados por su raíz), procesos que este
hilo vio nacer y que SIGUEN vivos ahora (pid, nombre, hora de arranque), y
puertos que vio abrirse y que SIGUEN en escucha ahora. `--limpiar` sin `--si`
solo dice qué HARÍA; con `--si`, mata SOLO los procesos cuyo pid Y hora de
arranque coinciden con lo registrado en ESE momento (un pid reciclado por el
sistema para otro proceso no se toca) y borra SOLO los ficheros registrados
que estén bajo el directorio temporal del sistema o bajo una subcarpeta que
ESTE módulo genera dentro de `memory/` (`huella/`, `mapas/`, `pdf/`) —
cualquier otro fichero registrado, incluidos `memory/MEMORY.md`, una ficha
`memory/*.md` o cualquier cosa suelta directamente en la raíz de `memory/`,
se lista y NUNCA se toca, tenga o no `--si`: eso es memoria o configuración
del usuario, no algo que este módulo genere.

`[id]` es opcional: sin él, usa el hilo con el latido más reciente
(heurística — con varios hilos activos a la vez podría acertar el
equivocado; `--sesion <id>` explícito siempre gana).

## Qué devuelve

`--informe` imprime tres listas (ficheros, procesos, puertos) o dice
explícitamente «sin dato: no se pudo consultar» si el instrumento de esta
máquina falló — nunca muestra una lista vacía que parezca "no hay nada" cuando
en realidad no se pudo mirar. `--limpiar` imprime qué mató/borró de verdad (o
qué haría, sin `--si`).

## Qué sale de la máquina

Nada. Todo local: solo procesos y puertos de esta máquina (PowerShell en
Windows; `ss`/`lsof`/`ps` en Linux/macOS — esta última rama está escrita
contra el formato documentado de esos comandos pero sin ejecutar en Windows).
Eso sí, `memory/huella/<sesión>.jsonl` guarda el TEXTO LITERAL de cada comando
de Bash/PowerShell (recortado a 200 caracteres): si sueles pasar un token o
una cabecera `Authorization` por línea de comandos, quedará ahí en local.

## Cómo activarla

Viene **apagada**, y encenderla es un comando:

```
python instalar.py --instalar huella
```

`python instalar.py --listar` la muestra con su estado, lo que toca y su aviso de coste
antes de que decidas. Para apagarla otra vez: `python instalar.py --desinstalar huella`.

Está apagada por el gancho `PostToolUse`, que corre **tras cada herramienta**: la foto de
puertos y procesos cuesta cerca de un segundo cada vez, y eso se paga en todos los comandos
del hilo, no solo en los que abren algo. Encenderla es una decisión sobre ese peaje, y por
eso no se toma por ti.

## Límites honestos

- **APAGADO por defecto** (`instalar.py`): el gancho `PostToolUse` corre tras
  CADA herramienta, y la foto de puertos/procesos tiene coste medible (~950 ms
  por PowerShell combinado, medido en la máquina de desarrollo). Por debajo de
  3 medidas de coste todavía fotografía siempre (para poder medir); con 3 o
  más, si la mediana supera 1,5 s, deja de fotografiar tras cada
  `Bash`/`PowerShell` y solo lo hace si el comando parece persistente
  (`start`, `python`, `node`, `serve`, `nohup`, `&` — heurística declarada: un
  `pip install` largo sin esas palabras se salta la foto aunque tarde; un
  `echo start` la dispara aunque no arranque nada). El comando en sí SIEMPRE
  se registra, se tome o no la foto.
- `--limpiar --si` solo actúa sobre lo que ESTE paquete registró en ESTA
  sesión: un proceso o fichero que otro programa dejó abierto no aparece aquí.
- El agrupado "por raíz" de `--informe` es una heurística (unidad + primer
  directorio en Windows, `/` + primer directorio en POSIX), no una ruta
  canónica.

## Reglas SGICP de esta pieza

- **Fail-closed, nunca inventar**: si `foto()` no puede consultar el sistema,
  el informe lo dice explícitamente en vez de mostrar una lista vacía.
- **El coste se mide, no se supone**: el guion guarda sus propias últimas 30
  medidas de coste (`memory/huella/_costes.json`) y decide el heurístico de
  arriba contra SU PROPIA mediana, no contra un número puesto a mano.
