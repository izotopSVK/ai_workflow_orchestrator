import uuid

from workflows.models.enums import ApprovalStatus, WorkflowStatus
from workflows.persistence.orm import HumanApproval, WorkflowEvent
from workflows.services.approval_service import ApprovalService


def test_full_workflow_with_human_approval(
    workflow_service, session_factory, artifact_dir
):
    final_state = workflow_service.start_workflow(goal="Draft a status report")

    assert final_state["status"] == WorkflowStatus.WAITING_FOR_HUMAN.value
    assert final_state.get("pending_approval_id") is not None
    assert "plan" in final_state["completed_steps"]
    assert "verify" in final_state["completed_steps"]
    assert "finalize" not in final_state["completed_steps"]

    workflow_id = final_state["workflow_id"]
    approval_id = uuid.UUID(final_state["pending_approval_id"])

    with session_factory() as session:
        approval = session.get(HumanApproval, approval_id)
        assert approval is not None
        assert approval.status == ApprovalStatus.PENDING.value
        assert str(approval.workflow_id) == workflow_id

    with session_factory() as session:
        ApprovalService(session).approve(approval_id, decided_by="tester")
        session.commit()

    resumed_state = workflow_service.resume_workflow(
        workflow_id,
        state_patch={
            "status": WorkflowStatus.RUNNING.value,
            "pending_approval_id": None,
        },
        as_node="human_review",
    )

    assert resumed_state["status"] == WorkflowStatus.COMPLETED.value
    assert "finalize" in resumed_state["completed_steps"]
    assert resumed_state.get("final_result") is not None
    assert resumed_state["final_result"]["report_uri"].startswith("file://")
    assert any(a["type"] == "report" for a in resumed_state["artifacts"])

    with session_factory() as session:
        events = (
            session.query(WorkflowEvent)
            .filter(WorkflowEvent.workflow_id == uuid.UUID(workflow_id))
            .all()
        )
        event_types = {e.event_type for e in events}

    assert "workflow_created" in event_types
    assert "approval_requested" in event_types
    assert "approval_granted" in event_types
    assert "workflow_completed" in event_types


def test_resume_idempotency_does_not_re_execute_completed_nodes(
    workflow_service, session_factory, artifact_dir
):
    final_state = workflow_service.start_workflow(goal="Idempotent run")
    workflow_id = final_state["workflow_id"]
    approval_id = uuid.UUID(final_state["pending_approval_id"])

    with session_factory() as session:
        ApprovalService(session).approve(approval_id, decided_by="tester")
        session.commit()

    workflow_service.resume_workflow(
        workflow_id,
        state_patch={
            "status": WorkflowStatus.RUNNING.value,
            "pending_approval_id": None,
        },
        as_node="human_review",
    )

    with session_factory() as session:
        plan_completed_events = (
            session.query(WorkflowEvent)
            .filter(WorkflowEvent.workflow_id == uuid.UUID(workflow_id))
            .filter(WorkflowEvent.event_type == "workflow_completed")
            .count()
        )
        approval_requested_events = (
            session.query(WorkflowEvent)
            .filter(WorkflowEvent.workflow_id == uuid.UUID(workflow_id))
            .filter(WorkflowEvent.event_type == "approval_requested")
            .count()
        )

    assert plan_completed_events == 1
    assert approval_requested_events == 1
