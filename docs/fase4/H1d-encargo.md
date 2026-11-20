# H1d — encargo (fase 4, parche D69): un dato no sustituye a otro de la misma frase

> Responde a: e77a764 (H1c-informe, anexo). 2026-11-20, arquitecto. Decisión: **D69** (ADR-MEMORIA §4, tentativa). Sin API.

## 1. Qué pasó en producción (20/11, 14:10 UTC)

Con el log de H1c ya desplegado, Josem repitió: «Recuerda que en Telegram mi id es <número> y mi usuario es @<usuario>».

- **El extractor sacó bien los dos hechos:** `crudos=2 validados=2`. El fallo de las tres veces anteriores (`hechos=0`) no se repitió. Sigue sin explicar, y el log de R10b lo verá si vuelve.
- **`mem_decisiones` 19–24**, sacado por Josem con un `SELECT` sin valores:
  - 20 `crear_atributo` `atributo=14` (`telegram_id`, numero, uno);
  - 21 `anadir` en el 14;
  - 23 `reutilizar_atributo` `atributo=14` `via=semantica` `puntuacion=0.866` `margen=0.359` `fuerte=true`;
  - 24 `sustituir` en el 14, `regla=uno_distinto_fuerte`.
- **El usuario sustituyó al id, y el id se perdió.** Alfred lo contó bien.

La causa es la escalera de D35. El segundo hecho traía otro nombre de atributo. No coincidía por alias, y la búsqueda semántica encontró `telegram_id`, recién indexado en ese mismo turno, por encima de los umbrales.

## 2. Requisitos (D69)

- **R11 — lo creado en esta llamada no es candidato semántico.**
  - En `ServicioMemoria.guardar`, el `turno` lleva los ids de los atributos creados en esta llamada.
  - `_resolver_atributo` los quita de los candidatos **semánticos**.
  - Por **alias exacto** sí se reutilizan: si el extractor repite el mismo nombre, es el mismo atributo.
- **R12 — un `tipo_valor` distinto hace débil la resolución semántica.**
  - Junto a `tipos_entidad`, `_resolver_atributo` añade a cada candidato su `tipo_valor`.
  - `resolver_atributo` recibe el `tipo_valor` del hecho. Si es distinto del del candidato, `fuerte=False`, igual que con un `tipos_entidad` incompatible.
  - Con eso, `decidir_hecho` ya manda a `nota` en lugar de sustituir. No hace falta cambiar nada más.
  - Por alias no se toca.
- **Cita D69 en un comentario,** en cada una de las dos costuras.

## 3. Pruebas (sin API, catálogo y embedder falsos; datos inventados)

1. **El caso de producción.** Una llamada con dos hechos de `yo`: `id_telegram=700111222` (numero) y `usuario_telegram=@usuario_prueba` (texto). La búsqueda semántica falsa devuelve el primer atributo con 0,87 y margen 0,36. Resultado esperado:
   - 2 atributos creados y 2 `anadir`;
   - ningún `sustituir`;
   - los dos valores vigentes.
2. **Mismo nombre en la misma llamada:** se reutiliza por alias, como hoy.
3. **R12 entre turnos:** un atributo numero con un valor vigente y un hecho texto que llega por semántica fuerte. Resultado: `nota`, y el valor anterior sigue vigente.
4. **Control:** el mismo `tipo_valor` por semántica fuerte sigue sustituyendo, como hoy.
5. **La suite de memoria** pasa sin tocar sus esperados. Si alguno cambia, dilo en el informe con el motivo.

## 4. Lista previa (§4)

- **¿Borra o sobrescribe datos?** No. Al contrario: evita una sustitución mala. No hay migración.
- **¿Llama a una API externa?** No.
- **¿Toca producción?** Solo al desplegar, con merge y reinicio, que hace Josem.

## Para el programador

Responde a: e77a764 (H1c-informe, anexo)

1. Haz R11 y R12 con las pruebas del §3.
2. Pasa la suite.
3. Escribe `docs/fase4/H1d-informe.md`, corto, con las órdenes de despliegue (merge y reinicio, en una línea), y para.

Sin gasto.
