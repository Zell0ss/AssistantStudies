# H6 — encargo (fase 3): diagnóstico de «Recuérdame … a la una» sin tool

> Responde a: 12ec219 (H5-revision). 2026-11-16, arquitecto. **Solo diagnóstico, sin cambios de
> código.** Josem lo ha pedido ya.

## 1. Qué pasó en producción

Producción lleva H5 (`12ec219`). Josem mandó, sobre las 16:30, dos mensajes que terminaron en
`iterations=1`, sin ninguna tool. Alfred contestó, por D44, «no he podido programar ese
recordatorio»:

1. «Recuérdame está noche a la una de la madrugada que me duerma ya» (`está` con tilde, tal cual).
2. «Recuérdame mañana martes 17 de noviembre a la 01:00 que me duerma ya».

En el mismo rato funcionaron otros:
- «Recuérdame el 17 a la una de la madrugada que me duerma ya» llamó a `compromisos_crear`, pero
  con la fecha del **17/12**.
- Un `compromisos_borrar` que vino después también funcionó.

En los dos turnos se cargaron 6 intercambios de historial. Hablaban de la colonoscopia, de
diciembre y del recordatorio mal fechado.

## 2. Qué hacer ([API], con el «sí» de Josem; quedan ≈ 0,10 $)

Con el arnés de R10, que saca el texto del planner cuando cierra sin tool:

| Prueba | Veces |
|---|---|
| Frase 1, sin historial | ×2 |
| Frase 2, sin historial | ×2 |
| Frase 2 con un historial inventado parecido al de producción (§3) | ×2 |

Total: 6 ejecuciones, ≈ 0,1 $. Si el gasto amenaza con pasar de 0,10 $, quita la última fila y
dilo.

**Por cada ejecución, apunta:**
- las tools que se llamaron;
- el texto del planner si cerró sin tool;
- la respuesta de Alfred.

**No cambies código ni prompts.** Lo que haya que arreglar lo decido yo con los datos.

## 3. Historial inventado para la tercera prueba

Usa datos inventados, como siempre:

```yaml
historia:
  - {user: "¿Qué tengo el mes que viene?", bot: "En diciembre: la endoscopia del jueves 17 a las 9:30 y pilates martes y jueves a las 19:00."}
  - {user: "Recuérdame el 17 a la una de la madrugada que me duerma ya", bot: "Anotado, señor. Le aviso el jueves 17 a la 1:00."}
  - {user: "Borra el recordatorio «Duérmete ya» del 17 de diciembre", bot: "Borrado, señor."}
```

Siembra el evento «Endoscopia» del 2026-12-17 a las 09:30 con `estado:`.

## Para el programador

Responde a: 12ec219 (H5-revision)

**H6, diagnóstico:**
1. Haz las 6 ejecuciones de §2. Cada paso, con el «sí» de Josem en tu ventana.
2. Sin cambios de código.
3. **Para** con `docs/fase3/H6-informe.md`: tabla de resultados y textos del planner. Cuenta tu
   hipótesis, pero sin arreglar nada.
