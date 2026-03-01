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
from utils.config import get_config

_MAX_ITERATIONS = 8


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

    def handle(self, user_message: str) -> str:
        """
        Process a user message and return the final Spanish response.

        Args:
            user_message: Raw text from the user

        Returns:
            Alfred-style Spanish response string
        """
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
                try:
                    raw = self._executor.execute(block.name, block.input)
                    result_content = json.dumps(raw, default=str, ensure_ascii=False)
                    tool_results_summary.append({
                        "tool": block.name,
                        "input": block.input,
                        "result": raw
                    })
                    logger.info(f"Tool {block.name} → {result_content[:150]}")
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

        return self._synthesize(user_message, tool_results_summary)

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
                f"El usuario preguntó: {user_message}\n\n"
                f"Datos recogidos:\n{context}\n\n"
                f"Responde al usuario en español, de forma concisa y útil."
            )
        else:
            synthesis_prompt = user_message

        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=_ALFRED_SYSTEM,
            messages=[{"role": "user", "content": synthesis_prompt}]
        )
        return response.content[0].text.strip()
