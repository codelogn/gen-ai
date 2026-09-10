"""Thin wrapper over gen-ai's REST API — this is the ENTIRE integration
surface. No gen-ai internals are imported or assumed; this example talks
to it exactly the way any other REST client would, using nothing but the
public contract in docs/08-api-reference.md.
"""

from typing import Optional

import httpx

from app.config import settings


class GenAIClient:
    def __init__(self) -> None:
        self._base_url = settings.GENAI_API_URL.rstrip("/")
        self._headers = {"X-API-Key": settings.GENAI_API_KEY, "Content-Type": "application/json"}

    async def create_memory(
        self, namespace: str, content: str, subject_id: str, metadata: Optional[dict] = None
    ) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base_url}/api/v1/memories",
                headers=self._headers,
                json={
                    "namespace": namespace,
                    "subject_id": subject_id,
                    "content": content,
                    "metadata": metadata,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def create_memories_batch(self, items: list[dict]) -> dict:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self._base_url}/api/v1/memories/batch",
                headers=self._headers,
                json={"items": items},
            )
            resp.raise_for_status()
            return resp.json()

    async def search(
        self, namespace: str, query: str, subject_id: Optional[str] = None, top_k: int = 5
    ) -> list[dict]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base_url}/api/v1/memories/search",
                headers=self._headers,
                json={
                    "namespace": namespace,
                    "subject_id": subject_id,
                    "query": query,
                    "top_k": top_k,
                },
            )
            resp.raise_for_status()
            return resp.json()["results"]


genai_client = GenAIClient()
