"""Prompt templates for the dev-orchestrator agents.

Kept separate from the LLM transport (``copilot`` / ``dev_llm``) so prompt
wording can change and be reviewed without touching how the model is called.
"""

from __future__ import annotations

from workflows.dev_orchestrator.schemas import AnalysisOutput, Lesson, PlanOutput, PromptContext

SYSTEM = (
    "You are a senior PHP engineer modernizing a legacy Yii 1.1 application to "
    "run on PHP 8.4 while enforcing SOLID principles. Yii 1.1 pitfalls on PHP "
    "8.4 you must respect: each() is removed; dynamic properties are deprecated "
    "(use #[AllowDynamicProperties] on CComponent/CActiveRecord subclasses or "
    "declare properties); create_function is gone; curly-brace string offsets "
    "are removed; watch magic __get/__set on CActiveRecord. Prefer constructor "
    "dependency injection, single-responsibility classes, and interfaces over "
    "concrete coupling. You propose changes; deterministic tools (Rector, "
    "PHPStan, PHPUnit) verify them."
)


def system_prompt(instructions: str = "") -> str:
    """Base system prompt, optionally extended with project instructions/skills."""
    if not instructions:
        return SYSTEM
    return f"{SYSTEM}\n\n# Project instructions & skills (from the target repo)\n{instructions}"


def lessons_block(lessons: list[Lesson]) -> str:
    if not lessons:
        return "None."
    return "\n".join(f"- {le.title}: {le.detail}" for le in lessons)


def analyze_prompt(goal: str, file_hints: list[str], ctx: PromptContext) -> str:
    return (
        f"Goal: {goal}\n\n"
        f"Candidate files (may be empty): {file_hints or 'unknown'}\n\n"
        f"Relevant lessons from past work:\n{lessons_block(ctx.lessons)}\n\n"
        "Identify the concrete target files to change and the PHP 8.4 / SOLID "
        "risks to watch for."
    )


def plan_prompt(goal: str, analysis: AnalysisOutput, ctx: PromptContext) -> str:
    return (
        f"Goal: {goal}\n\n"
        f"Target files: {analysis.target_files}\n"
        f"Known risks: {analysis.risks}\n\n"
        f"Relevant lessons:\n{lessons_block(ctx.lessons)}\n\n"
        "Produce an ordered plan of 3-6 steps to make the change PHP 8.4 "
        "compatible and SOLID-compliant."
    )


def implement_prompt(goal: str, plan: PlanOutput, ctx: PromptContext) -> str:
    reflection_block = "\n".join(f"- {r}" for r in ctx.reflections) if ctx.reflections else "None."
    return (
        f"Goal: {goal}\n\n"
        f"Plan steps: {[s.model_dump() for s in plan.steps]}\n\n"
        f"Prior failed-attempt reflections to fix this time:\n{reflection_block}\n\n"
        f"Relevant lessons:\n{lessons_block(ctx.lessons)}\n\n"
        "Return a unified diff implementing the plan, the files it touches, "
        "and a one-line summary."
    )


def review_solid_prompt(diff: str) -> str:
    return (
        "Review this unified diff strictly for SOLID violations "
        "(SRP, OCP, LSP, ISP, DIP). Report each violation with its principle "
        f"and file, and an overall score in [0,1].\n\nDiff:\n{diff}"
    )


def reflect_prompt(goal: str, verify_report: dict) -> str:
    return (
        f"Goal: {goal}\n\n"
        f"The verification gates reported:\n{verify_report}\n\n"
        "Write ONE concise, reusable lesson that would prevent this failure "
        "next time. Give it a short title, a detail, and tags."
    )
