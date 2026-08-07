from __future__ import annotations

import uuid
from typing import Protocol

from workflows.dev_orchestrator.schemas import Episode, Lesson
from workflows.dev_orchestrator.text import keyword_score as _score


class MemoryStore(Protocol):
    """Long-term memory that makes the orchestrator self-learning.

    Two tiers:
      * lessons  - distilled, reusable rules (semantic memory)
      * episodes - full run trajectories (episodic memory)

    ``retrieve_lessons`` feeds the planner; ``reinforce`` raises the weight of a
    lesson whenever a later verify passes after it was applied.
    """

    def retrieve_lessons(self, query: str, k: int) -> list[Lesson]: ...

    def record_lesson(self, lesson: Lesson) -> str: ...

    def reinforce(self, lesson_id: str, reward: float) -> None: ...

    def record_episode(self, episode: Episode) -> str: ...

    def retrieve_episodes(self, query: str, k: int) -> list[Episode]: ...


class InMemoryMemoryStore:
    """Fully functional non-persistent memory used in tests and local runs.

    Ranks by keyword overlap and lesson reward. A real deployment swaps this for
    :class:`PgVectorMemoryStore`.
    """

    def __init__(self) -> None:
        self._lessons: dict[str, Lesson] = {}
        self._episodes: list[Episode] = []

    def retrieve_lessons(self, query: str, k: int) -> list[Lesson]:
        ranked = sorted(
            self._lessons.values(),
            key=lambda le: (_score(query, f"{le.title} {le.detail} {' '.join(le.tags)}"), le.reward),
            reverse=True,
        )
        return [le for le in ranked if _score(query, f"{le.title} {le.detail} {' '.join(le.tags)}") > 0][:k]

    def record_lesson(self, lesson: Lesson) -> str:
        if not lesson.id:
            lesson.id = uuid.uuid4().hex
        self._lessons[lesson.id] = lesson
        return lesson.id

    def reinforce(self, lesson_id: str, reward: float) -> None:
        if lesson_id in self._lessons:
            self._lessons[lesson_id].reward += reward

    def record_episode(self, episode: Episode) -> str:
        self._episodes.append(episode)
        return episode.workflow_id

    def retrieve_episodes(self, query: str, k: int) -> list[Episode]:
        ranked = sorted(
            self._episodes,
            key=lambda ep: _score(query, f"{ep.goal} {ep.summary} {' '.join(ep.target_files)}"),
            reverse=True,
        )
        return [ep for ep in ranked if _score(query, f"{ep.goal} {ep.summary}") > 0][:k]


class PgVectorMemoryStore:
    """Persistent memory backed by Postgres + pgvector.

    Placeholder for the real deployment: store lessons/episodes as rows with an
    ``embedding vector`` column and retrieve via ``<->`` cosine distance. Left
    unimplemented in the scaffold so tests stay Postgres-free.
    """

    def __init__(self, *, session_factory, embedder) -> None:
        self._session_factory = session_factory
        self._embedder = embedder

    def _todo(self):  # pragma: no cover
        raise NotImplementedError(
            "PgVectorMemoryStore requires pgvector + an embedding model; "
            "wire it in once the target Yii repo and embeddings are configured."
        )

    def retrieve_lessons(self, query: str, k: int):  # pragma: no cover
        self._todo()

    def record_lesson(self, lesson: Lesson) -> str:  # pragma: no cover
        self._todo()

    def reinforce(self, lesson_id: str, reward: float) -> None:  # pragma: no cover
        self._todo()

    def record_episode(self, episode: Episode) -> str:  # pragma: no cover
        self._todo()

    def retrieve_episodes(self, query: str, k: int):  # pragma: no cover
        self._todo()
