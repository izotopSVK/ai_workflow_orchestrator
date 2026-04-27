from typing import Any

from pydantic import BaseModel, Field


class Budget(BaseModel):
    max_iterations: int = 10
    max_tool_calls: int = 50
    max_llm_calls: int = 20
    max_runtime_seconds: int = 1800
    max_cost_eur: float = 2.0


class BudgetUsed(BaseModel):
    iterations: int = 0
    tool_calls: int = 0
    llm_calls: int = 0
    runtime_seconds: int = 0
    cost_eur: float = 0.0


class PlanItem(BaseModel):
    id: str
    description: str
    expected_output: str


class PlanOutput(BaseModel):
    steps: list[PlanItem]
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


class StartWorkflowRequest(BaseModel):
    goal: str
    priority: str | None = None


class StartWorkflowResponse(BaseModel):
    workflow_id: str
    status: str
    pending_approval_id: str | None = None


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    status: str
    current_node: str | None = None
    plan: list[dict[str, Any]] = Field(default_factory=list)
    completed_steps: list[str] = Field(default_factory=list)
    pending_approval_id: str | None = None
    final_result: dict[str, Any] | None = None


class ApproveResponse(BaseModel):
    status: str
    workflow_id: str
