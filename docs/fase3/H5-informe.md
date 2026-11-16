# H5 — informe (fase 3, parche): el calendario lee el mes que viene

> Responde a: 203eb69 (H5-encargo). Programador, 2026-11-16. Rama `fase-3`, commit `46712d5`. Sin migración. No he fusionado,
> reiniciado ni tocado producción. `main` está en `eeee134`, antecesor de `fase-3`: el `ff-only` es posible.

## Hecho

- **R14 — `next_month` y `YYYY-MM`.** `next_month` es el mes siguiente entero (desde diciembre pasa a enero del año siguiente; febrero de
  28 o 29 días). `YYYY-MM` es ese mes entero, validado con `\d{4}-(0[1-9]|1[0-2])`. `month` sigue siendo lo que queda del mes en curso,
  desde hoy.
  - **Esquema:** JSON Schema no deja combinar `enum` con un patrón: quité el `enum`, los valores válidos van en la descripción del
    parámetro y valida el ejecutor.
  - **Descripción de la tool:** «Para "el mes que viene", `next_month`; para un mes con nombre ("diciembre", "en enero"), `YYYY-MM`, con el
    año que toque desde hoy…» y la línea de D55: «Lo que el usuario tiene que hacer (pasos, preparaciones) no está aquí: está en
    `compromisos_listar`».
- **R15 — `weekend`:** el próximo sábado y domingo. Si hoy es sábado, hoy y mañana; si es domingo, solo hoy. La regla está en el docstring
  de `_time_window_to_range`.
- **R16 — un valor desconocido ya no se lee como «hoy».** `_time_window_to_range` lanza `ValueError` con los valores válidos; el ejecutor
  lo recoge y devuelve `{"status": "invalid", "message": …}` (también si falta `time_window`). No lanza excepción.
- **Pruebas sin API:** `tests/test_calendar_ventanas.py` (28), con `hoy` fijado: `next_month` desde el 2026-11-16 (1–31/12) y desde el
  2026-12-20 (enero de 2027) y los bordes de febrero; `2026-12`; `weekend` desde miércoles, lunes, viernes, sábado y domingo (y que lista
  los eventos del fin de semana y no los de hoy); nueve valores mal escritos (`2026-13`, `diciembre`…) dan error; el error y el ejecutor
  nombran los valores válidos; el esquema y la descripción nombran `next_month`, `YYYY-MM` y `compromisos_listar`; un evento recurrente
  sale en `next_month` igual que en `month`. Las vi fallar antes de escribir el código (21 en rojo). **880 pasan** en total.
- **Goldens #77 y #78** copiados tal cual (`tests/test_golden_estado.py` comprueba que son los del encargo). El informe de la pasada
  imprime ahora el **`time_window`** de cada `calendar_list_events` (`response["ventanas"]`, solo en el test; no cambia el resultado).

## Resultados [API] y gasto

| Paso | Resultado | Coste |
|---|---|---|
| #77 y #78 ×3 | #78 **3 de 3** (`next_month`). #77 **2 de 3** (`2026-12` las dos veces que pasa) | 0,1901 $ |
| #7, #9, #50, #70 (los que pasan por `calendar_list_events` o su familia, una vez) | **4 de 4**; #7 `today`, #50 `tomorrow` | 0,1165 $ |
| **Total H5** | | **0,3066 $** |

**Gasto de la fase 3: ≈ 9,90 $ de 10 $** (≈ 9,59 $ antes de H5). Quedan **≈ 0,10 $**.
Autorizado por Josem en mi ventana: ya tenía el tope de 10 $ (H3d) y dio el «Si» a los dos pasos tras pedírselos por separado (2026-11-16).
Elegí los antiguos con un recorrido de `goldens.yaml` buscando `calendar_list_events` en las listas esperadas: #7, #9, #50, #70, más #77 y #78.

**El rojo de #77 (1 de 3), en la ejecución 1:** el planner **no llamó al calendario: llamó dos veces a `weather_forecast`** (`time_window: week`)
y Alfred contestó «mis datos solo alcanzan hasta el 22 de noviembre; diciembre queda fuera de la previsión». «¿Cómo se presenta el mes de
diciembre?» se lee, a veces, como una pregunta por el tiempo. Es el mismo modo de fallo que la frase de producción, con otra
herramienta equivocada (allí fue el calendario con el mes malo). No es una regresión de R14: en las dos ejecuciones que van al calendario,
`time_window` es `2026-12`. **No he hecho otra vuelta de prompts** (no me quedan [API] y la revisión no la pide).

## Desviaciones

- Los goldens antiguos elegidos son cuatro; no hay más de la familia del calendario que pasen por `calendar_list_events`. No he lanzado la
  pasada completa (no cabía: ≈ 2,2 $).
- #77 no sale 3/3. Lo cuento arriba; no cambia ninguna lista del encargo.

## Decisiones que necesito

1. **#77 (1 de 3, pregunta por el tiempo):** ¿lo aceptas como riesgo, o quieres una frase en la descripción de `weather_forecast` («no sirve
   para preguntar por un mes: la previsión llega a 7 días; un mes con nombre es del calendario»)? Costaría otra [API] (≈ 0,1 $) y ya solo
   quedan ≈ 0,10 $: haría falta que Josem suba el tope. Mi recomendación: aceptarlo. Cuando falla, Alfred lo dice claro («diciembre queda fuera
   de la previsión») y no crea nada.
2. **Despliegue** (de Josem, tras tu revisión; no hay migración, y los compromisos y la cita no cambian):

   ```bash
   cd /data/AssistantStudies && git status        # debe estar limpio y en main
   git rev-parse HEAD                              # APUNTA este hash: es la vuelta atrás (hoy eeee134)
   git merge --ff-only fase-3
   sudo systemctl restart sebastian.service
   bash /data/AssistantStudies/sebastian2/deploy/comprobar_fase3.sh      # debe terminar con «Todo bien.»
   ```

   Vuelta atrás: `sudo systemctl stop sebastian.service; cd /data/AssistantStudies && git reset --hard <el hash apuntado>; sudo systemctl start
   sebastian.service`. Después, por Telegram: «¿Cómo se presenta el mes de diciembre?» y «¿Qué tengo el mes que viene?» tienen que traer la
   endoscopia del 17/12 (ya existe: evento 4946, con sus compromisos) **sin ofrecerse a crearla**.
