from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres import PostgresSaver

from app.api.routes import router
from app.settings import Settings, get_settings
from workflows.graph.builder import build_workflow_graph
from workflows.graph.deps import WorkflowDeps
from workflows.llm.factory import build_llm
from workflows.persistence.db import init_engine, session_scope


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    init_engine(settings.db_url)

    llm = build_llm(
        settings.llm_provider,
        ollama_model=settings.ollama_model,
        ollama_base_url=settings.ollama_base_url,
    )
    deps = WorkflowDeps(llm=llm, session_factory=session_scope)

    with PostgresSaver.from_conn_string(settings.checkpoint_db_url) as checkpointer:
        checkpointer.setup()
        graph = build_workflow_graph(checkpointer=checkpointer, deps=deps)

        from workflows.services.workflow_service import WorkflowService

        app.state.workflow_service = WorkflowService(
            graph=graph, session_factory=session_scope
        )
        app.state.session_factory = session_scope

        yield


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="AI Workflow Orchestrator", lifespan=lifespan)
    app.state.settings = settings or get_settings()
    app.include_router(router)
    return app


app = create_app()
