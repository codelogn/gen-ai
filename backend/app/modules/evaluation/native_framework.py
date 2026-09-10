"""NativeEvaluationFramework — the zero-dependency baseline.

No judge LLM, no third-party framework — plain information-retrieval
metrics computed by comparing retrieved memory IDs against
expected_memory_ids via exact set/rank comparison. Deliberately does NOT
attempt a fuzzy text-overlap fallback when expected_memory_ids is
absent — that's what the LLM-judged frameworks (Ragas, DeepEval) are for.
This framework's job is to be a fast, free, always-available sanity check,
not to reimplement semantic judgment worse than an LLM would.
"""

from typing import Any, Optional
from uuid import UUID

from app.modules.applications.models import Application
from app.modules.evaluation.base import EvaluationFramework
from app.modules.retrieval.base import SearchResult


class NativeEvaluationFramework(EvaluationFramework):
    name = "native"

    async def evaluate_case(
        self,
        application: Application,
        query: str,
        retrieved: list[SearchResult],
        expected_memory_ids: Optional[list[UUID]],
        expected_context: Optional[str],
        generated_answer: Optional[str],
        judge_llm: Optional[Any],
    ) -> dict:
        if not expected_memory_ids:
            return {"skipped": "no expected_memory_ids provided"}

        expected_set = set(expected_memory_ids)
        retrieved_ids = [r.memory_id for r in retrieved]
        retrieved_set = set(retrieved_ids)

        k = len(retrieved_ids)
        hits = retrieved_set & expected_set

        precision_at_k = len(hits) / k if k else 0.0
        recall_at_k = len(hits) / len(expected_set) if expected_set else 0.0

        mrr = 0.0
        for rank, memory_id in enumerate(retrieved_ids, start=1):
            if memory_id in expected_set:
                mrr = 1.0 / rank
                break

        return {
            "precision_at_k": round(precision_at_k, 4),
            "recall_at_k": round(recall_at_k, 4),
            "mrr": round(mrr, 4),
        }


_native_framework = NativeEvaluationFramework()


def get_native_framework() -> NativeEvaluationFramework:
    return _native_framework
