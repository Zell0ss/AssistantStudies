# H1b — Informe del programador (fase 4, parche D68): Alfred no se corta a media frase

Responde a: `b9c9d7c` (H1b-encargo, `5421eb1`).
Commit en `fase-4`: `202fb56`. Suite completa: **1100 pruebas** pasan (1090 + 10), sin API.

## Hecho

Todo en `core/orchestrator.py`, con D68 citado en un comentario junto a las constantes.

- **R6 (techo):** constantes `_ALFRED_MAX_TOKENS = 1500` y `_ASK_MAX_TOKENS = 300`, en lugar de 400 y 100. El «concisa» del prompt no se toca.
- **R7 (corte):** con `stop_reason == "max_tokens"` hay:
  - un log `WARNING` sin texto: `Alfred cortado por max_tokens (<techo>) | user=… | chars=<n>`;
  - un recorte (`_recortar_corte`) en el último salto de línea, o, sin ninguno, en el último «. », «? » o «! » conservando el signo, o, sin ninguno, tal cual;
  - una línea aparte con «(Me he quedado sin espacio, señor. Dígame si quiere el resto.)».
- **R7 también en `_ask_user`:** los dos sitios pasan por la misma función, `_texto_de_alfred`.
- **R8 (sin texto):** si la respuesta no trae ningún bloque con texto, no hay `IndexError`. Se devuelve el mensaje que ya existía para un error del servicio de IA, y un `WARNING` con el `stop_reason`: `Alfred sin texto en la respuesta (stop_reason=…) | user=…`.
  - El mensaje está ahora en la constante `_MSG_ERROR_SERVICIO`. Su texto no cambia, y la rama de `APIError` de `handle()` usa la misma constante.
  - Se busca el primer bloque cuyo `text` es una cadena, así que un bloque de `thinking` o de `tool_use` delante no rompe nada.

**Pruebas** (las 6 del §3, con cliente falso; 10 en total, todas con `d68` en el nombre):

1. `max_tokens` de la síntesis = 1500 y de `_ask_user` = 300.
2. El inventario cortado («…• Tres — guardada en el vault de») acaba en «• Dos — b.» y luego la línea del aviso. Se comprueba pasando por `handle()`.
3. Sin saltos de línea se corta tras «Primera frase.». Además se prueba el signo conservado, el último de los tres fines de frase, el texto sin ninguno y el texto vacío. También se prueba en `_ask_user`.
4. Con `end_turn`, el texto sale exactamente igual que hoy.
5. Con una marca `ZZALFRED` en la respuesta, no aparece en ningún log, y el usuario sí la recibe. Los dos `WARNING` salen con su formato.
6. Con la lista de bloques vacía, o con solo `tool_use` o `thinking`, no hay excepción y sale el mensaje de error.

## Gasto

0 $. Sin API.

## Desviaciones

Ninguna respecto al encargo.

## Decisiones que necesito

1. **Un riesgo que no estaba en el encargo: el límite de Telegram.** Un mensaje de Telegram admite 4096 caracteres, y 1500 tokens de español son del orden de 5000 a 6000. He mirado `bot/handlers.py` y `_send_markdown` manda el texto entero: no divide.
   - Con 1500 tokens, una respuesta larga de Alfred podría pasar de 4096 caracteres y Telegram la rechazaría.
   - **Probabilidad baja:** el prompt pide «concisa» y hoy ninguna respuesta se acerca. Antes del parche la respuesta salía cortada, y ahora podría no llegar.
   - **Propongo, si quieres cubrirlo,** un parche pequeño en `_send_markdown` que parta por saltos de línea en trozos de 4000 caracteres, con su prueba. No lo he hecho porque no está en el encargo. ¿Lo hago, o lo dejas como riesgo aceptado y miramos en el log si se da?
2. **Despliegue:** Josem despliega H1 y H1b juntos, cuando revises este informe.
