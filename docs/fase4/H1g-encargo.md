# H1g — encargo (fase 4): modo depuración temporal, `/debug`

> Responde a: c13e0dc (H1f-informe). 2026-11-20, arquitecto. Decisión: **D72** (ADR-MEMORIA §4, tentativa). Josem lo aprueba («Sip!»). Sin API.

## 1. Por qué

Hoy hemos diagnosticado a ciegas tres fallos de la memoria: H1c, H1d y H1f. D42 deja el log sin lo que dijo el planner, y eso está bien de forma permanente. D72 abre una excepción acotada: una traza con contenido, solo para Josem, temporal y local.

## 2. Requisitos (D72)

- **R17 — el comando** (`bot/handlers.py`):
  - **`/debug [min]`:**
    - por defecto, 30 minutos; como mucho, 120;
    - un valor que no sea un número o que valga menos de 1 da un mensaje de uso y no activa nada.
  - **`/debug off`** lo apaga.
  - **Solo para el propietario del vault** (`propietario_vault(config)`).
    - Si lo pide otro usuario: «Este comando no está disponible», y nada más.
    - Ni el log ni la respuesta dicen por qué.
  - **Las respuestas:**
    - al activar: «Depuración activa hasta las HH:MM. Traza en `<ruta>`»;
    - al apagar: «Depuración apagada».
  - **El estado vive en memoria del proceso:** `{user_id: caduca_en}`. Un reinicio lo apaga, y está bien que sea así.
  - **El comando sale en `/ayuda`.**
- **R18 — la traza** (módulo nuevo, por ejemplo `core/depuracion.py`):
  - **Ruta:** `<logfolder>/debug/debug-<user>-<AAAAMMDD>.jsonl`.
    - El directorio se crea con 0700 y cada fichero con 0600 (`os.open` con modo; no basta con `chmod` después).
  - **Sin loguru y sin `get_logger`:**
    - se escribe a mano, JSON por línea, `{ts, turno, etapa, datos}`;
    - el motivo: loguru también escribe en stderr, que acaba en journald, y LogCentral lee los ficheros de loguru.
  - **`activa(user_id) -> bool`:** mira la caducidad cada vez. Al caducar, se escribe una sola vez en LogCentral «Depuración desactivada (caducó) | user=…».
  - **A LogCentral solo van** «Depuración activada | user=… | minutos=N» y «Depuración desactivada (off|caducó) | user=…». Nunca contenido.
- **R19 — qué se traza.** Solo si `activa(user_id)` y solo los turnos de ese usuario:
  - **mensaje:** el texto del usuario;
  - **planner:** en cada iteración, `stop_reason`, cada `tool_use` con su `name` e `input`, y el texto si lo hay;
  - **tools:** el resultado de cada una, recortado a 4000 caracteres con una marca de recorte;
  - **extractor:** el `texto` que recibe, la longitud del catálogo (no el catálogo) y `bloque.input` crudo;
  - **memoria (consulta):** los parámetros y la salida;
  - **Alfred:** el `tool_results_summary` que recibe, la `nota_planner`, el `stop_reason` y el texto final.

  Que pase por el contexto del turno lo que ya existe (`user_id` en el orquestador y en el servicio). Nada de variables globales nuevas aparte del estado de R17.
- **R20 — limpieza:**
  - al arrancar y al activar, se borran los `debug-*.jsonl` con más de 24 h de antigüedad (por `mtime`);
  - se registra cuántos se han borrado, sin rutas de contenido.
- **Cita D72 en un comentario** en cada costura.

## 3. Pruebas (sin API, datos inventados)

1. Otro usuario: `/debug` no activa nada y contesta «no disponible».
2. `/debug 30` activa la traza y `/debug off` la apaga. `/debug 500` se queda en 120 y `/debug abc` da el mensaje de uso.
3. **Caducidad:** con un reloj falso, al pasar la hora `activa` da `False`, y «caducó» se escribe una sola vez.
4. **Con la traza activa,** un turno completo con clientes falsos (planner → `mark_as_memorable` → extractor → Alfred) deja en el fichero todas las etapas de R19. Con una marca `ZZDEBUG` en el mensaje:
   - **está en el fichero;**
   - **no está** en ningún log de loguru ni en stderr.
5. **Sin la traza activa:** no se crea ningún fichero, y el turno sale igual que hoy.
6. **Solo el usuario activado:** con la traza activa para A, un turno de B no escribe nada.
7. **Permisos:** el directorio es 0700 y el fichero 0600.
8. **Limpieza:** un fichero con `mtime` de hace 25 h se borra y uno de hace 1 h se queda.
9. **Un fallo al escribir** la traza (disco lleno, permisos) no rompe el turno: un `WARNING` sin contenido.
10. **La suite** pasa sin tocar sus esperados.

## 4. Lista previa (§4)

- **¿Borra o sobrescribe datos?** Solo sus propios ficheros de traza, a las 24 h.
- **¿Llama a una API externa?** No.
- **¿Toca producción?** Solo al desplegar, con merge y reinicio, que hace Josem.
- **Privacidad:** el contenido se queda en seb01, en un fichero que solo puede leer el usuario `ubuntu`, y como mucho 24 h. Nada va a LogCentral ni a journald.

## Para el programador

Responde a: c13e0dc (H1f-informe)

1. Haz R17–R20 con las pruebas del §3.
2. Pasa la suite.
3. Escribe `docs/fase4/H1g-informe.md`, corto, con:
   - las órdenes de despliegue;
   - cómo leer la traza (`jq` o `less`, sin sudo).
4. Para.

Sin gasto.
