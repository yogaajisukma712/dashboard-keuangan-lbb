# LBB Web App Agent Setup

## MCP Roles

- `context-mode`: primary broad project context, project understanding, large-output analysis, planning, logs, test output, and repo-wide scans.
- `RepoMapper`: architecture or module map at start of large features, onboarding, or unfamiliar areas.
- `Serena`: symbol search, definition lookup, reference mapping, call-site inspection, and precise edits/refactors.
- `Playwright`: browser QA, screenshots, interaction checks, login/form/invoice/payment flow verification, and visual regression checks.

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
- Use `Playwright` after UI or route changes to verify real browser behavior.
- Do not re-add `hermes-workflow` or `Context7` unless explicitly requested.

## Project Preference

- Do not work directly before reading current project state.
- Keep changes scoped to requested behavior.
- Preserve user changes in dirty worktrees.
- Prefer self-hosted/local tools over external hosted MCP servers.
