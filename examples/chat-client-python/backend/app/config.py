from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # The gen-ai service this example is a reference consumer of. Deliberately
    # NOT bundled into this example's own docker-compose — gen-ai is expected
    # to already be running (see ../../../docs/13-adding-a-consuming-application.md).
    # 127.0.0.1 works both for local (non-Docker) runs and inside the
    # backend container, since docker-compose.yml uses network_mode: host
    # specifically so this doesn't need to change between the two — see
    # docker-compose.yml's comment for why host.docker.internal doesn't work here.
    GENAI_API_URL: str = "http://127.0.0.1:8020"
    GENAI_API_KEY: str = ""

    # Which namespaces this example uses in gen-ai — arbitrary, chosen by
    # this consumer, gen-ai never interprets them.
    MESSAGES_NAMESPACE: str = "messages"
    DOCUMENTS_NAMESPACE: str = "documents"

    # The chat LLM this example itself uses to generate responses — a
    # separate concern from gen-ai's embedding provider. Simple env-var
    # choice, not admin-configurable, since this is a demo client, not infrastructure.
    CHAT_LLM_PROVIDER: str = "ollama"  # or "openai"
    CHAT_LLM_MODEL: str = "llama3.2"
    CHAT_LLM_BASE_URL: str = "http://127.0.0.1:11434"
    CHAT_LLM_API_KEY: str = ""

    # Local SQLite — lightweight bookkeeping only (conversation titles,
    # upload metadata), never chat content itself. That lives in gen-ai.
    LOCAL_DB_PATH: str = "./data/chat_client.db"

    # Recency window: how many recent local messages to include verbatim
    # alongside gen-ai's semantic search results when building LLM context.
    RECENT_MESSAGES_WINDOW: int = 6
    SEMANTIC_SEARCH_TOP_K: int = 4

    # Chunking for uploaded documents
    CHUNK_SIZE_CHARS: int = 500
    CHUNK_OVERLAP_CHARS: int = 50


settings = Settings()
