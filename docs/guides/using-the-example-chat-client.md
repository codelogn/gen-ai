# Using the example chat client (Python)

This walks through actually *using* the Python example chat app at
`examples/chat-client-python/` — starting it, having a conversation, uploading a
document, and seeing what makes it different from a plain chatbot. If
you're looking for how it's *built* instead, see
[../14-example-chat-client.md](../14-example-chat-client.md).

A second, functionally-equivalent implementation exists in Spring Boot 3
+ Java 21 + React at `examples/chat-client-java/` — the setup steps and
UI are close enough to this walkthrough that
[examples/chat-client-java/README.md](../../examples/chat-client-java/README.md)
covers using it directly rather than duplicating this whole guide.

## Before you start

You need three things running:

1. **gen-ai itself**, with an application already registered for this
   example and an API key issued. The easy way: run
   `examples/chat-client-python/scripts/register_app.sh` — it prompts for your
   gen-ai admin login and writes a working key straight into `.env`. (The
   manual alternative, if you want to see what that script is doing under
   the hood, is [admin-panel-guide.md](./admin-panel-guide.md) or the
   curl-based recipe in
   [../13-adding-a-consuming-application.md](../13-adding-a-consuming-application.md).)
2. **Ollama**, with a chat-capable model downloaded (`ollama pull
   llama3.2` — this is separate from whatever embedding model gen-ai
   itself uses).
3. **Docker**, to actually run the example.

## Starting it

```bash
cd examples/chat-client-python
cp .env.example .env
# edit .env: paste the API key you issued in step 1 as GENAI_API_KEY
docker compose up --build
```

Once it's running, open **http://localhost:8080** in your browser.

## The interface

A simple two-panel layout: a sidebar on the left listing your
conversations, and the chat window on the right.

Click **+ New conversation** to start one. Type a message and press Enter
(or click Send). The first message you send becomes that conversation's
title in the sidebar automatically.

## Uploading a document

Below the chat window is a small upload bar. Choose a `.txt` or `.md`
file and click **Upload document**. Once it finishes, you'll see the
filename and how many pieces ("chunks") it was split into.

From this point on, you can ask questions about that document's content
in the same conversation, and the assistant will pull in relevant pieces
of it to answer — even though the file's raw text is never included
directly in your message. Try it: upload a document with a fact you know
isn't common knowledge, then ask a question that can only be answered from
that fact.

## What makes this different from a plain chatbot

Two things are worth deliberately noticing while you use it:

**It remembers things you said much earlier, not just recent messages.**
Most simple chatbots only "remember" what fits in the last few messages
you sent. This one is built to also search *everything* you've ever said
in that conversation, by meaning, when it's relevant — not just the
recent ones. To see this in action: mention something specific early in a
conversation (a preference, a name, a fact about yourself), have several
unrelated exchanges after it, then ask about that original thing again.
The assistant should still recall it correctly, even though it's long
scrolled off the visible recent context.

**Uploaded documents and your conversation are searched the same way.**
Under the hood, both your message history and any uploaded documents are
stored as searchable "memories" in gen-ai — the assistant looks through
both every time you send a message, which is why it can casually reference
something from a document you uploaded several messages ago without you
having to re-paste it.

## If something doesn't work

- **"Failed to send message"**: usually means gen-ai or Ollama isn't
  reachable, or the API key in `.env` is wrong/revoked. Check
  `docker compose logs backend` for the actual error.
- **Upload rejected**: only `.txt` and `.md` files are supported in this
  example — PDFs and other formats aren't handled (see
  [../14-example-chat-client.md](../14-example-chat-client.md) for why
  this wasn't built in).
- **The assistant doesn't recall something it should**: check that you're
  still in the *same* conversation — memory here is scoped per
  conversation, not shared globally across all your chats.
