"""Skills: reusable, task-scoped instruction packages loaded from the repo.

Mirrors the emerging "skill" convention (a markdown file with YAML frontmatter
``name`` / ``description`` plus a body of procedure). Skills are discovered from
standard locations in the target repo/worktree, and the ones relevant to a task
are selected (keyword match, same approach as lesson retrieval) and injected into
the agents' prompts.

Discovery locations (repo-relative), each holding ``*.md`` skill files or
``<skill>/SKILL.md`` directories:

* ``.claude/skills/``
* ``.agents/skills/``
* ``skills/``
"""

from __future__ import annotations

import glob
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

SKILL_DIRS = [".claude/skills", ".agents/skills", "skills"]


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: str


def _parse_frontmatter(text: str, *, fallback_name: str) -> tuple[str, str, str]:
    """Return (name, description, body) from optional ``--- ... ---`` frontmatter.

    Deliberately tiny (no PyYAML dependency): parses ``key: value`` lines.
    """
    name, description = fallback_name, ""
    body = text.strip()
    if body.startswith("---"):
        end = body.find("\n---", 3)
        if end != -1:
            header = body[3:end].strip()
            body = body[end + 4 :].lstrip("\n")
            for line in header.splitlines():
                key, sep, value = line.partition(":")
                if not sep:
                    continue
                key, value = key.strip().lower(), value.strip().strip("'\"")
                if key == "name":
                    name = value or name
                elif key == "description":
                    description = value
    if not description:
        # First non-empty, non-heading line becomes the description.
        for line in body.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                description = line
                break
    return name, description, body


def _score(query: str, text: str) -> int:
    q = {w for w in query.lower().split() if len(w) > 2}
    t = text.lower()
    return sum(1 for w in q if w in t)


class SkillLibrary(Protocol):
    def load(self, root: str) -> list[Skill]: ...

    def select(self, root: str, query: str, k: int) -> list[Skill]: ...


class EmptySkillLibrary:
    """No skills. Default when the target repo ships none."""

    def load(self, root: str) -> list[Skill]:
        return []

    def select(self, root: str, query: str, k: int) -> list[Skill]:
        return []


class DirectorySkillLibrary:
    """Loads skills from standard directories under a repo/worktree root."""

    def __init__(self, *, max_body_chars: int = 4000):
        self.max_body_chars = max_body_chars

    def _iter_files(self, base: Path):
        for skill_dir in SKILL_DIRS:
            root = base / skill_dir
            if not root.is_dir():
                continue
            yield from (Path(p) for p in glob.glob(str(root / "*.md")))
            yield from (Path(p) for p in glob.glob(str(root / "*" / "SKILL.md")))

    def load(self, root: str) -> list[Skill]:
        base = Path(root)
        skills: list[Skill] = []
        seen: set[str] = set()
        for path in self._iter_files(base):
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            fallback = path.parent.name if path.name == "SKILL.md" else path.stem
            name, description, body = _parse_frontmatter(text, fallback_name=fallback)
            skills.append(
                Skill(name=name, description=description, body=body[: self.max_body_chars],
                      path=str(path))
            )
        return skills

    def select(self, root: str, query: str, k: int) -> list[Skill]:
        skills = self.load(root)
        ranked = sorted(
            skills,
            key=lambda s: _score(query, f"{s.name} {s.description}"),
            reverse=True,
        )
        return [s for s in ranked if _score(query, f"{s.name} {s.description}") > 0][:k]
