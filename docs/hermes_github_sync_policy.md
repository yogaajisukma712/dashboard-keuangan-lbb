# Hermes GitHub Sync Policy

Tujuan:

- setiap siklus kerja punya `version count` yang terus naik
- state `hermes-workflow` ikut tersimpan di GitHub
- snapshot `context-mode` ikut tersimpan di repo agar lebih mudah dipulihkan di perangkat atau server lain

## Bagian yang benar-benar bisa dipulihkan dari repo

Hermes project state:

- `.codex-workflow/planner_state.json`
- `.codex-workflow/task_memory.jsonl`

Repo snapshot tambahan:

- `state/agent-sync/version.json`
- `state/agent-sync/hermes-state-manifest.json`
- `state/agent-sync/context-mode/project-snapshot.json`
- `state/agent-sync/RESTORE_NOTES.md`

## Kenyataan penting soal context-mode

Raw database `context-mode` pada mesin ini tidak hidup di repo project. Lokasinya ada di home-level seperti:

- `~/.codex/context-mode/sessions/*.db`
- `~/.codex/session_index.jsonl`
- `~/.codex/state_5.sqlite*`
- `~/.codex/logs_2.sqlite*`

Karena itu ada dua mode backup:

1. Project-safe snapshot
   - aman untuk repo project
   - hanya menyalin snapshot yang relevan ke repo ini
2. Global context snapshot
   - menyalin raw DB/context global ke repo
   - lebih portabel
   - tapi bisa ikut membawa data project lain dari mesin yang sama

## Script sinkron wajib

File:

- `scripts/hermes_github_sync.py`

Default script:

1. naikkan `sync_count`
2. refresh manifest Hermes
3. refresh snapshot context repo
4. `git add -A`
5. `git commit`
6. `git push origin <current-branch>`

Contoh:

```bash
python3 scripts/hermes_github_sync.py
```

Mode aman tanpa commit/push:

```bash
python3 scripts/hermes_github_sync.py --skip-git
```

Mode commit tanpa push:

```bash
python3 scripts/hermes_github_sync.py --skip-push
```

Mode dengan raw global context-mode backup:

```bash
python3 scripts/hermes_github_sync.py --include-global-context
```

## Cara membuatnya benar-benar wajib di Hermes

Hermes README menyebut enforcement ini ada di level project setting, bukan di file repo:

- set `github_repo_url`
- set `github_branch`
- set `github_token`
- aktifkan `github_required`

Jika `github_required=true`, task Hermes akan ditolak atau gagal bila push GitHub gagal.

Artinya:

- script repo ini menyiapkan data dan snapshot yang perlu ikut ke git
- enforcement wajib push tetap harus diaktifkan di UI / config project Hermes

## Saran operasional

Untuk repo ini:

1. aktifkan `github_required` di Hermes project
2. pakai script ini sebagai langkah sync manual/otomatis setelah task
3. pakai `--include-global-context` hanya jika Anda memang ingin backup raw context-mode lintas mesin
