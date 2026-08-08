from __future__ import annotations

import uuid
from typing import Protocol

from workflows.dev_orchestrator.embeddings import cosine_similarity
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


class SqlAlchemyMemoryStore:
    """Persistent memory backed by the app DB via SQLAlchemy + embeddings.

    Survives restarts and gives an audit trail (lessons + episodes tables).
    Embeddings are stored as JSON arrays and ranked with cosine similarity in
    Python, so this works on both SQLite (tests) and Postgres. For large lesson
    sets, subclass into :class:`PgVectorMemoryStore` to push the ranking into the
    DB with a native ``vector`` column + ``<->`` index.
    """

    def __init__(self, *, session_factory, embedder) -> None:
        self._session_factory = session_factory
        self._embedder = embedder

    # -- lessons ----------------------------------------------------------

    def record_lesson(self, lesson: Lesson) -> str:
        from workflows.persistence.orm import WorkflowLesson

        row_id = uuid.UUID(lesson.id) if lesson.id else uuid.uuid4()
        with self._session_factory() as session:
            session.add(WorkflowLesson(
                id=row_id,
                title=lesson.title,
                detail=lesson.detail,
                tags_json=list(lesson.tags),
                reward=lesson.reward,
                embedding_json=self._embedder.embed(f"{lesson.title} {lesson.detail}"),
            ))
            session.commit()
        return str(row_id)

    def reinforce(self, lesson_id: str, reward: float) -> None:
        from workflows.persistence.orm import WorkflowLesson

        with self._session_factory() as session:
            row = session.get(WorkflowLesson, uuid.UUID(lesson_id))
            if row is not None:
                row.reward += reward
                session.commit()

    def retrieve_lessons(self, query: str, k: int) -> list[Lesson]:
        from workflows.persistence.orm import WorkflowLesson

        q_emb = self._embedder.embed(query)
        with self._session_factory() as session:
            rows = list(session.query(WorkflowLesson).all())
        ranked = sorted(
            rows,
            key=lambda r: (cosine_similarity(q_emb, r.embedding_json or []), r.reward),
            reverse=True,
        )
        return [
            Lesson(id=str(r.id), title=r.title, detail=r.detail, tags=list(r.tags_json or []),
                   reward=r.reward)
            for r in ranked
            if cosine_similarity(q_emb, r.embedding_json or []) > 0
        ][:k]

    # -- episodes ---------------------------------------------------------

    def record_episode(self, episode: Episode) -> str:
        from workflows.persistence.orm import WorkflowEpisode

        with self._session_factory() as session:
            session.add(WorkflowEpisode(
                workflow_id=episode.workflow_id,
                goal=episode.goal,
                outcome=episode.outcome,
                iterations=episode.iterations,
                target_files_json=list(episode.target_files),
                summary=episode.summary,
                embedding_json=self._embedder.embed(f"{episode.goal} {episode.summary}"),
            ))
            session.commit()
        return episode.workflow_id

    def retrieve_episodes(self, query: str, k: int) -> list[Episode]:
        from workflows.persistence.orm import WorkflowEpisode

        q_emb = self._embedder.embed(query)
        with self._session_factory() as session:
            rows = list(session.query(WorkflowEpisode).all())
        ranked = sorted(
            rows,
            key=lambda r: cosine_similarity(q_emb, r.embedding_json or []),
            reverse=True,
        )
        return [
            Episode(workflow_id=r.workflow_id, goal=r.goal, outcome=r.outcome,
                    iterations=r.iterations, target_files=list(r.target_files_json or []),
                    summary=r.summary)
            for r in ranked
            if cosine_similarity(q_emb, r.embedding_json or []) > 0
        ][:k]


class PgVectorMemoryStore(SqlAlchemyMemoryStore):
    """Scale variant: rank in Postgres via a native pgvector ``<->`` index.

    Inherits all writes from :class:`SqlAlchemyMemoryStore`; a production
    deployment overrides ``retrieve_*`` to run ``ORDER BY embedding <-> :q`` on a
    ``vector`` column (requires the pgvector extension and a vector-typed column,
    added by a Postgres-only migration). Until that column exists it behaves like
    the portable parent. Verify against a real Postgres (integration test) before
    relying on the native path.
    """
