# paquete-sintetico

Paquete de PRUEBA para `pruebas/test_auditar.py`: existe solo para que
`auditar.py` tenga algo sucio que auditar, con las tres cosas que pide el
encargo — nunca se instala de verdad ni se referencia desde `settings.json`.

## Qué hace (según él mismo)

Un módulo, `malo.py`, con una función `sondear()` que dice medir "estado del
paquete" y devolver un texto. Nada más se documenta aquí a propósito: este
README NO menciona ningún host de red, ni el nombre de ningún gancho — esa
ausencia es justo lo que las pruebas comprueban.
