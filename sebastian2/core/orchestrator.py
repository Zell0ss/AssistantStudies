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
from datetime import datetime
from logcentral_client import get_logger
from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError
from core.tools import ALL_TOOLS, build_capabilities_digest
from core.tool_executor import ToolExecutor, _TOOLS_SIN_LOG_DE_CONTENIDO
from db.conversation_repo import ConversationRepository
from db.pending_plan_repo import PendingPlanRepository
from modules.ticket_generator import generate_image
from utils.config import get_config

logger = get_logger("sebastian")

_MAX_ITERATIONS = 8

# D28 (tentativa): modelo del planner en un solo sitio. Haiku 5.5 piensa por defecto y el razonamiento
# se cobra como salida y cuenta para max_tokens: de ahí el esfuerzo (`low` falló 4 goldens de forma estable; H0-revision R1 prueba `medium`) y el margen de max_tokens
# (es un techo, no un gasto: solo se paga lo que se genera). Si se vuelve a Haiku 4.5, _PLANNER_EXTRA
# tiene que quedar VACÍO ({}): `effort` da 400 en 4.5.
_MODELO_PLANNER = "claude-haiku-5-5"
_PLANNER_EXTRA = {"output_config": {"effort": "medium"}}
_PLANNER_MAX_TOKENS = 4096
_PLAN_REPLY_MAX_TOKENS = 512  # SI/NO, pero con razonamiento previo que también cuenta
_CAPABILITIES_DIGEST = build_capabilities_digest()


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


def _now_str() -> str:
    """Return the current date AND time as a Spanish sentence, for prompt injection."""
    now = datetime.now()
    return f"Hoy es {now.strftime('%Y-%m-%d')} y son las {now.strftime('%H:%M')}."


def _planner_system() -> str:
    """Return planner system prompt with today's date and current time injected."""
    return (
        f"{_now_str()}\n"
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

Estas son tus capacidades actuales — si el usuario pregunta qué sabes hacer o duda de si puedes algo, responde desde aquí:
{_CAPABILITIES_DIGEST}"""


class Orchestrator:
    """Handles any user message by orchestrating module tools via Haiku + Alfred synthesis."""

    def __init__(self, db, user_id: str, config: dict = None):
        self._db = db
        self._user_id = user_id
        config = config if config is not None else get_config()
        self._client = Anthropic(api_key=config['anthropic_apikey'], timeout=60.0)
        self._executor = ToolExecutor(db, user_id, config=config)
        self._repo = PendingPlanRepository(db)
        self._conversations = ConversationRepository(db)
        historial_cfg = config.get("historial", {})
        self._historial_limite = historial_cfg.get("intercambios", 6)
        self._historial_ventana_min = historial_cfg.get("ventana_min", 120)
        self._turn_usage = {"tokens_in": 0, "tokens_out": 0, "models": set()}

    def _track_usage(self, response, model: str) -> None:
        """Accumulate model + token usage for the current turn (telemetry only)."""
        self._turn_usage["models"].add(model)
        usage = getattr(response, "usage", None)
        if usage is not None:
            self._turn_usage["tokens_in"] += getattr(usage, "input_tokens", 0) or 0
            self._turn_usage["tokens_out"] += getattr(usage, "output_tokens", 0) or 0

    def _llamar_planner(self, messages: list):
        """Una llamada al planner (D28): modelo único, esfuerzo bajo, uso contabilizado y vigilado."""
        response = self._client.messages.create(
            model=_MODELO_PLANNER,
            max_tokens=_PLANNER_MAX_TOKENS,
            system=_planner_system(),
            tools=ALL_TOOLS,
            messages=messages,
            **_PLANNER_EXTRA,
        )
        self._track_usage(response, _MODELO_PLANNER)
        self._avisar_si_el_planner_no_decidio(response)
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
            latency_ms=latency_ms,
            outcome=outcome,
        ).info(
            f"Turn end | user={self._user_id} | outcome={outcome} | iterations={iterations} | "
            f"models={models} | tokens_in={usage['tokens_in']} | tokens_out={usage['tokens_out']} | "
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
        for iteration in range(_MAX_ITERATIONS):
            iterations_used = iteration + 1
            response = self._llamar_planner(messages)

            tool_blocks = [b for b in response.content if b.type == 'tool_use']

            if response.stop_reason in ('end_turn', 'refusal') or not tool_blocks:
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
                    break

            if had_error:
                break

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        self._repo.delete(self._user_id)
        text = self._synthesize(original_message, tool_results_summary)
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
        truncated = user_message[:200]
        try:
            result = self._handle_inner(user_message)
        except APIConnectionError:
            logger.bind(user_id=self._user_id).exception(
                f"Anthropic API connection error | user={self._user_id} | message={truncated!r}"
            )
            return {"text": "Lo siento, no puedo conectar con el servicio en este momento. Por favor, inténtelo más tarde.", "images": []}
        except RateLimitError:
            logger.bind(user_id=self._user_id).exception(
                f"Anthropic API rate limit | user={self._user_id} | message={truncated!r}"
            )
            return {"text": "Demasiadas solicitudes al servicio. Por favor, espere un momento.", "images": []}
        except APIError as e:
            logger.bind(user_id=self._user_id).exception(
                f"Anthropic API error (status={getattr(e, 'status_code', '?')}) | "
                f"user={self._user_id} | message={truncated!r}"
            )
            if "credit balance" in str(e).lower() or "too low" in str(e).lower():
                return {"text": "El servicio no está disponible temporalmente (créditos agotados). Por favor, contacte al administrador.", "images": []}
            return {"text": "Error en el servicio de IA. Por favor, inténtelo más tarde.", "images": []}
        # Solo los turnos que terminan sin error de API entran en el historial (D21, D22).
        self._guardar_intercambio(user_message, result["text"])
        return result

    def _handle_inner(self, user_message: str) -> dict:
        """Core message handling logic (API errors propagate to handle())."""
        turn_start = time.perf_counter()
        self._turn_usage = {"tokens_in": 0, "tokens_out": 0, "models": set()}
        logger.bind(user_id=self._user_id).info(
            f"Turn start | user={self._user_id} | message={user_message[:200]!r}"
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

        for iteration in range(_MAX_ITERATIONS):
            iterations_used = iteration + 1
            response = self._llamar_planner(messages)

            tool_blocks = [b for b in response.content if b.type == 'tool_use']

            if response.stop_reason in ('end_turn', 'refusal') or not tool_blocks:
                # Planner is done — move to synthesis
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
                    # On tool error, break out of the loop immediately
                    # so synthesis can handle graceful degradation
                    break

            if had_error:
                break

            # Add assistant turn + tool results to messages
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        text = self._synthesize(user_message, tool_results_summary, historial)
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

    def _synthesize(self, user_message: str, tool_results: list, historial: list | None = None) -> str:
        """Call Sonnet to synthesize a Spanish Alfred-style response."""
        if tool_results:
            context_lines = []
            for item in tool_results:
                context_lines.append(
                    f"[{item['tool']}({json.dumps(item['input'], ensure_ascii=False)})]:\n"
                    f"{json.dumps(item['result'], default=str, ensure_ascii=False)}"
                )
            context = "\n\n".join(context_lines)
            synthesis_prompt = (
                f"{_now_str()}\n"
                f"El usuario preguntó: {user_message}\n\n"
                f"Datos recogidos:\n{context}\n\n"
                f"Responde al usuario en español, de forma concisa y útil."
            )
        else:
            synthesis_prompt = f"{_now_str()}\n{user_message}"

        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=_ALFRED_SYSTEM,
            messages=(historial or []) + [{"role": "user", "content": synthesis_prompt}]
        )
        self._track_usage(response, "claude-sonnet-4-6")
        return response.content[0].text.strip()

    def _ask_user(self, question: str) -> str:
        """Have Alfred ask the user for clarification in his characteristic style."""
        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            system=_ALFRED_SYSTEM,
            messages=[{"role": "user", "content": f"Necesito preguntarle esto al usuario: {question}"}]
        )
        self._track_usage(response, "claude-sonnet-4-6")
        return response.content[0].text.strip()
