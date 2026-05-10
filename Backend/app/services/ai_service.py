from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.ai_gamification import AIGamifyDraft, AIGamifyRequest, AIGamifySourceType

# Canonical constants using ASCII-safe unicode escapes.
DEFAULT_ANIME_UNIVERSE = "Jujutsu Kaisen (\u041c\u0430\u0433\u0438\u0447\u0435\u0441\u043a\u0430\u044f \u0411\u0438\u0442\u0432\u0430)"
ANIME_UNIVERSE_HINT = (
    "Jujutsu Kaisen (\u041c\u0430\u0433\u0438\u0447\u0435\u0441\u043a\u0430\u044f \u0411\u0438\u0442\u0432\u0430), "
    "Naruto, Bleach"
)


class AIGamificationError(RuntimeError):
    pass


class AIGamificationDisabledError(AIGamificationError):
    pass


class AIGamificationConfigError(AIGamificationError):
    pass


class AIGatewayError(AIGamificationError):
    pass


class _AIGatewayTransientError(AIGatewayError):
    pass


@dataclass
class AIGamifyGenerationResult:
    draft: AIGamifyDraft
    model: str
    provider: str | None
    usage: dict[str, Any] | None
    latency_ms: int
    raw_response: dict[str, Any]


def ensure_ai_gamification_ready() -> None:
    if not settings.ai_gamification_enabled:
        raise AIGamificationDisabledError("AI gamification is disabled")
    if not settings.openrouter_api_key:
        raise AIGamificationConfigError("OPENROUTER_API_KEY is required when AI gamification is enabled")


def _candidate_models() -> list[str]:
    models: list[str] = []
    if settings.openrouter_model:
        models.append(settings.openrouter_model)
    models.extend(settings.get_openrouter_fallback_models())
    # Keep order but remove duplicates.
    deduped: list[str] = []
    seen: set[str] = set()
    for model in models:
        if model not in seen:
            seen.add(model)
            deduped.append(model)
    if not deduped:
        raise AIGamificationConfigError("No OpenRouter model configured")
    return deduped


def _build_headers() -> dict[str, str]:
    ensure_ai_gamification_ready()
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    if settings.openrouter_site_url:
        headers["HTTP-Referer"] = settings.openrouter_site_url
    if settings.openrouter_app_name:
        headers["X-Title"] = settings.openrouter_app_name
    return headers


def _build_system_prompt() -> str:
    return (
        "You are an instructional designer for first-year university students learning C#. "
        "Your task is to rewrite an existing assignment into an engaging anime-inspired narrative "
        "without changing the assignment semantics. "
        "Return only JSON that matches the requested schema. "
        "Do not include markdown fences. "
        "Hard rules: keep all original logic, constraints, formulas, and every numeric value unchanged; "
        "do not invent new requirements; keep grading-relevant details intact; keep output safe and classroom-appropriate."
    )


def _resolve_anime_universe(constraints: list[str]) -> str:
    joined = " ".join(constraints).lower()
    if "naruto" in joined or "\u043d\u0430\u0440\u0443\u0442\u043e" in joined:
        return "Naruto"
    if "bleach" in joined or "\u0431\u043b\u0438\u0447" in joined:
        return "Bleach"
    if (
        "jujutsu" in joined
        or "\u043c\u0430\u0433\u0438\u0447\u0435\u0441" in joined
        or "\u043c\u0430\u0433. \u0431\u0438\u0442\u0432\u0430" in joined
        or "\u043c\u0430\u0433\u0438\u0447\u0435\u0441\u043a\u0430\u044f \u0431\u0438\u0442\u0432\u0430" in joined
    ):
        return DEFAULT_ANIME_UNIVERSE
    return DEFAULT_ANIME_UNIVERSE


def _build_user_prompt(payload: AIGamifyRequest, source_text: str) -> str:
    constraints = payload.constraints or []
    constraints_text = "\n".join(f"- {item}" for item in constraints) if constraints else "- none"
    anime_universe = _resolve_anime_universe(constraints)
    return (
        "Rewrite the assignment in an anime-gamified style for first-year students.\n"
        "The resulting text must stay equivalent to the original assignment.\n"
        f"Preferred anime universe: {anime_universe}\n"
        f"If no strict preference is provided, use one from: {ANIME_UNIVERSE_HINT}.\n"
        f"source_type: {payload.source_type.value}\n"
        f"target_level: {payload.target_level.value if payload.target_level else 'not_specified'}\n"
        f"language: {payload.language}\n"
        f"style: {payload.style.value if payload.style else 'not_specified'}\n"
        f"tone: {payload.tone.value if payload.tone else 'not_specified'}\n"
        "Non-negotiable invariants:\n"
        "- Preserve every numeric value exactly as in source (counts, limits, points, percentages, deadlines).\n"
        "- Preserve task logic, required output, acceptance criteria, and constraints.\n"
        "- Add only narrative framing, references, and motivational context.\n"
        "- Do not simplify away required checks and do not add hidden assumptions.\n"
        "Output shaping guidance:\n"
        "- story_frame: short anime setup with recognizable references.\n"
        "- task_goal: the rewritten assignment text with preserved logic and all numbers.\n"
        "- game_rules/acceptance_criteria: mirror original rules/validation in concise bullets.\n"
        "constraints:\n"
        f"{constraints_text}\n\n"
        "Source content:\n"
        f"{source_text.strip()}"
    )


def _extract_message_content(message_content: Any) -> str:
    if isinstance(message_content, str):
        return message_content
    if isinstance(message_content, list):
        parts: list[str] = []
        for item in message_content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    if isinstance(message_content, dict):
        text = message_content.get("text") or message_content.get("content")
        if isinstance(text, str):
            return text
    return ""


def _extract_json_payload(content: str) -> dict[str, Any]:
    raw = content.strip()
    if not raw:
        raise AIGatewayError("Empty content from AI provider")

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if fenced:
        data = json.loads(fenced.group(1))
        if isinstance(data, dict):
            return data

    first = raw.find("{")
    last = raw.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidate = raw[first : last + 1]
        data = json.loads(candidate)
        if isinstance(data, dict):
            return data

    raise AIGatewayError("AI response is not valid JSON object")


def _extract_draft_from_response(data: dict[str, Any]) -> AIGamifyDraft:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AIGatewayError("OpenRouter response has no choices")
    first_choice = choices[0] if isinstance(choices[0], dict) else None
    if not first_choice:
        raise AIGatewayError("OpenRouter response choice is malformed")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise AIGatewayError("OpenRouter response message is malformed")

    content = _extract_message_content(message.get("content"))
    payload = _extract_json_payload(content)
    return AIGamifyDraft.model_validate(payload)


async def _request_once(
    client: httpx.AsyncClient,
    payload: AIGamifyRequest,
    source_text: str,
    model: str,
) -> AIGamifyGenerationResult:
    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    request_body = {
        "model": model,
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": _build_system_prompt()},
            {"role": "user", "content": _build_user_prompt(payload, source_text)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "ai_gamify_draft",
                "strict": True,
                "schema": AIGamifyDraft.model_json_schema(),
            },
        },
    }

    started = time.monotonic()
    response = await client.post(url, headers=_build_headers(), json=request_body)
    latency_ms = int((time.monotonic() - started) * 1000)

    if response.status_code == 429 or response.status_code >= 500:
        raise _AIGatewayTransientError(
            f"Transient OpenRouter error status={response.status_code}: {response.text[:300]}"
        )
    if response.status_code >= 400:
        raise AIGatewayError(f"OpenRouter request failed status={response.status_code}: {response.text[:500]}")

    data = response.json()
    draft = _extract_draft_from_response(data)

    provider = data.get("provider") if isinstance(data.get("provider"), str) else None
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else None

    return AIGamifyGenerationResult(
        draft=draft,
        model=model,
        provider=provider,
        usage=usage,
        latency_ms=latency_ms,
        raw_response=data,
    )


async def generate_gamification_draft(
    payload: AIGamifyRequest,
    source_text: str | None = None,
) -> AIGamifyGenerationResult:
    """
    Calls OpenRouter and returns validated gamification draft JSON.
    The caller controls persistence/job state.
    """
    ensure_ai_gamification_ready()

    effective_text = (payload.raw_text or "") if payload.source_type == AIGamifySourceType.RAW_TEXT else (source_text or "")
    if not effective_text or not effective_text.strip():
        raise ValueError("source_text is required for non-raw_text sources")

    models = _candidate_models()
    attempts_per_model = max(1, settings.openrouter_max_retries + 1)
    timeout = httpx.Timeout(float(settings.openrouter_timeout_seconds))
    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=timeout) as client:
        for model in models:
            for attempt in range(attempts_per_model):
                try:
                    return await _request_once(client, payload=payload, source_text=effective_text, model=model)
                except (httpx.TimeoutException, httpx.NetworkError, _AIGatewayTransientError) as exc:
                    last_error = exc
                    if attempt < attempts_per_model - 1:
                        await asyncio.sleep(min(0.5 * (attempt + 1), 2.0))
                        continue
                    break
                except Exception as exc:
                    # Non-transient errors: try fallback model (if any) before failing.
                    last_error = exc
                    break

    raise AIGatewayError(f"Failed to generate AI draft: {last_error}") from last_error
