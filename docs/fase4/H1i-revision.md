# H1i — revisión (fase 4, parche D73)

> Responde a: 563370b (H1i-informe). 2026-11-20, arquitecto. Revisado contra `fd49190..563370b` y la suite.

**Veredicto: aprobado. Josem lo despliega.**

- **R23:**
  - solo actúa sin entidad ni atributo;
  - mira los hechos vigentes del usuario, sin `nota`;
  - compara el nombre de la entidad o sus alias, y las piezas del nombre del atributo;
  - el tope es de 20 y la señal solo aparece si hay coincidencias.

  `_terminos` es uno solo para R15, R23 y R24. Bien.
- **R24:** las palabras de la `query` se unen a las de la entidad y el atributo para buscar notas. Bien.
- **Prompt de Alfred y log:** los dos citan D73. Acepto el orden de `por_palabras` en el log.
- **Suite:** la he ejecutado yo: **1203 pasan**. `main` (`dc0ca28`) es ancestro de `fase-4`.
- **Gasto:** 0 $.
- **Tus límites:** los acepto. La próxima traza de `/debug` dirá si las palabras comunes meten ruido.

## Para el programador

Responde a: 563370b (H1i-informe)

H1i aprobado. Para hasta que te escriba.
