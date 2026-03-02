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
from datetime import date
from loguru import logger
from anthropic import Anthropic
from core.tools import ALL_TOOLS
from core.tool_executor import ToolExecutor
from db.pending_plan_repo import PendingPlanRepository
from modules.ticket_generator import generate_image
from utils.config import get_config

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


def _planner_system() -> str:
    """Return planner system prompt with today's date injected."""
    today = date.today().isoformat()
    return (
        f"Hoy es {today}.\n"
        "Eres el núcleo de razonamiento de Sebastian, asistente personal.\n"
        "Tu único trabajo es decidir qué herramientas usar para responder la pregunta del usuario.\n"
        "Usa las herramientas necesarias para reunir la información. No respondas al usuario directamente.\n"
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

    def __init__(self, db, user_id: str):
        self._db = db
        self._user_id = user_id
        config = get_config()
        self._client = Anthropic(api_key=config['anthropic_apikey'])
        self._executor = ToolExecutor(db, user_id)
        self._repo = PendingPlanRepository(db)

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
        return response.content[0].text.strip().upper().startswith('S')

    def _resume_plan(self, plan: dict, user_answer: str) -> str:
        """Resume a pending plan by injecting the user's answer as a tool_result."""
        messages = _messages_from_json(plan["messages_json"])
        original_message = plan["original_message"]

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
            response = self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=_planner_system(),
                tools=ALL_TOOLS,
                messages=messages
            )

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
                return {"text": self._ask_user(rc.input["question"]), "images": []}

            # Execute tools normally
            tool_results = []
            had_error = False
            for block in tool_blocks:
                try:
                    logger.debug(
                        f"Calling tool {block.name} | input: "
                        f"{json.dumps(block.input, ensure_ascii=False)}"
                    )
                    raw = self._executor.execute(block.name, block.input)
                    result_content = json.dumps(raw, default=str, ensure_ascii=False)
                    tool_results_summary.append({"tool": block.name, "input": block.input, "result": raw})
                    logger.info(f"Tool {block.name} → {result_content[:200]}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_content
                    })
                except Exception as e:
                    logger.error(f"Tool {block.name} failed: {e}")
                    had_error = True
                    break

            if had_error:
                break

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        self._repo.delete(self._user_id)
        return {
            "text": self._synthesize(original_message, tool_results_summary),
            "images": self._collect_images(tool_results_summary),
        }

    def handle(self, user_message: str) -> str:
        """
        Process a user message and return the final Spanish response.

        Args:
            user_message: Raw text from the user

        Returns:
            Alfred-style Spanish response string
        """
        # ── Pending plan check ─────────────────────────────────────────────────────
        plan = self._repo.get_active(self._user_id)
        if plan:
            if self._is_plan_reply(user_message, plan["question"]):
                return self._resume_plan(plan, user_message)
            else:
                self._repo.delete(self._user_id)
                # Fall through to normal handling
        # ───────────────────────────────────────────────────────────────────────────

        messages = [{"role": "user", "content": user_message}]
        tool_results_summary = []

        for iteration in range(_MAX_ITERATIONS):
            response = self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=_planner_system(),
                tools=ALL_TOOLS,
                messages=messages
            )

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
                    return {"text": self._ask_user(block.input["question"]), "images": []}
                try:
                    logger.debug(
                        f"Calling tool {block.name} | input: "
                        f"{json.dumps(block.input, ensure_ascii=False)}"
                    )
                    raw = self._executor.execute(block.name, block.input)
                    result_content = json.dumps(raw, default=str, ensure_ascii=False)
                    tool_results_summary.append({
                        "tool": block.name,
                        "input": block.input,
                        "result": raw
                    })
                    logger.info(f"Tool {block.name} → {result_content[:200]}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_content
                    })
                except Exception as e:
                    logger.error(f"Tool {block.name} failed: {e}")
                    had_error = True
                    # On tool error, break out of the loop immediately
                    # so synthesis can handle graceful degradation
                    break

            if had_error:
                break

            # Add assistant turn + tool results to messages
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        return {
            "text": self._synthesize(user_message, tool_results_summary),
            "images": self._collect_images(tool_results_summary),
        }

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
                f"Hoy es {date.today().isoformat()}.\n"
                f"El usuario preguntó: {user_message}\n\n"
                f"Datos recogidos:\n{context}\n\n"
                f"Responde al usuario en español, de forma concisa y útil."
            )
        else:
            synthesis_prompt = f"Hoy es {date.today().isoformat()}.\n{user_message}"

        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=_ALFRED_SYSTEM,
            messages=[{"role": "user", "content": synthesis_prompt}]
        )
        return response.content[0].text.strip()

    def _ask_user(self, question: str) -> str:
        """Have Alfred ask the user for clarification in his characteristic style."""
        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            system=_ALFRED_SYSTEM,
            messages=[{"role": "user", "content": f"Necesito preguntarle esto al usuario: {question}"}]
        )
        return response.content[0].text.strip()
