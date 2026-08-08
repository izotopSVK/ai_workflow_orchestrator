from __future__ import annotations

import pytest

from workflows.dev_orchestrator.config import DevOrchestratorConfig
from workflows.dev_orchestrator.embeddings import (
    FakeEmbeddingProvider,
    cosine_similarity,
)
from workflows.dev_orchestrator.factory import build_memory
from workflows.dev_orchestrator.schemas import Episode, Lesson
from workflows.dev_orchestrator.tools.memory import (
    InMemoryMemoryStore,
    SqlAlchemyMemoryStore,
)


# --- embeddings -------------------------------------------------------------

def test_fake_embedding_is_deterministic_and_similar_for_shared_tokens():
    emb = FakeEmbeddingProvider()
    assert emb.embed("migrate yii model") == emb.embed("migrate yii model")
    close = cosine_similarity(emb.embed("migrate yii model to php"), emb.embed("migrate yii model"))
    far = cosine_similarity(emb.embed("migrate yii model"), emb.embed("docker deployment pipeline"))
    assert close > far


# --- persistent store (SQLite) ---------------------------------------------

@pytest.fixture
def store(session_factory):
    return SqlAlchemyMemoryStore(session_factory=session_factory, embedder=FakeEmbeddingProvider())


def test_lesson_roundtrip_and_similarity_ranking(store):
    store.record_lesson(Lesson(title="Yii model to PHP 8.4",
                               detail="add AllowDynamicProperties; each() removed",
                               tags=["yii", "php84"]))
    store.record_lesson(Lesson(title="Docker deployment", detail="build and push image",
                               tags=["ops"]))

    hits = store.retrieve_lessons("migrate yii model to php 8.4", k=5)
    assert hits, "the relevant lesson should be retrieved"
    # The relevant lesson ranks first (similarity-ordered).
    assert hits[0].title == "Yii model to PHP 8.4"
    titles = [h.title for h in hits]
    if "Docker deployment" in titles:
        assert titles.index("Yii model to PHP 8.4") < titles.index("Docker deployment")


def test_reinforce_persists(store):
    lid = store.record_lesson(Lesson(title="phpstan dynamic property",
                                     detail="declare properties", tags=["phpstan"]))
    store.reinforce(lid, 2.0)
    hit = store.retrieve_lessons("phpstan dynamic property declare", k=1)[0]
    assert hit.reward == 2.0


def test_memory_survives_a_restart(session_factory):
    first = SqlAlchemyMemoryStore(session_factory=session_factory, embedder=FakeEmbeddingProvider())
    first.record_lesson(Lesson(title="persisted lesson", detail="survives restart", tags=["x"]))

    # A brand-new store instance (simulating a process restart) still sees it.
    second = SqlAlchemyMemoryStore(session_factory=session_factory, embedder=FakeEmbeddingProvider())
    assert second.retrieve_lessons("persisted lesson survives restart", k=5)


def test_episode_roundtrip(store):
    store.record_episode(Episode(workflow_id="wf-1", goal="Migrate User model to PHP 8.4",
                                 outcome="completed", iterations=2,
                                 target_files=["protected/models/User.php"],
                                 summary="completed in 2 iterations"))
    hits = store.retrieve_episodes("migrate user model php", k=5)
    assert hits and hits[0].workflow_id == "wf-1"
    assert hits[0].outcome == "completed"


# --- factory ----------------------------------------------------------------

def test_build_memory_selects_backend(session_factory):
    assert isinstance(build_memory(DevOrchestratorConfig()), InMemoryMemoryStore)
    sql = build_memory(
        DevOrchestratorConfig(memory_backend="sql"),
        session_factory=session_factory,
        embedder=FakeEmbeddingProvider(),
    )
    assert isinstance(sql, SqlAlchemyMemoryStore)
    # sql backend without a session_factory falls back to in-memory (no crash).
    assert isinstance(build_memory(DevOrchestratorConfig(memory_backend="sql")), InMemoryMemoryStore)