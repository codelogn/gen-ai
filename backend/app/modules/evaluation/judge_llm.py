"""The judge-LLM builder — gen-ai's first chat-completion capability.

Every prior capability in this service only ever embedded text
(EmbeddingProviderRegistry, app/modules/embeddings/registry.py — raw httpx
calls, no LangChain chat-model dependency). Ragas and DeepEval's headline
metrics work via LLM-as-judge: they need a chat-completion model to score
things like "is this context actually relevant to the query." That's a
genuinely different capability, not a variation on embedding.

Built on LangChain's ChatOllama/ChatOpenAI specifically because Ragas's
primary integration point (LangchainLLMWrapper) expects a LangChain
BaseChatModel — reusing it here means DeepEval's adapter below can share
the exact same underlying model/config instead of each framework needing
its own provider-branching code.
"""

from typing import Optional

from deepeval.models import DeepEvalBaseLLM
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.core.crypto import decrypt_secret
from app.modules.applications.models import Application, EmbeddingProviderName


class JudgeLLMNotConfigured(Exception):
    """Raised when an evaluation framework that needs a judge LLM
    (Ragas, DeepEval) is requested but the application has no
    judge_llm_* configuration set. NativeEvaluationFramework never
    raises this — it needs no judge LLM at all."""


def build_judge_chat_model(application: Application) -> BaseChatModel:
    if application.judge_llm_provider is None or not application.judge_llm_model:
        raise JudgeLLMNotConfigured(
            f"Application '{application.slug}' has no evaluation judge LLM configured — "
            f"set judge_llm_provider and judge_llm_model before running Ragas/DeepEval evaluations."
        )

    api_key: Optional[str] = None
    if application.judge_llm_api_key_encrypted:
        api_key = decrypt_secret(application.judge_llm_api_key_encrypted)

    if application.judge_llm_provider == EmbeddingProviderName.OLLAMA:
        return ChatOllama(
            model=application.judge_llm_model,
            base_url=application.judge_llm_base_url or "http://localhost:11434",
        )
    elif application.judge_llm_provider == EmbeddingProviderName.OPENAI:
        kwargs = {"model": application.judge_llm_model}
        if api_key:
            kwargs["api_key"] = api_key
        if application.judge_llm_base_url:
            kwargs["base_url"] = application.judge_llm_base_url
        return ChatOpenAI(**kwargs)
    else:
        raise ValueError(f"Unsupported judge LLM provider: {application.judge_llm_provider}")


class DeepEvalLangchainAdapter(DeepEvalBaseLLM):
    """Wraps the same LangChain chat model Ragas uses (via LangchainLLMWrapper)
    so DeepEval's metrics run against the identical judge — one config, one
    underlying call path, two framework integrations. Implements
    DeepEvalBaseLLM's four required methods (load_model/generate/a_generate/
    get_model_name) as thin delegation to the wrapped chat model.
    """

    def __init__(self, chat_model: BaseChatModel, model_name: str):
        self._chat_model = chat_model
        self._model_name = model_name
        super().__init__(model=model_name)

    def load_model(self):
        return self._chat_model

    def generate(self, prompt: str) -> str:
        return self._chat_model.invoke(prompt).content

    async def a_generate(self, prompt: str) -> str:
        response = await self._chat_model.ainvoke(prompt)
        return response.content

    def get_model_name(self) -> str:
        return self._model_name
