"""
Orchestrator — multi-step query handler using Anthropic Tool Use.

Flow:
1. Haiku receives the user message + all tool definitions.
2. If Haiku selects tools, ToolExecutor calls the relevant module methods.
3. Tool results are fed back to Haiku (tool_result blocks).
4. Loop continues until stop_reason=end_turn or MAX_ITERATIONS reached.
5. Sonnet/Alfred synthesizes a Spanish response from collected data.
"""
import json
import time
import uuid
from datetime import datetime, timedelta
from logcentral_client import get_logger
from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError
from core import depuracion
from core.memoria.ajustes import propietario_vault
from core.memoria.catalogo import indice_memoria
from core.memoria.repositorio import RepositorioMemoria
from core.memoria.vault import leer_proyectos
from core.tools import ALL_TOOLS, build_capabilities_digest
from core.tool_executor import ToolExecutor, _TOOLS_SIN_LOG_DE_CONTENIDO
from db.conversation_repo import ConversationRepository
from db.pending_plan_repo import PendingPlanRepository
from modules.ticket_generator import generate_image
from utils.config import get_config

logger = get_logger("sebastian")

_MAX_ITERATIONS = 8

# D28: modelo del planner en un solo sitio. Haiku 5.5 se probó con esfuerzo `low` (51/55 goldens, 4 fallos
# estables) y `medium` (47/55: 5 fallos de comportamiento más 3 por un problema de entorno, ver
# docs/fase2/H0-informe.md): no cumplió el criterio, así que el planner sigue en Haiku 4.5.
# Para probar otro modelo con razonamiento por defecto: el razonamiento se cobra como salida y cuenta
# para max_tokens, y `effort` va en _PLANNER_EXTRA. Con Haiku 4.5 _PLANNER_EXTRA tiene que quedar VACÍO
# ({}): `effort` da 400 en 4.5.
_MODELO_PLANNER = "claude-haiku-4-5-20251001"
_PLANNER_EXTRA = {}
_PLANNER_MAX_TOKENS = 4096
_PLAN_REPLY_MAX_TOKENS = 512  # SI/NO, pero con razonamiento previo que también cuenta
_CAPABILITIES_DIGEST = build_capabilities_digest()

# D68 (fase 4, H1b): Alfred no se corta a media frase. 400 tokens cortaban un inventario de herramientas en mitad de una
# palabra, sin aviso. El techo no cuesta nada si no se usa (peor caso 1500 × 15 $/MTok ≈ 0,02 $ por turno), y si aun así
# se corta (`stop_reason == "max_tokens"`) se recorta limpio y se avisa. El «concisa» del prompt se queda.
_ALFRED_MAX_TOKENS = 1500
_ASK_MAX_TOKENS = 300
_AVISO_SIN_ESPACIO = "(Me he quedado sin espacio, señor. Dígame si quiere el resto.)"
_MSG_ERROR_SERVICIO = "Error en el servicio de IA. Por favor, inténtelo más tarde."

# D59: las tools del planner van con un marcador de caché (TTL de 5 min) en la última, que cachea todo el
# prefijo `tools`. Copia de ALL_TOOLS: solo se copia el último dict, y ALL_TOOLS no se muta (lo usan los
# tests y el digest). El `system` empieza por la hora y cambia en cada llamada, pero va después de `tools`
# en el orden de la caché, así que no la invalida. Mínimo cacheable de Haiku 4.5: 4096 tokens.
_PLANNER_TOOLS = [*ALL_TOOLS[:-1], {**ALL_TOOLS[-1], "cache_control": {"type": "ephemeral"}}]


def _recortar_corte(texto: str) -> str:
    """D68 (R7): un texto cortado por `max_tokens` se recorta en el último salto de línea; sin ninguno, en el último fin de
    frase («. », «? », «! », conservando el signo); y si tampoco hay, se deja como está."""
    corte = texto.rfind("\n")
    if corte > 0:
        return texto[:corte].rstrip()
    fin = max(texto.rfind(". "), texto.rfind("? "), texto.rfind("! "))
    return texto[:fin + 1] if fin > 0 else texto


def _uso_vacio() -> dict:
    """Contadores de uso de un turno (telemetría)."""
    return {"tokens_in": 0, "tokens_out": 0, "cache_read": 0, "cache_creation": 0, "models": set()}


def _messages_to_json(messages: list) -> str:
    """Serialize Haiku messages to JSON. Converts SDK objects via model_dump()."""
    serializable = []
    for msg in messages:
        content = msg["content"]
        if isinstance(content, list):
            content = [
                block.model_dump() if hasattr(block, 'model_dump') else block
                for block in content
            ]
        serializable.append({"role": msg["role"], "content": content})
    return json.dumps(serializable, ensure_ascii=False)


def _messages_from_json(json_str: str) -> list:
    """Deserialize messages JSON. Anthropic API accepts plain dicts."""
    return json.loads(json_str)


def _summarize_tool_result(raw) -> str:
    """One-line summary of a tool result for INFO-level logging (full payload stays at DEBUG)."""
    if isinstance(raw, dict):
        if "status" in raw:
            return f"status={raw['status']}"
        return f"dict with {len(raw)} keys"
    if isinstance(raw, list):
        return f"{len(raw)} items"
    if isinstance(raw, str):
        return raw[:80] + ("…" if len(raw) > 80 else "")
    if isinstance(raw, (int, float, bool)) or raw is None:
        return f"value={raw}"
    return str(type(raw).__name__)


def _log_tool_execution(tool_name: str, tool_input: dict, raw, latency_ms: float, result_content: str) -> None:
    """INFO summary + DEBUG full payload for a completed tool call — except `salud`
    (D39-D42: nunca el texto del usuario ni lo leído por el modelo en los logs, en ningún
    nivel; solo el nombre de la tool y que terminó bien)."""
    if tool_name in _TOOLS_SIN_LOG_DE_CONTENIDO:
        logger.bind(tool=tool_name, latency_ms=latency_ms).info(f"Tool {tool_name} → ok ({latency_ms}ms)")
        return
    logger.bind(tool=tool_name, latency_ms=latency_ms).info(
        f"Tool {tool_name} → {_summarize_tool_result(raw)} ({latency_ms}ms)"
    )
    logger.debug(
        f"Tool {tool_name} | input={json.dumps(tool_input, ensure_ascii=False)} | "
        f"full_result={result_content[:2000]}"
    )


# D60: nombres de los días escritos aquí, sin `locale` (el servidor no tiene por qué tener el español instalado).
_DIAS_SEMANA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_DIAS_VISTOS = 14   # hoy y los 13 siguientes


def _reloj() -> datetime:
    """La hora de ahora; un solo sitio para fijarla en las pruebas (y en los goldens con `ahora`)."""
    return datetime.now()


def _contexto_fecha(ahora: datetime | None = None) -> str:
    """D60: la fecha y hora de ahora con el día de la semana, y los próximos 14 días (día de la semana y d/m).

    Al planner no se le puede pedir que calcule «este viernes» desde «2026-11-19»: el 19/11 salió el viernes 27 (H9).
    Planner y Alfred ven el mismo texto."""
    ahora = ahora or _reloj()
    dias = []
    for n in range(_DIAS_VISTOS):
        d = ahora.date() + timedelta(days=n)
        nombre = f"{_DIAS_SEMANA[d.weekday()]} {d.day}/{d.month}"
        dias.append(f"hoy {nombre}" if n == 0 else f"mañana {nombre}" if n == 1 else nombre)
    return (f"Hoy es {_DIAS_SEMANA[ahora.weekday()]} {ahora:%Y-%m-%d} y son las {ahora:%H:%M}.\n"
            f"Próximos días: {', '.join(dias)}.")


# D43: el historial lleva el texto del asistente («Anotado…», «Retirado…») y el planner lo imitaba: contestaba en texto
# «He retirado…» sin llamar a la tool (E5 y #66: 0 de 6). Con la regla en medio del prompt no bastaba; al final, justo
# antes de decidir, y más fuerte, sí (3 de 3, diagnóstico de H3). Acotada a datos de memoria: «Guárdame esta nota» o
# «apunta leche» tienen su propia tool.
_REGLA_ACCIONES_CON_HISTORIAL = (
    "\n\nSi el usuario pide guardar, corregir u olvidar un dato de memoria (algo duradero sobre él, su gente, sus cosas "
    "o sus proyectos), tu respuesta de este turno tiene que ser una llamada a `mark_as_memorable`, aunque el historial "
    "parezca que ya se hizo: el historial es lo que se dijo, no lo que se ha hecho en este turno. Nunca contestes en "
    "texto que ya está hecho: aunque en el historial el asistente diga «Anotado» o «Retirado», eso fue otro turno y no cuenta."
)


# Fase 3 (D45, D52): #74 y #76 acababan en `mark_as_memorable` porque «si tomo X tengo que…» parece un dato duradero.
# Lo que el usuario tiene que HACER (con día, hora o condición) es un compromiso, no memoria; y un resultado médico o un
# diagnóstico no se guarda en ningún sitio. Va después de la regla de acciones para que no la pise.
_REGLA_COMPROMISOS = (
    "\n\nLo que el usuario tiene que HACER con un día, una hora o una condición («recuérdame que…», los pasos de una "
    "preparación, «si tomo X tengo que dejarlo…») no es un dato de memoria: es un compromiso (`compromisos_crear`), o, "
    "si depende de algo que no sabes, se pregunta con `request_clarification`. Un resultado médico o un diagnóstico "
    "no se guarda en ninguna tool."
    # Fase 3 H7 (R18, D58): «esta noche a la una» salió el 16/11 con la 01:00 de ese mismo día, que ya había pasado.
    "\n\nHoras de madrugada: una hora entre las 00:00 y las 05:59 con «esta noche» es de la fecha de mañana (la noche que "
    "viene; solo si ya es de madrugada y esa hora aún no ha llegado, es la de hoy). Si el usuario da una fecha explícita "
    "(«martes 17 de noviembre»), esa fecha manda sobre «mañana» o «esta noche». En otro caso dudoso, elige la ocurrencia "
    "más próxima que aún no ha pasado, sin preguntar: nunca una fecha y hora que ya ha pasado."
)

# Fase 3 H9 (R22, D60): «este viernes tengo cena…» dicho el jueves 19/11 creó el evento el 27/11 (el planner solo veía
# «2026-11-19» y calculó mal el día de la semana). Ahora ve los próximos 14 días con su día de la semana (`_contexto_fecha`).
_REGLA_FECHAS = (
    "\n\n«Este viernes», «el lunes», «el martes que viene»: toma la fecha de la lista de próximos días de arriba. "
    "«Este X» es el próximo X que aún no ha pasado. No calcules el día de la semana."
)


# Fase 3 H3c (R9): E10 mostró al planner buscando la cita (`calendar_search_events`) y cerrando el turno sin llamar a la tool
# que la cambia, y a Alfred contando como hecho lo que no se hizo (D54 cubre lo segundo). Mismo patrón que D43: al final,
# justo antes de decidir.
_REGLA_BUSCAR_NO_TERMINA = (
    "\n\nBuscar no termina el turno. Si el usuario pidió cambiar algo (una cita, su nota, un compromiso) y la búsqueda lo "
    "encontró, llama en este mismo turno a la tool que lo cambia."
)


def _planner_system(indice_memoria: str = "") -> str:
    """Return planner system prompt with today's date and current time injected.

    `indice_memoria` (D36): lo que consta del usuario, sin valores, después de las capacidades. No va en
    `_ALFRED_SYSTEM`: la síntesis solo afirma lo que trajeron las herramientas de este turno (D26)."""
    return (
        f"{_contexto_fecha()}\n"
        "Eres el núcleo de razonamiento de Sebastian, asistente personal.\n"
        "Tu único trabajo es decidir qué herramientas usar para responder la pregunta del usuario.\n"
        "Usa las herramientas necesarias para reunir la información. No respondas al usuario directamente.\n"
        "Si la pregunta es la hora o la fecha actual, ya las tienes arriba — no necesitas ninguna herramienta.\n"
        "Cuando tengas toda la información necesaria, devuelve un texto breve indicando que ya tienes los datos.\n"
        # D26: «qué sabes de mí» no es una pregunta de capacidades; el incidente del 2026-10-14
        # nació de confundirlas (el planner no llamó a search_memory y Alfred rellenó una ficha).
        "Si la pregunta es sobre tus capacidades (lo que Sebastian sabe HACER, p. ej. «qué sabes hacer»), "
        "no necesitas ninguna herramienta — ya tienes la lista abajo y quien sintetiza la respuesta la usará.\n"
        "Las preguntas sobre el usuario (D26) — «qué sabes de mí», «cómo me llamo», «cuándo es mi cumpleaños», "
        "«qué te he contado de…» — NO son preguntas de capacidades: usa search_memory para consultar lo que "
        "consta de él. No las des por respondidas sin consultar la memoria.\n\n"
        "Estas son tus capacidades actuales:\n"
        f"{_CAPABILITIES_DIGEST}"
        + (f"\n\n{indice_memoria}" if indice_memoria else "")
        + _REGLA_ACCIONES_CON_HISTORIAL
        + _REGLA_COMPROMISOS
        + _REGLA_FECHAS
        + _REGLA_BUSCAR_NO_TERMINA
    )

# D26: regla de honestidad sobre el usuario (ver también _planner_system).
_ALFRED_SYSTEM = f"""Eres Sebastian, el asistente personal de tu señor.
Tu estilo es el de Alfred Pennyworth: servicial, eficiente, con flema británica.
Eres discreto — no te extiendes innecesariamente, mides cada palabra.
Nunca preguntas más de lo estrictamente necesario.
Respondes siempre en español.
Si el contexto incluye datos de herramientas, úsalos para dar una respuesta precisa y útil.

Honestidad sobre tu señor (D26): de él solo sabes lo que traigan los datos de herramientas de este turno
o lo que él mismo haya dicho en la conversación. Lo que tú dijiste en turnos anteriores no es una fuente
de datos sobre él: pudiste equivocarte, y repetirlo lo convertiría en un hecho. Si algo no te consta,
dilo con naturalidad («no me consta», «no lo tengo anotado») y, si viene a cuento, ofrécete a apuntarlo.
Nunca rellenes con datos plausibles: ni nombres, ni fechas, ni gustos.
Resultados médicos (D52). Si el usuario cuenta un resultado o un diagnóstico médico, no ofrezcas guardarlo: Sebastian no los guarda. Comentarlo con él sigue estando bien.

Memoria (D16): si el resultado de mark_as_memorable trae `nuevos_pendientes` (una entidad o un atributo nuevos),
dilo en una frase corta, solo para informar («he abierto la categoría *lugar de residencia*»); no ofrezcas cambiarle el nombre ni confirmarla: eso todavía no se puede. Si un
elemento de `guardados` trae `sustituye`, di qué valor sustituyó. Si el dato quedó en `notas` o en `sin_cambio`,
no afirmes que lo guardaste o corregiste: cuenta lo que pasó de verdad («lo he dejado como nota» / «ya constaba»).

Memoria (consulta): el resultado de search_memory trae `hechos` (lo vigente, con `desde`), `historial` (lo que valía
antes, solo si se pidió), `notas` (texto libre parecido a la pregunta), `vault` (el valor en vivo de un proyecto) y
`conflictos`. Si `conflictos` no está vacío, gana el vault: da el valor del vault y avisa de que lo que el señor
había dicho no coincide. Si el resultado trae `atributo_no_resuelto`, el atributo pedido no existe con ese nombre y `hechos` son todos
los vigentes de esa entidad: contesta solo con los que vienen a cuento de la pregunta y, si ninguno viene a cuento, dilo (D71).
Si todo viene vacío, no me consta (D26): dilo y, si viene a cuento, ofrécete a apuntarlo.
El vault es de solo lectura para ti: no puedes cambiar el vault. Si lo que dice está mal, hay que corregirlo en `proyecto.md`.
No afirmes que has guardado, corregido, olvidado, apuntado o creado nada si en este turno no hay un resultado de
herramienta que lo diga. Si el usuario pidió guardar, corregir u olvidar y en este turno no hay resultado, dile en
llano que no lo has hecho y ofrécete a intentarlo de nuevo. No menciones herramientas, resultados ni reglas.
Tú no ejecutas herramientas: solo lees lo que ya trajeron. Si en este turno no te llegan datos de la memoria, no
digas «permítame consultarlo»; di que no te consta.
Al confirmar un compromiso creado, di el día de la semana, el día y el mes tal como vienen en `cuando_texto` («martes 17/11
a las 01:00»), nunca «mañana a la una» sin más.
Si no encuentras algo que el usuario da por hecho (un evento, un compromiso), di que no lo encuentras con esa búsqueda, sin
suponer por qué. No digas que no se guardó. Si ofreces crearlo, avisa de que podría quedar duplicado. (D62)

Estas son tus capacidades actuales — si el usuario pregunta qué sabes hacer o duda de si puedes algo, responde desde aquí:
{_CAPABILITIES_DIGEST}"""


# D44: cuando el planner no ejecuta ninguna herramienta, `_synthesize` no recibe resultados y Alfred solo veía el mensaje y el
# historial: con «Anotado… al marisco» en el historial y «Olvida lo del marisco» delante, contestaba «He retirado…» sin haber
# retirado nada. Que en este turno no se ha hecho nada lo sabe el código; ahora se le dice, después del mensaje del usuario.
_TURNO_SIN_HERRAMIENTAS = (
    "[En este turno no se ha ejecutado ninguna herramienta: no has guardado, cambiado, borrado, apuntado ni creado nada. "
    "Si el usuario lo pidió, dile en llano que no lo has hecho y ofrécete a intentarlo.]"
)


# Fase 3 H7 (R17, D57): en producción (16/11) el planner cerró dos turnos SIN tool y con un texto corto, y ese texto se
# descartaba: Alfred solo decía «no he podido». Ahora, si no se ejecutó ninguna tool, el texto le llega como NOTA, después de
# `_TURNO_SIN_HERRAMIENTAS` y sin sustituirlo (que no se ha hecho nada sigue siendo cierto). No es un dato ni algo hecho.
_NOTA_PLANNER_MAX = 600
# D72 (R19): el resumen de tools que recibe Alfred, en la traza de depuración, se recorta a este tamaño (el de cada tool, a 4000).
_RECORTE_ALFRED = 12000


def _texto_del_planner(response) -> str:
    """El texto (bloques `text`) de una respuesta del planner, sin espacios en los extremos. Vacío si no escribió ninguno."""
    return " ".join(
        b.text for b in response.content if getattr(b, "type", None) == "text" and isinstance(getattr(b, "text", None), str)
    ).strip()


def _nota_del_planner(texto: str) -> str:
    return (f"[Nota de quien planifica este turno, no es un dato ni algo hecho: «{texto}». "
            "Si es una pregunta para el usuario o le falta un dato, házsela tú en una frase.]")


# Fase 3 H3c (D54, extiende D44): D44 solo vigila el turno SIN ninguna tool. E10 enseñó el hueco de al lado: el planner busca
# (`calendar_search_events`), cierra el turno, y Alfred contaba como hecho lo que no se hizo. Si todas las tools del turno son
# de lectura, a Alfred se le dice. Dos conjuntos explícitos, y una prueba (`test_toda_tool_esta_clasificada_lectura_o_escritura`)
# que obliga a clasificar toda tool nueva: ninguna se adivina por el nombre. `request_clarification` no cambia nada: va con las
# de lectura (el orquestador la intercepta y el turno no llega a `_synthesize` con ella).
_TOOLS_DE_LECTURA = frozenset({
    "calendar_search_events", "calendar_list_events", "calendar_find_by_datetime", "calendar_get_tickets",
    "weather_get", "weather_forecast", "weather_forecast_for_date",
    "inventory_list", "inventory_check_low_stock", "list_items",
    "notes_search", "notes_get", "tasks_list", "consult_docs", "search_memory",
    "compromisos_listar", "request_clarification",
})
_TOOLS_DE_ESCRITURA = frozenset({
    "calendar_add_event", "calendar_remove_event", "calendar_update_event", "calendar_clear_tickets", "calendar_add_note",
    "inventory_add", "inventory_remove", "inventory_set_quantity", "inventory_update_quantity",
    "list_add_item", "list_remove_item", "list_clear",
    "notes_create", "notes_append", "notes_add_tag", "notes_remove_tag", "notes_delete",
    "tasks_create", "tasks_complete", "mark_as_memorable", "youtube_transcript", "salud",
    "compromisos_crear", "compromisos_completar", "compromisos_borrar",
})


def _nota_turno_solo_lectura(tool_results: list) -> str:
    """La nota de D54, o '' si el turno escribió algo (o no corrió ninguna tool: eso es de D44)."""
    nombres = list(dict.fromkeys(item["tool"] for item in tool_results))
    if not nombres or any(n not in _TOOLS_DE_LECTURA for n in nombres):
        return ""
    return (f"[En este turno solo has consultado ({', '.join(nombres)}): no has guardado, cambiado, borrado, apuntado ni "
            "creado nada. Si el usuario pedía un cambio, dile que no lo has hecho y ofrécete a hacerlo.]")


class Orchestrator:
    """Handles any user message by orchestrating module tools via Haiku + Alfred synthesis."""

    def __init__(self, db, user_id: str, config: dict = None):
        self._db = db
        self._user_id = user_id
        config = config if config is not None else get_config()
        self._client = Anthropic(api_key=config['anthropic_apikey'], timeout=60.0)
        self._executor = ToolExecutor(
            db, user_id, config=config, on_usage=lambda response, model: self._track_usage(response, model))
        self._repo = PendingPlanRepository(db)
        self._conversations = ConversationRepository(db)
        historial_cfg = config.get("historial", {})
        self._historial_limite = historial_cfg.get("intercambios", 6)
        self._historial_ventana_min = historial_cfg.get("ventana_min", 120)
        self._turn_usage = _uso_vacio()
        self._vault_path = config.get("vault_docs_path")
        self._propietario_vault = propietario_vault(config)
        self._indice_turno = None   # el índice de la memoria se calcula una vez por turno (D36)
        self._turno_debug = None    # D72: id del turno si la traza de depuración estaba activa al empezar; None si no

    def _depurando(self) -> bool:
        return self._turno_debug is not None

    def _trazar(self, etapa: str, datos) -> None:
        """D72 (R19): una línea en la traza de depuración del usuario, con contenido. Solo si el turno empezó con la traza
        activa; nunca va a loguru ni a LogCentral (`depuracion.traza` escribe a mano y no lanza)."""
        if self._depurando():
            depuracion.traza(self._user_id, self._turno_debug, etapa, datos)

    def _indice_del_turno(self) -> str:
        """D36: lo que consta del usuario, sin valores. Si falla, el turno sigue sin índice (patrón D22)."""
        if self._indice_turno is None:
            try:
                proyectos = leer_proyectos(self._vault_path) if self._user_id == self._propietario_vault else None
                self._indice_turno = indice_memoria(RepositorioMemoria(self._db), self._user_id, proyectos)
            except Exception as e:
                logger.warning(
                    f"No se pudo construir el índice de la memoria | user={self._user_id} | error={type(e).__name__}"
                )
                self._indice_turno = ""
        return self._indice_turno

    def _track_usage(self, response, model: str) -> None:
        """Accumulate model + token usage for the current turn (telemetry only)."""
        self._turn_usage["models"].add(model)
        usage = getattr(response, "usage", None)
        if usage is not None:
            self._turn_usage["tokens_in"] += getattr(usage, "input_tokens", 0) or 0
            self._turn_usage["tokens_out"] += getattr(usage, "output_tokens", 0) or 0
            # D59: `tokens_in` es solo lo no cacheado; la caché va aparte.
            self._turn_usage["cache_read"] += getattr(usage, "cache_read_input_tokens", 0) or 0
            self._turn_usage["cache_creation"] += getattr(usage, "cache_creation_input_tokens", 0) or 0

    def _llamar_planner(self, messages: list):
        """Una llamada al planner (D28): modelo único, esfuerzo bajo, uso contabilizado y vigilado."""
        response = self._client.messages.create(
            model=_MODELO_PLANNER,
            max_tokens=_PLANNER_MAX_TOKENS,
            system=_planner_system(self._indice_del_turno()),
            tools=_PLANNER_TOOLS,
            messages=messages,
            **_PLANNER_EXTRA,
        )
        self._track_usage(response, _MODELO_PLANNER)
        self._avisar_si_el_planner_no_decidio(response)
        if self._depurando():       # D72 (R19): lo que decidió el planner, con el input crudo de cada tool
            self._trazar("planner", {
                "stop_reason": response.stop_reason, "n_mensajes": len(messages), "texto": _texto_del_planner(response),
                "tools": [{"name": b.name, "input": b.input} for b in response.content if b.type == "tool_use"]})
        return response

    def _avisar_si_el_planner_no_decidio(self, response) -> None:
        """D28: un rechazo o un corte por max_tokens no deben ser silenciosos. Sin contenido del mensaje."""
        if response.stop_reason == "refusal":
            categoria = getattr(getattr(response, "stop_details", None), "category", None)
            logger.warning(f"Planner rechazó la petición | user={self._user_id} | categoria={categoria}")
        elif response.stop_reason == "max_tokens":
            logger.warning(
                f"Planner cortado por max_tokens ({_PLANNER_MAX_TOKENS}) antes de decidir | user={self._user_id}"
            )

    def _cargar_historial(self) -> list:
        """Mensajes user/assistant de los últimos intercambios (D21). Si falla, vacío (D22).

        Al log no va el contenido del historial (puede ser de salud), solo cuántos intercambios."""
        try:
            pares = self._conversations.recientes(
                self._user_id, limite=self._historial_limite, ventana_min=self._historial_ventana_min
            )
        except Exception as e:
            logger.warning(
                f"No se pudo leer el historial | user={self._user_id} | error={type(e).__name__}"
            )
            return []
        mensajes = []
        usados = 0
        for par in pares:
            # La API rechaza contenido vacío; un intercambio con un lado vacío no aporta contexto.
            if not (par["user_msg"] or "").strip() or not (par["bot_reply"] or "").strip():
                continue
            mensajes.append({"role": "user", "content": par["user_msg"]})
            mensajes.append({"role": "assistant", "content": par["bot_reply"]})
            usados += 1
        logger.info(f"Historial cargado | user={self._user_id} | intercambios={usados}")
        return mensajes

    def _guardar_intercambio(self, user_message: str, texto: str) -> None:
        """Guarda el turno para los siguientes (D21). Si falla, la respuesta sale igual (D22)."""
        if not (texto or "").strip():
            return
        try:
            self._conversations.guardar(self._user_id, user_message, texto)
        except Exception as e:
            logger.warning(
                f"No se pudo guardar el intercambio | user={self._user_id} | error={type(e).__name__}"
            )

    def _log_turn_end(self, turn_start: float, iterations: int, outcome: str) -> None:
        """Emit the single end-of-turn INFO line: iterations, models, tokens, total latency."""
        latency_ms = round((time.perf_counter() - turn_start) * 1000, 1)
        usage = self._turn_usage
        models = ",".join(sorted(usage["models"])) or "none"
        logger.bind(
            user_id=self._user_id,
            iterations=iterations,
            models=models,
            tokens_in=usage["tokens_in"],
            tokens_out=usage["tokens_out"],
            cache_read=usage["cache_read"],
            cache_creation=usage["cache_creation"],
            latency_ms=latency_ms,
            outcome=outcome,
        ).info(
            f"Turn end | user={self._user_id} | outcome={outcome} | iterations={iterations} | "
            f"models={models} | tokens_in={usage['tokens_in']} | tokens_out={usage['tokens_out']} | "
            f"cache_read={usage['cache_read']} | cache_creation={usage['cache_creation']} | "
            f"latency_ms={latency_ms}"
        )

    def _is_plan_reply(self, user_message: str, plan_question: str) -> bool:
        """Ask the planner model whether the user message answers the pending plan question."""
        response = self._client.messages.create(
            model=_MODELO_PLANNER,
            max_tokens=_PLAN_REPLY_MAX_TOKENS,
            system="Responde solo 'SI' o 'NO', sin más texto.",
            messages=[{"role": "user", "content": (
                f"Pregunta pendiente: '{plan_question}'.\n"
                f"Mensaje del usuario: '{user_message}'.\n"
                f"¿Es el mensaje una respuesta directa a la pregunta pendiente?"
            )}],
            **_PLANNER_EXTRA,
        )
        self._track_usage(response, _MODELO_PLANNER)
        # D28: la respuesta puede empezar por bloques `thinking`: se lee el primer bloque de tipo text.
        texto = next((b.text for b in response.content if b.type == "text"), None)
        if texto is None:
            logger.warning(
                f"_is_plan_reply sin bloque de texto (stop_reason={response.stop_reason}) | "
                f"user={self._user_id}: se trata como NO"
            )
            return False
        return texto.strip().upper().startswith('S')

    def _resume_plan(self, plan: dict, user_answer: str, turn_start: float) -> str:
        """Resume a pending plan by injecting the user's answer as a tool_result."""
        messages = _messages_from_json(plan["messages_json"])
        original_message = plan["original_message"]
        iterations_used = 0

        # Find the request_clarification tool_use_id from the last assistant message
        last_content = messages[-1]["content"]
        rc_block = next(
            b for b in last_content
            if isinstance(b, dict)
            and b.get("type") == "tool_use"
            and b.get("name") == "request_clarification"
        )

        # Inject user's answer as the tool_result for that call
        messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": rc_block["id"],
                "content": user_answer
            }]
        })

        # Resume the tool loop
        tool_results_summary = []
        nota_planner = ""
        for iteration in range(_MAX_ITERATIONS):
            iterations_used = iteration + 1
            response = self._llamar_planner(messages)

            tool_blocks = [b for b in response.content if b.type == 'tool_use']

            if response.stop_reason in ('end_turn', 'refusal') or not tool_blocks:
                if not tool_results_summary:
                    nota_planner = _texto_del_planner(response)        # R17 (D57)
                break

            # Check if Haiku needs yet another clarification
            rc = next((b for b in tool_blocks if b.name == 'request_clarification'), None)
            if rc:
                messages_to_save = messages + [{"role": "assistant", "content": response.content}]
                self._repo.save(
                    self._user_id,
                    original_message,
                    _messages_to_json(messages_to_save),
                    rc.input["question"],
                    rc.input.get("missing_field"),
                )
                text = self._ask_user(rc.input["question"])
                self._log_turn_end(turn_start, iterations_used, "clarification_requested")
                return {"text": text, "images": []}

            # Execute tools normally
            tool_results = []
            had_error = False
            for block in tool_blocks:
                try:
                    t0 = time.perf_counter()
                    raw = self._executor.execute(block.name, block.input)
                    latency_ms = round((time.perf_counter() - t0) * 1000, 1)
                    result_content = json.dumps(raw, default=str, ensure_ascii=False)
                    tool_results_summary.append({"tool": block.name, "input": block.input, "result": raw})
                    _log_tool_execution(block.name, block.input, raw, latency_ms, result_content)
                    if self._depurando():       # D72 (R19): el resultado de la tool, recortado
                        self._trazar("tool", {"tool": block.name, "resultado": depuracion.recortar(result_content)})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_content
                    })
                except Exception:
                    if block.name in _TOOLS_SIN_LOG_DE_CONTENIDO:
                        logger.exception(f"Tool {block.name} failed | user={self._user_id}")
                    else:
                        logger.exception(
                            f"Tool {block.name} failed | user={self._user_id} | "
                            f"input={json.dumps(block.input, ensure_ascii=False)}"
                        )
                    had_error = True
                    self._trazar("tool", {"tool": block.name, "error": "la tool falló"})
                    break

            if had_error:
                break

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        self._repo.delete(self._user_id)
        text = self._synthesize(original_message, tool_results_summary, nota_planner=nota_planner)
        images = self._collect_images(tool_results_summary)
        self._log_turn_end(turn_start, iterations_used, "completed")
        return {"text": text, "images": images}

    def handle(self, user_message: str) -> str:
        """
        Process a user message and return the final Spanish response.

        Args:
            user_message: Raw text from the user

        Returns:
            Alfred-style Spanish response string
        """
        # D42 (R14): ni el texto del mensaje ni un recorte de él van al log, tampoco en los errores: solo su longitud.
        chars = len(user_message)
        try:
            result = self._handle_inner(user_message)
        except APIConnectionError:
            logger.bind(user_id=self._user_id).exception(
                f"Anthropic API connection error | user={self._user_id} | chars={chars}"
            )
            return {"text": "Lo siento, no puedo conectar con el servicio en este momento. Por favor, inténtelo más tarde.", "images": []}
        except RateLimitError:
            logger.bind(user_id=self._user_id).exception(
                f"Anthropic API rate limit | user={self._user_id} | chars={chars}"
            )
            return {"text": "Demasiadas solicitudes al servicio. Por favor, espere un momento.", "images": []}
        except APIError as e:
            logger.bind(user_id=self._user_id).exception(
                f"Anthropic API error (status={getattr(e, 'status_code', '?')}) | "
                f"user={self._user_id} | chars={chars}"
            )
            if "credit balance" in str(e).lower() or "too low" in str(e).lower():
                return {"text": "El servicio no está disponible temporalmente (créditos agotados). Por favor, contacte al administrador.", "images": []}
            return {"text": _MSG_ERROR_SERVICIO, "images": []}
        # Solo los turnos que terminan sin error de API entran en el historial (D21, D22).
        self._guardar_intercambio(user_message, result["text"])
        return result

    def _handle_inner(self, user_message: str) -> dict:
        """Core message handling logic (API errors propagate to handle())."""
        turn_start = time.perf_counter()
        self._turn_usage = _uso_vacio()
        self._indice_turno = None
        self._executor.mensaje_del_turno = user_message   # D41: la fuente de la memoria guarda el literal
        # D72: el id del turno solo existe si la traza está activa ahora. Sin traza, el ejecutor y la memoria se llaman
        # exactamente igual que antes.
        self._turno_debug = uuid.uuid4().hex[:8] if depuracion.activa(self._user_id) else None
        self._executor.turno_debug = self._turno_debug
        self._trazar("mensaje", {"texto": user_message})
        logger.bind(user_id=self._user_id).info(
            # D42: el texto del usuario no va al log (olvidar lo de alguien tiene que borrarlo también de aquí): longitud y usuario.
            f"Turn start | user={self._user_id} | chars={len(user_message)}"
        )
        iterations_used = 0

        # ── Pending plan check ─────────────────────────────────────────────────────
        plan = self._repo.get_active(self._user_id)
        if plan:
            if self._is_plan_reply(user_message, plan["question"]):
                return self._resume_plan(plan, user_message, turn_start)
            else:
                self._repo.delete(self._user_id)
                # Fall through to normal handling
        # ───────────────────────────────────────────────────────────────────────────

        historial = self._cargar_historial()
        messages = historial + [{"role": "user", "content": user_message}]
        tool_results_summary = []
        nota_planner = ""

        for iteration in range(_MAX_ITERATIONS):
            iterations_used = iteration + 1
            response = self._llamar_planner(messages)

            tool_blocks = [b for b in response.content if b.type == 'tool_use']

            if response.stop_reason in ('end_turn', 'refusal') or not tool_blocks:
                # Planner is done — move to synthesis. R17 (D57): si cierra SIN haber ejecutado ninguna tool, lo que escribió
                # (a veces una pregunta) llega a Alfred; con tools, su cierre normal («Hecho…») no.
                if not tool_results_summary:
                    nota_planner = _texto_del_planner(response)
                break

            # Execute each tool call and collect results
            tool_results = []
            had_error = False
            for block in tool_blocks:
                if block.name == "request_clarification":
                    # Save loop state including the assistant turn that made the call
                    messages_to_save = messages + [{"role": "assistant", "content": response.content}]
                    self._repo.save(
                        self._user_id,
                        user_message,
                        _messages_to_json(messages_to_save),
                        block.input["question"],
                        block.input.get("missing_field"),
                    )
                    text = self._ask_user(block.input["question"])
                    self._log_turn_end(turn_start, iterations_used, "clarification_requested")
                    return {"text": text, "images": []}
                try:
                    t0 = time.perf_counter()
                    raw = self._executor.execute(block.name, block.input)
                    latency_ms = round((time.perf_counter() - t0) * 1000, 1)
                    result_content = json.dumps(raw, default=str, ensure_ascii=False)
                    tool_results_summary.append({
                        "tool": block.name,
                        "input": block.input,
                        "result": raw
                    })
                    _log_tool_execution(block.name, block.input, raw, latency_ms, result_content)
                    if self._depurando():       # D72 (R19): el resultado de la tool, recortado
                        self._trazar("tool", {"tool": block.name, "resultado": depuracion.recortar(result_content)})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_content
                    })
                except Exception:
                    if block.name in _TOOLS_SIN_LOG_DE_CONTENIDO:
                        logger.exception(f"Tool {block.name} failed | user={self._user_id}")
                    else:
                        logger.exception(
                            f"Tool {block.name} failed | user={self._user_id} | "
                            f"input={json.dumps(block.input, ensure_ascii=False)}"
                        )
                    had_error = True
                    self._trazar("tool", {"tool": block.name, "error": "la tool falló"})
                    # On tool error, break out of the loop immediately
                    # so synthesis can handle graceful degradation
                    break

            if had_error:
                break

            # Add assistant turn + tool results to messages
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        text = self._synthesize(user_message, tool_results_summary, historial, nota_planner)
        images = self._collect_images(tool_results_summary)
        self._log_turn_end(turn_start, iterations_used, "completed")
        return {"text": text, "images": images}

    def _collect_images(self, tool_results_summary: list) -> list:
        """Generate ticket images from any calendar_get_tickets tool results."""
        images = []
        for item in tool_results_summary:
            if item['tool'] == 'calendar_get_tickets':
                for ticket in item.get('result', []):
                    try:
                        img_bytes = generate_image(ticket)
                        if img_bytes:
                            images.append(img_bytes)
                    except Exception as e:
                        logger.warning(f"Failed to generate ticket image: {e}")
        return images

    def _synthesize(self, user_message: str, tool_results: list, historial: list | None = None,
                    nota_planner: str = "") -> str:
        """Call Sonnet to synthesize a Spanish Alfred-style response.

        `nota_planner` (R17, D57): lo que el planner escribió al cerrar un turno sin ninguna tool. Solo se usa sin
        resultados de tools, va después de `_TURNO_SIN_HERRAMIENTAS` y nunca al log (D42): solo que hubo nota y su longitud."""
        if tool_results:
            context_lines = []
            for item in tool_results:
                context_lines.append(
                    f"[{item['tool']}({json.dumps(item['input'], ensure_ascii=False)})]:\n"
                    f"{json.dumps(item['result'], default=str, ensure_ascii=False)}"
                )
            context = "\n\n".join(context_lines)
            nota = _nota_turno_solo_lectura(tool_results)          # D54: vacía si el turno escribió algo
            bloque_nota = f"{nota}\n\n" if nota else ""
            synthesis_prompt = (
                f"{_contexto_fecha()}\n"
                f"El usuario preguntó: {user_message}\n\n"
                f"Datos recogidos:\n{context}\n\n"
                f"{bloque_nota}"
                f"Responde al usuario en español, de forma concisa y útil."
            )
        else:
            synthesis_prompt = f"{_contexto_fecha()}\n{user_message}\n\n{_TURNO_SIN_HERRAMIENTAS}"
            nota_planner = (nota_planner or "").strip()[:_NOTA_PLANNER_MAX]
            if nota_planner:
                synthesis_prompt += "\n\n" + _nota_del_planner(nota_planner)
                logger.info(f"Planner cerró sin tool y con nota | user={self._user_id} | "
                            f"planner_nota=1 chars={len(nota_planner)}")

        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=_ALFRED_MAX_TOKENS,
            system=_ALFRED_SYSTEM,
            messages=(historial or []) + [{"role": "user", "content": synthesis_prompt}]
        )
        self._track_usage(response, "claude-sonnet-4-6")
        texto = self._texto_de_alfred(response, _ALFRED_MAX_TOKENS)
        if self._depurando():       # D72 (R19): lo que recibió Alfred (resumen de tools y nota del planner) y lo que contestó
            self._trazar("alfred", {
                "tool_results_summary": depuracion.recortar(context, _RECORTE_ALFRED) if tool_results else "",
                "nota_planner": "" if tool_results else nota_planner,
                "stop_reason": getattr(response, "stop_reason", None), "texto": texto})
        return texto

    def _ask_user(self, question: str) -> str:
        """Have Alfred ask the user for clarification in his characteristic style."""
        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=_ASK_MAX_TOKENS,
            system=_ALFRED_SYSTEM,
            messages=[{"role": "user", "content": f"Necesito preguntarle esto al usuario: {question}"}]
        )
        self._track_usage(response, "claude-sonnet-4-6")
        texto = self._texto_de_alfred(response, _ASK_MAX_TOKENS)
        self._trazar("alfred_pregunta", {"pregunta": question, "stop_reason": getattr(response, "stop_reason", None),
                                         "texto": texto})              # D72 (R19)
        return texto

    def _texto_de_alfred(self, response, techo: int) -> str:
        """D68 (R7, R8): el texto de una respuesta de Alfred, sin cortes mudos ni IndexError.

        - Sin bloque de texto: el mismo mensaje de error del servicio de IA, y un WARNING con el `stop_reason`.
        - Cortada por `max_tokens`: WARNING y, en el texto, un recorte limpio (`_recortar_corte`) y el aviso al usuario.
        Ningún log lleva el texto de la respuesta (D42): solo el techo, la longitud y el `stop_reason`."""
        parada = getattr(response, "stop_reason", None)
        bloque = next((b for b in response.content if isinstance(getattr(b, "text", None), str)), None)
        if bloque is None:
            logger.warning(f"Alfred sin texto en la respuesta (stop_reason={parada}) | user={self._user_id}")
            return _MSG_ERROR_SERVICIO
        texto = bloque.text.strip()
        if parada == "max_tokens":
            logger.warning(f"Alfred cortado por max_tokens ({techo}) | user={self._user_id} | chars={len(texto)}")
            texto = f"{_recortar_corte(texto)}\n{_AVISO_SIN_ESPACIO}"
        return texto
