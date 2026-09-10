# Glossary

Every RAG/evaluation term used across this documentation, in one place,
each with a one-line definition and a link to where it's explained in
full. If you're new to these concepts entirely, read
[00-rag-concepts-primer.md](./00-rag-concepts-primer.md) start to finish
instead — this page is for looking a term up quickly once you already
have the general shape, not for learning it for the first time.

**Answer relevancy** — does a generated answer actually address what was
asked (as opposed to being faithful to the context but off-topic)? See
[15-evaluation-frameworks.md](./15-evaluation-frameworks.md).

**Chunking** — splitting a long document into smaller, overlapping pieces
before embedding each one separately, so search can find the one relevant
part instead of "the whole document, vaguely." See
[00-rag-concepts-primer.md](./00-rag-concepts-primer.md#chunking-what-to-do-with-long-documents).

**Context precision / context recall** — of the text retrieved for a
query, how much of it was actually relevant (precision), and how much of
the relevant material that exists did it actually find (recall)? Measured
by an LLM judge, not exact-ID matching. See
[15-evaluation-frameworks.md](./15-evaluation-frameworks.md).

**Cosine similarity** — the standard way to measure how similar two
embedding vectors are: the angle between them, from -1 (opposite) to 1
(same direction/meaning). See
[00-rag-concepts-primer.md](./00-rag-concepts-primer.md#cosine-similarity-measuring-how-close).

**Cross-encoder reranking** — re-scoring a candidate pool by feeding the
query and each candidate *together* into one model, rather than comparing
two independently-computed vectors — catches relevance cosine similarity
alone can miss. See
[05-retrieval-strategies.md](./05-retrieval-strategies.md#crossencoderrerankstrategy--cross-encoder-reranking).

**Embedding** — a vector (list of numbers) an embedding model produces
from text, representing its meaning as a point in space — similar
meanings end up as nearby points. See
[00-rag-concepts-primer.md](./00-rag-concepts-primer.md#embeddings-turning-text-into-a-location).

**Faithfulness** — does a generated answer actually follow from the
retrieved context, or does it contradict/invent something not supported
by it? See [15-evaluation-frameworks.md](./15-evaluation-frameworks.md).

**Fan-out (evaluation frameworks)** — running multiple evaluation
frameworks against the same test cases at once and comparing their
opinions, as opposed to picking one — the key way evaluation frameworks
differ architecturally from vector backends/retrieval strategies (which
are "pick one"). See
[15-evaluation-frameworks.md](./15-evaluation-frameworks.md#why-this-looks-different-from-vectorstoreadapterretrievalstrategy).

**Hybrid search** — combining keyword search and vector search on the
same query and merging the ranked lists, getting the precision of exact
matching and the recall of semantic matching at once. See
[00-rag-concepts-primer.md](./00-rag-concepts-primer.md#the-limits-of-pure-vector-search--and-hybrid-search).

**Judge LLM** — a chat-completion model used to score retrieval/answer
quality (LLM-as-judge) rather than to generate anything user-facing —
gen-ai's first capability needing a chat model, not just an embedding
model. See [15-evaluation-frameworks.md](./15-evaluation-frameworks.md).

**LLM-as-judge** — using a language model to evaluate something (is this
context relevant? does this answer follow from it?) that plain ID/exact
matching structurally can't judge. See
[00-rag-concepts-primer.md](./00-rag-concepts-primer.md#how-do-you-know-if-a-rag-system-is-actually-good).

**MRR (Mean Reciprocal Rank)** — not just whether the right result came
back, but how high it ranked; a relevant result at position 1 scores
higher than the same result buried at position 10. See
[00-rag-concepts-primer.md](./00-rag-concepts-primer.md#how-do-you-know-if-a-rag-system-is-actually-good).

**Precision@k** — of the k results a search returned, what fraction were
actually relevant. See
[00-rag-concepts-primer.md](./00-rag-concepts-primer.md#how-do-you-know-if-a-rag-system-is-actually-good).

**RAG (Retrieval-Augmented Generation)** — the two-step pattern of
retrieving relevant text, then generating an answer by handing a language
model that text plus the question. See
[00-rag-concepts-primer.md](./00-rag-concepts-primer.md#the-problem-rag-solves).

**Recall@k** — of all the relevant items that exist, what fraction did
the search actually find. See
[00-rag-concepts-primer.md](./00-rag-concepts-primer.md#how-do-you-know-if-a-rag-system-is-actually-good).

**Reciprocal rank fusion** — the way `EnsembleRetriever` merges a keyword
ranked list and a vector ranked list into one: a result's final score
depends on how high it ranked in *each* list, not a raw similarity number.
See [05-retrieval-strategies.md](./05-retrieval-strategies.md#langchainretrievalstrategy--hybrid-keyword--vector-search).

**Vector database** — a database (or an extension on one, like pgvector)
built to make nearest-neighbor vector search fast at scale, via indexing
techniques like HNSW instead of comparing against every stored vector.
See [00-rag-concepts-primer.md](./00-rag-concepts-primer.md#where-the-vectors-live-a-vector-database).

**Vector search / nearest-neighbor search** — embedding a query, then
finding which stored vectors have the highest cosine similarity to it.
See [00-rag-concepts-primer.md](./00-rag-concepts-primer.md#cosine-similarity-measuring-how-close).
