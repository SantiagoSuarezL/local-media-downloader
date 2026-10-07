"""Output root and folder rules.

Final media lives outside the job directory on purpose: the job directory holds
temporary artifacts (``source/``, ``work/``, ``logs/``) that cleanup may delete
at any time, while the file the user asked for must survive that. The root is
configured by the operator (``LMD_OUTPUT_ROOT``), never by a request — the API
selects a *rule*, not a path (TECHNICAL_SPEC §11: "only allow configured output
roots").

Rules are a closed set. Each is a template over a small vocabulary of tokens;
every segment is sanitized and the final path is proven to stay inside the root,
so a hostile title can never escape it.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from .filenames import sanitize_filename


class OutputRule(StrEnum):
    """How final files are organized under the output root."""

    FLAT = "flat"
    BY_EXTRACTOR = "by_extractor"
    BY_DATE = "by_date"


_DEFAULT_RULE = OutputRule.FLAT

# Tokens a rule template may use. Anything else is a programming error, not a
# user input: the rule name comes from the closed OutputRule enum.
_TOKEN = re.compile(r"\{(\w+)\}")

_KNOWN_TOKENS = frozenset({"title", "ext", "extractor", "year", "month", "day"})


def resolve_output_root(root: str | Path) -> Path:
    """Expand and validate the configured output root.

    The root is operator configuration, so it may be absolute or ``~``-relative.
    It is resolved once and every final path is proven to stay inside it.
    """
    candidate = Path(root).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    return candidate.resolve()


def build_output_path(
    root: Path,
    *,
    rule: OutputRule,
    title: str | None,
    extension: str,
    extractor: str | None = None,
    created_at: str | None = None,
    fallback: str,
) -> Path:
    """Build the final path for a job under ``root`` and prove containment.

    ``created_at`` is the job's ISO timestamp; when absent the current UTC date
    is used so the rule is still deterministic within a run.
    """
    extension = extension.strip().lstrip(".")
    stem = sanitize_filename(title, fallback=fallback, extension="")
    ext = sanitize_filename(extension, fallback="bin", extension="")

    tokens = {
        "title": stem,
        "ext": ext,
        "extractor": sanitize_filename(extractor, fallback="unknown", extension=""),
        **_date_tokens(created_at),
    }

    template = _TEMPLATES[rule]
    segments = [_render(segment, tokens) for segment in template.split("/")]

    base = root.resolve()
    candidate = base.joinpath(*segments).resolve()
    if candidate.parent != base and base not in candidate.parents:
        raise ValueError(f"refusing to write outside {base}: {candidate}")
    return candidate


def _render(segment: str, tokens: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in _KNOWN_TOKENS:
            raise ValueError(f"unknown output token: {name}")
        return tokens[name]

    return _TOKEN.sub(replace, segment)


def _date_tokens(created_at: str | None) -> dict[str, str]:
    try:
        parsed = datetime.fromisoformat(created_at) if created_at else datetime.now(UTC)
    except ValueError:
        parsed = datetime.now(UTC)
    return {
        "year": f"{parsed.year:04d}",
        "month": f"{parsed.month:02d}",
        "day": f"{parsed.day:02d}",
    }


_TEMPLATES: dict[OutputRule, str] = {
    OutputRule.FLAT: "{title}.{ext}",
    OutputRule.BY_EXTRACTOR: "{extractor}/{title}.{ext}",
    OutputRule.BY_DATE: "{year}/{month}/{title}.{ext}",
}
