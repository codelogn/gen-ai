# The example chat client (Java), walked through

This documents the **Spring Boot 3 + Java 21 + React** implementation —
the Java sibling of [14-example-chat-client.md](./14-example-chat-client.md)'s
Python/FastAPI client. Same purpose (exercise gen-ai's REST API end to
end with a real, working RAG chat app), same feature set (multi-turn
conversations, document upload/RAG, long-term semantic recall), same
integration surface (nothing but the public contract in
[08-api-reference.md](./08-api-reference.md)) — different stack, so the
two can be read side by side to see how the same integration looks in
each language.

## What it is

A Spring Boot backend (`examples/chat-client-java/backend/`) using
Postgres for local bookkeeping (the Python client uses SQLite for the
same role — a dedicated container here instead of a file, since that was
the explicit choice for this implementation) + a Vite/React frontend
(`examples/chat-client-java/frontend/`), each in their own Docker
container, plus a third container for that Postgres instance.

## The RAG loop is identical logic, different implementation

`RagChatService.sendMessage()` is a literal 5-step port of the Python
client's `send_message`: persist the user's message (gen-ai first, then
locally) → build context (a `Pageable`-limited recency-window query
against Postgres, plus two independent gen-ai semantic searches over the
`"messages"` and `"documents"` namespaces) → generate a reply → persist
the reply the same dual way. `SystemPromptBuilder` mirrors
`_build_system_prompt` line for line, including deduping semantic
message-hits against the recency window's own content.

**Spring AI's `ChatClient` genuinely simplifies one thing over Python**:
`ChatClientConfig` builds a single `ChatClient` at startup from whichever
provider (`OllamaChatModel`/`OpenAiChatModel`) `chat-client.provider`
selects — a Java 21 `switch` expression, done once, not per request. From
there, `chatClient.prompt().system(...).user(...).call().content()`
normalizes both providers' very different wire formats behind one call;
the Python client's `chat_llm.py` has to manually branch on provider and
parse each one's differently-shaped response.

## Three real bugs, found by actually running it — not by code review

All three were caught because this was verified against real containers
talking to a real gen-ai instance and a real Ollama, the same bar
`docs/14`'s Python client was held to. Each is a genuine interoperability
lesson, not a typo:

1. **Spring AI's OpenAI autoconfiguration validates its API key EAGERLY,
   at context-startup bean creation — not lazily at call time.** The
   original design assumed (reasonably, but wrongly) that an unset
   `spring.ai.openai.api-key` would only matter if the app actually tried
   to call OpenAI. In fact, `OpenAiChatAutoConfiguration`'s `openAiApi()`
   bean method calls `Assert.hasText(apiKey, ...)` directly, so the
   *entire application* fails to start under `provider=ollama` with no
   OpenAI key configured, even though nothing would ever call OpenAI.
   Fixed with a non-blank placeholder default
   (`spring.ai.openai.api-key: ${CHAT_LLM_API_KEY:not-configured}`) so
   the bean can construct regardless of provider — it only matters, and
   correctly fails at OpenAI's own API rather than at Spring startup, if
   `provider` is actually switched to `openai` without a real key.
   **A second layer to this bug**: the first fix alone didn't work,
   because `docker-compose.yml` was passing `CHAT_LLM_API_KEY` through as
   an *empty string* (`${CHAT_LLM_API_KEY:-}`) rather than leaving it
   genuinely unset — and Spring's `${VAR:default}` placeholder syntax
   only falls back to `default` when a property is entirely **absent**,
   not when it's present-but-empty. The actual fix had to move to the
   compose layer (`${CHAT_LLM_API_KEY:-not-configured}`, using shell/
   compose's own `:-` semantics, which *do* treat empty-as-unset) —
   two different "default" mechanisms with two different empty-string
   behaviors, stacked on top of each other.

2. **The JDK's built-in `java.net.http.HttpClient` (Spring's `RestClient`
   default backing client) probes for an HTTP/2 cleartext ("h2c") upgrade
   by default.** uvicorn (gen-ai's server) doesn't support that upgrade
   and rejects the probe outright — visible in gen-ai's own logs as
   `WARNING: Unsupported upgrade request.` / `WARNING: Invalid HTTP
   request received.` — which surfaced in the Java client as a bogus
   `400 Bad Request: "Invalid HTTP request received."` before any real
   request was even processed. Fixed in `GenAiClient` by explicitly
   pinning the underlying `HttpClient` to `HTTP_1_1`
   (`HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1)`,
   wrapped via `JdkClientHttpRequestFactory`). Worth knowing generically:
   any Java HTTP client talking to a plain HTTP/1.1 ASGI server should
   expect this same interop wrinkle.

3. **`RestClient.builder()` called directly builds its own default
   Jackson `ObjectMapper` — it does NOT inherit
   `spring.jackson.property-naming-strategy: SNAKE_CASE`
   (`application.yml`), even though that property is set globally for
   the application.** The symptom was silent and easy to miss: every
   memory this client wrote to gen-ai came back with `subject_id: null`
   in gen-ai's own data — the field wrote fine as far as HTTP status
   codes were concerned (`201 Created`), but `"subjectId"` was being
   serialized literally instead of translated to `"subject_id"`, so
   gen-ai received a request with no recognized `subject_id` key and
   silently defaulted it to null. This broke `subject_id`-scoped semantic
   search entirely — document RAG and long-term recall would have
   appeared to "not work" with no error anywhere, the response would just
   quietly not be grounded in anything. Fixed by injecting Spring Boot's
   auto-configured `RestClient.Builder` bean into `GenAiClient`'s
   constructor instead of calling the static `RestClient.builder()`
   factory — the injected builder carries the application's actual
   configured `ObjectMapper`, fixing the naming strategy for every DTO
   field project-wide, not just this one. **The general lesson**: always
   inject `RestClient.Builder` in a Spring Boot app rather than calling
   `RestClient.builder()` directly, specifically so it inherits the
   app's message-converter/Jackson customizations rather than a fresh,
   unconfigured default.

## Docker networking: the Postgres wrinkle

The Python client's backend needs `network_mode: host` because gen-ai and
Ollama are both loopback-bound, and `host.docker.internal` cannot reach a
`127.0.0.1`-bound service on Linux (see
[14-example-chat-client.md](./14-example-chat-client.md) and the Python
client's own `docker-compose.yml`). The Java client's backend has the
same requirement, plus a wrinkle Python didn't have: it also needs to
reach its own Postgres container — but `network_mode: host` is exclusive
of joining any other compose network, so it cannot resolve a `postgres`
service-name via Docker's embedded DNS.

**Resolution**: Postgres publishes its port to the host loopback interface
(`127.0.0.1:5434:5432` — `5434` chosen to avoid both the standard `5432`
and gen-ai's own dev-Postgres `5433`, following the exact same
published-port idiom `database/docker-compose.yml` already uses), and the
host-networked backend reaches it the same way it reaches gen-ai and
Ollama: as a plain `127.0.0.1:<port>` peer, not via compose DNS. JDBC URL:
`jdbc:postgresql://127.0.0.1:5434/chatclient_java`. Verified for real:
Flyway's own startup log shows it connecting and migrating through
exactly this URL, and every message/upload written during testing landed
correctly in that Postgres instance (confirmed via direct `psql` queries
against the running container).

## Verified, not just designed

All of the following were run against real containers (`docker compose up
--build`), a real gen-ai instance, and a real local Ollama, exactly
matching `docs/14`'s own acceptance bar:

1. **Basic RAG loop**: created a conversation, sent a message with no
   prior context, got a real generated reply back, confirmed both the
   user message and the assistant reply landed in gen-ai (`subject_id`
   correctly set, per bug #3 above) and in the local Postgres `messages`
   table.
2. **Document RAG**: uploaded a `.txt` file containing an invented policy
   (a "Zylophone Accord" data-retention rule, invented specifically so
   the answer couldn't come from the model's own training), asked a
   question only answerable from it, got back the correct fabricated
   details — proving the upload → chunk → embed → search → answer path
   works end to end.
3. **Long-term conversation memory**: stated a fact ("my favorite
   programming language is Rust"), sent seven unrelated filler messages
   (pushing it outside the 6-message recency window), then asked "what
   programming language did I say I liked earlier?" — answered correctly,
   sourced from gen-ai's semantic search over the `"messages"` namespace,
   not local short-term context.
4. **The actual React UI**, via a real headless-Chrome browser session
   (not just the REST API): created a conversation, sent a message, saw
   the real reply rendered; uploaded a document through the file-upload
   control, saw the "N chunks" summary update, asked a document-grounded
   question, saw the correctly-grounded reply rendered in the chat.
5. **Both example clients running simultaneously** against the same
   gen-ai instance (Python on 9000/8080, Java on 9001/8081) — confirmed
   no port conflicts, and confirmed complete data isolation via gen-ai's
   admin panel (two distinct `application` records, `example-chat-client`
   and `example-chat-client-java`) and each client's own `GET
   /conversations` only ever showing its own data.

## What's intentionally out of scope

Same disclaimers as the Python client: no PDF parsing (`.txt`/`.md`
only), no auth on the example's own endpoints, no admin-configurable
behavior in the example itself (chat provider is a plain environment
variable, not a dropdown — that sophistication belongs to gen-ai, which
this is a consumer of).
