# Restore Notes

- Hermes planner state: `.codex-workflow/planner_state.json`
- Hermes task memory: `.codex-workflow/task_memory.jsonl`
- Hermes manifest: `state/agent-sync/hermes-state-manifest.json`
- Context project snapshot: `state/agent-sync/context-mode/project-snapshot.json`
- Version counter: `state/agent-sync/version.json`

Global context-mode backup included: no

Restoration notes:
- Clone repo.
- Place repo at target workspace path.
- Hermes project-local state is restored directly from `.codex-workflow`.
- Project-safe context snapshot files are restored from `state/agent-sync/context-mode/`.
- If global context backup exists, copy files from `state/agent-sync/context-mode/global/` back into `~/.codex/` carefully.
- Global context-mode restore may mix data from multiple projects and machines. Review before overwrite.
