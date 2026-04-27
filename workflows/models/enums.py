from enum import StrEnum


class WorkflowStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_FOR_HUMAN = "waiting_for_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_FOR_HUMAN = "waiting_for_human"


class ToolCallStatus(StrEnum):
    REQUESTED = "requested"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED_ALREADY_COMPLETED = "skipped_already_completed"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalType(StrEnum):
    FINAL_REPORT_APPROVAL = "final_report_approval"
    CUSTOM = "custom"


class ArtifactType(StrEnum):
    LLM_RESPONSE = "llm_response"
    INTERMEDIATE_JSON = "intermediate_json"
    REPORT = "report"


class ActorType(StrEnum):
    USER = "user"
    SYSTEM = "system"
    LLM = "llm"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class WorkflowPriority(StrEnum):
    NORMAL = "normal"
    HIGH = "high"
