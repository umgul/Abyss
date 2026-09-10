---
name: auditar
description: >
  Las cinco comprobaciones sobre un paquete ANTES de instalarlo — de dónde
  viene, qué ejecuta y cuándo, qué escribe fuera de su carpeta, a qué hosts
  llama sin decirlo, y qué dominios hay que leer letra a letra — cada hallazgo
  con fichero y línea, y sin ejecutar jamás el código auditado. Actívala cuando
  el usuario vaya a instalar algo de fuera o dude de algo ya instalado: "audita
  este paquete antes de instalarlo", "mira qué hace este plugin de verdad", "es
  seguro esto que me he bajado", "qué toca este instalador en mi sistema",
  "audit this package before I install it", "what does this plugin actually do",
  "is this safe to install". Sin gancho: siempre a petición.
allowed-tools: Bash, Read
abyss-managed: true
---

# auditar

## Qué hace

Cinco comprobaciones sobre una carpeta, cada una con su evidencia en
`fichero:línea` — nunca una nota de confianza ni una promesa:

| # | comprobación | pregunta | genera hallazgo |
|---|---|---|---|
| 1 | procedencia | ¿hay autor con nombre real, repositorio, licencia, historia de commits? | `roza` |
| 2 | comandos | ¿qué corre y cuándo? Ganchos por evento, y `subprocess`/`eval`/`exec`/descarga-a-intérprete como evidencia | `rompe` |
| 3 | permisos | ¿qué escribe FUERA de su carpeta (`~/.claude`, `settings.json`, el registro) y declara cómo deshacerlo? | `rompe` |
| 4 | red | todos los hosts del paquete, contrastados contra sus `README*`: uno que el código usa y ningún README nombra | `rompe` |
| 5 | dominio | reúne los dominios para que una persona los compare carácter a carácter | **nunca** |

El veredicto global es el peor hallazgo de las comprobaciones 1-4, en tres
niveles: `rompe` (hace algo que no declara), `engaña` (declara algo que no
cumple) y `roza`. Sin ninguno: `sin hallazgos`.

**Nunca ejecuta el código auditado**, ni lo importa ni lo corre: todo sale de
leer texto y, para la historia, de `git log` **local** sobre el `.git` del propio
paquete. Auditar un paquete malicioso con esto no lo dispara.

Viene de un caso real: a alguien lo comprometieron con un comando que le dio su
propia IA, apuntando a un dominio copia. La comprobación 4 es esa pregunta
aplicada a un paquete entero, y es la que ningún antivirus hace.

## Cómo se ejecuta

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/auditar.py" <ruta_del_paquete>
python "${CLAUDE_PLUGIN_ROOT}/abyss/auditar.py" <ruta_del_paquete> --json
python "${CLAUDE_PLUGIN_ROOT}/abyss/auditar.py" <ruta_del_paquete> --markdown informe.md
```

También se llega desde la skill `esceptico` con `--paquete <ruta>`: corre esto y
le da el informe a un Opus para que lea lo que el automatismo no ve. Esa vía
cuesta una llamada a otro modelo; ésta no cuesta nada.

## Qué devuelve

Un informe legible por pantalla, o `--json` con `procedencia`, `comandos`,
`permisos`, `red`, `dominio`, `hallazgos` y `veredicto`, o `--markdown` con la
tabla de hallazgos para pegarla en un documento. Cada hallazgo lleva
`severidad`, `comprobación`, `fichero`, `línea` y `resumen`.

Los terceros embebidos (`vendor/`, `dist/`, `build/`) se leen **aparte**
(`hosts_terceros_embebidos`) y nunca cuentan como hallazgo contra el README: no
son el código de este paquete. Pero se declaran, para que un informe «sin
hallazgos» no sea indistinguible de «no miré ahí».

## Qué sale de la máquina

Nada. No hay red en ningún punto: se lee el disco, y `git log` es local.

## Límites honestos

- **La comprobación 5 no puede hacer su trabajo, y por eso no lo finge.**
  `pollinations.ai` y `pollinations.ai` se leen igual de rápido y este guion no
  sabe distinguirlos. Reúne los dominios y te los pone delante; compararlos es
  tuyo.
- **No todo `subprocess` es malo.** Las llamadas a `subprocess`, `os.system`,
  `eval` y `exec` salen como evidencia para leerlas juntas, no como acusación.
- **`engaña` no se infiere solo.** Hace falta que alguien compare lo que el
  paquete promete con lo que hace; el guion no lee promesas.
- **Audita una RUTA, no un repositorio.** Si dentro de la carpeta hay algo
  generado que no es código del paquete, lo cuenta como si lo fuera. Medido el
  8-sep-2026 sobre el propio Abyss: un perfil de navegador de 782 MB que se
  había quedado dentro dio **3.082 hallazgos de red falsos**, con dominios que
  salían de una lista de bloqueo del navegador y que el paquete no llama jamás.
  Si el veredicto sale absurdo, lo primero que hay que mirar es qué carpetas
  generadas están dentro.
- **Sus propios tests se auditan a sí mismos.** `pruebas/test_auditar.py` inventa
  dominios para probar el guion (`api.declarado.com`, `api.oculto.net`), y al
  auditar el paquete entero salen como hallazgos reales.
- **Un veredicto limpio no es un certificado.** Es «hasta donde esta vara mira,
  no encontré nada», y la vara mira cinco cosas concretas.

## Reglas SGICP de esta pieza

- **Evidencia o nada**: cada hallazgo lleva fichero y línea. No hay puntuaciones
  de confianza, ni sellos, ni «parece seguro».
- **Leer nunca es ejecutar**: la única forma honesta de auditar algo que puede
  ser hostil.
- **Declarar lo que no se mira** (`hosts_terceros_embebidos`) vale tanto como
  informar de lo que se mira: el silencio es lo que convierte un informe en una
  promesa.
- **La quinta comprobación existe para decir que no puede**: una pieza que
  entrega su propio límite como resultado en vez de esconderlo.
