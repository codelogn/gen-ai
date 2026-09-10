"""Embedding provider abstraction — mirrors a standard provider-factory
pattern: branch on the configured provider, decrypt secrets if needed,
call the right API. See docs/06-embedding-providers.md.
"""

import httpx

from app.core.crypto import decrypt_secret
from app.modules.applications.models import Application, EmbeddingProviderName


class EmbeddingProviderRegistry:
    """Turns an Application's embedding_provider config into actual vectors.

    Every retrieval strategy and every storage adapter's provisioning step
    calls this same registry — the embedding layer doesn't change based on
    which strategy or backend is active for a given application.
    """

    @staticmethod
    async def embed(application: Application, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if application.embedding_provider == EmbeddingProviderName.OLLAMA:
            return await EmbeddingProviderRegistry._embed_ollama(application, texts)
        elif application.embedding_provider == EmbeddingProviderName.OPENAI:
            return await EmbeddingProviderRegistry._embed_openai(application, texts)
        else:
            raise ValueError(f"Unsupported embedding provider: {application.embedding_provider}")

    @staticmethod
    async def _embed_ollama(application: Application, texts: list[str]) -> list[list[float]]:
        base_url = application.embedding_base_url or "http://localhost:11434"
        results: list[list[float]] = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Ollama's /api/embeddings endpoint takes one prompt per call.
            for text in texts:
                resp = await client.post(
                    f"{base_url.rstrip('/')}/api/embeddings",
                    json={"model": application.embedding_model, "prompt": text},
                )
                resp.raise_for_status()
                data = resp.json()
                embedding = data.get("embedding")
                if not embedding:
                    raise ValueError(
                        f"Ollama returned no embedding for model '{application.embedding_model}' "
                        f"— is the model pulled? (ollama pull {application.embedding_model})"
                    )
                results.append(embedding)
        return results

    @staticmethod
    async def _embed_openai(application: Application, texts: list[str]) -> list[list[float]]:
        if not application.embedding_api_key_encrypted:
            raise ValueError(
                f"Application '{application.slug}' has embedding_provider=openai "
                f"but no embedding_api_key is configured."
            )
        api_key = decrypt_secret(application.embedding_api_key_encrypted)
        if api_key is None:
            raise ValueError(
                f"Could not decrypt embedding_api_key for application '{application.slug}' "
                f"— was it encrypted under a different ENCRYPTION_KEY?"
            )

        base_url = (application.embedding_base_url or "https://api.openai.com/v1").rstrip("/")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{base_url}/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": application.embedding_model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
        # OpenAI's /embeddings endpoint returns entries in the same order as input.
        return [item["embedding"] for item in data["data"]]

    @staticmethod
    async def detect_dimension(application: Application) -> int:
        """Probe once at config time, before provisioning the vector
        backend, so it's provisioned with the correct width rather than an
        admin-typed guess."""
        vectors = await EmbeddingProviderRegistry.embed(application, ["dimension probe"])
        return len(vectors[0])
