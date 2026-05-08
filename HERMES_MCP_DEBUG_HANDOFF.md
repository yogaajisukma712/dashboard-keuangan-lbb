# Handoff: Hermes Workflow MCP Gagal Attach ke Codex VS Code Chat

Tanggal konteks: 2026-05-07
Workspace: `/home/ubuntu/Documents/lembaga/aplikasi lembaga`

## Masalah

`hermes-workflow` sudah terpasang dan server MCP sehat, tetapi tidak muncul sebagai tool aktif di chat Codex VS Code.

Gejala utama:

- Chat baru/reload tetap tidak menampilkan tool `hermes-workflow`.
- Log Codex menunjukkan thread dibuat dengan `thread_start.dynamic_tool_count=0`.
- Artinya custom MCP tidak ikut dikirim ke toolset thread.

## Yang Sudah Dicek

Config Codex:

- File: `/home/ubuntu/.codex/config.toml`
- `codex mcp list --json` melihat dua server aktif:
  - `context-mode`
  - `hermes-workflow`
- `codex mcp get hermes-workflow` menunjukkan:
  - `enabled: true`
  - command: `/home/ubuntu/Hermes/scripts/hermes-codex-workflow-mcp`

Server Hermes:

- File wrapper ada dan executable:
  - `/home/ubuntu/Hermes/scripts/hermes-codex-workflow-mcp`
- Handshake manual MCP berhasil.
- `tools/list` manual berhasil dan mengembalikan 14 tool:
  - `planner_state_get`
  - `planner_state_upsert`
  - `planner_state_update_step`
  - `task_memory_add`
  - `task_memory_search`
  - `workspace_intelligence_scan`
  - `git_control_status`
  - `test_runner_run`
  - `runtime_observer_snapshot`
  - `browser_ui_plan`
  - `browser_ui_scaffold_playwright`
  - `browser_ui_run_smoke`
  - `deploy_release_check`
  - `deploy_release_execute`

VS Code / Codex extension:

- Extension: `openai.chatgpt-26.429.30905-linux-x64`
- Binary bawaan extension:
  - `/home/ubuntu/.vscode/extensions/openai.chatgpt-26.429.30905-linux-x64/bin/linux-x86_64/codex`
  - version: `codex-cli 0.128.0-alpha.1`
- Binary global/user:
  - `/home/ubuntu/.local/bin/codex`
  - version: `codex-cli 0.128.0`
- Binary lama juga ada:
  - `/usr/local/bin/codex`
  - version: `codex-cli 0.124.0`

## Perubahan Yang Sudah Dilakukan

File diubah:

- `/home/ubuntu/.config/Code/User/settings.json`

Perubahan:

- Menghapus setting:
  - `"chatgpt.cliExecutable": "/home/ubuntu/.local/bin/codex"`

Alasan:

- Extension Codex menyebut `chatgpt.cliExecutable` sebagai `DEVELOPMENT ONLY`.
- Deskripsinya memperingatkan bahwa sebagian extension mungkin tidak bekerja normal jika setting ini dipakai.
- Setelah setting ini dihapus, extension akan memakai binary bawaannya sendiri.

Validasi setelah perubahan:

- `settings.json` valid.
- `chatgpt.cliExecutable` sudah tidak ada.
- Binary bawaan extension tetap bisa membaca MCP dari `/home/ubuntu/.codex/config.toml`.
- `context-mode` dan `hermes-workflow` tetap `enabled: true`.

## Jika Di Chat Baru Masih Gagal

Jangan ulangi setup dari nol. Fokus debug di layer ini:

`VS Code Codex extension -> thread/start -> dynamic tool registration`

Hal pertama yang harus dicek:

1. Query log terbaru di `/home/ubuntu/.codex/logs_2.sqlite`.
2. Cari event `thread/start`.
3. Pastikan apakah masih ada `thread_start.dynamic_tool_count=0`.
4. Cari event `mcpServerStatus/list`.
5. Cari apakah ada error saat MCP server status dibaca.

Jika `dynamic_tool_count` masih `0`, kesimpulan sementara:

- Config MCP benar.
- Hermes server sehat.
- Binary extension bisa membaca MCP.
- Gagal terjadi saat VS Code extension membuat thread dan mengirim daftar custom tool ke session/model.

Langkah berikutnya:

- Cek apakah extension Codex versi `26.429.30905` punya known issue custom MCP di VS Code.
- Coba update extension Codex atau Codex CLI.
- Coba jalankan Codex dari terminal/TUI dengan config yang sama untuk membandingkan apakah custom MCP muncul di luar VS Code extension.
- Jika terminal/TUI bisa memakai MCP tapi VS Code tidak, masalah spesifik di extension VS Code.

## Prompt Untuk Chat Baru

Saya sedang debug `hermes-workflow` MCP di Codex VS Code. Tolong lanjut dari file ini:

`/home/ubuntu/Documents/lembaga/aplikasi lembaga/HERMES_MCP_DEBUG_HANDOFF.md`

Jangan mulai setup dari nol. Tolong cek log terbaru setelah reload VS Code dan thread baru dibuat. Fokus pada:

- apakah `thread_start.dynamic_tool_count` masih `0`
- apakah `mcpServerStatus/list` melihat `hermes-workflow`
- apakah ada error registration custom MCP
- apakah problemnya ada di VS Code extension layer, bukan di server Hermes

Gunakan context-mode untuk membaca log besar dan jangan dump raw output.
