from __future__ import annotations

from app.config import settings

_PROVIDER_DEFAULTS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-20241022",
    "gemini": "gemini-1.5-flash",
    "openrouter": "openai/gpt-4o-mini",
}


class AIClientError(Exception):
    pass


async def _call_openai(model: str, prompt: str, content: str) -> str:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": content},
            ],
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        raise AIClientError(f"openai: {exc}") from exc


async def _call_anthropic(model: str, prompt: str, content: str) -> str:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        msg = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=prompt,
            messages=[{"role": "user", "content": content}],
        )
        return msg.content[0].text
    except Exception as exc:
        raise AIClientError(f"anthropic: {exc}") from exc


async def _call_gemini(model: str, prompt: str, content: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    try:
        model_obj = genai.GenerativeModel(model, system_instruction=prompt)
        resp = await model_obj.generate_content_async(content)
        return resp.text
    except Exception as exc:
        raise AIClientError(f"gemini: {exc}") from exc


async def _call_openrouter(model: str, prompt: str, content: str) -> str:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": content},
            ],
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        raise AIClientError(f"openrouter: {exc}") from exc


_DISPATCH = {
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "gemini": _call_gemini,
    "openrouter": _call_openrouter,
}


async def complete(prompt: str, content: str) -> str:
    provider = settings.ai_provider
    model = settings.ai_model or _PROVIDER_DEFAULTS[provider]
    return await _DISPATCH[provider](model, prompt, content)
