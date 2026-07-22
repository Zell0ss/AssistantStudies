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
from core.tools import ALL_TOOLS
from core.tool_executor import ToolExecutor
from db.pending_plan_repo import PendingPlanRepository
from modules.ticket_generator import generate_image
from utils.config import get_config

logger = get_logger("sebastian")

_MAX_ITERATIONS = 8


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
        "Cuando tengas toda la información necesaria, devuelve un texto breve indicando que ya tienes los datos."
    )

_ALFRED_SYSTEM = """Eres Sebastian, el asistente personal de tu señor.
Tu estilo es el de Alfred Pennyworth: servicial, eficiente, con flema británica.
Eres discreto — no te extiendes innecesariamente, mides cada palabra.
Nunca preguntas más de lo estrictamente necesario.
Respondes siempre en español.
Si el contexto incluye datos de herramientas, úsalos para dar una respuesta precisa y útil."""


class Orchestrator:
    """Handles any user message by orchestrating module tools via Haiku + Alfred synthesis."""

    def __init__(self, db, user_id: str, config: dict = None):
        self._db = db
        self._user_id = user_id
        config = config if config is not None else get_config()
        self._client = Anthropic(api_key=config['anthropic_apikey'], timeout=60.0)
        self._executor = ToolExecutor(db, user_id, config=config)
        self._repo = PendingPlanRepository(db)
        self._turn_usage = {"tokens_in": 0, "tokens_out": 0, "models": set()}

    def _track_usage(self, response, model: str) -> None:
        """Accumulate model + token usage for the current turn (telemetry only)."""
        self._turn_usage["models"].add(model)
        usage = getattr(response, "usage", None)
        if usage is not None:
            self._turn_usage["tokens_in"] += getattr(usage, "input_tokens", 0) or 0
            self._turn_usage["tokens_out"] += getattr(usage, "output_tokens", 0) or 0

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
        """Ask Haiku whether the user message answers the pending plan question."""
        response = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            system="Responde solo 'SI' o 'NO', sin más texto.",
            messages=[{"role": "user", "content": (
                f"Pregunta pendiente: '{plan_question}'.\n"
                f"Mensaje del usuario: '{user_message}'.\n"
                f"¿Es el mensaje una respuesta directa a la pregunta pendiente?"
            )}]
        )
        self._track_usage(response, "claude-haiku-4-5-20251001")
        return response.content[0].text.strip().upper().startswith('S')

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
            response = self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=_planner_system(),
                tools=ALL_TOOLS,
                messages=messages
            )
            self._track_usage(response, "claude-haiku-4-5-20251001")

            tool_blocks = [b for b in response.content if b.type == 'tool_use']

            if response.stop_reason == 'end_turn' or not tool_blocks:
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
                    logger.bind(tool=block.name, latency_ms=latency_ms).info(
                        f"Tool {block.name} → {_summarize_tool_result(raw)} ({latency_ms}ms)"
                    )
                    logger.debug(
                        f"Tool {block.name} | input={json.dumps(block.input, ensure_ascii=False)} | "
                        f"full_result={result_content[:2000]}"
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_content
                    })
                except Exception:
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
            return self._handle_inner(user_message)
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

        messages = [{"role": "user", "content": user_message}]
        tool_results_summary = []

        for iteration in range(_MAX_ITERATIONS):
            iterations_used = iteration + 1
            response = self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=_planner_system(),
                tools=ALL_TOOLS,
                messages=messages
            )
            self._track_usage(response, "claude-haiku-4-5-20251001")

            tool_blocks = [b for b in response.content if b.type == 'tool_use']

            if response.stop_reason == 'end_turn' or not tool_blocks:
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
                    logger.bind(tool=block.name, latency_ms=latency_ms).info(
                        f"Tool {block.name} → {_summarize_tool_result(raw)} ({latency_ms}ms)"
                    )
                    logger.debug(
                        f"Tool {block.name} | input={json.dumps(block.input, ensure_ascii=False)} | "
                        f"full_result={result_content[:2000]}"
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_content
                    })
                except Exception:
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

        text = self._synthesize(user_message, tool_results_summary)
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

    def _synthesize(self, user_message: str, tool_results: list) -> str:
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
            messages=[{"role": "user", "content": synthesis_prompt}]
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
