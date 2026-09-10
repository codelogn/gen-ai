# gen-ai example chat client (Java)

The Java sibling of [../chat-client-python/](../chat-client-python/) — the
same reference/test consumer (multi-turn conversations, RAG over uploaded
documents, long-term semantic recall) exercising gen-ai's REST API end to
end, built with **Spring Boot 3, Java 21, and React** instead of FastAPI
and vanilla JS. Not a production app, not tied to any specific external
system. See [../../docs/18-chat-client-java.md](../../docs/18-chat-client-java.md)
for the full architecture walkthrough, including three real interop bugs
found and fixed while building this (an eager Spring AI bean-validation
failure, a JDK HTTP/2-upgrade incompatibility with gen-ai's server, and a
Jackson naming-strategy gap that silently broke request scoping).

## Prerequisites

1. **gen-ai must already be running** — this example does not bundle it.
   Follow gen-ai's own setup (`../../backend/scripts/setup.sh`).
2. **Ollama running locally** with a chat-capable model pulled (separate
   from gen-ai's own embedding provider):
   ```bash
   ollama pull llama3.2
   ```
3. **Docker + Docker Compose**, to run the example as three containers
   (Postgres, backend, frontend).
4. For local (non-Docker) development only: **JDK 21 + Maven**, and
   **Node 20+**.

## Run it

```bash
cp .env.example .env
./scripts/register_app.sh          # registers this example with gen-ai and
                                    # writes a working API key into .env —
                                    # prompts for your gen-ai admin login
docker compose up --build
```

`register_app.sh` registers a gen-ai application with the distinct slug
`example-chat-client-java` — separate from the Python client's
`example-chat-client`, so the two examples' data never mix even though
both use the same `"messages"`/`"documents"` namespace *names* (gen-ai
scopes all memories per-application). Safe to run alongside the Python
client at the same time; see the ports table below.

Open **http://localhost:8081** for the chat UI. The backend API is on
**http://localhost:9001**.

## Local dev loop (without Docker for the app itself)

```bash
# Postgres still needs to be running — the easiest way:
docker compose up postgres -d

cd backend
mvn spring-boot:run   # reads the same env vars from your shell/.env

# in another terminal
cd frontend
npm install
VITE_API_BASE=http://localhost:9001 npm run dev   # hot reload on :8081
```

## Ports

| Service | Port | Notes |
|---|---|---|
| Java backend | `9001` | Distinct from the Python client's `9000` — both can run at once. |
| Java frontend | `8081` | Distinct from the Python client's `8080`. |
| This example's own Postgres | `5434` | Published to `127.0.0.1` only — see networking note below. |
| gen-ai / Ollama | `8020` / `11434` | Unchanged, shared by both example clients. |

## `.env`

```
GENAI_API_URL=http://127.0.0.1:8020
GENAI_API_KEY=gak_...                 # written by register_app.sh
CHAT_LLM_PROVIDER=ollama
CHAT_LLM_MODEL=llama3.2
CHAT_LLM_BASE_URL=http://127.0.0.1:11434
POSTGRES_USER=chatclient
POSTGRES_PASSWORD=...                 # pick a real one
POSTGRES_DB=chatclient_java
POSTGRES_PORT=5434
```

### Why the backend needs `network_mode: host`, and what that means for Postgres

Same root cause as the Python client: gen-ai and Ollama are both bound to
`127.0.0.1` only, and `host.docker.internal` cannot reach a loopback-bound
service on Linux — `network_mode: host` makes `127.0.0.1` inside the
backend container mean the same thing as on the host.

This example adds a wrinkle the Python one doesn't have: its own Postgres
container. `network_mode: host` is exclusive of joining any other compose
network, so the backend **cannot** resolve a `postgres` service-name via
Docker's embedded DNS. The fix: Postgres publishes its port straight to
the host's loopback interface (`127.0.0.1:5434:5432`), and the backend
reaches it exactly the way it reaches gen-ai and Ollama — as a plain
`127.0.0.1:<port>` peer, not via compose DNS. See
[../../docs/18-chat-client-java.md](../../docs/18-chat-client-java.md)
for the full reasoning.

## What it demonstrates

- **Document RAG**: upload a `.txt`/`.md` file, ask a question only
  answerable from its content.
- **Long-term conversation memory**: mention a fact, have several
  unrelated exchanges, then ask about it again — the answer comes from
  gen-ai's semantic search, not the recency window.
- **Chunking as an ingestion-side concern**: this backend chunks
  documents before sending them to gen-ai (`TextChunker`, a literal port
  of the Python client's `chunk_text`) — gen-ai itself imposes none.
- **Spring AI's `ChatClient`** unifying Ollama and OpenAI chat completion
  behind one call — contrast with the Python client's `chat_llm.py`,
  which hand-rolls a separate HTTP call and response parser per provider.

## What it is not

Same disclaimers as the Python client: no tool-calling/agentic behavior
(a plain retrieve-then-generate loop), not production-hardened (no auth
on the example's own endpoints, no rate limiting), and no admin-
configurable behavior of its own (chat provider is a plain environment
variable — that sophistication belongs to gen-ai, which this is a
consumer of).
