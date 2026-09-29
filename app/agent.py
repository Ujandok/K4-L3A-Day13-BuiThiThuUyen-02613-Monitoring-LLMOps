from __future__ import annotations

import os
import time
from dataclasses import dataclass

from . import metrics
from .mock_llm import FakeLLM
from .mock_rag import retrieve
from .pii import hash_user_id, summarize_text
from .prompt_management import resolve_prompt
from .tracing import (
    get_langfuse_client,
    observe,
    propagate_attributes,
    start_child_observation,
    tracing_enabled,
)

# Đơn giá giả lập (USD / 1M tokens) — dùng chung cho log và trace.
INPUT_PRICE_PER_M = 3
OUTPUT_PRICE_PER_M = 15


@dataclass
class AgentResult:
    answer: str
    latency_ms: int
    ttft_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    quality_score: float


class LabAgent:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model
        self.llm = FakeLLM(model=model)

    @observe(name="lab-agent-run", as_type="agent", capture_input=False, capture_output=False)
    def run(
        self,
        user_id: str,
        feature: str,
        session_id: str,
        message: str,
        correlation_id: str,
    ) -> AgentResult:
        langfuse_client = get_langfuse_client()
        with propagate_attributes(
            user_id=hash_user_id(user_id),
            session_id=session_id,
            tags=["lab", feature, self.model],
            trace_name="day13-agent-request",
            environment=os.getenv("APP_ENV", "dev"),
            metadata={
                "feature": feature,
                "model": self.model,
                "correlation_id": correlation_id,
            },
        ):
            started = time.perf_counter()

            # --- Child 1: retrieval -------------------------------------------------
            docs = self._traced_retrieve(message)

            prompt = resolve_prompt(
                langfuse_client,
                feature=feature,
                docs=docs,
                message=message,
                enabled=tracing_enabled(),
            )
            langfuse_client.update_current_span(
                metadata={
                    "doc_count": len(docs),
                    "query_preview": summarize_text(message),
                    "prompt_name": prompt.name,
                    "prompt_label": prompt.label,
                    "prompt_version": prompt.version,
                    "prompt_source": prompt.source,
                    "prompt_fetch_error": prompt.fetch_error or "",
                },
                version=prompt.version,
            )

            # --- Child 2: LLM generation --------------------------------------------
            with propagate_attributes(prompt=prompt.managed_prompt):
                with start_child_observation(
                    name="llm-generate",
                    as_type="generation",
                    model=self.model,
                    prompt=prompt.managed_prompt,  # link generation -> prompt version
                    version=prompt.version,
                    # Chỉ gửi bản đã scrub/rút gọn, KHÔNG gửi raw prompt chứa PII.
                    input={"prompt_preview": summarize_text(prompt.text, max_len=160)},
                    metadata={
                        "prompt_name": prompt.name,
                        "prompt_label": prompt.label,
                        "prompt_version": prompt.version,
                        "prompt_source": prompt.source,
                    },
                ) as generation:
                    response = self.llm.generate(prompt.text)
                    tokens_in = response.usage.input_tokens
                    tokens_out = response.usage.output_tokens
                    input_cost, output_cost = self._cost_parts(tokens_in, tokens_out)
                    generation.update(
                        output={"answer_preview": summarize_text(response.text)},
                        usage_details={
                            "input": tokens_in,
                            "output": tokens_out,
                            "total": tokens_in + tokens_out,
                        },
                        cost_details={
                            "input": input_cost,
                            "output": output_cost,
                            "total": round(input_cost + output_cost, 6),
                        },
                        metadata={
                            "ttft_ms": response.ttft_ms,
                            "input_tokens": tokens_in,
                            "output_tokens": tokens_out,
                        },
                    )

            quality_score = self._heuristic_quality(message, response.text, docs)
            latency_ms = int((time.perf_counter() - started) * 1000)
            cost_usd = self._estimate_cost(tokens_in, tokens_out)

        metrics.record_request(
            latency_ms=latency_ms,
            ttft_ms=response.ttft_ms,
            cost_usd=cost_usd,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            quality_score=quality_score,
        )

        return AgentResult(
            answer=response.text,
            latency_ms=latency_ms,
            ttft_ms=response.ttft_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            quality_score=quality_score,
        )

    def _traced_retrieve(self, message: str) -> list[str]:
        with start_child_observation(
            name="retrieval",
            as_type="retriever",
            input={"query_preview": summarize_text(message)},
        ) as span:
            try:
                docs = retrieve(message)
            except Exception as exc:
                # Đánh dấu span lỗi để waterfall chỉ ra đúng bước hỏng (tool_fail).
                span.update(level="ERROR", status_message=f"{type(exc).__name__}: {exc}")
                raise
            span.update(output={"doc_count": len(docs)}, metadata={"tool_success": True})
            return docs

    def _cost_parts(self, tokens_in: int, tokens_out: int) -> tuple[float, float]:
        input_cost = (tokens_in / 1_000_000) * INPUT_PRICE_PER_M
        output_cost = (tokens_out / 1_000_000) * OUTPUT_PRICE_PER_M
        return round(input_cost, 6), round(output_cost, 6)

    def _estimate_cost(self, tokens_in: int, tokens_out: int) -> float:
        input_cost = (tokens_in / 1_000_000) * INPUT_PRICE_PER_M
        output_cost = (tokens_out / 1_000_000) * OUTPUT_PRICE_PER_M
        return round(input_cost + output_cost, 6)

    def _heuristic_quality(self, question: str, answer: str, docs: list[str]) -> float:
        score = 0.5
        if docs:
            score += 0.2
        if len(answer) > 40:
            score += 0.1
        if question.lower().split()[0:1] and any(token in answer.lower() for token in question.lower().split()[:3]):
            score += 0.1
        if "[REDACTED" in answer:
            score -= 0.2
        return round(max(0.0, min(1.0, score)), 2)
