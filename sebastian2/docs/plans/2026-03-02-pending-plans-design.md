# Pending Plans — Design

**Date:** 2026-03-02
**Status:** Approved

## Problem

When the Orchestrator lacks a required input to complete a task, it asks the user via Alfred. However, the user's follow-up answer is treated as a brand-new independent query, losing all context. The user must rephrase the entire original request.

**Example:**
- User: "¿debo llevar paraguas a pilates?"
- Bot: "¿En qué ciudad tienes pilates?"
- User: "Madrid"
- Bot: treats "Madrid" as a new query → fails

## Solution

A persistent "pending plan" system. When the Orchestrator needs a missing input it cannot resolve via other tools, it saves the full Haiku loop state to the DB, asks the user for the missing data, and resumes execution when the answer arrives.

## Approach

**Approach B — Clarification tool.** Minimal changes to the existing tool-use loop. A single new tool `request_clarification` is added; the Orchestrator detects it by name and triggers the pending plan save. All other tools and the Haiku loop remain unchanged.

## Data Layer

New table: `pending_plans` (migration `007_pending_plans.sql`).

```sql
CREATE TABLE pending_plans (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    user_id          TEXT NOT NULL,
    original_message TEXT NOT NULL,
    messages_json    LONGTEXT NOT NULL,
    question         TEXT NOT NULL,
    missing_field    TEXT,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at       DATETIME NOT NULL
);
```

- `messages_json`: the full Haiku messages array at the point `request_clarification` was called, including the assistant turn containing the call. Allows exact loop resumption.
- `expires_at`: `created_at + 24h`. Only one open plan per user at a time.

## New Tool: `request_clarification`

Added to `core/tools/clarification_tools.py`, included in `ALL_TOOLS`.

```python
{
    "name": "request_clarification",
    "description": (
        "Llama a esta herramienta cuando necesitas un dato del usuario para completar "
        "la tarea y ese dato no está en el mensaje original ni puede obtenerse de otras "
        "herramientas. Úsala como último recurso."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "question":      {"type": "string"},
            "missing_field": {"type": "string"}
        },
        "required": ["question", "missing_field"]
    }
}
```

## Orchestrator Changes

### Start of `handle()` — check for open plan

```
plan = db.query pending_plans WHERE user_id AND expires_at > NOW()

if plan:
    mini Haiku call:
        "Plan abierto: preguntaste '{plan.question}'. Usuario responde: '{user_message}'. ¿Es respuesta al plan o nueva orden?"

    if → respuesta al plan:
        messages = deserialize(plan.messages_json)
        append tool_result for request_clarification with user_message
        continue loop from here

    if → nueva orden:
        delete plan
        proceed with normal flow

else:
    normal flow (current behavior unchanged)
```

### During tool loop — detect `request_clarification`

```
if block.name == "request_clarification":
    messages.append({"role": "assistant", "content": response.content})
    db.upsert pending_plans (user_id, original_message, messages_json, question, missing_field, expires_at)
    return alfred_ask(block.input["question"])   # Alfred reformulates in his style
```

### On plan completion

When the loop finishes without `request_clarification`:
```
db.delete pending_plans WHERE user_id
```

## Bot Handler Changes

### `/abort` command

```python
@bot.message_handler(commands=['abort'])
def handle_abort(message):
    deleted = db.execute("DELETE FROM pending_plans WHERE user_id = ?", user_id)
    if deleted.rowcount > 0:
        bot.reply_to(message, "Plan cancelado, señor.")
    else:
        bot.reply_to(message, "No hay ningún plan pendiente.")
```

### Bot startup cleanup

In `sebastian_bot.py`, before `bot.infinity_polling()`:

```python
db.execute("DELETE FROM pending_plans")  # clear all plans on restart
```

## Plan Lifecycle

Three triggers that terminate an open plan:

| Trigger | Mechanism |
|---|---|
| User sends `/abort` | Handler deletes row |
| 24h TTL expires | Row found expired at next access → ignored/deleted |
| Bot restarts | Startup cleanup deletes all rows |

## Testing

- `test_pending_plans.py` with in-memory SQLite
- Test: no open plan → normal flow unchanged
- Test: `request_clarification` called → plan saved, question returned
- Test: resume flow → tool_result injected, loop continues
- Test: Haiku decides new order → plan deleted, fresh flow
- Test: `/abort` with and without open plan
- Test: expired plan treated as no plan
