---
name: mapa_codigo
description: >
  El índice greppable de un repo Python, sacado con `ast` (nunca ejecuta el
  código): módulos, clases, métodos, funciones e imports, cada uno con su
  línea. Actívala cuando el usuario pida orientarse en un repo grande antes de
  leerlo entero: "hazme un mapa de este código", "dónde está la clase X",
  "busca la función Y en el repo", "map out this codebase", "where is class X
  defined". Sin gancho: siempre a petición.
allowed-tools: Bash
---

# mapa_codigo

## Qué hace

Recorre todos los `.py` de una carpeta (excluye `.git`, `venv`, `.venv`,
`node_modules`, `__pycache__`, `site-packages`) y, por fichero, saca con
`ast.parse` — nunca ejecuta el código — el docstring y las líneas del módulo,
sus imports, sus clases (línea inicio-fin, bases, docstring) con sus métodos
(línea inicio-fin, firma reconstruida, decoradores, docstring), y sus
funciones de nivel de módulo. Un fichero con error de sintaxis se lista como
`<ruta> (no parsea: <error>)` y no tumba el resto del recorrido.

## Cómo se ejecuta

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/mapa_codigo.py" <carpeta> [--salida fichero] [--json] --proyecto "$(pwd)"
python "${CLAUDE_PLUGIN_ROOT}/abyss/mapa_codigo.py" --buscar <nombre> --proyecto "$(pwd)"
```

Salida por defecto: texto greppable en `memory/mapas/<nombre de la
carpeta>.txt`, una línea por símbolo (`ruta:línea_ini-línea_fin
Clase.metodo(args) — docstring`). `--salida <fichero>` la escribe ahí en vez
de `memory/mapas/`. `--json` escribe además un `.json` con la estructura
completa. `--buscar <nombre>` busca esa subcadena en el ÚLTIMO mapa `.txt`
escrito, sin volver a analizar nada.

Uso recomendado: antes de explorar un repo grande a golpe de `Read`/`Grep`
fichero a fichero, generar el mapa una vez y usar `--buscar` (o `grep` normal
sobre el `.txt`) para ubicar el símbolo exacto y su línea antes de abrir el
fichero.

## Qué devuelve

La ruta del mapa escrito, y una medida siempre impresa sin adjetivos: ficheros
analizados, líneas de código totales, líneas que ocupa el propio mapa, y la
proporción entre ambas (cuánto se lee de menos si se consulta el mapa en vez
del código para ubicar un símbolo). Los ficheros rotos se listan aparte.

## Qué sale de la máquina

Nada. Ninguna llamada de red; ningún fichero fuera de la carpeta pedida se lee
más que para listar `.py`.

## Límites honestos

- La proporción medida dice cuánto pesa el mapa frente al código — no mide si
  el mapa BASTA para entender el código, eso no está medido aquí.
- Clases anidadas dentro de otra clase no se recorren: solo los métodos de
  primer nivel de cada clase (caso raro, declarado, no oculto).
- `--buscar` es una subcadena literal sobre el ÚLTIMO mapa escrito, sin
  distinguir mayúsculas — no hay regex, no hay ranking de relevancia.

## Reglas SGICP de esta pieza

- **Un fichero roto no tumba el resto**: cada fichero se analiza en su propio
  `try`; un `SyntaxError` en uno solo se señala en su línea del mapa, el resto
  del repo se sigue analizando igual.
- **Medir, no decretar**: la proporción mapa/código se calcula e imprime
  siempre — no hay una afirmación tipo "el mapa ahorra mucho" sin el número
  que la sostenga.
