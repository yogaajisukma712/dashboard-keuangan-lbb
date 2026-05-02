# Agent Sync State

Folder ini menyimpan snapshot yang sengaja dibuat agar state kerja bisa ikut ke GitHub.

Isi utama:

- `version.json` -> counter sinkronisasi
- `hermes-state-manifest.json` -> ringkasan planner/task memory Hermes
- `context-mode/` -> snapshot context yang bisa ikut repo
- `RESTORE_NOTES.md` -> catatan pemulihan

Raw state Hermes yang dipulihkan langsung:

- `.codex-workflow/planner_state.json`
- `.codex-workflow/task_memory.jsonl`
