"""Mutation boundary enforcement for managed agent repos."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import PurePosixPath
from typing import Iterable, List

from superagent.config import MutationBoundaryConfig


BUILTIN_DENYLIST_PATTERNS = [
    ".git/",
    ".superagent/",
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa",
    "id_ed25519",
    ".superagent_hidden/",
    ".superagent_control/",
    ".superagent_eval_assets/",
    ".superagent_gold/",
]


def normalize_relative_path(path: str) -> str:
    raw = path.replace("\\", "/").strip("/")
    pure = PurePosixPath(raw or ".")
    if pure.is_absolute():
        raise AssertionError("Absolute paths are not allowed inside the mutation boundary.")
    if ".." in pure.parts:
        raise AssertionError("Escaping paths are not allowed inside the mutation boundary.")
    normalized = pure.as_posix()
    return "." if normalized in ("", ".") else normalized


def enforce_boundary(changed_paths: Iterable[str], boundary: MutationBoundaryConfig) -> List[str]:
    flags: List[str] = []
    for raw_path in changed_paths:
        path = normalize_relative_path(raw_path)
        if path == ".":
            continue
        if matches_builtin_denylist(path):
            flags.append("blocking:denylist:" + path)
            continue
        if any(is_within_root(path, protected_root) for protected_root in boundary.protected_roots):
            flags.append("blocking:protected_root:" + path)
            continue
        if not any(is_within_root(path, mutable_root) for mutable_root in boundary.mutable_roots):
            flags.append("blocking:outside_mutable_roots:" + path)
    return sorted(set(flags))


def is_within_root(path: str, root: str) -> bool:
    if root == ".":
        return True
    path_parts = PurePosixPath(path).parts
    root_parts = PurePosixPath(root).parts
    return path_parts[: len(root_parts)] == root_parts


def matches_builtin_denylist(path: str) -> bool:
    basename = PurePosixPath(path).name
    for pattern in BUILTIN_DENYLIST_PATTERNS:
        if pattern.endswith("/"):
            prefix = pattern[:-1]
            if path == prefix or path.startswith(prefix + "/"):
                return True
            continue
        if fnmatch(path, pattern) or fnmatch(basename, pattern):
            return True
    return False
