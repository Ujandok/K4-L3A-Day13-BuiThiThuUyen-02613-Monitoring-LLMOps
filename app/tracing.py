from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

try:
    from langfuse import get_client, observe, propagate_attributes

    LANGFUSE_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover - chỉ dùng khi chưa cài requirements
    LANGFUSE_SDK_AVAILABLE = False

    def observe(*args: Any, **kwargs: Any):
        def decorator(func):
            return func

        return decorator

    class _DummyObservation:
        def update(self, **kwargs: Any) -> "_DummyObservation":
            return self

    class _DummyClient:
        def update_current_span(self, **kwargs: Any) -> None:
            return None

        def update_current_generation(self, **kwargs: Any) -> None:
            return None

        @contextmanager
        def start_as_current_observation(self, **kwargs: Any):
            yield _DummyObservation()

    def get_client():
        return _DummyClient()

    @contextmanager
    def propagate_attributes(**kwargs: Any):
        yield


def get_langfuse_client():
    return get_client()


def tracing_enabled() -> bool:
    return LANGFUSE_SDK_AVAILABLE and bool(
        os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")
    )


def start_child_observation(**kwargs: Any):
    """Mở một child observation dưới observation hiện tại (root = lab-agent-run).

    Cố ý dùng get_client() của module này thay vì client truyền từ agent, để
    test có thể thay client giả (chỉ có get_prompt/update_current_span) mà
    child observation vẫn chạy qua SDK thật (no-op khi không có key).
    """
    return get_client().start_as_current_observation(**kwargs)
