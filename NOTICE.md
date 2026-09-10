# NOTICE — lo que este paquete lleva dentro y no es suyo

Abyss se publica bajo Apache-2.0 (ver `LICENSE`). Pero dentro viajan tres obras de
terceros, vendorizadas a propósito para que el paquete funcione sin pedirle al
usuario que descargue nada. Cada una conserva su licencia, y aquí están todas
juntas para que se vean de un vistazo.

| qué | dónde | de quién | licencia | su texto |
|---|---|---|---|---|
| three.js r160 (`three.min.js`, 669.884 B) | `abyss/vendor/` | three.js Authors | MIT | `abyss/vendor/LICENSE-three.txt` |
| MediaPipe Tasks Vision 0.10.14 + `hand_landmarker.task` | `abyss/vendor/mp/` | Google | Apache-2.0 | `abyss/vendor/mp/LICENSE-mediapipe.txt` |
| U²-Net p (`u2netp.onnx`, 4.574.861 B) | `abyss/vendor/modelos/` | Xuebin Qin et al. (red) · Daniel Gatis / rembg (el fichero) | Apache-2.0 · MIT | `abyss/vendor/modelos/LICENSE-u2netp.txt` |

Los tamaños están medidos con `os.path.getsize`, no estimados.

## Por qué van dentro y no se descargan al vuelo

Porque un paquete que se baja cosas de internet la primera vez que lo usas es un
paquete que no se puede auditar antes de instalarlo, y auditar antes de instalar
es justamente lo que hace `abyss/auditar.py`. Lo que viaja dentro se puede leer,
pesar y comprobar sin ejecutar nada.

La excepción es MediaPipe: son unos 26 MB y **no** se instalan por defecto. Se
piden aparte con `python instalar.py --manos`, y sin ellos los visores cinéticos
funcionan igual, sin manos, y lo dicen en pantalla.

## Lo que este paquete NO hace con ellas

- No entrena, no reentrena y no modifica ningún modelo.
- No redistribuye ninguna versión alterada: los ficheros son los que se bajaron.
- No manda nada a ningún servidor: los tres corren en la máquina del usuario.

## Lo que sí es de este paquete

Todo lo demás — el código de `abyss/`, las plantillas, las skills, las pruebas y
la documentación — es obra propia y va bajo Apache-2.0, igual que el conjunto.
