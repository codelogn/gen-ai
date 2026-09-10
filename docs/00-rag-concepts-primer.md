# RAG concepts, from zero

Read this before [01-architecture.md](./01-architecture.md) if terms like
"embedding," "cosine similarity," or "hybrid search" are new to you. It
explains the ideas in plain language first; every other doc in this folder
assumes you already know them and jumps straight to how *this specific
service* uses them.

## The problem RAG solves

A language model can only "know" what's in its training data plus
whatever text you put directly in its prompt. If you want it to answer
questions about *your* data — a document you just uploaded, a fact a user
told it yesterday — you have to find the relevant piece of text yourself
and paste it into the prompt before asking the question.

**Retrieval-Augmented Generation (RAG)** is the two-step pattern that does
this: **retrieve** the relevant text from somewhere you stored it, then
**generate** an answer by handing the model that text plus the question.
Everything in this service exists to make the "retrieve" half fast and
accurate.

## Embeddings: turning text into a location

An **embedding model** reads a piece of text and outputs a list of
numbers — a vector — that represents its *meaning* as a point in space.
The key property: texts with similar meaning end up at nearby points, even
if they don't share any of the same words.

```
"The user enjoys cooking pasta"     -> [0.12, -0.05, 0.88, ...]   (768 numbers)
"What does the user like to eat?"   -> [0.14, -0.02, 0.81, ...]   (nearby!)
"The user goes hiking on weekends"  -> [-0.30, 0.61, 0.02, ...]   (far away)
```

Two sentences about food end up close together in this space; a sentence
about hiking ends up somewhere else. This is what lets a search work by
*meaning* instead of exact keyword matching — a search for "what does the
user like to eat" can find "enjoys cooking pasta" even though they share
almost no words.

In this codebase: `EmbeddingProviderRegistry.embed()`
(`app/modules/embeddings/registry.py`) is the function that does this,
calling either a local Ollama model or OpenAI's API. See
[06-embedding-providers.md](./06-embedding-providers.md).

## Cosine similarity: measuring "how close"

Once text is turned into vectors, "how similar are these two pieces of
text" becomes a geometry question: how close together are their two
points? **Cosine similarity** is the standard way to measure this — it
looks at the *angle* between two vectors, not their raw distance, which
matters because embedding vectors can have very different magnitudes even
when they point in almost the same direction. The result is a number from
roughly -1 to 1: **1 means "pointing the same direction" (very similar
meaning), 0 means unrelated, negative means opposite.**

A **vector search** (also called nearest-neighbor search) takes a query,
embeds it into the same space, then finds which stored vectors have the
highest cosine similarity to it — those are your most relevant results.

In this codebase: every `VectorStoreAdapter` implementation
(SQLite-vec, pgvector, Qdrant) does exactly this — see
[04-vector-store-adapters.md](./04-vector-store-adapters.md). All three
were verified to produce matching similarity scores on the same data,
because cosine similarity is a well-defined, deterministic calculation.

## Where the vectors live: a "vector database"

You could compute cosine similarity by hand against every stored vector
every time you search, and at small scale that's exactly what happens.
A **vector database** (or a plain database extended with vector support,
like pgvector) exists to make this fast at large scale, using indexing
techniques (like HNSW, used by both the pgvector and Qdrant backends here)
that avoid comparing against *every* stored vector for every query.

This service deliberately supports three different options for "where do
the vectors live" — a local file (SQLite-vec), an extension on a
relational database you already have (pgvector), or a dedicated vector
database server (Qdrant) — because that choice is really about
infrastructure tradeoffs (do you want to run a separate server? how much
data do you have?), not about the RAG concept itself. See
[02-multi-tenancy-and-adapters.md](./02-multi-tenancy-and-adapters.md).

## The limits of pure vector search — and hybrid search

Vector search is powerful but not perfect: it can be fooled by words that
*look* similar but mean different things. A search for "Mercurial" (the
version control tool) can end up ranking a sentence about the *planet*
Mercury above a sentence about *managing source code* — because
"Mercurial" and "Mercury" are close together in embedding space (they
share a root word), even though "managing source code" is the actually
relevant answer and shares no words with the query at all.

**Keyword search** (the classic kind — does this document literally
contain this word?) doesn't have this problem, but has the opposite one:
it can't find "enjoys cooking pasta" from a query like "what does the user
like to eat," since they share no exact words.

**Hybrid search** combines both: run a keyword search and a vector search
on the same query, then merge the two ranked lists (commonly via
*reciprocal rank fusion* — each result's final score depends on how high
it ranked in *each* list, not a raw similarity number). This gets the
precision of keyword matching and the recall of semantic matching at once.

In this codebase: this exact failure mode (Mercurial vs. Mercury) was
reproduced and fixed by switching to hybrid search — see
[05-retrieval-strategies.md](./05-retrieval-strategies.md) for the worked
example with real scores.

## Chunking: what to do with long documents

An embedding model has a limit on how much text it can turn into one
vector meaningfully — and even within that limit, embedding an entire long
document as one vector tends to blur together many different topics into
one point, making it a poor match for specific questions about any one
part of it. **Chunking** means splitting a long document into smaller,
overlapping pieces *before* embedding each one separately, so a search can
find the one paragraph that's actually relevant instead of "the whole
document, vaguely."

A short chat message or a single stored fact doesn't need this — it's
already one coherent unit. A ten-page document does.

In this codebase: gen-ai itself never chunks anything — that's a decision
left to whichever application is sending it data, since different
applications may want different chunk sizes. The example chat client
chunks uploaded documents before sending them; see
[14-example-chat-client.md](./14-example-chat-client.md).

## How do you know if a RAG system is actually good?

Everything above makes retrieval *possible*. None of it tells you whether
retrieval is actually *working well* for your specific data. That needs
**evaluation** — running known queries with known-good answers through the
real system and measuring how close the results come.

There are two genuinely different ways to measure this, needing very
different amounts of machinery:

**Exact-match metrics** (no AI involved) — if you already know exactly
which stored items *should* come back for a given query, you can just
check whether they did, with plain set arithmetic:
- **Precision@k**: of the k results returned, what fraction were actually
  relevant? (Low precision = the search is returning a lot of noise.)
- **Recall@k**: of all the relevant items that exist, what fraction did
  the search actually find? (Low recall = the search is missing things.)
- **MRR (Mean Reciprocal Rank)**: not just *whether* the right answer came
  back, but *how high it ranked* — a relevant result buried at position 10
  is far less useful than one at position 1, even though both count as a
  "hit" for recall.

These require you to already know the ground truth (e.g. "for this query,
memory X is the one correct answer") — cheap and fast to compute, but only
as good as the ground truth you supply, and they can't judge anything
subtler than "was this exact stored item retrieved or not."

**LLM-as-judge metrics** — for the questions exact matching can't answer
at all, like "does this retrieved text actually support this generated
answer, or does the answer contradict it?" (**faithfulness**), or "is the
retrieved context actually relevant to what was asked, even if it's not
one of your pre-labeled 'correct' items?" (**context precision/recall**),
you need something that can *read and reason about* the text — which
means using another language model as a **judge**: you show it the query,
the retrieved text, and (optionally) a generated answer, and ask it to
score how well they fit together.

This is powerful — it can catch subtle relevance and correctness problems
exact-ID matching structurally cannot — but it inherits a real limitation:
**the judge model itself needs to be capable enough to judge reliably.** A
small model that's perfectly adequate for embedding text (which just needs
to represent meaning as a vector) can fail outright at judging, because
judging requires actual structured reasoning, not just representation.
This isn't a theoretical concern — it's a real, observed failure mode in
this codebase, documented with actual numbers in
[15-evaluation-frameworks.md](./15-evaluation-frameworks.md).

Because "does this LLM-as-judge library's opinion match reality" is itself
a real question with no single trusted authority, this service runs
**multiple independent judge frameworks side by side** on request (rather
than picking one and trusting it) — see
[15-evaluation-frameworks.md](./15-evaluation-frameworks.md) for the full
design and a worked example of two frameworks genuinely disagreeing on the
same case.

## Putting it together: the whole loop

```
1. Some text arrives (a chat message, a document chunk, a fact about a user).
2. An embedding model turns it into a vector.                    [embeddings]
3. The vector is stored, alongside the original text.            [vector database]
4. Later, a query arrives ("what does the user like to eat").
5. The query is embedded into the same vector space.
6. The stored vectors are searched for the closest matches
   (optionally combined with keyword search).                    [cosine similarity / hybrid search]
7. The matching original text is retrieved and handed to a
   language model, along with the question, to generate an answer.  [the "generation" in RAG]
```

Every doc after this one is about how gen-ai implements each of these
steps as swappable, admin-configurable pieces — but the steps themselves
are the same seven steps described above, regardless of which storage
backend or retrieval strategy is chosen.
