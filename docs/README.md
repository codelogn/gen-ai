# gen-ai — Shared AI Memory & RAG Service

A standalone microservice providing AI memory and retrieval-augmented
generation (RAG) capabilities to any REST-capable client. It is built as
independent infrastructure: no other application's internals, schemas, or
code patterns are assumed — a client integrates by registering as an
"application," getting an API key, and calling the REST API.

This is the first shared-backend service of its kind in this environment —
a service other things call over the network, rather than a self-contained
application. That shapes some of the design defaults documented here: every
seam (storage backend, retrieval strategy) is a real, enforced interface,
and the admin panel's troubleshooting surface is not a nice-to-have, since
it's the only visibility anyone has into a dependency they don't otherwise
see inside.

## Start here if you're new to RAG

[00-rag-concepts-primer.md](./00-rag-concepts-primer.md) explains
embeddings, cosine similarity, hybrid search, and chunking in plain
language, from zero — read this first if those terms are new to you.
Every other doc in this folder assumes you already know them.

## Using the application (no code reading required)

| Guide | What's in it |
|---|---|
| [guides/admin-panel-guide.md](./guides/admin-panel-guide.md) | Step-by-step: logging in, registering an application, issuing API keys, reading usage/logs, running evaluations |
| [guides/using-the-example-chat-client.md](./guides/using-the-example-chat-client.md) | Step-by-step: running the example chat app (Python), uploading documents, seeing long-term memory recall in action |
| [guides/choosing-your-configuration.md](./guides/choosing-your-configuration.md) | Quick decision guide: which vector backend / retrieval strategy / evaluation frameworks to pick |
| [../examples/rag-cookbook/](../examples/rag-cookbook/) | Hands-on, runnable scripts: real embeddings, cosine similarity, and a hand-rolled hybrid-search fix — no gen-ai dependency |

## Architecture & internals (for extending or debugging the code)

| File | What's in it |
|---|---|
| [01-architecture.md](./01-architecture.md) | End-to-end request flow, the two independently-swappable axes (storage, retrieval) |
| [02-multi-tenancy-and-adapters.md](./02-multi-tenancy-and-adapters.md) | The `Application` tenant model, the adapter/port pattern |
| [03-memory-data-model.md](./03-memory-data-model.md) | The generic `memories` table, worked examples, the honest tradeoff |
| [04-vector-store-adapters.md](./04-vector-store-adapters.md) | All three storage backends (SQLite-vec, pgvector, Qdrant), the fresh-start-on-switch policy |
| [05-retrieval-strategies.md](./05-retrieval-strategies.md) | The `RetrievalStrategy` interface, native vs. LangChain hybrid search |
| [06-embedding-providers.md](./06-embedding-providers.md) | Ollama/OpenAI, dimension auto-detection |
| [07-auth-and-api-keys.md](./07-auth-and-api-keys.md) | The two auth realms, the hash-vs-encrypt distinction |
| [08-api-reference.md](./08-api-reference.md) | Every endpoint with example request/response JSON |
| [09-observability-and-troubleshooting.md](./09-observability-and-troubleshooting.md) | Request logs, usage aggregation, a worked debugging walkthrough |
| [10-latest-practices-checklist.md](./10-latest-practices-checklist.md) | API versioning, idempotency, health/readiness, and why each matters here |
| [11-adding-a-vector-store-adapter.md](./11-adding-a-vector-store-adapter.md) | Recipe: add a fourth storage backend |
| [12-adding-a-retrieval-strategy.md](./12-adding-a-retrieval-strategy.md) | Recipe: add a fourth retrieval strategy |
| [13-adding-a-consuming-application.md](./13-adding-a-consuming-application.md) | Recipe: register an app, issue a key, first upsert+search |
| [14-example-chat-client.md](./14-example-chat-client.md) | The dockerized reference consumer (Python/FastAPI), worked end to end |
| [15-evaluation-frameworks.md](./15-evaluation-frameworks.md) | Multi-framework RAG evaluation (native, Ragas, DeepEval), the judge-LLM concept, why it's a fan-out not a switch |
| [16-adding-an-evaluation-framework.md](./16-adding-an-evaluation-framework.md) | Recipe: add a fourth evaluation framework |
| [17-glossary.md](./17-glossary.md) | Every RAG/evaluation term used in these docs, one line each, linked to its full explanation |
| [18-chat-client-java.md](./18-chat-client-java.md) | The same reference consumer, in Spring Boot 3 + Java 21 + React — three real interop bugs found and fixed |

## The one-paragraph version

A consumer registers as an **application** (`POST /admin/api/v1/applications`,
admin-authenticated) choosing three independent things via dropdowns: a
**vector storage backend** (SQLite-vec, pgvector, or Qdrant — where vectors
physically live), a **retrieval strategy** (native cosine search, a
LangChain-based hybrid keyword+vector search, or cross-encoder reranking —
how a query becomes ranked results), and an **embedding provider** (Ollama
or OpenAI — how text becomes vectors). The admin issues that application an API key
(`POST /admin/api/v1/applications/{id}/api-keys` — shown once, stored only
as a hash). From then on the application calls `POST /api/v1/memories` to
store text under a `namespace`+`subject_id` it defines, and
`POST /api/v1/memories/search` to retrieve it by meaning. Every write is
retained in a single control-plane Postgres table (`memories`) regardless
of backend choice — the backend only ever holds the vector, never the
system-of-record content — so switching storage or retrieval strategy later
never risks data loss, only a fresh, empty index until re-upserted.
