#!/usr/bin/env python3
"""
Project-side Hermes/context sync helper.

Purpose:
- Keep Hermes project state (.codex-workflow) tracked in Git.
- Export a repo-restorable snapshot of context-related state.
- Maintain a monotonically increasing sync version counter.
- Optionally commit and push to GitHub.

Default behavior is strict:
- export snapshots
- increment version counter
- git add -A
- git commit
- git push origin <current-branch>

Safer verification options:
- --skip-git
- --skip-push
- --include-global-context
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = REPO_ROOT / ".codex-workflow"
STATE_DIR = REPO_ROOT / "state" / "agent-sync"
CONTEXT_DIR = STATE_DIR / "context-mode"
GLOBAL_CONTEXT_DIR = CONTEXT_DIR / "global"
VERSION_FILE = STATE_DIR / "version.json"
HERMES_MANIFEST_FILE = STATE_DIR / "hermes-state-manifest.json"
CONTEXT_MANIFEST_FILE = CONTEXT_DIR / "project-snapshot.json"
GLOBAL_CONTEXT_MANIFEST_FILE = GLOBAL_CONTEXT_DIR / "manifest.json"
RESTORE_NOTES_FILE = STATE_DIR / "RESTORE_NOTES.md"

HOME = Path.home()
CODEX_HOME = HOME / ".codex"
GLOBAL_CONTEXT_SOURCES = [
    CODEX_HOME / "context-mode" / "sessions",
    CODEX_HOME / "session_index.jsonl",
    CODEX_HOME / "logs_2.sqlite",
    CODEX_HOME / "logs_2.sqlite-shm",
    CODEX_HOME / "logs_2.sqlite-wal",
    CODEX_HOME / "state_5.sqlite",
    CODEX_HOME / "state_5.sqlite-shm",
    CODEX_HOME / "state_5.sqlite-wal",
]
PROJECT_CONTEXT_FILES = [
    REPO_ROOT / "docs" / "context_mode_app_analysis_2026-04-29.md",
    REPO_ROOT / "context_dashboard_keuangan_lbb_super_smart.txt",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl_tail(path: Path, limit: int = 5) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"raw": line})
    return rows[-limit:]


def ensure_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def copy_file(src: Path, dest: Path) -> dict[str, Any] | None:
    if not src.exists() or not src.is_file():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return {
        "source": str(src),
        "dest": str(dest.relative_to(REPO_ROOT)),
        "size": dest.stat().st_size,
        "sha256": sha256_of(dest),
    }


def export_hermes_state() -> dict[str, Any]:
    planner_path = WORKFLOW_DIR / "planner_state.json"
    task_memory_path = WORKFLOW_DIR / "task_memory.jsonl"
    planner = read_json(planner_path, {})
    task_memory_tail = read_jsonl_tail(task_memory_path, limit=10)
    payload = {
        "exported_at": now_iso(),
        "planner_file": str(planner_path.relative_to(REPO_ROOT)),
        "task_memory_file": str(task_memory_path.relative_to(REPO_ROOT)),
        "planner_exists": planner_path.exists(),
        "task_memory_exists": task_memory_path.exists(),
        "planner_snapshot": planner,
        "task_memory_tail": task_memory_tail,
        "task_memory_count": sum(1 for _ in task_memory_path.open("r", encoding="utf-8")) if task_memory_path.exists() else 0,
    }
    write_json(HERMES_MANIFEST_FILE, payload)
    return payload


def export_project_context_snapshot(include_global_context: bool) -> dict[str, Any]:
    copied_files = []
    for src in PROJECT_CONTEXT_FILES:
        result = copy_file(src, CONTEXT_DIR / src.name)
        if result is not None:
            copied_files.append(result)

    payload = {
        "exported_at": now_iso(),
        "project_context_files": copied_files,
        "global_context_backup_included": include_global_context,
        "global_context_note": (
            "Raw context-mode DB files live under ~/.codex and are global to this machine. "
            "Use --include-global-context if you want a portable but broader backup."
        ),
    }
    write_json(CONTEXT_MANIFEST_FILE, payload)
    return payload


def export_global_context_snapshot() -> dict[str, Any]:
    if GLOBAL_CONTEXT_DIR.exists():
        shutil.rmtree(GLOBAL_CONTEXT_DIR)
    GLOBAL_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

    copied = []
    for src in GLOBAL_CONTEXT_SOURCES:
        if src.is_dir():
            dest_dir = GLOBAL_CONTEXT_DIR / src.name
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(src, dest_dir)
            for item in sorted(dest_dir.rglob("*")):
                if item.is_file():
                    copied.append(
                        {
                            "source": str(src / item.relative_to(dest_dir)),
                            "dest": str(item.relative_to(REPO_ROOT)),
                            "size": item.stat().st_size,
                            "sha256": sha256_of(item),
                        }
                    )
        else:
            result = copy_file(src, GLOBAL_CONTEXT_DIR / src.name)
            if result is not None:
                copied.append(result)

    payload = {
        "exported_at": now_iso(),
        "copied_files": copied,
        "warning": (
            "This snapshot may include context-mode data from more than one project on this machine."
        ),
    }
    write_json(GLOBAL_CONTEXT_MANIFEST_FILE, payload)
    return payload


def update_version() -> dict[str, Any]:
    version = read_json(VERSION_FILE, {})
    sync_count = int(version.get("sync_count") or 0) + 1
    payload = {
        "sync_count": sync_count,
        "version_label": f"v{sync_count:04d}",
        "updated_at": now_iso(),
    }
    write_json(VERSION_FILE, payload)
    return payload


def write_restore_notes(include_global_context: bool) -> None:
    content = f"""# Restore Notes

- Hermes planner state: `.codex-workflow/planner_state.json`
- Hermes task memory: `.codex-workflow/task_memory.jsonl`
- Hermes manifest: `state/agent-sync/hermes-state-manifest.json`
- Context project snapshot: `state/agent-sync/context-mode/project-snapshot.json`
- Version counter: `state/agent-sync/version.json`

Global context-mode backup included: {"yes" if include_global_context else "no"}

Restoration notes:
- Clone repo.
- Place repo at target workspace path.
- Hermes project-local state is restored directly from `.codex-workflow`.
- Project-safe context snapshot files are restored from `state/agent-sync/context-mode/`.
- If global context backup exists, copy files from `state/agent-sync/context-mode/global/` back into `~/.codex/` carefully.
- Global context-mode restore may mix data from multiple projects and machines. Review before overwrite.
"""
    RESTORE_NOTES_FILE.write_text(content, encoding="utf-8")


def run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def current_branch() -> str:
    return run_git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def ensure_origin_remote() -> str:
    remote = run_git("remote", "get-url", "origin").stdout.strip()
    if not remote:
        raise RuntimeError("Remote origin tidak ditemukan.")
    return remote


def has_changes() -> bool:
    result = run_git("status", "--porcelain", check=False)
    return bool(result.stdout.strip())


def git_commit_and_push(version_payload: dict[str, Any], skip_push: bool) -> dict[str, Any]:
    remote_url = ensure_origin_remote()
    branch = current_branch()
    run_git("add", "-A")
    if not has_changes():
        return {
            "remote": remote_url,
            "branch": branch,
            "committed": False,
            "pushed": False,
            "message": "Tidak ada perubahan baru untuk di-commit.",
        }

    commit_message = f"chore(sync): workflow state {version_payload['version_label']}"
    run_git("commit", "-m", commit_message)

    pushed = False
    if not skip_push:
        run_git("push", "origin", branch)
        pushed = True

    return {
        "remote": remote_url,
        "branch": branch,
        "committed": True,
        "pushed": pushed,
        "message": commit_message,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Hermes/context project state to GitHub.")
    parser.add_argument(
        "--include-global-context",
        action="store_true",
        help="Copy raw ~/.codex context-mode DB/session files into the repo snapshot.",
    )
    parser.add_argument(
        "--skip-git",
        action="store_true",
        help="Export snapshots only. Do not git add/commit/push.",
    )
    parser.add_argument(
        "--skip-push",
        action="store_true",
        help="Do git add/commit but stop before push.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_dirs()

    version_payload = update_version()
    hermes_payload = export_hermes_state()
    context_payload = export_project_context_snapshot(
        include_global_context=args.include_global_context
    )
    global_context_payload = None
    if args.include_global_context:
        global_context_payload = export_global_context_snapshot()
    write_restore_notes(args.include_global_context)

    git_payload = None
    if not args.skip_git:
        git_payload = git_commit_and_push(version_payload, skip_push=args.skip_push)

    summary = {
        "ok": True,
        "repo_root": str(REPO_ROOT),
        "version": version_payload,
        "hermes_manifest": str(HERMES_MANIFEST_FILE.relative_to(REPO_ROOT)),
        "context_manifest": str(CONTEXT_MANIFEST_FILE.relative_to(REPO_ROOT)),
        "global_context_manifest": (
            str(GLOBAL_CONTEXT_MANIFEST_FILE.relative_to(REPO_ROOT))
            if global_context_payload is not None
            else None
        ),
        "restore_notes": str(RESTORE_NOTES_FILE.relative_to(REPO_ROOT)),
        "git": git_payload,
        "context_project_files": len(context_payload["project_context_files"]),
        "global_context_files": len(global_context_payload["copied_files"]) if global_context_payload else 0,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        message = {
            "ok": False,
            "command": exc.cmd,
            "returncode": exc.returncode,
            "stdout": exc.stdout,
            "stderr": exc.stderr,
        }
        print(json.dumps(message, indent=2, ensure_ascii=True))
        raise SystemExit(exc.returncode)
    except Exception as exc:  # pragma: no cover - CLI fallback
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, ensure_ascii=True))
        raise SystemExit(1)
