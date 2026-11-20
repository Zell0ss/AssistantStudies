# H1b — revisión (fase 4, parche D68): Alfred no se corta

> Responde a: f22cf41 (H1b-informe). 2026-11-20, arquitecto. Revisado contra `5421eb1..2f10d30` y la suite.

**Veredicto: aprobado con un retoque (R9).** El riesgo de Telegram que señalas es real, y lo introduce este mismo parche, así que no se despliega sin él.

## 1. Contra el código

- **R6:** las constantes están junto a las de D28, con el comentario de D68.
- **R7:** `_recortar_corte` hace lo que pide el encargo y conserva el signo de fin de frase. El log no lleva texto, solo techo, usuario y longitud. Bien.
- **R8:** `_texto_de_alfred` busca el primer bloque con `text`, así que un `thinking` o un `tool_use` delante no lo rompen. Sacar `_MSG_ERROR_SERVICIO` a una constante, sin cambiar el texto, está bien.
- **Pruebas:** las 6 del encargo y los bordes. La 2 pasa por `handle()`, que es donde importa.
- **Suite:** la he ejecutado yo: **1100 pasan**.
- **Gasto:** 0 $.

## 2. Tu decisión 1: el límite de Telegram

El hueco es mío. Subí el techo a 1500 tokens sin mirar el otro extremo: un mensaje de Telegram admite 4096 caracteres, y `_send_markdown` (`bot/handlers.py:23`) manda el texto entero. Sin el parche, lo largo llegaba cortado; con el parche, podría no llegar. Es poco probable, pero sería peor que lo de antes. **Se arregla ahora.**

## 3. Retoque

- **R9 — `_send_markdown` parte los mensajes largos (D68):**
  - Si el texto pasa de 4000 caracteres, se divide **antes** de `parse_markdown_to_entities`, porque los offsets de las entidades son por trozo.
  - Se corta por saltos de línea, en trozos de como mucho 4000 caracteres. Una línea suelta de más de 4000 se corta a la fuerza en 4000.
  - Cada trozo se parsea y se envía por separado, en orden.
  - Un texto de 4000 caracteres o menos sale exactamente igual que hoy, en una sola llamada.
  - **Pruebas (bot falso):**
    - con 9000 caracteres en líneas de 100, salen 3 llamadas, ninguna de más de 4000 caracteres, y al unirlas está todo el texto en orden;
    - un `**negrita**` en el segundo trozo lleva su entidad con el offset relativo a ese trozo;
    - una línea sola de 5000 caracteres se manda en 2 llamadas;
    - un texto corto sale en 1 llamada, igual que hoy.
- **Las vigilancias no se tocan:** `armar_mensaje` ya recorta a 4000 por anuncios enteros y manda con `send_message`, no con `_send_markdown`.

## Para el programador

Responde a: f22cf41 (H1b-informe)

1. Haz R9 con sus pruebas. Cita D68 en un comentario.
2. Pasa la suite.
3. Escribe un anexo corto al final de `H1b-informe.md` y para.

Sin gasto. Si R9 queda como está aquí, Josem despliega H1 y H1b juntos con la sección «Fase 4» de `PASOS-CON-SUDO.md`.

## 4. Revisión del anexo (2026-11-20)

> Responde a: 2472db5 (H1b-informe, anexo R9). Revisado contra `189e40d..ad369f8`.

**Veredicto: aprobado.** H1 y H1b quedan listos para que Josem los despliegue juntos.

- **R9:** se parte antes de parsear y cada trozo lleva sus propias entidades. Un texto que cabe sale en una llamada, igual que antes. Las pruebas cubren los bordes de 4000 y 4001.
- **Acepto los dos límites que señalas:** una negrita que cruce el corte, y que la cuenta sea en caracteres y no en UTF-16. Hay holgura de 96, y Alfred no escribe textos llenos de emojis.
- **Hallazgo menor (implementación), no bloquea:** si una línea en blanco va justo antes de una línea que no cabe, el trozo `"\n"` se queda en `""` y Telegram rechaza un mensaje vacío. Hacen falta una línea en blanco y luego más de 3999 caracteres sin salto, que Alfred no produce. Va a la próxima vez que se toque: descartar los trozos vacíos.
- **Suite:** la he ejecutado yo: **1107 pasan**.
- **Gasto:** 0 $.

## Para el programador

Responde a: 2472db5 (H1b-informe, anexo)

H1b aprobado. No queda nada más: para hasta que te escriba (H2, después del despliegue y de unos días de uso).
