# H1c — encargo (fase 4, diagnóstico): la memoria no guarda un identificador

> Responde a: 2472db5 (H1b-informe, anexo). 2026-11-20, arquitecto. Josem autoriza **≤ 0,05 $** de API (Haiku 4.5).
> Primero el diagnóstico; el arreglo, después de mi revisión.

## 1. Qué pasa en producción (20/11, tras desplegar H1 + H1b)

Josem pidió tres veces que se guardara su id y su usuario de Telegram. La última vez lo dijo como dato: «Recuerda que en Telegram mi id es <número> y mi usuario es @<usuario>».

- **Las tres veces el planner llamó a `mark_as_memorable`**, y el servicio registró `hechos=0 guardados=0 notas=0 sin_cambio=0` (13:35:34, 13:38:58 y 13:41:44 UTC).
- **El extractor devolvió una lista vacía.** No hubo excepción ni aviso: el aviso «la respuesta no trae la tool» no aparece.
- **Alfred se inventó la causa:** primero «no hay categorías», después «apúntelo en el vault bajo /whoami». Eso no se toca aquí: va a la fase 5.

El texto no está en ningún log (D42), así que hay que reproducirlo.

## 2. Hipótesis

- **(A) El planner pierde el dato.** La frase `texto` que le pasa al extractor ya no lleva el id ni el usuario.
- **(B) El extractor no guarda identificadores.** Haiku trata un número de cuenta o un @usuario como algo que no se guarda y devuelve `hechos: []`. Si es así, tampoco guardaría matrículas, números de socio ni cosas parecidas.
- **(C) Otra causa.** Si no es ninguna de las dos, dila con lo que veas.

Ya descartado (sin API): la regla 5 del prompt («órdenes operativas»). La tercera frase era un dato puro y también dio 0.

## 3. Qué hacer

Todos los datos tienen que ser **inventados**: ids, usuarios, matrículas y números de socio. Usa la BD de desarrollo, o un catálogo inventado con la forma del real: la entidad `yo` con `es_usuario` y unos cuantos atributos.

1. **Planner, 2 llamadas.** Lanza el planner real (prompt y tools de producción) con «Recuerda que en Telegram mi id es 700111222 y mi usuario es @usuario_prueba». Apunta el `texto` que manda a `mark_as_memorable`.
2. **Extractor, como mucho 10 llamadas,** con el prompt y la tool reales:
   - el `texto` del paso 1, tal cual;
   - «Mi id de Telegram es 700111222»;
   - «Mi usuario de Telegram es @usuario_prueba»;
   - «La matrícula de mi coche es 1234 ABC»;
   - «Mi número de socio del gimnasio es 55821»;
   - y, como control, «Mi color favorito es el verde», que tiene que dar 1 hecho.

   Cada caso, 1 o 2 pasadas. Guarda la entrada de la tool tal como llega (`bloque.input`), sin validar: así se ve si Haiku no devuelve nada o si lo descarta `_validar`.
3. **Para** si el gasto llega a 0,05 $.

Esto es un script de diagnóstico en `scripts/` o en `experiments/`. No cambia el código de producto.

## 4. Lista previa (§4)

- **¿Borra o sobrescribe datos?** No. Solo se usa la BD de desarrollo, o ninguna.
- **¿Llama a una API externa?** Sí: Haiku 4.5, como mucho 12 llamadas, ≤ 0,05 $ (autorizado por Josem). Precio según la skill `claude-api`: 1 $ / 5 $ por MTok.
- **¿Toca producción?** No.

## Para el programador

Responde a: 2472db5 (H1b-informe, anexo)

1. Haz el §3, dentro del tope de 0,05 $.
2. Escribe `docs/fase4/H1c-informe.md`, corto:
   - qué hipótesis se confirma, con las entradas y salidas de cada caso (son datos inventados, así que pueden ir en el informe);
   - el gasto real;
   - el arreglo que propones, sin aplicarlo.
3. Para.
