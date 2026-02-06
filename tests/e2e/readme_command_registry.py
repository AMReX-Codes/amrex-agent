from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

BASH_LANGS = {"bash", "sh", "shell"}
FENCE_RE = re.compile(r"^```(\w+)?\s*$")


def iter_readme_files(repo_root: Path) -> list[Path]:
    return sorted(p for p in repo_root.rglob("README.md") if p.is_file())


def extract_readme_entries(repo_root: Path) -> list[dict]:
    entries: list[dict] = []

    for path in iter_readme_files(repo_root):
        text = path.read_text(encoding="utf-8")
        entries.extend(_extract_from_text(path, text, repo_root))

    return entries


def extract_readme_commands(repo_root: Path) -> list[dict]:
    commands: list[dict] = []

    for path in iter_readme_files(repo_root):
        text = path.read_text(encoding="utf-8")
        commands.extend(_extract_commands_from_text(path, text, repo_root))

    return commands


def _extract_from_text(path: Path, text: str, repo_root: Path) -> list[dict]:
    entries: list[dict] = []
    rel_path = str(path.relative_to(repo_root))

    in_fence = False
    fence_lang = ""
    fence_start_line = 0
    block_lines: list[str] = []
    line_no = 0
    bash_block_index = 0
    amrex_block_index = 0

    for line in text.splitlines():
        line_no += 1
        fence_match = FENCE_RE.match(line.strip())
        if fence_match:
            if in_fence:
                block_text = "\n".join(block_lines).strip("\n")
                kind = _classify_block(fence_lang, block_text)
                if kind:
                    if kind == "bash_block":
                        bash_block_index += 1
                        index = bash_block_index
                    else:
                        amrex_block_index += 1
                        index = amrex_block_index
                    entries.append(
                        _make_entry(
                            rel_path,
                            kind,
                            index,
                            block_text,
                            fence_start_line,
                        )
                    )
                in_fence = False
                fence_lang = ""
                block_lines = []
                fence_start_line = 0
            else:
                in_fence = True
                fence_lang = (fence_match.group(1) or "").strip().lower()
                fence_start_line = line_no
                block_lines = []
            continue

        if in_fence:
            block_lines.append(line)

    if in_fence:
        block_text = "\n".join(block_lines).strip("\n")
        kind = _classify_block(fence_lang, block_text)
        if kind:
            if kind == "bash_block":
                bash_block_index += 1
                index = bash_block_index
            else:
                amrex_block_index += 1
                index = amrex_block_index
            entries.append(
                _make_entry(
                    rel_path,
                    kind,
                    index,
                    block_text,
                    fence_start_line,
                )
            )

    entries.extend(_extract_inline_amrex(rel_path, text))

    return entries


def _extract_commands_from_text(path: Path, text: str, repo_root: Path) -> list[dict]:
    rel_path = str(path.relative_to(repo_root))
    commands: list[dict] = []

    in_fence = False
    fence_lang = ""
    fence_start_line = 0
    block_lines: list[str] = []
    line_no = 0
    bash_block_index = 0
    amrex_block_index = 0

    for line in text.splitlines():
        line_no += 1
        fence_match = FENCE_RE.match(line.strip())
        if fence_match:
            if in_fence:
                block_text = "\n".join(block_lines).strip("\n")
                kind = _classify_block(fence_lang, block_text)
                if kind:
                    if kind == "bash_block":
                        bash_block_index += 1
                        index = bash_block_index
                    else:
                        amrex_block_index += 1
                        index = amrex_block_index
                    commands.append(
                        _make_command(
                            rel_path,
                            kind,
                            index,
                            block_text,
                            fence_start_line,
                        )
                    )
                in_fence = False
                fence_lang = ""
                block_lines = []
                fence_start_line = 0
            else:
                in_fence = True
                fence_lang = (fence_match.group(1) or "").strip().lower()
                fence_start_line = line_no
                block_lines = []
            continue

        if in_fence:
            block_lines.append(line)

    if in_fence:
        block_text = "\n".join(block_lines).strip("\n")
        kind = _classify_block(fence_lang, block_text)
        if kind:
            if kind == "bash_block":
                bash_block_index += 1
                index = bash_block_index
            else:
                amrex_block_index += 1
                index = amrex_block_index
            commands.append(
                _make_command(
                    rel_path,
                    kind,
                    index,
                    block_text,
                    fence_start_line,
                )
            )

    commands.extend(_extract_inline_amrex_commands(rel_path, text))

    return commands


def _extract_inline_amrex(rel_path: str, text: str) -> Iterable[dict]:
    entries: list[dict] = []
    in_fence = False
    line_no = 0
    inline_index = 0

    for line in text.splitlines():
        line_no += 1
        fence_match = FENCE_RE.match(line.strip())
        if fence_match:
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if "amrex_agent.py" in line:
            inline_index += 1
            entries.append(
                _make_entry(
                    rel_path,
                    "amrex_agent_inline",
                    inline_index,
                    line.strip(),
                    line_no,
                )
            )

    return entries


def _extract_inline_amrex_commands(rel_path: str, text: str) -> Iterable[dict]:
    commands: list[dict] = []
    in_fence = False
    line_no = 0
    inline_index = 0

    for line in text.splitlines():
        line_no += 1
        fence_match = FENCE_RE.match(line.strip())
        if fence_match:
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if "amrex_agent.py" in line:
            inline_index += 1
            commands.append(
                _make_command(
                    rel_path,
                    "amrex_agent_inline",
                    inline_index,
                    line.strip(),
                    line_no,
                )
            )

    return commands


def _classify_block(lang: str, block_text: str) -> str | None:
    if lang in BASH_LANGS:
        return "bash_block"
    if "amrex_agent.py" in block_text:
        return "amrex_agent_block"
    return None


def _make_entry(
    rel_path: str,
    kind: str,
    index: int,
    raw_text: str,
    start_line: int,
) -> dict:
    normalized = _normalize_text(raw_text)
    return {
        "id": f"{rel_path}::{kind}::{index}",
        "path": rel_path,
        "kind": kind,
        "index": index,
        "start_line": start_line,
        "hash": _hash_text(normalized),
        "first_line": _first_line(normalized),
    }


def _make_command(
    rel_path: str,
    kind: str,
    index: int,
    raw_text: str,
    start_line: int,
) -> dict:
    normalized = _normalize_text(raw_text)
    return {
        "id": f"{rel_path}::{kind}::{index}",
        "path": rel_path,
        "kind": kind,
        "index": index,
        "start_line": start_line,
        "text": normalized,
        "hash": _hash_text(normalized),
        "first_line": _first_line(normalized),
    }


def _normalize_text(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    normalized = "\n".join(lines).strip("\n")
    return normalized


def _hash_text(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:160]
    return ""
