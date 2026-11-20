# H1c — Informe del programador (fase 4, diagnóstico): la memoria no guarda un identificador

Responde a: `2472db5` (H1c-encargo, `ce97b1a`).
Commit del script en `fase-4`: `7c544d9`. Salida completa guardada fuera del repo (scratchpad, `f4_h1c.txt`). Suite: **1113 pruebas** pasan (1107 + 6 del script, con cliente falso).

## Veredicto

**Ni (A) ni (B): no se reproduce.** Con datos inventados, el planner y el extractor reales hacen lo correcto en las 12 llamadas. La causa tiene que estar en algo que el script no tenía: el catálogo real de Josem, los valores reales, o el `texto` que el planner mandó de verdad. Es (C), y no puedo decir cuál con lo que hay.

## Qué se hizo

Script `scripts/memoria/diagnostico_identificadores.py`, sin BD y sin tocar producción.

- **Planner:** `_planner_system`, `_PLANNER_TOOLS`, `_MODELO_PLANNER` (Haiku 4.5) y `_PLANNER_MAX_TOKENS` de `core/orchestrator.py`. El índice de memoria es inventado: «- yo (tú): preferencia».
- **Extractor:** prompt, tool, modelo y techo de `core/memoria/extractor.py`. El catálogo es inventado con la forma de `texto_catalogo`: la entidad `yo` (es el propio usuario) y los 10 atributos semilla de la migración 011.
- Se guarda `bloque.input` tal como llega y, aparte, lo que dejaría pasar `_validar`.

## Resultados (datos inventados)

**Planner**, «Recuerda que en Telegram mi id es 700111222 y mi usuario es @usuario_prueba», 2 pasadas. Las dos llaman a `mark_as_memorable` con el mismo `texto`:

> «En Telegram mi id es 700111222 y mi usuario es @usuario_prueba»

**(A) no se confirma:** el planner no pierde el id ni el usuario.

**Extractor** (todas las salidas, también tras `_validar`, tienen `entidad: yo`):

| Caso | Pasadas | Hechos en `bloque.input` | Pasan `_validar` |
|---|---|---|---|
| `texto` del planner | 2 | `telegram_id = 700111222` (numero) y `telegram_usuario = @usuario_prueba` (texto) | 2 y 2 |
| «Mi id de Telegram es 700111222» | 2 | `id_telegram = 700111222` | 1 y 1 |
| «Mi usuario de Telegram es @usuario_prueba» | 2 | `usuario_telegram = @usuario_prueba` | 1 y 1 |
| «La matrícula de mi coche es 1234 ABC» | 2 | `matricula_coche = 1234 ABC` | 1 y 1 |
| «Mi número de socio del gimnasio es 55821» | 1 | `numero_socio_gimnasio = 55821` (numero) | 1 |
| «Mi color favorito es el verde» (control) | 1 | `preferencia = verde` | 1 |

**(B) no se confirma:** el extractor guarda ids, usuarios, matrículas y números de socio, con atributo nuevo y su `descripcion_atributo`. 12 de 12 llamadas dan lo esperado; ninguna devuelve lista vacía.

Los hechos nunca llevan marcador en la entidad (`<UNKNOWN>`), así que tampoco es R10. En producción, además, un marcador habría dejado `sin_cambio=1`, y salió `0`.

## Lo que sí enseña el log de producción

`memoria.guardar` mide `hechos=len(hechos)` **después** de `_validar`. Los tres avisos de Josem dicen `hechos=0` sin `sin_cambio`, y no aparece el aviso «la respuesta no trae la tool». Así que o Haiku devolvió `hechos: []`, o devolvió hechos que `_validar` descartó (atributo vacío u operación fuera de la lista). **El log no permite distinguirlo.** Es lo primero que hay que poder ver.

El log solo conserva esas tres líneas de `memoria.guardar`. No hay ninguna anterior con `hechos>0` para comparar.

Descartado además, sin API: el código de memoria (`core/memoria/`, `memory_tools.py`) es idéntico en `main` y en `fase-4`, así que H1/H1b no han cambiado nada aquí.

## Gasto

**0,0488 $** de los 0,05 autorizados (Haiku 4.5; 2 llamadas del planner, 0,0151 y 0,0032 $, y 10 del extractor, de 0,0028 a 0,0036 $). Autorizó Josem el 2026-11-20, en el encargo del arquitecto y con su «Dale» en mi ventana. Fase 4 acumulada ≈ 0,098 $ de 3 $.

## Desviaciones

Ninguna respecto al encargo. Como el `texto` del planner salió igual en las dos pasadas, solo hay un `texto` distinto para el extractor. Las 10 llamadas del extractor fueron: una pasada de cada caso (6) y una segunda de los cuatro primeros (`texto` del planner, id, usuario y matrícula).

## Arreglo que propongo (sin aplicar)

No hay un arreglo para A ni para B. Propongo dos pasos, en este orden:

1. **Ver qué devuelve el extractor, sin contenido (D42).** En `Extractor.extraer`, un `logger.info` con `stop_reason`, nº de hechos crudos y nº de validados: `Extractor: stop=… crudos=N validados=M`. Pequeño, con su prueba, sin API. Un `crudos=0` dice que Haiku no devolvió nada. Un `crudos>0 validados=0` dice que lo tiró `_validar`.
2. **Reproducir con el catálogo real.** El script admitiría `--catalogo FICHERO` con la salida de `texto_catalogo` del usuario. Esa salida son datos de Josem, así que la sacaría él (o la autorizaría el arquitecto), solo con `SELECT`, y yo no tocaría producción. Con ese catálogo y las mismas cinco frases se vería si el catálogo real (hasta 60 entidades, atributos que ha ido abriendo la memoria) empuja a Haiku a devolver `[]`. Coste estimado: ~0,03 $.

Si tras el paso 2 sigue sin reproducirse, quedaría el `texto` real del planner (que no se loguea por D42) o los valores reales del id y el usuario: eso lo decidiría el arquitecto.

## Decisiones que necesito

1. ¿Hago el paso 1 (log de `stop`, `crudos`, `validados`) y lo despliega Josem con H1/H1b, o prefieres otra cosa?
2. ¿Quieres el paso 2? Necesita que alguien saque `texto_catalogo` del usuario real (datos de Josem, solo lectura) y un nuevo «sí» de gasto (~0,03 $).

---

# Anexo — R10b y R10c (log del extractor)

Responde a: `0a534fb` (H1c-revision).
Commit en `fase-4`: `f82ba62`. Suite completa: **1122 pruebas** pasan (1113 + 9), sin API. Gasto: 0 $.

## Hecho

- **R10b (`core/memoria/extractor.py`):** `Extractor.extraer` deja un `logger.info` por llamada:
  `Extractor: stop=<stop_reason> crudos=N validados=M` y, si hubo descartes, ` descartes=<etiquetas>`.
  - Las etiquetas, una por cada crudo descartado y en su orden, son `marcador`, `sin_atributo`, `operacion_invalida` y `no_es_dict`.
  - Si `hechos` no es una lista (un string, por ejemplo), no hay excepción: sale `crudos=0 validados=0 descartes=hechos_no_lista`. Falta de `hechos` o lista vacía siguen siendo `crudos=0` sin descartes.
  - `_motivo_de_descarte` sigue el mismo orden que `_validar`, y una prueba comprueba que dicen lo mismo con nueve entradas.
  - Nunca va el valor de la operación ni texto del modelo. El `stop_reason` es el del API, no texto del modelo.
  - Comentario con D42 y H1c junto al log.
- **R10c (`core/memoria/servicio.py`):** la línea `memoria.guardar` termina en `chars=<len(texto)>`.
- **Pruebas** (cliente falso, 8 en `test_memoria_extractor.py` y 1 en `test_memoria_servicio.py`, todas con `h1c` en el nombre):
  - con `hechos: []`: `crudos=0 validados=0`;
  - con un hecho bueno y uno sin atributo: `crudos=2 validados=1 descartes=sin_atributo`;
  - las cuatro etiquetas, juntas en una sola llamada;
  - con `hechos` como string: sin excepción y `descartes=hechos_no_lista`;
  - con la marca `ZZEXTR` en el valor, la entidad, la operación, un crudo suelto, el texto y el catálogo, no aparece en ningún log;
  - `stop=max_tokens` sale tal cual;
  - `memoria.guardar` lleva `chars=40` y `chars=0` (con la marca `ZZTEXTO` fuera del log).

## Desviaciones

1. **Edité un fichero con Bash:** añadí las pruebas del extractor a `tests/test_memoria_extractor.py` con un `cat >>` en lugar de Edit/Write. Es la tercera vez, contra la memoria de Josem «Editar sin Bash». El resto de ediciones, con Edit. No se repetirá.

## Despliegue (de Josem)

`main` está en `1124aa3` y es ancestro de `fase-4`, así que el merge es un avance directo. Hash para volver atrás: `1124aa3`.

Merge y reinicio:

`cd /data/AssistantStudies && git merge --ff-only fase-4 && sudo systemctl restart sebastian.service`

Volver atrás, si hiciera falta:

`sudo systemctl stop sebastian.service && cd /data/AssistantStudies && git reset --hard 1124aa3 && sudo systemctl start sebastian.service`

Para ver el log después de repetir la petición (sin `sudo`):

`logcentral query --source sebastian --grep "Extractor: stop" --pretty`

Cuando Josem repita lo del id y el usuario, `crudos=0` dice que Haiku no devolvió nada; `crudos>0 validados=0 descartes=…` dice que lo tiró `_validar`. `chars=` en `memoria.guardar` dice si el planner mandó una frase vacía o muy corta.

## Decisiones que necesito

Ninguna. El paso 2 (catálogo real) queda en espera, como dices.
