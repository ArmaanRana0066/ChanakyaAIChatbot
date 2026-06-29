"""
Multi-provider failover for the chat answer.

When one provider's free quota is exhausted (HTTP 429) or it errors, we automatically
fall back to the next provider in the chain — WITHOUT losing conversation context, because
the full message history + system prompt (incl. RAG grounding) is passed to whichever
provider answers.

Chain order (a provider is included only if its API key is set in the environment):
  1. Gemini  gemini-2.5-flash   (GEMINI_API_KEY)
  2. Gemini  gemini-2.0-flash   (GEMINI_API_KEY)      <- separate quota, same key
  3. Groq    llama-3.3-70b      (GROQ_API_KEY)        <- free, no card
  4. OpenRouter (free model)    (OPENROUTER_API_KEY)  <- free, no card
  5. Mistral mistral-small      (MISTRAL_API_KEY)

All non-Gemini providers use the OpenAI-compatible /chat/completions streaming format,
so one adapter covers Groq, OpenRouter and Mistral.

Fallback only happens BEFORE any text has streamed to the client (e.g. on a 429 at connect
time). Once a provider starts streaming successfully, we stay with it.
"""

import json
import os

import httpx

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class ProviderUnavailable(Exception):
    """Raised when a provider is rate-limited or errors before streaming starts."""


def build_chain() -> list[dict]:
    """Build the ordered provider chain from whatever keys are present (read fresh each call).

    Priority: Groq first (fast + generous free tier), then Gemini as fallback, then the rest.
    """
    chain: list[dict] = []

    groq = os.getenv("GROQ_API_KEY", "").strip()
    if groq:
        chain.append({
            "name": "groq", "type": "openai", "key": groq,
            "base_url": "https://api.groq.com/openai/v1",
            "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        })

    gem = os.getenv("GEMINI_API_KEY", "").strip()
    if gem:
        primary = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        chain.append({"name": f"gemini:{primary}", "type": "gemini", "key": gem, "model": primary})
        # A second Gemini model (separate daily quota) before leaving the provider.
        if "2.0-flash" not in primary:
            chain.append({"name": "gemini:2.0-flash", "type": "gemini", "key": gem, "model": "gemini-2.0-flash"})

    oro = os.getenv("OPENROUTER_API_KEY", "").strip()
    if oro:
        chain.append({
            "name": "openrouter", "type": "openai", "key": oro,
            "base_url": "https://openrouter.ai/api/v1",
            "model": os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
        })

    mistral = os.getenv("MISTRAL_API_KEY", "").strip()
    if mistral:
        chain.append({
            "name": "mistral", "type": "openai", "key": mistral,
            "base_url": "https://api.mistral.ai/v1",
            "model": os.getenv("MISTRAL_MODEL", "mistral-small-latest"),
        })

    return chain


def active_provider_names() -> list[str]:
    return [c["name"] for c in build_chain()]


def _needs_thinking_off(model: str) -> bool:
    # Only 2.5 / 3.x Gemini models "think"; passing thinkingConfig to 2.0 can 400.
    return "2.5" in model or "gemini-3" in model


async def _gemini_stream(cfg: dict, system_text: str, messages: list[dict]):
    url = f"{GEMINI_URL}/{cfg['model']}:streamGenerateContent?alt=sse&key={cfg['key']}"
    contents = []
    for m in messages:
        text = (m.get("text") or "").strip()
        if not text:
            continue
        contents.append({"role": "model" if m["role"] == "model" else "user", "parts": [{"text": text}]})
    gen_cfg = {"temperature": 0.7, "maxOutputTokens": 2048}
    if _needs_thinking_off(cfg["model"]):
        gen_cfg["thinkingConfig"] = {"thinkingBudget": 0}
    body = {
        "system_instruction": {"parts": [{"text": system_text}]},
        "contents": contents,
        "generationConfig": gen_cfg,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, json=body, headers={"Content-Type": "application/json"}) as resp:
            if resp.status_code != 200:
                await resp.aread()
                raise ProviderUnavailable(f"{cfg['name']} HTTP {resp.status_code}")
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                    for p in obj["candidates"][0]["content"]["parts"]:
                        if "text" in p:
                            yield p["text"]
                except (KeyError, IndexError, json.JSONDecodeError):
                    continue


async def _openai_stream(cfg: dict, system_text: str, messages: list[dict]):
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    msgs = [{"role": "system", "content": system_text}]
    for m in messages:
        text = (m.get("text") or "").strip()
        if not text:
            continue
        msgs.append({"role": "assistant" if m["role"] == "model" else "user", "content": text})
    body = {"model": cfg["model"], "messages": msgs, "stream": True, "temperature": 0.7, "max_tokens": 2048}
    headers = {"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"}
    if cfg["name"] == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/ArmaanRana0066/ChanakyaAIChatbot"
        headers["X-Title"] = "Chanakya AI"
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, json=body, headers=headers) as resp:
            if resp.status_code != 200:
                await resp.aread()
                raise ProviderUnavailable(f"{cfg['name']} HTTP {resp.status_code}")
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                    delta = obj["choices"][0]["delta"].get("content")
                    if delta:
                        yield delta
                except (KeyError, IndexError, json.JSONDecodeError):
                    continue


async def stream_with_fallback(system_text: str, messages: list[dict]):
    """Yield answer text, walking the provider chain until one succeeds."""
    chain = build_chain()
    if not chain:
        yield "[error] No AI provider keys configured. Set GEMINI_API_KEY (and optionally GROQ_API_KEY, OPENROUTER_API_KEY, MISTRAL_API_KEY)."
        return

    errors = []
    for cfg in chain:
        stream = _gemini_stream if cfg["type"] == "gemini" else _openai_stream
        started = False
        try:
            async for chunk in stream(cfg, system_text, messages):
                started = True
                yield chunk
            return  # provider finished cleanly
        except ProviderUnavailable as e:
            errors.append(str(e))
            if started:
                return  # already streamed partial output; cannot switch mid-answer
            continue   # try next provider
        except (httpx.RequestError, Exception) as e:  # noqa: BLE001 - degrade gracefully
            errors.append(f"{cfg['name']}: {e}")
            if started:
                return
            continue

    # Every provider failed (usually all free quotas hit at once).
    only_gemini = all(c["type"] == "gemini" for c in chain)
    tip = (
        " Add a free GROQ_API_KEY (console.groq.com/keys) so the bot can fall back to another "
        "provider when Gemini's quota runs out." if only_gemini else " Try again in a minute."
    )
    yield (
        "🙏 Kshama karein — abhi saare AI providers vyast hain (free quota khatam)." + tip +
        f"\n\n_(debug: {'; '.join(errors)})_"
    )
