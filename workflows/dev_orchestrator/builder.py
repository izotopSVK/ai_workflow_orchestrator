from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.nodes.analyze import make_analyze_node
from workflows.dev_orchestrator.nodes.apply import make_apply_node
from workflows.dev_orchestrator.nodes.bootstrap import make_bootstrap_node
from workflows.dev_orchestrator.nodes.finalize import make_finalize_node
from workflows.dev_orchestrator.nodes.human_review import make_human_review_node
from workflows.dev_orchestrator.nodes.implement import make_implement_node
from workflows.dev_orchestrator.nodes.learn import make_learn_node
from workflows.dev_orchestrator.nodes.load_context import make_load_context_node
from workflows.dev_orchestrator.nodes.plan import make_plan_node
from workflows.dev_orchestrator.nodes.reflect import make_reflect_node
from workflows.dev_orchestrator.nodes.retrieve import make_retrieve_node
from workflows.dev_orchestrator.nodes.teardown import make_teardown_node
from workflows.dev_orchestrator.nodes.verify import make_verify_node
from workflows.dev_orchestrator.routing import (
    route_after_apply,
    route_after_human_review,
    route_after_verify,
)
from workflows.dev_orchestrator.state import DevOrchestratorState


def build_dev_orchestrator_graph(*, checkpointer, deps: DevOrchestratorDeps):
    """Wire the self-learning Yii 1.1 -> PHP 8.4 dev pipeline.

    START -> bootstrap -> load_context -> retrieve -> analyze -> plan -> implement
      -> apply -> verify
      apply --patch failed--> reflect (retry)
      verify --ok--> human_review --approved--> finalize -> learn -> teardown -> END
      verify --red,budget-left--> reflect -> implement   (Reflexion retry loop)
      verify --red,exhausted--> finalize (failure)
      human_review --parked--> END (resume later)
    """
    builder = StateGraph(DevOrchestratorState)

    builder.add_node("bootstrap", make_bootstrap_node(deps))
    builder.add_node("load_context", make_load_context_node(deps))
    builder.add_node("retrieve", make_retrieve_node(deps))
    builder.add_node("analyze", make_analyze_node(deps))
    builder.add_node("plan", make_plan_node(deps))
    builder.add_node("implement", make_implement_node(deps))
    builder.add_node("apply", make_apply_node(deps))
    builder.add_node("verify", make_verify_node(deps))
    builder.add_node("reflect", make_reflect_node(deps))
    builder.add_node("human_review", make_human_review_node(deps))
    builder.add_node("finalize", make_finalize_node(deps))
    builder.add_node("learn", make_learn_node(deps))
    builder.add_node("teardown", make_teardown_node(deps))

    builder.add_edge(START, "bootstrap")
    builder.add_edge("bootstrap", "load_context")
    builder.add_edge("load_context", "retrieve")
    builder.add_edge("retrieve", "analyze")
    builder.add_edge("analyze", "plan")
    builder.add_edge("plan", "implement")
    builder.add_edge("implement", "apply")

    builder.add_conditional_edges(
        "apply",
        route_after_apply,
        {
            "verify": "verify",
            "reflect": "reflect",
            "finalize": "finalize",
        },
    )

    builder.add_conditional_edges(
        "verify",
        route_after_verify,
        {
            "review": "human_review",
            "reflect": "reflect",
            "finalize": "finalize",
        },
    )

    builder.add_edge("reflect", "implement")

    builder.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "finalize": "finalize",
            "end": END,
        },
    )

    builder.add_edge("finalize", "learn")
    builder.add_edge("learn", "teardown")
    builder.add_edge("teardown", END)

    return builder.compile(checkpointer=checkpointer)
