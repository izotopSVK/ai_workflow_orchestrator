import uuid
from collections.abc import Callable
from typing import Any

from workflows.graph.deps import WorkflowDeps
from workflows.graph.state import AgentWorkflowState
from workflows.models.enums import ActorType, ArtifactType, WorkflowStatus
from workflows.persistence.repositories import (
    WorkflowArtifactRepository,
    WorkflowEventRepository,
)
from workflows.services.artifact_service import ArtifactService


def make_finalize_node(deps: WorkflowDeps) -> Callable[[AgentWorkflowState], dict[str, Any]]:
    def finalize_node(state: AgentWorkflowState) -> dict[str, Any]:
        workflow_id = uuid.UUID(state["workflow_id"])
        artifact_service = ArtifactService()

        report_payload = {
            "goal": state["goal"],
            "plan": state.get("plan", []),
            "completed_steps": state.get("completed_steps", []),
        }
        report_uri = artifact_service.put_json(
            workflow_id=state["workflow_id"],
            name="final_report",
            data=report_payload,
        )

        with deps.session_factory() as session:
            artifact_repo = WorkflowArtifactRepository(session)
            event_repo = WorkflowEventRepository(session)
            artifact_repo.create(
                workflow_id=workflow_id,
                artifact_type=ArtifactType.REPORT.value,
                uri=report_uri,
                mime_type="application/json",
                metadata={"name": "final_report"},
            )
            event_repo.append(
                workflow_id=workflow_id,
                event_type="workflow_completed",
                actor_type=ActorType.SYSTEM.value,
                payload={"report_uri": report_uri},
            )
            session.commit()

        completed = list(state.get("completed_steps", []))
        completed.append("finalize")

        artifacts = list(state.get("artifacts", []))
        artifacts.append({"type": ArtifactType.REPORT.value, "uri": report_uri})

        return {
            "current_node": "finalize",
            "status": WorkflowStatus.COMPLETED.value,
            "completed_steps": completed,
            "artifacts": artifacts,
            "final_result": {
                "message": "Workflow completed successfully",
                "report_uri": report_uri,
            },
        }

    return finalize_node
