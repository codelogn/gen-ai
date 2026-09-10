# Recipe: registering a new consuming application

End-to-end, copy-pasteable. Assumes an admin session (browser cookie or a
JWT from `POST /admin/api/v1/auth/login`).

## 1. Register the application

Via the admin UI: `/admin/ui/applications/new`, fill in the three
dropdowns (a sensible default: `sqlite_vec` + `native` + `ollama` — the
simplest combination, upgradeable later without data loss).

Or via the API:

```bash
curl -X POST http://localhost:8020/admin/api/v1/applications \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{
    "slug": "my-app",
    "display_name": "My Application",
    "vector_backend": "sqlite_vec",
    "retrieval_strategy": "native",
    "embedding_provider": "ollama",
    "embedding_model": "nomic-embed-text"
  }'
```

## 2. Issue an API key

```bash
curl -X POST http://localhost:8020/admin/api/v1/applications/$APP_ID/api-keys \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"label": "production"}'
# {"full_key": "gak_...", ...}  <- copy this now, it is never shown again
```

## 3. First write

```bash
curl -X POST http://localhost:8020/api/v1/memories \
  -H "X-API-Key: gak_..." -H "Content-Type: application/json" \
  -d '{"namespace": "notes", "content": "Hello, gen-ai."}'
```

This triggers dimension auto-detection and backend provisioning
automatically — no separate setup step. Check
`GET /admin/api/v1/applications/$APP_ID` afterward and confirm
`embedding_dimension` is now populated.

## 4. First search

```bash
curl -X POST http://localhost:8020/api/v1/memories/search \
  -H "X-API-Key: gak_..." -H "Content-Type: application/json" \
  -d '{"namespace": "notes", "query": "greeting", "top_k": 5}'
```

## Choosing `namespace` and `subject_id`

`namespace` is yours to define — a reasonable default is one namespace per
*kind* of thing your application stores (e.g. `"messages"` for chat
history, `"documents"` for uploaded files), not one namespace per user.
`subject_id` is the per-entity scope *within* a namespace (a conversation
id, a user id) — pass it on every write and every search to keep one
subject's data from leaking into another's results within the same
namespace.

## What you don't need to build

Chunking, if your content is naturally short (a chat message, a single
fact). If you're ingesting longer documents, chunk them client-side before
calling `POST /memories/batch` — see
[14-example-chat-client.md](./14-example-chat-client.md) for a worked
example of exactly this.
