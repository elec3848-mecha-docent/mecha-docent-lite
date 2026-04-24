"""Background pre-generation of exhibit explanations.

:class:`ExplanationCache` uses a single-worker ``ThreadPoolExecutor`` to
generate chunked LLM explanations for upcoming exhibits while the robot is
still presenting the current one, eliminating the LLM latency from the
visitor's perspective.

Usage
-----
1. Call :meth:`~ExplanationCache.schedule` as soon as the next exhibit is
   known.  The work is queued but does not block.
2. Before presenting the exhibit, call :meth:`~ExplanationCache.ensure` which
   blocks for up to 8 seconds to guarantee the chunks are ready.
3. Retrieve individual feature chunks via
   :meth:`~ExplanationCache.get_feature_chunk`.

Fallback
--------
If generation fails or times out the cache falls back to splitting the
exhibit feature annotation text at its midpoint into ``segment_a`` and
``segment_b``.
"""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor

from LLM.domain.models import Exhibit, ExhibitFeature, VisitorProfile
from LLM.generation.llm_client import call_json
from LLM.generation.prompts import explanation_chunks_prompt


class ExplanationCache:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, dict[str, str]]] = {}
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._pending: dict[str, Future] = {}

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def schedule(self, llm, profile: VisitorProfile, exhibit: Exhibit, max_tokens: int, temperature: float) -> None:
        if exhibit.id in self._cache or exhibit.id in self._pending:
            return
        future = self._executor.submit(
            self._generate, llm, profile, exhibit, max_tokens, temperature
        )
        self._pending[exhibit.id] = future

    def _generate(self, llm, profile: VisitorProfile, exhibit: Exhibit, max_tokens: int, temperature: float) -> dict[str, dict[str, str]]:
        messages = [
            {"role": "system", "content": explanation_chunks_prompt(profile, exhibit)},
            {"role": "user", "content": "Generate concise chunked explanations."},
        ]
        data = call_json(llm, messages, max_tokens=max_tokens, temperature=temperature)
        chunks = {}
        for item in data.get("chunks", []):
            tag = item.get("feature_tag")
            if isinstance(tag, str) and tag:
                chunks[tag] = {
                    "segment_a": str(item.get("segment_a", "")).strip(),
                    "segment_b": str(item.get("segment_b", "")).strip(),
                    "question": str(item.get("question", "What stands out to you?")).strip(),
                }
        return chunks

    def ensure(self, llm, profile: VisitorProfile, exhibit: Exhibit, max_tokens: int, temperature: float) -> None:
        if exhibit.id in self._cache:
            return
        future = self._pending.get(exhibit.id)
        if future is None:
            self.schedule(llm, profile, exhibit, max_tokens, temperature)
            future = self._pending[exhibit.id]
        try:
            self._cache[exhibit.id] = future.result(timeout=8)
        except Exception:
            self._cache[exhibit.id] = {}
        finally:
            self._pending.pop(exhibit.id, None)

    def get_feature_chunk(self, exhibit: Exhibit, feature: ExhibitFeature) -> dict[str, str]:
        exhibit_cache = self._cache.get(exhibit.id, {})
        if feature.tag in exhibit_cache:
            return exhibit_cache[feature.tag]

        words = feature.annotation.split()
        midpoint = max(1, len(words) // 2)
        segment_a = " ".join(words[:midpoint])
        segment_b = " ".join(words[midpoint:])
        return {
            "segment_a": segment_a,
            "segment_b": segment_b,
            "question": "Does this level of detail work for you?",
        }
