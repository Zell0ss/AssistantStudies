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
