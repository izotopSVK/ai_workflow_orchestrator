import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from workflows.models.enums import WorkflowStatus
from workflows.models.schemas import (
    ApproveResponse,
    StartWorkflowRequest,
    StartWorkflowResponse,
    WorkflowStatusResponse,
)
from workflows.services.approval_service import (
    ApprovalAlreadyDecided,
    ApprovalNotFound,
    ApprovalService,
)
from workflows.services.workflow_service import WorkflowService


router = APIRouter()


def get_workflow_service(request: Request) -> WorkflowService:
    return request.app.state.workflow_service


def get_session_factory(request: Request):
    return request.app.state.session_factory


@router.post("/workflows", response_model=StartWorkflowResponse)
def create_workflow(
    payload: StartWorkflowRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
):
    final_state = workflow_service.start_workflow(goal=payload.goal)
    return StartWorkflowResponse(
        workflow_id=final_state["workflow_id"],
        status=final_state.get("status", WorkflowStatus.CREATED.value),
        pending_approval_id=final_state.get("pending_approval_id"),
    )


@router.get("/workflows/{workflow_id}", response_model=WorkflowStatusResponse)
def get_workflow(
    workflow_id: str,
    workflow_service: WorkflowService = Depends(get_workflow_service),
):
    state = workflow_service.get_state(workflow_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return WorkflowStatusResponse(
        workflow_id=state["workflow_id"],
        status=state.get("status", "unknown"),
        current_node=state.get("current_node"),
        plan=state.get("plan", []),
        completed_steps=state.get("completed_steps", []),
        pending_approval_id=state.get("pending_approval_id"),
        final_result=state.get("final_result"),
    )


@router.post("/workflows/{workflow_id}/resume", response_model=WorkflowStatusResponse)
def resume_workflow(
    workflow_id: str,
    workflow_service: WorkflowService = Depends(get_workflow_service),
):
    final_state = workflow_service.resume_workflow(workflow_id)
    return WorkflowStatusResponse(
        workflow_id=final_state["workflow_id"],
        status=final_state.get("status", "unknown"),
        current_node=final_state.get("current_node"),
        plan=final_state.get("plan", []),
        completed_steps=final_state.get("completed_steps", []),
        pending_approval_id=final_state.get("pending_approval_id"),
        final_result=final_state.get("final_result"),
    )


@router.post("/approvals/{approval_id}/approve", response_model=ApproveResponse)
def approve_workflow(
    approval_id: str,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    session_factory=Depends(get_session_factory),
):
    try:
        approval_uuid = uuid.UUID(approval_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid approval id") from exc

    with session_factory() as session:
        service = ApprovalService(session)
        try:
            approval = service.approve(approval_uuid, decided_by="api-user")
        except ApprovalNotFound as exc:
            raise HTTPException(status_code=404, detail="Approval not found") from exc
        except ApprovalAlreadyDecided as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        session.commit()
        workflow_id = str(approval.workflow_id)

    workflow_service.resume_workflow(
        workflow_id,
        state_patch={
            "status": WorkflowStatus.RUNNING.value,
            "pending_approval_id": None,
        },
        as_node="human_review",
    )
    return ApproveResponse(status="resumed", workflow_id=workflow_id)
