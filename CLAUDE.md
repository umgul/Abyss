# Para Claude: esto es un paquete de skills, y esto es lo que hay que hacer con él

Si estás leyendo esto es porque alguien ha descargado **Abyss** y te ha abierto en
su carpeta. No es un proyecto que haya que desarrollar: es un paquete de skills y
de instrumentación para Claude Code que se **instala**. Lo que sigue es la receta,
y las tres cosas que NO puedes hacer.

## Lo primero: pregunta, no instales

Instalar esto toca la configuración de Claude Code del usuario. Antes de correr
nada, enséñale lo que hay y deja que elija:

```bash
python instalar.py --listar
```

Sale la lista de módulos con, para cada uno, qué hace y **qué toca** — si pone un
gancho, si escribe en `settings.json`, si resuelve proyecto, si necesita red. Léela
con él. Hay `--idioma en` si prefiere inglés.

## La instalación

```bash
python instalar.py
```

Instala los módulos marcados por defecto. Para elegir a mano:

```bash
python instalar.py --solo kinetico,kinetica,vigia,auditar
python instalar.py --skills-dir <ruta>     # si sus skills no viven en ~/.claude/skills
```

Y para deshacer, entero y sin restos:

```bash
python instalar.py --desinstalar
```

## Lo que hay que bajar aparte, y por qué no viene dentro

**Este repositorio solo contiene texto.** Ninguna biblioteca de terceros, ningún
modelo y ningún `.wasm` viajan dentro, porque este mismo paquete ofrece
`auditar.py` para mirar un paquete ANTES de instalarlo, y un repositorio que se
puede leer entero es la única forma de que esa promesa la sostenga la lectura y no
la confianza. La excepción declarada es `abyss/vendor/three.min.js` (669.884 B,
MIT), que ya estaba en la historia y sin el cual los visores 3D no arrancan.

Lo que falta se baja con una orden, y cada descarga deja su licencia al lado:

```bash
python instalar.py --manos       # MediaPipe Tasks Vision, ~27 MB: manos por cámara
python instalar.py --modelo      # U^2-Net p, 4.574.861 B: quitar el fondo de una foto
```

**Pregúntale antes de bajar nada.** Son megas de su conexión y de su disco, y sin
ellos el paquete funciona igual con menos: los visores cinéticos se sirven sin
manos y lo dicen en pantalla, y `fondo.py` usa el motor que tenga y declara cuál.

Las dependencias de Python (`opencv-python`, `numpy`, `Pillow`, `onnxruntime`…)
las lista `requirements.txt`. **No corras `pip install` por tu cuenta**: enséñale
la lista y que decida él si instala, y con qué.

## Las tres cosas que NO puedes hacer aquí

1. **No edites `settings.json` a mano.** De eso se encarga `instalar.py`, que
   además apunta la firma de cada gancho para poder quitarlo después. Un gancho
   puesto a mano es un gancho que nadie sabrá desinstalar.
2. **No bajes nada sin preguntar** — ni modelos, ni paquetes de pip, ni ficheros
   de vendor. Ninguna skill de este paquete descarga nada por su cuenta, y tú
   tampoco.
3. **No metas datos personales en este repositorio.** Ni nombres de personas, ni
   rutas `C:/Users/<alguien>`, ni tokens ni claves. Aquí el usuario es «el
   usuario». Hay una prueba que lo comprueba y falla si se cuela algo:
   `python -m pytest pruebas/test_sin_datos_personales.py -q`

## Si el usuario prefiere el camino de plugin

Abyss también es un plugin de Claude Code, y por ahí las skills se descubren
solas sin copiar nada:

```
/plugin marketplace add umgul/Abyss
/plugin install abyss
```

Ese camino instala las skills. Los ganchos y la instrumentación (memoria,
propiocepción, vigía) siguen necesitando `instalar.py`.

## Comprobar que quedó bien

```bash
python instalar.py --listar          # cada módulo dice si está instalado
python -m pytest pruebas/ -q         # la suite entera
```

## Qué es cada cosa, si te lo preguntan

- `abyss/` — los módulos. Cada uno se puede correr suelto por línea de órdenes.
- `skills/` — las skills de Claude Code, una carpeta por skill.
- `plantillas/` — las semillas de configuración que `instalar.py` copia a la
  memoria del proyecto del usuario la primera vez.
- `pruebas/` — la suite.
- `docs/` — entre ellas la auditoría del propio paquete hecha con `auditar.py`.
- `NOTICE.md` — qué obras de terceros lleva dentro y bajo qué licencia.

El paquete completo, módulo a módulo y con lo que toca cada uno, está en
`README.md` (y `README.en.md` en inglés).
