# H1e — encargo (fase 4, parche D70): el valor tiene que encajar con el tipo del atributo

> Responde a: H1d-informe (390b89c). 2026-11-20, arquitecto. Decisión: **D70** (ADR-MEMORIA §4, tentativa). Sin API.

## 1. Qué pasó en producción, con H1d ya desplegado (14:18–14:19 UTC)

1. «Corrige: mi id de Telegram es <número>». Resultado: `crudos=1 validados=1 guardados=1`. Corregido bien.
2. «Mi usuario de Telegram es @<usuario>». Resultado: `crudos=1 validados=1 guardados=1 notas=0`. El usuario **volvió a sustituir el id**.

Con `notas=0`, no entró por semántica: si hubiera entrado, R12 la habría dejado débil y habría ido a `nota`.

**Lo probable es que entrara por alias.** El extractor escribió `telegram_id`, que es el nombre exacto del catálogo. Es lo que le manda su regla 1, y el catálogo no le enseña el tipo. **El hueco es mío:** en D69 dejé el alias fuera de R12.

## 2. Requisito (D70)

- **R13 — el valor encaja con el tipo del atributo**, por alias y por semántica.
  - Una función pura en `resolucion.py`, `valor_encaja(valor, tipo_valor) -> bool`:
    - `numero`: empieza por una cifra, con signo opcional, y admite decimales con `,` o `.` y una unidad detrás. Patrón orientativo: `^[+-]?\d[\d.,]*(\s*\S.*)?$`.
    - `fecha`: `AAAA-MM-DD` o `--MM-DD`.
    - `booleano`: sí, si, no, true, false, verdadero o falso, sin distinguir mayúsculas.
    - `texto`: cualquier valor.
  - **Dónde se aplica:** en `_procesar`, después de resolver el atributo (ya existente, no creado) y antes de `decidir_hecho`.
  - **Qué hace:** si el atributo reutilizado no acepta el valor, la resolución pasa a **débil**. El resto lo hace la escalera: con un valor vigente va a `nota`, y sin vigente se añade como hoy.
  - **`retirar` no se toca:** su valor puede ir vacío.
  - **Registro:** la decisión lleva en `senales` `"tipo_no_encaja": true`. No lleva el valor (D42).
  - **Cita D70 en un comentario.**
- **Retoques pendientes de H1d, aquí mismo:**
  - R12 no se aplica a `retirar`;
  - descartar los trozos vacíos en `_partir_en_trozos` (H1b §4);
  - el espacio que falta en `atributo =self._repo…`.

## 3. Pruebas (sin API, datos inventados)

1. **El caso de producción, por alias:** `telegram_id` (numero, uno) con `700111222` vigente, y un hecho `telegram_id = @usuario_prueba` que llega por alias. Resultado esperado:
   - `nota`;
   - el id sigue vigente;
   - `tipo_no_encaja` en las señales.
2. **Corrección legítima por alias:** `telegram_id = 700999888` sustituye al anterior, como hoy.
3. **`valor_encaja`, tabla de casos:**
   - `numero`: `2,4 bar` sí, `-3.5` sí, `815566372` sí, `@usuario` no, `unos 30` no;
   - `fecha`: `--03-12` sí, `12 de marzo` no;
   - `booleano`: `sí` sí, `quizá` no;
   - `texto`: cualquier valor sí.
4. **Sin valor vigente y sin encaje:** el hecho se añade, igual que hoy. Es débil, pero no pisa nada.
5. **`retirar`** por alias con valor vacío sigue funcionando. También con R12 por semántica, que ya no le afecta.
6. **`_partir_en_trozos`** no devuelve trozos vacíos.
7. **La suite de memoria** pasa sin tocar sus esperados. Si alguno cambia, dilo con el motivo.

## 4. Lista previa (§4)

- **¿Borra o sobrescribe datos?** No. Evita una sustitución mala. No hay migración.
- **¿Llama a una API externa?** No.
- **¿Toca producción?** Solo al desplegar, con merge y reinicio, que hace Josem.

## Para el programador

Responde a: H1d-informe (390b89c)

1. Haz R13 y los tres retoques pendientes, con las pruebas del §3.
2. Pasa la suite.
3. Escribe `docs/fase4/H1e-informe.md`, corto, con las órdenes de despliegue, y para.

Sin gasto.
