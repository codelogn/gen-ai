"""The LLM this example uses to actually generate chat responses — a
separate concern from gen-ai's embedding provider. Plain chat completion,
no tool calling, no agent loop; this example is a RAG-loop demonstration,
not a tool-calling one.
"""

import httpx

from app.config import settings


async def generate_reply(system_prompt: str, user_message: str) -> str:
    if settings.CHAT_LLM_PROVIDER == "ollama":
        return await _generate_ollama(system_prompt, user_message)
    elif settings.CHAT_LLM_PROVIDER == "openai":
        return await _generate_openai(system_prompt, user_message)
    else:
        raise ValueError(f"Unsupported CHAT_LLM_PROVIDER: {settings.CHAT_LLM_PROVIDER}")


async def _generate_ollama(system_prompt: str, user_message: str) -> str:
    base_url = settings.CHAT_LLM_BASE_URL.rstrip("/")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{base_url}/api/chat",
            json={
                "model": settings.CHAT_LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "stream": False,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]


async def _generate_openai(system_prompt: str, user_message: str) -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.CHAT_LLM_API_KEY}"},
            json={
                "model": settings.CHAT_LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
