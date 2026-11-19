"""H7 (R17-R19): el criterio de los goldens #79 y #80, que miran QUÉ se creó y no solo qué tools se llamaron.

Es una función pura (sin API) para poder probarla en `tests/test_golden_estado.py`. Los demás goldens siguen con
`_matches` de `test_goldens.py`.

Modos:
- `crea_con_fecha`: pasa si el turno fue exactamente `[compromisos_crear]`, algún compromiso creado trae la `entrada` del golden
  (por ejemplo `fecha_inicio` y `hora`) y la respuesta de Alfred menciona lo de `alfred_menciona`.
- `crea_con_fecha_o_pregunta`: lo mismo, o bien no crea nada y Alfred pregunta (R17: el texto del planner no se pierde).
  Falla si crea otra fecha, o si no crea nada y Alfred no pregunta (el «no he podido» de producción del 16/11, aunque
  acabe en «¿lo intento de nuevo?»).
- `calendario` (H9, #81-#85): mira la secuencia de tools, la fecha y hora de lo que se creó o movió en el calendario y lo que
  dice Alfred (`evaluar_calendario`).
"""

import re

MODOS = ("crea_con_fecha", "crea_con_fecha_o_pregunta", "calendario")


def _crea_lo_pedido(creaciones: list, entrada: dict) -> bool:
    items = [item for llamada in creaciones for item in llamada.get("items", [])]
    return bool(items) and all(all(str(item.get(k)) == str(v) for k, v in entrada.items()) for item in items)


def evaluar_compromiso(golden: dict, tools: list, creaciones: list, texto_alfred: str) -> bool:
    texto = texto_alfred or ""
    if tools == ["compromisos_crear"]:
        menciona = all(m in texto for m in golden.get("alfred_menciona", []))
        return _crea_lo_pedido(creaciones, golden["entrada"]) and menciona
    if golden["mode"] == "crea_con_fecha_o_pregunta":
        # Una pregunta de verdad: «¿Lo quiere el 17 de noviembre o el de diciembre?». «No he podido… ¿lo intento de nuevo?» lleva
        # `?` pero es el fallo de producción con una oferta de reintento: no cuenta (H7, ejecución 2 de #80).
        return tools in ([], ["request_clarification"]) and "?" in texto and "no he podido" not in texto.lower()
    return False


def _incluye(entradas: list, esperado: dict) -> bool:
    """Hubo al menos una llamada y TODAS traen los pares `esperado` (como texto: «20:30» y 20:30 son lo mismo)."""
    return bool(entradas) and all(all(str(e.get(k)) == str(v) for k, v in esperado.items()) for e in entradas)


def evaluar_calendario(golden: dict, tools: list, entradas: dict, texto_alfred: str) -> bool:
    """H9 (#81-#85, modo `calendario`). `entradas` es {tool: [entrada de cada llamada]} de las tools de escritura del calendario.

    - Las tools: la secuencia exacta de `expected`, o, con `expected_any`, al menos una y solo de esa lista (solo lecturas).
    - `entrada`: todas las llamadas a `calendar_add_event` la traen. `entrada_update`: igual con `calendar_update_event`.
    - `alfred_menciona`: todo aparece. `alfred_no_menciona`: nada aparece (sin mirar mayúsculas)."""
    texto = (texto_alfred or "").lower()

    def aparece(frase: str) -> bool:
        # Como palabras completas: «…de la uni es» no casa dentro de «…de la uni está» (#85, pasada de H9).
        return re.search(rf"(?<!\w){re.escape(frase.lower())}(?!\w)", texto) is not None

    if "expected" in golden:
        if tools != golden["expected"]:
            return False
    elif not tools or not set(tools) <= set(golden["expected_any"]):
        return False
    if "entrada" in golden and not _incluye(entradas.get("calendar_add_event", []), golden["entrada"]):
        return False
    if "entrada_update" in golden and not _incluye(entradas.get("calendar_update_event", []), golden["entrada_update"]):
        return False
    if not all(aparece(m) for m in golden.get("alfred_menciona", [])):
        return False
    return not any(aparece(m) for m in golden.get("alfred_no_menciona", []))
