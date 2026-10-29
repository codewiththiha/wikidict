#!/usr/bin/env python3
"""Refuse a commit subject that breaks the rules in AGENTS.md.

A subject is a conventional commit no longer than 50 characters:
`type(scope): summary`, scope optional, summary in lower case, no full stop.

  python3 tools/commit_check.py --install          # wire into .git/hooks
  python3 tools/commit_check.py --uninstall
  python3 tools/commit_check.py --status           # is the gate armed?
  python3 tools/commit_check.py --range main..HEAD # audit committed history
  python3 tools/commit_check.py <file>             # hook mode

Git skips a hook it cannot execute, and a fresh clone has none, so run
`--status` at the start of a session. CI audits the pushed range as well.
Exit 0 when every subject passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

LIMIT = 50
TYPES = ("feat", "fix", "docs", "refactor", "perf", "test", "build", "ci",
         "chore", "revert", "style")
SHAPE = re.compile(r"^(?P<type>[a-z]+)(\((?P<scope>[a-z0-9._/-]+)\))?!?: "
                   r"(?P<summary>.+)$")
HOOK_MARKER = "wikidict: commit subject gate"
HOOK_BODY = f"""#!/bin/sh
# {HOOK_MARKER}, see tools/commit_check.py.
exec python3 "$(git rev-parse --show-toplevel)/tools/commit_check.py" "$1"
"""


def subject_of(message: str) -> str:
    """The first line that is neither blank nor a git comment."""
    for line in message.splitlines():
        if line.strip() and not line.startswith("#"):
            return line.rstrip()
    return ""


def problems(subject: str) -> list[str]:
    """Every rule the subject breaks; empty when it passes."""
    if not subject:
        return ["there is no subject line"]
    # Git writes these itself; they are rewritten before a merge.
    if subject.startswith(("fixup! ", "squash! ", "amend! ")):
        return []
    found = []
    if len(subject) > LIMIT:
        found.append(f"{len(subject)} characters, over {LIMIT}")
    shape = SHAPE.match(subject)
    if not shape:
        found.append("not `type(scope): summary`")
        return found
    if shape["type"] not in TYPES:
        found.append(f"type `{shape['type']}` is not one of {', '.join(TYPES)}")
    summary = shape["summary"]
    if summary[0].isupper() and not summary.split()[0].isupper():
        found.append("the summary starts with a capital letter")
    if summary.endswith("."):
        found.append("the summary ends with a full stop")
    return found


def check(subject: str, label: str, stream) -> bool:
    found = problems(subject)
    for problem in found:
        print(f"{label}: {problem}", file=stream)
    if found and subject:
        print(f"    {subject}", file=stream)
    return not found


def hook(path: str) -> int:
    with open(path, encoding="utf-8") as handle:
        subject = subject_of(handle.read())
    if check(subject, "commit refused", sys.stderr):
        return 0
    print("Detail belongs in the body, after a blank line.", file=sys.stderr)
    return 1


def audit(rev_range: str) -> int:
    out = subprocess.run(["git", "log", "--format=%h%x09%s", rev_range],
                         capture_output=True, text=True, check=True)
    rows = [line.split("\t", 1) for line in out.stdout.splitlines() if line]
    bad = sum(not check(subject, sha, sys.stdout) for sha, subject in rows)
    print(f"{len(rows) - bad} of {len(rows)} subjects pass.")
    return 1 if bad else 0


def hook_path() -> str:
    git_dir = subprocess.run(["git", "rev-parse", "--absolute-git-dir"],
                             capture_output=True, text=True,
                             check=True).stdout.strip()
    return os.path.join(git_dir, "hooks", "commit-msg")


def ours(path: str) -> bool:
    with open(path, encoding="utf-8") as handle:
        return HOOK_MARKER in handle.read()


def install(force: bool) -> int:
    path = hook_path()
    if os.path.exists(path) and not ours(path) and not force:
        print(f"{path} exists and is not ours; pass --force to replace it.")
        return 1
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(HOOK_BODY)
    os.chmod(path, 0o755)
    print(f"installed {path}")
    return 0


def status() -> int:
    path = hook_path()
    if not os.path.exists(path):
        print(f"no commit-msg hook at {path}: run --install.")
        return 1
    if not ours(path):
        print(f"{path} is not ours, so subjects are unchecked.")
        return 1
    if not os.access(path, os.X_OK):
        print(f"{path} is not executable, so git skips it: run --install.")
        return 1
    print(f"{path} is armed.")
    return 0


def uninstall() -> int:
    path = hook_path()
    if not os.path.exists(path):
        print("no commit-msg hook is installed.")
        return 0
    if not ours(path):
        print(f"{path} is not ours; leaving it alone.")
        return 1
    os.unlink(path)
    print(f"removed {path}")
    return 0


def self_test() -> int:
    assert not problems("feat(packs): add the Thai pack")
    assert not problems("docs: explain the pack format")
    assert not problems("fix: handle JMdict 3.7 layout")
    assert problems("Add the Thai pack")
    assert problems("feat: Add the Thai pack")
    assert problems("feat: add the Thai pack.")
    assert problems("wip: something")
    assert problems("feat: " + "x" * 50)
    assert not problems("fixup! feat: add the Thai pack")
    print("self-test passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("message_file", nargs="?", help="hook mode: the message")
    ap.add_argument("--range", dest="rev_range", metavar="REV",
                    help="audit every subject in a range, e.g. main..HEAD")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="with --install, replace a hook we do not own")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.install:
        return install(args.force)
    if args.uninstall:
        return uninstall()
    if args.status:
        return status()
    if args.rev_range:
        return audit(args.rev_range)
    if args.message_file:
        return hook(args.message_file)
    print("pass a message file, --range, --status or --install.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
