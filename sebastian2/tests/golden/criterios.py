"""H7 (R17-R19): el criterio de los goldens #79 y #80, que miran QUÉ se creó y no solo qué tools se llamaron.

Es una función pura (sin API) para poder probarla en `tests/test_golden_estado.py`. Los demás goldens siguen con
`_matches` de `test_goldens.py`.

Modos:
- `crea_con_fecha`: pasa si el turno fue exactamente `[compromisos_crear]`, algún compromiso creado trae la `entrada` del golden
  (por ejemplo `fecha_inicio` y `hora`) y la respuesta de Alfred menciona lo de `alfred_menciona`.
- `crea_con_fecha_o_pregunta`: lo mismo, o bien no crea nada y Alfred pregunta (R17: el texto del planner no se pierde).
  Falla si crea otra fecha, o si no crea nada y Alfred no pregunta (el «no he podido» de producción del 16/11, aunque
  acabe en «¿lo intento de nuevo?»).
"""

MODOS = ("crea_con_fecha", "crea_con_fecha_o_pregunta")


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
