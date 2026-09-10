# Embedding providers

`EmbeddingProviderRegistry` (`app/modules/embeddings/registry.py`) turns
text into vectors — one static method, one branch per provider:

```python
class EmbeddingProviderRegistry:
    @staticmethod
    async def embed(application, texts: list[str]) -> list[list[float]]:
        if application.embedding_provider == "ollama":
            ...  # POST {base_url}/api/embeddings, one call per text
        elif application.embedding_provider == "openai":
            ...  # decrypt embedding_api_key_encrypted, call OpenAI's /embeddings
        else:
            raise ValueError(...)
```

Only two providers, deliberately: Ollama (local, free, no API key —
defaults to `http://localhost:11434`) and OpenAI (cloud, needs a key,
Fernet-encrypted at rest — see
[07-auth-and-api-keys.md](./07-auth-and-api-keys.md)). Chat-only LLM
providers (Anthropic, Google's Gemini chat models) were never real
candidates here — they have no embeddings API.

Every retrieval strategy and every write calls this same registry — the
embedding layer doesn't change based on which storage backend or retrieval
strategy is active for a given application.

## Dimension auto-detection

`embedding_dimension` is never admin-typed. On an application's first
write, `MemoryService._ensure_provisioned()` calls
`EmbeddingProviderRegistry.detect_dimension()`, which embeds a one-word
probe string and measures the resulting vector's length:

```python
@staticmethod
async def detect_dimension(application) -> int:
    vectors = await EmbeddingProviderRegistry.embed(application, ["dimension probe"])
    return len(vectors[0])
```

This value then gates `adapter.provision()` — the vector store is created
with the *correct* width from the start, not a guess. Verified directly:
registering an application with `nomic-embed-text` (Ollama) auto-detected
768; the same flow with a hypothetical 1536-dimension OpenAI model would
detect that instead, with no admin input required either way.

Switching `embedding_model` or `embedding_provider` resets
`embedding_dimension` to `None`, which forces re-detection and
re-provisioning under a new generation — the exact same mechanism as a
`vector_backend` switch (see
[04-vector-store-adapters.md](./04-vector-store-adapters.md)), since a
model change can also change dimension and therefore also invalidates the
existing vector store.
