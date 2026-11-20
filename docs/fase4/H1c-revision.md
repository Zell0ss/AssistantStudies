# H1c — revisión (fase 4, diagnóstico): la memoria no guarda un identificador

> Responde a: c4378ad (H1c-informe). 2026-11-20, arquitecto. Revisado contra `ce97b1a..c4378ad` y la suite.

**Veredicto: diagnóstico aceptado.** Se hace tu paso 1, con dos añadidos. El paso 2 solo se hace si el paso 1 lo pide.

## 1. Contra el código

- **El script** usa el prompt, las tools, el modelo y el techo de producción tal como se importan (`_planner_system`, `_PLANNER_TOOLS`, `extractor._prompt`…). No copia nada, así que la prueba vale. Los datos son inventados y no hay BD.
- **Tu lectura del log es correcta.** En `core/memoria/servicio.py:76`, `hechos` cuenta lo que queda después de `_validar` (`extractor.py:116`). Con el log de hoy no se distingue entre «Haiku devolvió `[]`» y «`_validar` lo tiró todo». Tampoco queda rastro del `texto`: `purgar_fuente_sin_hechos` borra la fuente cuando no hay hechos.
- **Descartes válidos:** A y B con datos inventados (12/12), R10 por `sin_cambio=0`, y que el código de memoria no ha cambiado entre `main` y `fase-4`.
- **Suite:** la he ejecutado yo: **1113 pasan**.
- **Gasto:** 0,0488 $ de 0,05. Fase 4 ≈ 0,098 $ de 3 $.

Una corrección: **H1 y H1b ya están desplegados** (20/11, 14:37). Este log irá en un despliegue propio y pequeño.

## 2. Qué falta saber

Hay que repetir lo de Josem una vez, en producción, con un log que diga qué pasó. Esa repetición no cuesta nada extra: es una llamada normal de Josem. Solo hace falta reproducirlo con el catálogo real (tu paso 2) si el log dice que Haiku devuelve `[]`.

## 3. Retoque

- **R10b — el extractor dice qué devuelve, sin contenido (D42).** En `Extractor.extraer`, un `logger.info` con:
  - `stop_reason`;
  - `crudos=N`: el número de elementos en `bloque.input["hechos"]`;
  - `validados=M`;
  - `descartes=`: el motivo de cada crudo descartado, como **etiqueta fija**:
    - `marcador`;
    - `sin_atributo`;
    - `operacion_invalida`;
    - `no_es_dict`.
  - Nunca el valor de la operación ni ningún texto del modelo: solo la etiqueta.
  - Si `hechos` no es una lista (por ejemplo, un string), cuenta como `crudos=0` con `descartes=hechos_no_lista`. Hoy, `or []` lo trataría como una lista vacía sin decir nada.
- **R10c — longitud del `texto`.** En la línea `memoria.guardar` de `servicio.py`, añade `chars=<len(texto)>`. Si el planner manda una frase vacía o de pocas letras (hipótesis A, en producción y con historial), se verá. No lleva contenido.
- **Pruebas (cliente falso, sin API):**
  - con `hechos: []`, el log dice `crudos=0 validados=0`;
  - con un hecho bueno y uno sin atributo, dice `crudos=2 validados=1 descartes=sin_atributo`;
  - con `hechos` como string, dice `descartes=hechos_no_lista` y no hay excepción;
  - con una marca `ZZEXTR` en el valor y en el texto, no aparece en ningún log;
  - `memoria.guardar` lleva `chars=`.
- **Cita D42 y H1c en un comentario.**

## 4. Lista previa (§4)

- **¿Borra o sobrescribe datos?** No.
- **¿Llama a una API externa?** No en las pruebas. En producción, la misma llamada de siempre.
- **¿Toca producción?** Solo al desplegar: merge y reinicio, que hace Josem.

## Para el programador

Responde a: c4378ad (H1c-informe)

1. Haz R10b y R10c con sus pruebas.
2. Pasa la suite.
3. Escribe un anexo corto al final de `H1c-informe.md`, con las órdenes de despliegue (merge y reinicio, en una línea con `&&`, sin comentarios), y para.

El paso 2 (catálogo real) no se hace todavía. Sin gasto.
