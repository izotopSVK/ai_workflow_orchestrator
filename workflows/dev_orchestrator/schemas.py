from __future__ import annotations

from pydantic import BaseModel, Field


class AnalysisOutput(BaseModel):
    """Result of the analyze node: which files to touch and what to watch for."""

    target_files: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    notes: str = ""


class PlanStep(BaseModel):
    id: str
    description: str
    target_file: str | None = None
    expected_output: str = ""


class PlanOutput(BaseModel):
    steps: list[PlanStep] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


class ImplementOutput(BaseModel):
    """A proposed change as a unified diff plus a human summary."""

    diff: str = ""
    summary: str = ""
    touched_files: list[str] = Field(default_factory=list)


class SolidViolation(BaseModel):
    principle: str  # one of S, O, L, I, D
    file: str | None = None
    message: str = ""


class SolidReview(BaseModel):
    score: float = Field(ge=0.0, le=1.0, default=1.0)
    violations: list[SolidViolation] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.violations


class Lesson(BaseModel):
    """A distilled, reusable rule learned from a run (self-learning memory)."""

    id: str = ""
    title: str
    detail: str = ""
    tags: list[str] = Field(default_factory=list)
    reward: float = 0.0  # reinforced when a later verify passes after applying it


class Episode(BaseModel):
    """A full trajectory of one run, embedded for similarity retrieval."""

    workflow_id: str
    goal: str
    outcome: str  # completed | failed
    iterations: int = 0
    target_files: list[str] = Field(default_factory=list)
    summary: str = ""


class ToolResult(BaseModel):
    """Uniform result of a PHP toolchain invocation."""

    tool: str
    ok: bool
    output: str = ""
    findings: list[str] = Field(default_factory=list)
