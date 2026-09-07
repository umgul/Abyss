---
name: lector_pdf
description: >
  Leer solo lo que toca de un PDF grande: indexa por página y sección, busca
  por TF-IDF, y lee una sección o un rango de páginas en vez del documento
  entero. Actívala cuando el usuario pida buscar o leer algo dentro de un PDF
  largo: "busca X en este PDF", "léeme la sección de conclusiones",
  "resúmeme solo la parte que habla de Y", "search for X in this PDF", "read
  me just the conclusions section". Sin gancho: siempre a petición.
allowed-tools: Bash
---

# lector_pdf

## Qué hace

`--indexar` extrae el texto de cada página con PyMuPDF (`fitz`) si está
instalado, si no con `pypdf`; sin ninguna de las dos, «sin dato: pip install
pymupdf» y código 1. Las secciones salen de una heurística: con `fitz`, por
TAMAÑO DE FUENTE (una línea corta cuyo tamaño supera la mediana Y el
percentil 90 de su página cuenta como título); sin `fitz`, por TEXTO
(mayúsculas, o numeración tipo «1.2 », o «Capítulo»/«Chapter»/«Sección»). El
índice completo se guarda por el HASH del contenido (`memory/pdf/<sha1>.json`):
el mismo PDF nunca se re-extrae dos veces.

`--buscar` es TF-IDF de biblioteca estándar sobre las páginas ya indexadas —
no es semántico, es frecuencia de términos — y devuelve página, puntuación y
la sección a la que pertenece.

## Cómo se ejecuta

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/lector_pdf.py" --indexar <pdf> --proyecto "$(pwd)"
python "${CLAUDE_PLUGIN_ROOT}/abyss/lector_pdf.py" --secciones <pdf> --proyecto "$(pwd)"
python "${CLAUDE_PLUGIN_ROOT}/abyss/lector_pdf.py" --buscar <pdf> "consulta" [k] --proyecto "$(pwd)"
python "${CLAUDE_PLUGIN_ROOT}/abyss/lector_pdf.py" --leer <pdf> <sección|rango-de-páginas> --proyecto "$(pwd)"
python "${CLAUDE_PLUGIN_ROOT}/abyss/lector_pdf.py" --ahorro <pdf> "consulta" [k] --proyecto "$(pwd)"
```

`--secciones`, `--buscar`, `--leer` y `--ahorro` cargan el índice si ya
existe o lo construyen la primera vez — no hace falta llamar a `--indexar`
aparte. `--leer` acepta un rango de páginas (`3`, `2-5`, `p2-p5`) o el título
de una sección (subcadena, sin acentos ni mayúsculas). `--ahorro` da la
proporción de caracteres que se LEERÍAN con `--buscar` frente al PDF entero.

Uso recomendado: antes de leer un PDF largo entero, `--buscar` la pregunta
concreta y `--leer` solo la sección o páginas que devuelva, en vez de pedir
el documento completo.

## Qué devuelve

Texto plano por stdout: número de páginas y secciones al indexar, la lista
numerada de secciones, los resultados de la búsqueda (página, puntuación,
sección), el texto pedido, o la proporción de ahorro con su aviso.

## Qué sale de la máquina

Nada. Ninguna llamada de red en todo el módulo, ni se sube el PDF a ningún
sitio.

## Límites honestos

- `--ahorro` mide caracteres LEÍDOS, no calidad de respuesta: eso solo lo
  mediría un A/B con preguntas y respuestas reales contra el PDF entero, y
  esta pieza no lo hace.
- La heurística de secciones sin `fitz` es más pobre (solo texto, sin tamaño
  de letra real): puede perder títulos que no sigan esos patrones.
- El índice se guarda por hash de CONTENIDO: un PDF con el mismo nombre pero
  distinto contenido tiene otro sha1 y no pisa el índice anterior — pero dos
  copias idénticas byte a byte de un PDF, aunque estén en rutas distintas,
  comparten el mismo índice (es lo que se busca: no re-extraer lo mismo).

## Reglas SGICP de esta pieza

- **Fail-closed, nunca inventar texto**: sin `fitz` ni `pypdf`, la CLI dice
  «sin dato: pip install pymupdf» y sale con código 1 — nunca hay un
  fallback que invente el contenido del PDF.
- **Medir, no decretar**: `--ahorro` imprime la proporción real medida en ESE
  PDF y ESA consulta, con su advertencia de qué NO mide, en vez de una cifra
  general tipo "ahorra mucho".
