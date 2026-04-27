from langgraph.graph import END, START, StateGraph

from workflows.graph.deps import WorkflowDeps
from workflows.graph.routing import route_after_human_review, route_after_verify
from workflows.graph.state import AgentWorkflowState
from workflows.nodes.finalize import make_finalize_node
from workflows.nodes.human_review import make_human_review_node
from workflows.nodes.plan import make_plan_node
from workflows.nodes.verify import make_verify_node


def build_workflow_graph(*, checkpointer, deps: WorkflowDeps):
    builder = StateGraph(AgentWorkflowState)

    builder.add_node("plan", make_plan_node(deps))
    builder.add_node("verify", make_verify_node(deps))
    builder.add_node("human_review", make_human_review_node(deps))
    builder.add_node("finalize", make_finalize_node(deps))

    builder.add_edge(START, "plan")
    builder.add_edge("plan", "verify")

    builder.add_conditional_edges(
        "verify",
        route_after_verify,
        {
            "human_review": "human_review",
            "end": END,
        },
    )

    builder.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "finalize": "finalize",
            "end": END,
        },
    )

    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)
