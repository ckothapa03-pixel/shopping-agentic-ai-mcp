from types import SimpleNamespace
from typing import Any, Callable


class GeminiStreamError(RuntimeError):
    def __init__(self, status_code: int | None = None) -> None:
        super().__init__("Gemini streaming response failed")
        self.status_code = status_code


def field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def output_text_from_steps(steps: list[Any]) -> str:
    text_parts: list[str] = []
    for step in steps:
        if field(step, "type") != "model_output":
            continue
        for content in field(step, "content", []) or []:
            if field(content, "type") == "text":
                text = field(content, "text", "")
                if text:
                    text_parts.append(text)
    return "".join(text_parts)


async def consume_interaction_stream(
    stream: Any,
    on_text_delta: Callable[[str], None],
    on_stage: Callable[[str], None] | None = None,
) -> Any:
    if not hasattr(stream, "__aiter__"):
        return stream

    text_parts: list[str] = []
    completed_interaction = None
    first_event_seen = False
    async for event in stream:
        if not first_event_seen:
            first_event_seen = True
            if on_stage:
                on_stage("first_stream_event_received")
        event_type = field(event, "event_type")
        if event_type == "error":
            error = field(event, "error")
            code = field(error, "code")
            raise GeminiStreamError(code if isinstance(code, int) else None)
        if event_type == "step.delta":
            delta = field(event, "delta")
            if field(delta, "type") == "text":
                text = field(delta, "text", "")
                if text:
                    text_parts.append(text)
                    on_text_delta(text)
        elif event_type == "interaction.completed":
            completed_interaction = field(event, "interaction")

    if completed_interaction is None:
        raise RuntimeError("Gemini streaming response ended before completion")
    if field(completed_interaction, "status") not in (None, "completed"):
        raise RuntimeError("Gemini could not complete the response")
    steps = field(completed_interaction, "steps", []) or []
    answer = "".join(text_parts) or output_text_from_steps(steps)
    if answer and not steps:
        steps = [{"type": "model_output", "content": [{"type": "text", "text": answer}]}]
    return SimpleNamespace(steps=steps, output_text=answer)
