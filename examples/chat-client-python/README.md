# gen-ai example chat client

A small, real, working chat application built purely to exercise gen-ai's
REST API end to end — conversations with multi-turn memory, and RAG over
uploaded documents. This is a reference/test consumer, not a production
app, and not tied to or modeled after any specific external system. See
[../../docs/14-example-chat-client.md](../../docs/14-example-chat-client.md)
for the full walkthrough of how it works.

## Prerequisites

1. **gen-ai must already be running** — this example does not bundle it.
   Follow gen-ai's own setup (`../../backend/scripts/setup.sh`).

2. **Ollama running locally** with a chat-capable model pulled (the
   example's own LLM calls are separate from gen-ai's embedding provider):
   ```bash
   ollama pull llama3.2
   ```

## Run it

```bash
./scripts/register_app.sh          # registers this example with gen-ai and
                                    # writes a working API key into .env —
                                    # prompts for your gen-ai admin login
docker compose up --build
```

`register_app.sh` is the whole setup step — it replaces manually creating
an application and issuing a key through the admin panel or curl. It's
safe to re-run any time (e.g. if you lose the key — a key can't be viewed
again after issuance, only reissued).

Open http://localhost:8080 for the chat UI. The backend API is on
http://localhost:9000.

### `.env`

```
GENAI_API_URL=http://127.0.0.1:8020
GENAI_API_KEY=gak_...                 # from the gen-ai admin panel
CHAT_LLM_PROVIDER=ollama
CHAT_LLM_MODEL=llama3.2
CHAT_LLM_BASE_URL=http://127.0.0.1:11434
```

**Why `127.0.0.1`, not `host.docker.internal`**: gen-ai and Ollama are both
bound to `127.0.0.1` only, for security. `host.docker.internal` cannot
reach a loopback-bound service on Linux (verified directly during
development — Linux doesn't route loopback-bound traffic across
network-namespace boundaries, even via the Docker bridge gateway). The
backend service in `docker-compose.yml` uses `network_mode: host`
specifically so `127.0.0.1` inside the container means the same thing as
on the host, with no change needed to gen-ai's or Ollama's bind address.

## What it demonstrates

- **Document RAG**: upload a `.txt`/`.md` file, ask a question only
  answerable from its content.
- **Long-term conversation memory**: mention a fact, have several
  unrelated exchanges, then ask about the fact again — the answer comes
  from gen-ai's semantic search, not the recency window, once enough turns
  have passed that the original message would otherwise have been
  forgotten.
- **Chunking as an ingestion-side concern**: this backend chunks uploaded
  documents before sending them to gen-ai — gen-ai itself imposes no
  chunking (see gen-ai's own docs/04, messages/facts don't need it; longer
  documents do, and that decision belongs to whoever is doing the
  ingesting, not the storage service).

## What it is not

Not a demonstration of tool-calling or agentic behavior — this is a plain
RAG loop (retrieve, then generate), no tool use, no multi-step planning.
Not a production chat app — no auth on the example's own endpoints, no
rate limiting, a single flat SQLite file for local bookkeeping. Its job is
to prove gen-ai's REST contract works for a real use case, not to be
deployed anywhere.
