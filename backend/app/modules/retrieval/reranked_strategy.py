"""CrossEncoderRerankStrategy — re-scores a wider candidate pool with a
cross-encoder before returning the top_k.

This is the FIRST feature in this service that runs actual local ML
inference (a HuggingFace cross-encoder via sentence-transformers/torch)
rather than calling an HTTP API — every other embedding/chat/judge-LLM
capability so far is either raw httpx or a thin LangChain wrapper around
an HTTP endpoint (Ollama/OpenAI). That distinction drives every design
choice below:

- Cross-encoder inference is synchronous, CPU-bound PyTorch code. Calling
  it directly inside `async def search()` would block the event loop for
  every other concurrent request this process is serving. Offloaded to a
  small dedicated ThreadPoolExecutor instead of the default loop executor
  (isolates this CPU-bound workload from any future I/O-bound to_thread
  usage) and NOT a process pool (model objects aren't cheaply shareable
  across processes, and PyTorch releases the GIL during tensor math, so
  threads already give real concurrency here).
- torch.set_num_threads(1) is pinned per model load so worker threads
  don't each try to grab every core via BLAS and thrash each other —
  concurrency is controlled via the executor's max_workers instead.
- Model loading is seconds-slow, so it's cached in-process by model name,
  with a negative cache (TTL) on load failures — without that, a bad
  model name would retry the same slow failure on every single request.
- Cache is per-process, matching app/core/rate_limit.py's existing,
  already-documented single-process-for-now stance (revisit only if this
  service ever runs with multiple uvicorn workers).
- rerank_model is validated against an allowlist (not free text) and
  rerank_candidate_pool is hard-capped in code regardless of what a
  tenant configures — both are real latency/memory-exhaustion vectors in
  a shared multi-tenant process, not just tuning knobs.
- Failure is soft, not hard: any error loading the model or scoring
  candidates logs a warning and falls back to plain vector-score
  ordering (i.e. exactly NativeRetrievalStrategy's result). This
  deliberately does NOT copy JudgeLLMNotConfigured's hard-fail-with-a-
  visible-error pattern from app/modules/evaluation/ — that pattern fits
  an async, polled report with a per-case error slot and no possible
  fallback. search() is a synchronous, on-the-request-path REST response
  with no error-shaped hole to put "reranking degraded" into, and a
  correct, cheap fallback already exists because reranking is built on
  top of native retrieval.

See docs/05-retrieval-strategies.md for a worked before/after example.
"""

import asyncio
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.applications.models import Application
from app.modules.retrieval.base import RetrievalStrategy, SearchResult
from app.modules.retrieval.native_strategy import NativeRetrievalStrategy

# Set before sentence_transformers/huggingface_hub is imported anywhere in
# this process, so downloaded models are cached to a persistent, mountable
# path (mirrors VECTOR_DATA_DIR) instead of the default ~/.cache/huggingface,
# which is typically wiped on every container restart.
os.environ.setdefault("HF_HOME", settings.RERANK_MODEL_CACHE_DIR)

logger = logging.getLogger("gen_ai.retrieval.reranked")

DEFAULT_RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
ALLOWED_RERANK_MODELS = (
    "cross-encoder/ms-marco-MiniLM-L-6-v2",  # default: 6-layer, ~80MB, fast
    "cross-encoder/ms-marco-MiniLM-L-12-v2",  # slower, more accurate
)
MIN_CANDIDATE_POOL = 20
MAX_CANDIDATE_POOL = 100  # hard cap regardless of config — see module docstring
CANDIDATE_POOL_MULTIPLIER = 4
NEGATIVE_CACHE_TTL_SECONDS = 300

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cross-encoder-rerank")
_model_cache: dict[str, Any] = {}
_model_load_errors: dict[str, tuple[str, float]] = {}
_cache_lock = threading.Lock()

_candidate_source = NativeRetrievalStrategy()


def _load_model_sync(model_name: str):
    import torch
    from sentence_transformers import CrossEncoder

    torch.set_num_threads(1)
    return CrossEncoder(model_name)


async def _get_cross_encoder(model_name: str):
    now = time.monotonic()
    with _cache_lock:
        if model_name in _model_cache:
            return _model_cache[model_name]
        cached_error = _model_load_errors.get(model_name)
        if cached_error and cached_error[1] > now:
            raise RuntimeError(cached_error[0])

    loop = asyncio.get_running_loop()
    try:
        model = await loop.run_in_executor(_executor, _load_model_sync, model_name)
    except Exception as exc:
        with _cache_lock:
            _model_load_errors[model_name] = (str(exc), now + NEGATIVE_CACHE_TTL_SECONDS)
        raise
    with _cache_lock:
        _model_cache[model_name] = model
    return model


class CrossEncoderRerankStrategy(RetrievalStrategy):
    async def search(
        self,
        db: AsyncSession,
        application: Application,
        query: str,
        top_k: int,
        namespace: str,
        subject_id: Optional[str] = None,
        filters: Optional[dict] = None,
    ) -> list[SearchResult]:
        config = application.retrieval_strategy_config or {}

        pool = int(config.get("rerank_candidate_pool") or max(top_k * CANDIDATE_POOL_MULTIPLIER, MIN_CANDIDATE_POOL))
        pool = min(max(pool, top_k), MAX_CANDIDATE_POOL)

        candidates = await _candidate_source.search(
            db, application, query, top_k=pool, namespace=namespace,
            subject_id=subject_id, filters=filters,
        )
        if len(candidates) <= 1:
            return candidates[:top_k]

        model_name = config.get("rerank_model") or DEFAULT_RERANK_MODEL
        if model_name not in ALLOWED_RERANK_MODELS:
            logger.warning(
                f"Unrecognized rerank_model '{model_name}' for application "
                f"{application.slug}, falling back to default {DEFAULT_RERANK_MODEL}"
            )
            model_name = DEFAULT_RERANK_MODEL

        try:
            cross_encoder = await _get_cross_encoder(model_name)
            pairs = [(query, c.content) for c in candidates]
            loop = asyncio.get_running_loop()
            scores = await loop.run_in_executor(_executor, cross_encoder.predict, pairs)
        except Exception as exc:
            logger.warning(
                f"Cross-encoder rerank unavailable for application {application.slug} "
                f"(model={model_name}): {exc} — falling back to unreranked vector ordering"
            )
            return candidates[:top_k]

        reranked = sorted(zip(candidates, scores), key=lambda pair: pair[1], reverse=True)
        return [
            SearchResult(
                memory_id=c.memory_id, content=c.content, metadata=c.metadata,
                score=float(s), created_at=c.created_at,
            )
            for c, s in reranked[:top_k]
        ]


_reranked_strategy = CrossEncoderRerankStrategy()


def get_reranked_strategy() -> CrossEncoderRerankStrategy:
    return _reranked_strategy
