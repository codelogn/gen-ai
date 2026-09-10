# gen-ai — Shared AI Memory & RAG Service

A standalone microservice providing AI memory and retrieval-augmented
generation (RAG) capabilities to any REST-capable client — three
interchangeable vector storage backends, a swappable retrieval strategy
(plain semantic search vs. hybrid keyword+semantic), and an admin panel to
configure it all, per registered application.

**New to RAG?** Start with
[docs/00-rag-concepts-primer.md](./docs/00-rag-concepts-primer.md).
**Just want to use it?** See [docs/guides/](./docs/guides/).
**Extending or debugging the code?** See [docs/](./docs/) — the full
index is in [docs/README.md](./docs/README.md).

## Repository layout

```
backend/     the gen-ai service itself (FastAPI, Postgres, admin UI)
examples/    a dockerized reference chat client that consumes gen-ai's REST API
docs/        architecture docs, usage guides, and a RAG concepts primer
```

## Quickstart (local dev)

```bash
cd backend
./scripts/setup.sh        # venv, deps, .env with generated secrets, Postgres role/db,
                           # pgvector extension, migrations, optional admin seed

./venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8020
# or, to run it as a persistent, auto-restarting systemd service instead:
./scripts/install_systemd.sh
```

Then open `http://localhost:8020/admin/ui/login` and follow
[docs/guides/admin-panel-guide.md](./docs/guides/admin-panel-guide.md) to
register your first application and issue it an API key.

### If you want the `qdrant` vector backend

`sqlite_vec` and `pgvector` need no extra setup beyond `setup.sh` above.
Qdrant is a separate server process — install it with:

```bash
cd backend
./scripts/install_qdrant.sh
```

### Trying the example chat clients

Two reference implementations of the same gen-ai integration — same
features (chat, conversation history, document upload/RAG), different
stacks, both independent and safe to run at once:

```bash
# Python (FastAPI + vanilla JS) — http://localhost:8080
cd examples/chat-client-python
./scripts/register_app.sh          # registers this example with gen-ai, writes .env
docker compose up --build

# Java (Spring Boot 3 + React) — http://localhost:8081
cd examples/chat-client-java
./scripts/register_app.sh
docker compose up --build
```

See [docs/guides/using-the-example-chat-client.md](./docs/guides/using-the-example-chat-client.md)
for what to actually do with the Python client once it's running, and
[examples/chat-client-python/README.md](./examples/chat-client-python/README.md) /
[examples/chat-client-java/README.md](./examples/chat-client-java/README.md)
for setup details (both need Ollama running locally with a chat model pulled).

## Prerequisites

- Python 3.12
- PostgreSQL 16 (running locally or reachable — `setup.sh` creates the
  role/database for you if it can reach Postgres as the `postgres`
  superuser)
- [Ollama](https://ollama.com) if using the default `ollama` embedding
  provider — pull an embedding model, e.g. `ollama pull nomic-embed-text`
- Docker, only if you want to run the example chat client
