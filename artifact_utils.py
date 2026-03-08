"""Utilities for cleaning LLM-generated artifacts before writing them to disk."""
from __future__ import annotations

import os
import re


_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+.+$")
_FENCE_RE = re.compile(r"```(?:[\w.+-]+)?\s*\n(.*?)```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"^\s*`{1,3}([^`]+)`{1,3}\s*$")


def strip_markdown_fences(text: str) -> str:
    """Remove a single outer markdown fence if present."""
    text = (text or "").strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def clean_generated_content(path: str, content: str) -> str:
    """Extract the most likely file body from an LLM response."""
    cleaned = (content or "").replace("\r\n", "\n").strip()
    if not cleaned:
        return ""

    block = _extract_best_block(path, cleaned)
    if block:
        return block.strip()

    lines = cleaned.splitlines()
    start = _find_content_start(path, lines)
    if start > 0:
        cleaned = "\n".join(lines[start:]).strip()

    cleaned = strip_markdown_fences(cleaned)
    return _strip_trailing_markdown(cleaned).strip()


def _extract_best_block(path: str, content: str) -> str:
    """Extract the most appropriate fenced block for the target file."""
    matches = list(re.finditer(r"```(?P<lang>[\w.+-]*)\s*\n(?P<body>.*?)```", content, re.DOTALL))
    if not matches:
        return ""

    desired = _expected_languages(path)
    if desired:
        for match in matches:
            lang = (match.group("lang") or "").strip().lower()
            if lang in desired:
                return match.group("body").strip()

    return matches[0].group("body").strip()


def _expected_languages(path: str) -> set[str]:
    """Map filename extensions to likely fence languages."""
    base = os.path.basename(path).lower()
    ext = os.path.splitext(base)[1]
    mapping = {
        ".py": {"python", "py"},
        ".js": {"javascript", "js"},
        ".ts": {"typescript", "ts"},
        ".tsx": {"tsx", "typescript", "ts"},
        ".jsx": {"jsx", "javascript", "js"},
        ".json": {"json"},
        ".yml": {"yaml", "yml"},
        ".yaml": {"yaml", "yml"},
        ".sh": {"bash", "sh", "shell"},
        ".md": {"markdown", "md"},
        ".toml": {"toml"},
        ".html": {"html"},
        ".css": {"css"},
        ".go": {"go"},
        ".rs": {"rust", "rs"},
    }
    if base == "dockerfile":
        return {"dockerfile"}
    if base == "requirements.txt":
        return {"txt", "text", "requirements"}
    return mapping.get(ext, set())


def _find_content_start(path: str, lines: list[str]) -> int:
    """Skip common prose preambles before actual file content starts."""
    for idx, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        if _looks_like_prose_preamble(line):
            continue
        if _HEADING_RE.match(line):
            continue
        if line.lower().startswith(("file:", "filename:", "path:", "here is", "below is")):
            continue
        inline = _INLINE_CODE_RE.match(line)
        if inline:
            lines[idx] = inline.group(1)
        if _looks_like_content(path, lines[idx]):
            return idx
    return 0


def _looks_like_prose_preamble(line: str) -> bool:
    lowered = line.lower()
    return (
        lowered.endswith(":")
        and any(
            token in lowered
            for token in ("code", "implementation", "example", "output", "file", "snippet", "content")
        )
    )


def _looks_like_content(path: str, line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False

    base = os.path.basename(path).lower()
    ext = os.path.splitext(base)[1]

    if base == "dockerfile":
        return bool(re.match(r"^(FROM|RUN|WORKDIR|COPY|ADD|CMD|ENTRYPOINT|ENV|ARG|EXPOSE|USER|LABEL)\b", stripped))
    if base == "requirements.txt":
        return bool(re.match(r"^[A-Za-z0-9_.-]+([<>=!~]=.+)?$", stripped)) and " " not in stripped
    if ext == ".py":
        return bool(re.match(r"^(from |import |def |class |if __name__ == ['\"]__main__['\"]:|@|\"\"\"|'''|[A-Za-z_][A-Za-z0-9_]*\s*=)", stripped))
    if ext in {".json"}:
        return stripped.startswith(("{", "["))
    if ext in {".yml", ".yaml"}:
        return ":" in stripped and not stripped.startswith("#")
    if ext in {".md"}:
        return True
    return True


def _strip_trailing_markdown(text: str) -> str:
    """Trim obvious markdown commentary that trails after content."""
    lines = text.splitlines()
    end = len(lines)
    for idx, line in enumerate(lines):
        if idx == 0:
            continue
        stripped = line.strip()
        if _HEADING_RE.match(stripped):
            end = idx
            break
        if stripped.startswith(("Explanation:", "Notes:", "Why this works:", "Summary:")):
            end = idx
            break
    return "\n".join(lines[:end])
