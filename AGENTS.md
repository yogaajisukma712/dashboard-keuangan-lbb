# LBB Web App Agent Setup

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
