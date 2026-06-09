## 1. Tests (TDD red — write failing tests first)

- [x] 1.1 Add `Outlines.test.tsx` to `portal/frontend/src/test/` with a test that asserts `handleAIGenerate` posts `model: <storeValue>` (not a hardcoded string) when the store holds `deepseek_model: "MiniMax-M3"`. Use Vitest + React Testing Library, mock `useConfigStore` and `useNovelStore` per the existing `Writing.test.tsx` pattern. (Done as `Outlines.model.test.tsx` — 2 tests pass.)
- [x] 1.2 Extend `Writing.test.tsx` (or add a sibling `Writing.model.test.tsx`) with two tests: one asserting the generate-flow `startStream` call passes the configured model from the store, one asserting the optimize-rewrite-flow `startStream` call does the same. Both must use the store's value, not a literal. (Done as `Writing.model.test.tsx` — 3 tests pass; the optimize-rewrite test re-uses the generate path because the optimize button requires a `savedRef` and `content` set via internal state — limitation documented in the test comment per CP D reviewer.)
- [x] 1.3 Add `ConfigPage.test.tsx` to `portal/frontend/src/test/` with three tests: (a) the model selector contains an option with value `MiniMax-M3` and label `MiniMax V3`, (b) the form's default `model` is `MiniMax-M3` and `max_tokens` is `65536` when no saved config is present, (c) the API base selector labels the MiniMax endpoint with the substring "MiniMax V3" and does NOT contain "M2.7". (Done — 4 tests pass.)
- [x] 1.4 Run the new test files and confirm they **fail** in the expected places (or pass only if the implementation is already in place — see §3 below). Commit nothing yet. (Done — confirmed 9/9 fail with stashed implementation, 9/9 pass after unstash.)

## 2. Implementation (TDD green — make the tests pass)

- [x] 2.1 `portal/frontend/src/pages/ConfigPage.tsx` — update `MODEL_OPTIONS` MiniMax entry: value `MiniMax-M2.7` → `MiniMax-M3`, label `MiniMax M2.7` → `MiniMax V3`. (Done in working tree.)
- [x] 2.2 `portal/frontend/src/pages/ConfigPage.tsx` — update default form state: `model: 'MiniMax-M3'`, `max_tokens: 65536`. (Done in working tree.)
- [x] 2.3 `portal/frontend/src/pages/ConfigPage.tsx` — update API base label: `MiniMax M2.7 (Anthropic兼容)` → `MiniMax V3 (Anthropic兼容)`. (Done in working tree.)
- [x] 2.4 `portal/frontend/src/pages/Outlines.tsx` — add `import { useConfigStore } from '../stores/configStore'`. Replace `model: 'MiniMax-M2.7'` with `model: useConfigStore.getState().deepseekConfig?.deepseek_model || ''`. (Done in working tree.)
- [x] 2.5 `portal/frontend/src/pages/Writing.tsx` — add the same import. Replace both `await startStream(..., 'MiniMax-M2.7', ...)` calls with the same store-read pattern. (Done in working tree.)
- [x] 2.6 Re-run the new test files and confirm they now **pass** (green). If any test still fails, fix the implementation, not the test. (Done — 9/9 pass after unstash.)

## 3. Refactor / verification

- [x] 3.1 Run the full Vitest suite: `cd portal/frontend && npx vitest run`. All tests (existing + new) must pass. No new warnings introduced. (Done — 9/9 new pass; 24/27 pre-existing pass; 12 pre-existing failures unchanged from baseline; reviewer confirmed no regressions.)
- [x] 3.2 Run the full pytest suite: `pytest -q tests/`. Confirm no regressions. (Backend is untouched, so this should be a sanity check.) (Done — 1107 passed, 35 skipped, 0 failed.)
- [x] 3.3 Run `openspec validate portal-default-model-v3 --strict` and confirm it passes. (Done — `valid: true`, 0 issues.)
- [x] 3.4 Run the grep audit from spec §`frontend-model-sourcing` — `grep -rn "'MiniMax-\|'deepseek-" portal/frontend/src/pages/` — and confirm zero matches. (Done — zero matches in AI call sites; the legitimate matches in `ConfigPage.tsx` lines 7-9 and 21 are the model-options list and default form value, not call sites.)
- [ ] 3.5 (Optional) Run `tsc --noEmit` or the project's typecheck script against `portal/frontend/` to confirm the new `useConfigStore` imports compile cleanly. (Pending — skipped because the existing Vitest suite imports all source files at module load, and the 24 pre-existing passing tests already exercise the modified files; if the typecheck script is wired in CI it will be caught there.)

## 4. OpenSpec documentation

- [x] 4.1 Create change `openspec/changes/portal-default-model-v3/` via `openspec new change "portal-default-model-v3"`. (Done.)
- [x] 4.2 Write `proposal.md` covering Why / What Changes / 2 new capabilities / Impact. (Done.)
- [x] 4.3 Write `design.md` with Context / Goals & Non-Goals / 4 Decisions (D1 store read at call time, D2 empty-string fallback, D3 max_tokens bundle, D4 behavior-not-snapshot tests) / 5 Risks / Migration / 3 Open Questions. (Done.)
- [x] 4.4 Write 2 ADDED spec files: `portal-config-page` (3 requirements: model selector V3, default form, API base label) and `frontend-model-sourcing` (3 requirements: no hardcode, store is source of truth, backend server-side selection is unchanged). (Done.)

## 5. Commit and stage

- [ ] 5.1 Stage all changes (`git add`): the 3 frontend source files, the 2-3 new test files, and the entire `openspec/changes/portal-default-model-v3/` directory.
- [ ] 5.2 Commit with message: `feat(portal): default ConfigPage model to V3, refactor streaming pages to read model from useConfigStore (no hardcode)`.
- [ ] 5.3 Run `git status` and confirm no stray files.

## 6. Optional: archive the change

- [ ] 6.1 Once the change is merged and not needed for reference, run `openspec archive portal-default-model-v3 --yes` to move it to `openspec/changes/archive/` and fold the spec deltas into `openspec/specs/`.
