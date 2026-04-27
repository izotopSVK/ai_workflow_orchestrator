from __future__ import annotations

import os
import tempfile
from collections.abc import Generator

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.orm import Session

from workflows.graph.builder import build_workflow_graph
from workflows.graph.deps import WorkflowDeps
from workflows.llm.factory import FakeWorkflowLLM
from workflows.persistence import db as db_module
from workflows.persistence.orm import Base
from workflows.services.workflow_service import WorkflowService


@pytest.fixture
def artifact_dir(tmp_path) -> Generator[str, None, None]:
    path = tmp_path / "artifacts"
    path.mkdir()
    previous = os.environ.get("ARTIFACT_DIR")
    os.environ["ARTIFACT_DIR"] = str(path)
    try:
        yield str(path)
    finally:
        if previous is None:
            os.environ.pop("ARTIFACT_DIR", None)
        else:
            os.environ["ARTIFACT_DIR"] = previous


@pytest.fixture
def session_factory(tmp_path):
    db_path = tmp_path / "test.sqlite"
    engine = db_module.init_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    def _factory() -> Session:
        return db_module.session_scope()

    return _factory


@pytest.fixture
def fake_llm() -> FakeWorkflowLLM:
    return FakeWorkflowLLM()


@pytest.fixture
def graph(fake_llm, session_factory):
    deps = WorkflowDeps(llm=fake_llm, session_factory=session_factory)
    checkpointer = InMemorySaver()
    return build_workflow_graph(checkpointer=checkpointer, deps=deps)


@pytest.fixture
def workflow_service(graph, session_factory) -> WorkflowService:
    return WorkflowService(graph=graph, session_factory=session_factory)
