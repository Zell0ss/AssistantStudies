# H1g — revisión (fase 4, D72): `/debug`

> Responde a: 456918f (H1g-informe). 2026-11-20, arquitecto. Revisado contra `4dfba4b..456918f` y la suite.

**Veredicto: aprobado. Josem lo despliega junto con H1f.**

- **R17:** se compara con `propietario_vault(config)`, y en producción ese valor resuelve al id de Josem (`cuaderno_chat_id`; lo he comprobado sin imprimirlo). La entrada se valida como pide el encargo. Si falla al activar, no deja nada a medias. Bien.
- **R18:**
  - el fichero se crea con `os.open(…, 0o600)`;
  - el directorio, con 0700 y `chmod` si ya existía;
  - la traza no pasa por loguru;
  - la prueba con `capfd` comprueba que `ZZDEBUG` no sale por stderr.

  La comprobación de `vector.toml` (ruta exacta) es un buen añadido. Bien.
- **R19:** el id de turno solo existe con la traza activa, y sin ella las llamadas son idénticas a las de antes. Lo prueba `assert_called_once_with`. Bien.
- **R20:** se aplica solo a `debug-*.jsonl` y nunca lanza. Bien.
- **Tu desviación 1** (el tope de 12000 para el resumen de Alfred): la acepto.
- **Suite:** la he ejecutado yo: **1186 pasan**.
- **Gasto:** 0 $.

## Tus decisiones

1. **Los dos logs con contenido de `handle_text`: sí, se arreglan.** Es una fuga de D42 que tenía que haber visto yo. Va en H1h, R21:
   - `Processing text from …` sin el texto: `chars=` en lugar de los 50 primeros;
   - `Orchestrator response` sin el texto: solo la longitud;
   - **y una prueba con marca** de que el texto no sale.
2. **`limpiar()` periódico: sí.** También en H1h, R22: un `limpiar()` en la tarea del planificador, una vez por hora, y otro al caducar o apagar. Así, «24 h» quiere decir 24 h.

Las dos cosas son pequeñas y sin API. No bloquean este despliegue.

## Para el programador

Responde a: 456918f (H1g-informe)

1. Haz H1h, R21 y R22, con sus pruebas (una prueba con marca para R21; reloj falso para R22).
2. Pasa la suite.
3. Escribe un anexo corto al final de `H1g-informe.md`, con las órdenes de despliegue, y para.

Sin gasto.
