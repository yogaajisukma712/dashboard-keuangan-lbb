# LBB Web App Agent Setup

## ⚠️ DEPLOYMENT — WAJIB BACA SEBELUM UBAH KODE PRODUKSI

Aplikasi produksi ini **di-host di Vercel**, domain: `https://app.supersmart.click`.

### Fakta penting (jangan ulangi kesalahan lama)
- **Auto-deploy dari GitHub TIDAK AKTIF / tidak reliabel.** Push ke `main` saja TIDAK membuat perubahan tampil. Deploy terakhir via Git bisa tertinggal berjam-jam. SETIAP perubahan produksi HARUS deploy manual via Vercel CLI.
- App ini **tidak jalan** sebagai proses lokal di server dev ini. Proses gunicorn di port 4500 (`admin_app:app`) dan container Docker (Portainer port 8000, generator-*) adalah aplikasi LAIN — bukan dashboard ini. Jangan bingung.
- Entrypoint Vercel: `api/index.py` (import `app` dari `run.py`). Config: `vercel.json` (rewrite semua ke `api/index.py`, region `sin1`).

### Cara deploy ke Vercel (produksi)
```bash
cd "/home/ubuntu/Documents/lembaga/aplikasi lembaga"
TOK=$(tr -d ' \n\r' < "api key penting/vercel.key")
vercel --prod --yes --token "$TOK"
```
- Token Vercel ada di: `api key penting/vercel.key` (JANGAN tempel isinya ke chat/commit).
- Project Vercel: `lbb-dashboard` (id `prj_Fvlx3HeQBQ6FONGxitY5LSo7eMZR`, team `lbbsupersmart-1572`). Sudah ter-link di `.vercel/project.json`.
- Cek status: `vercel ls --token "$TOK"` atau `vercel inspect <url> --token "$TOK"`.
- Setelah deploy sukses akan muncul `Aliased: https://app.supersmart.click`. Lalu minta user hard-refresh (Ctrl+Shift+R).

### `.vercelignore` — HATI-HATI
- Saat deploy CLI, bundle function dibatasi **500 MB**. Folder berat WAJIB ada di `.vercelignore`: `.codex-workflow` (~646MB), `.venv`, `.gitnexus`, `.serena`, `backups`, `graphify-out`, `node_modules`, `.repomap.tags.cache.v1`. Kalau deploy gagal "Total bundle size exceeds 500 MB", cari folder besar baru dengan `du -sh */ .[!.]*/ | sort -rh | head` lalu tambahkan ke `.vercelignore`.
- **JANGAN** masukkan `*.html` ke `.vercelignore` — itu membuang semua template Jinja dan app rusak saat deploy CLI. (Pernah terjadi; sudah diperbaiki.)

### GitHub
- Remote: `https://github.com/yogaajisukma712/dashboard-keuangan-lbb.git`, branch `main`.
- Commit + push tetap dilakukan untuk histori kode, TAPI ingat: push ≠ deploy. Deploy tetap manual via CLI di atas.

### Database (produksi)
- PostgreSQL **Neon** (bukan Postgres Docker lokal). Koneksi asli: `api key penting/neon-direct-conn.txt` (host `ep-ancient-mountain-b3vwbagh.c-4.ap-southeast-1.aws.neon.tech`, db `neondb`).
- Query manual pakai `python3` + `psycopg2` (sudah terpasang); `psql` tidak tersedia di server ini.

## Primary Project Map

Before changing this project, read `PROJECT_MAP.md`.

`PROJECT_MAP.md` is the canonical handoff for agents and developers. It points to the OpenSpec requirements, detailed integration blueprints, architecture coverage audit, audit question suite, ADRs, and guardrails needed to understand the project without the user re-explaining it.

For any non-trivial change, do not start from route files alone. Start from:

1. `PROJECT_MAP.md`
2. `docs/architecture/README.md`
3. `docs/architecture/blueprint-coverage-audit.md`
4. relevant `openspec/specs/*/spec.md`
5. relevant `docs/blueprints/*.md`

## MCP Roles

- `context-mode`: primary broad project context, project understanding, large-output analysis, planning, logs, test output, and repo-wide scans.
- `RepoMapper`: architecture or module map at start of large features, onboarding, or unfamiliar areas.
- `Serena`: symbol search, definition lookup, reference mapping, call-site inspection, and precise edits/refactors.

## Before Editing

1. Build a short affected-area map.
2. Identify entry points, symbols, references, and relevant tests/checks.
3. Produce a concise implementation plan.
4. Edit only after the plan is clear.
5. Run relevant tests/checks.

## Tool Routing

- Use `context-mode` first for repo state, large command output, logs, test output, and broad planning.
- Use `Serena` when changing code around known functions/classes/routes/services/templates.
- Use `RepoMapper` only for large or unfamiliar architecture tasks.
- Do not re-add `hermes-workflow` or `Context7` unless explicitly requested.

## Project Preference

- Do not work directly before reading current project state.
- Keep changes scoped to requested behavior.
- Preserve user changes in dirty worktrees.
- Prefer self-hosted/local tools over external hosted MCP servers.

## MCP-First Mandatory Workflow

Do not work without MCP when MCP can help. Use MCP proactively without waiting for the user to ask.

Before code work:
- Use context-mode for broad scan, large outputs, logs, test output, dependency output, git history, and any command likely over 20 lines.
- Use repomapper for architecture/module map when starting unfamiliar feature work or cross-file changes.
- Use serena for symbol lookup, definitions, references, call sites, and precise refactor planning.

Execution rules:
- Start with a short affected-area map from MCP evidence.
- Prefer ctx_batch_execute for gathering multiple facts.
- Prefer ctx_execute or ctx_execute_file for count/filter/parse/summarize work.
- Do not dump raw large shell output into chat.
- Do not claim MCP is unavailable until codex mcp list and the relevant binary/config have been checked.
- If an MCP server is configured but not attached in the current Codex session, say that first, then continue with the safest fallback and tell the user to restart Codex for full MCP tools.

Default tool roles:
- context-mode: primary context and large-output analysis.
- serena: code symbols, references, and precise edits.
- repomapper: architecture maps and module relationships.

Only skip MCP for tiny one-command tasks where MCP adds no value.

## Handoff Continuity

At the start of every new Codex session or chat in code-server:
- Read `/root/CODEX_HANDOFF.md`.
- Read `/workspace/CODEX_HANDOFF.md` when present.
- Check current real state before edits.
- Continue from the handoff and dirty worktree; do not restart setup from zero.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **dashboard-keuangan-lbb** (4374 symbols, 15583 relationships, 370 execution flows).

> Index stale? Run `node .gitnexus/run.cjs analyze --index-only` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? Bootstrap with `npx`, `bunx`, or `pnpm dlx` — e.g. `bunx gitnexus@latest analyze` (npm 11 npx crash; #1939).

## Always Do

- **MUST run impact analysis before editing.** Use `impact({target: "symbolName", direction: "upstream"})` (MCP) or `node .gitnexus/run.cjs impact "symbolName" --direction upstream --repo .` (CLI fallback); report callers, processes, and risk. Never substitute grep for graph analysis.
- **MUST analyze graph changes before committing.** Use `detect_changes({scope: "all"})` (MCP) or `node .gitnexus/run.cjs detect-changes --scope all --repo .` (CLI fallback). `partial: true` or `truncated: true` is not a clean check — a zero means unseen, not unaffected; re-run it. For regression review: `detect_changes({scope: "compare", base_ref: "main"})` or `node .gitnexus/run.cjs detect-changes --scope compare --base-ref "main" --repo .`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- **MUST treat `risk: UNKNOWN` as unresolved, not as low.** An empty caller set is not evidence the symbol is unused — it can also mean the callers are not resolvable by the index (plain-object property access, dynamic dispatch, cross-language calls). `impact` pairs `UNKNOWN` with a `riskNote` saying so. Confirm with a text search before treating the symbol as safe to change or delete; do not proceed on the strength of a zero.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method before MCP/CLI impact analysis.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis, and never read `UNKNOWN` as an all-clear — it means the walk could not answer, which is the one verdict that requires confirming by other means.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit before MCP/CLI graph change analysis.

## Resources

| Resource | Use for |
| --- | --- |
| `gitnexus://repo/dashboard-keuangan-lbb/context` | Codebase overview, check index freshness |
| `gitnexus://repo/dashboard-keuangan-lbb/clusters` | All functional areas |
| `gitnexus://repo/dashboard-keuangan-lbb/processes` | All execution flows |
| `gitnexus://repo/dashboard-keuangan-lbb/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
| --- | --- |
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
