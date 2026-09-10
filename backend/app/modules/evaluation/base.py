"""The EvaluationFramework contract every implementation follows.

Unlike VectorStoreAdapter/RetrievalStrategy — "pick one, it's how
production behaves" — evaluation frameworks are run several at once
against the same test cases and compared. There is deliberately no
single-choice factory here (no get_evaluation_framework(application));
EvaluationService (service.py) is a fan-out orchestrator that instantiates
every framework requested for a given run. See
docs/15-evaluation-frameworks.md for the full reasoning.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from uuid import UUID

from app.modules.applications.models import Application
from app.modules.retrieval.base import SearchResult


class EvaluationFramework(ABC):
    name: str

    @abstractmethod
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
        """Returns a metric-name -> score dict, or {"skipped": "<reason>"}
        when this framework structurally can't evaluate this case (e.g.
        native without expected_memory_ids). Never raises for a
        "can't run this case" situation — only for genuine failures
        (e.g. a judge LLM call erroring out), which the caller records as
        {"error": "..."} instead of failing the whole run.
        """
        raise NotImplementedError
