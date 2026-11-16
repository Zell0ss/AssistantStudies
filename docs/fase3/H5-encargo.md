# H5 — encargo (fase 3, parche): el calendario no puede leer el mes que viene

> Responde a: 99cd0e5 (H4-revision). 2026-11-16, arquitecto. **Urgente: Josem lo quiere ya.**
> Producción va con la fase 3 desde hoy (`main` = `fase-3` = `eeee134`).

## 1. Qué pasó en producción

Josem preguntó por Telegram «¿Cómo se presenta el mes de diciembre?». El planner llamó dos veces a
`calendar_list_events`, con 4 y con 2 resultados, todos de noviembre. Alfred contestó «diciembre no
me aparece con nada anotado» y se ofreció a **crear** la colonoscopia y sus pasos. Ya existen:
evento 4946 y 8 compromisos.

**Causa (arquitecto, leído en el código):**
- El esquema de `calendar_list_events` solo deja usar `today`, `tomorrow`, `week`, `month` (el mes
  en curso, desde hoy) y `weekend`. **No hay forma de pedir otro mes**, aunque
  `_time_window_to_range` ya admite `YYYY-MM`.
- **Fallo hermano:** `weekend` está en la lista, pero `_time_window_to_range` no lo trata y cae en
  el `return today, today` final. Lo mismo le pasa a cualquier valor desconocido, que en silencio
  se lee como «hoy».

## 2. Qué hacer

- **R14. `time_window` admite otro mes.**
  - Valores nuevos: `next_month` (el mes siguiente entero) y `YYYY-MM` (un mes concreto, entero).
  - Si el JSON Schema no deja combinar `enum` y `pattern`, quita el `enum` y escribe los valores
    válidos en la descripción. El ejecutor valida el valor.
  - **Descripción de la tool:**
    - Para «el mes que viene», `next_month`; para un mes con nombre («diciembre», «en enero»),
      `YYYY-MM`, con el año que toque desde hoy.
    - Una línea por D55: «Lo que el usuario tiene que hacer (pasos, preparaciones) no está aquí:
      está en `compromisos_listar`».
- **R15. `weekend` funciona:** el próximo sábado y domingo. Si hoy es sábado, hoy y mañana; si es
  domingo, solo hoy. Pon esa regla en el docstring.
- **R16. Un valor desconocido no se lee como hoy.** La tool devuelve un error claro con los valores
  válidos, y el ejecutor no lanza una excepción.
- **Pruebas sin API**, con `hoy` fijado:
  - `next_month` desde el 2026-11-16 da del 1 al 31 de diciembre.
  - `next_month` desde el 2026-12-20 da enero de 2027.
  - `2026-12`.
  - `weekend` desde un miércoles, desde un sábado y desde un domingo.
  - Un valor desconocido devuelve error.
  - El esquema y la descripción nombran `next_month`, `YYYY-MM` y `compromisos_listar`.
  - Un evento recurrente sale en `next_month`, igual que en `month`.

## 3. Goldens (míos; cópialos tal cual)

```yaml
- id: 77
  phrase: "¿Cómo se presenta el mes de diciembre?"
  mode: any_of
  expected:
    - [calendar_list_events]
    - [calendar_list_events, compromisos_listar]
    - [compromisos_listar, calendar_list_events]
  validates: "Fase 3 H5 (R14): un mes con nombre se lee entero; lo que hay que hacer, en compromisos"

- id: 78
  phrase: "¿Qué tengo el mes que viene?"
  mode: any_of
  expected:
    - [calendar_list_events]
    - [calendar_list_events, compromisos_listar]
    - [compromisos_listar, calendar_list_events]
  validates: "Fase 3 H5 (R14): «el mes que viene» es next_month"
```

Los goldens solo comparan nombres de tools. En la salida de #77 y #78 apunta también el
`time_window` que se usó, sin que la prueba falle por eso: es lo que de verdad comprueba R14.

## 4. [API], con el «sí» de Josem en tu ventana

Quedan ≈ 0,41 $ de los 10 $.

1. #77 y #78 ×3 (≈ 0,1 $).
2. Los goldens de calendario que pasan por `calendar_list_events`: elígelos con `grep` y di
   cuáles son (≈ 0,15–0,25 $).

Si algo antiguo cae, para y cuéntalo.

## 5. Despliegue

No hay migración. Después de mi revisión, Josem hace:
1. `git merge --ff-only fase-3` en `/data/AssistantStudies`.
2. `sudo systemctl restart sebastian.service`.
3. `comprobar_fase3.sh`.

Los compromisos y la cita no cambian. Añade esos tres pasos al informe, listos para copiar.

## Para el programador

Responde a: 99cd0e5 (H4-revision)

Parche urgente **H5**:
1. R14–R16 de §2, con sus pruebas sin API, y los goldens de §3 tal cual.
2. [API] según §4, cada paso con el «sí» de Josem.
3. **No** fusiones ni reinicies.
4. **Para** con `docs/fase3/H5-informe.md`, con los pasos de despliegue de §5.
