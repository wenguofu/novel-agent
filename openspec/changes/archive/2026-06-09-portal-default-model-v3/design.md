## Context

The Novel Agent portal frontend has three classes of "model name" references that have drifted out of sync with the backend:

1. **ConfigPage display** — `MODEL_OPTIONS` array (option value + label + description), the form's default `model` field, and the `api_base` label.
2. **Hardcoded fallback model strings** in `Outlines.tsx` (1) and `Writing.tsx` (2) — passed as the `model` field in request bodies to `/api/ai/chat` and `/api/ai/stream`.
3. **No frontend test** currently locks down the model selection behavior or the no-hardcode rule.

The backend (`portal/app.py`) was updated in commit `2386210` to default to `MiniMax-M3` and the `/api/ai/stream` endpoint ([app.py:1565-1568](portal/app.py#L1565)) plus `deepseek_chat` ([app.py:468-472](portal/app.py#L468)) both **ignore the request's `model` field**, always using `cfg["model"]` from `get_active_deepseek_config()`. This makes the hardcoded frontend string dead code today, but a maintenance trap: the next person reading the frontend would assume V2.7 is in use, and a future backend change to honor the request field would silently override the user's saved selection.

The frontend uses Zustand (`useConfigStore`) to hold the loaded config. The `fetchConfig` action populates `deepseekConfig` with the full response from `/api/config`, which includes `deepseek_model`.

## Goals / Non-Goals

**Goals:**
- ConfigPage shows V3 as the recommended default (matches backend `MINIMAX_MODEL`).
- All streaming/chat pages source the model from `useConfigStore` (the user's saved selection) — no hardcoded model strings anywhere in the frontend.
- Add Vitest coverage that locks down both behaviors so future drift gets caught at test time.
- Keep the change minimal and reversible.

**Non-Goals:**
- Changing the backend API surface (no new endpoints, no schema changes).
- Migrating existing user-saved M2.7 configs automatically (intentional — could silently change behavior for users with custom setups).
- Refactoring the `useSSEStream` hook to drop the `model` parameter (separate concern; the request field is currently ignored anyway, and dropping it would require coordinated changes to every caller).
- Adding lint rules to forbid hardcoded model strings (could be a follow-up; this change just removes the existing ones).

## Decisions

### D1: Read model from store at call time, not via component subscription

**Choice:** Use `useConfigStore.getState().deepseekConfig?.deepseek_model || ''` at the call site inside the event handler, not `const model = useConfigStore(s => s.deepseekConfig.deepseek_model)` at the top of the component.

**Rationale:** The model is only needed when the user clicks a button (handleAIGenerate, handleOptimizeRewrite, handleGenerate). Subscribing the component to that slice would cause re-renders on every config change for no user-visible benefit. Reading via `getState()` is the same pattern used in ConfigPage itself ([ConfigPage.tsx:35](portal/frontend/src/pages/ConfigPage.tsx#L35)) to populate the form from the store after `fetchConfig` resolves.

**Alternatives considered:**
- *Top-of-component subscription*: simpler code but couples re-renders to config state.
- *Pass model through a context provider*: over-engineered for a single store read.
- *Pre-fetch config on app load and cache in module state*: no benefit over `getState()`.

### D2: Fall back to empty string when config is not loaded

**Choice:** `... || ''` (empty string) when `deepseek_model` is undefined.

**Rationale:** The backend ignores the request `model` field and uses `cfg["model"]` server-side, so empty string is safe — the server falls back to `MINIMAX_MODEL` from `config.py` (currently `MiniMax-M3`). Hardcoding `'MiniMax-M3'` in the frontend as a fallback would re-introduce the very drift this change is fixing, just at a different version.

**Alternatives considered:**
- *Hardcode `'MiniMax-M3'`*: same drift problem, just on V3.
- *Throw if config not loaded*: bad UX — the user would have to visit ConfigPage first before any AI feature works.
- *Auto-call `fetchConfig` in the calling pages*: adds network roundtrips and out-of-order store updates.

### D3: Bundle `max_tokens` bump into the same change

**Choice:** While editing the default form state in ConfigPage, also raise `max_tokens` from `8192` to `65536`.

**Rationale:** The backend default was raised in commit `223a9d5` from 8K → 64K. The frontend default was still 8K, so a user who hits "Save" without changing anything would silently downgrade their config. The fix is a one-token edit on the same line being modified for the model default, and it's the same kind of "keep the frontend in sync with the backend default" maintenance. Documented in the proposal under "What Changes".

**Alternatives considered:**
- *Leave max_tokens alone, file a separate change*: creates a confusing two-commit story for what is effectively the same sync-up.
- *Auto-migrate the user's saved max_tokens on load*: out of scope; touches the config-load path and the saving user could legitimately want a lower value.

### D4: Tests cover behavior, not snapshot

**Choice:** New Vitest cases in `ConfigPage.test.tsx`, `Outlines.test.tsx`, `Writing.test.tsx` assert: (a) the model dropdown has V3 in its options, (b) the default form value is V3, (c) `handleAIGenerate` in Outlines posts `model: <configured-model>` (not a hardcoded string), (d) the two `startStream` calls in Writing pass the configured model.

**Rationale:** Snapshot tests would catch the literal string change but not the rule. Behavior tests let us change the model name in the future and update the test intentionally, rather than rubber-stamping.

**Alternatives considered:**
- *Snapshot tests only*: catches the current diff but won't catch a future re-introduction of a hardcoded `'MiniMax-M4'` (or whatever) on a different page.
- *ESLint rule forbidding `'MiniMax-...'` strings*: powerful but noisy — model strings could legitimately appear in comments, changelogs, or test fixtures.

## Risks / Trade-offs

- **[Risk] User with a saved M2.7 config continues using M2.7 silently** → Mitigation: the V3 option is now the **default** in the dropdown, so the next time the user opens ConfigPage the change is visible. Documented in proposal under "What Changes". No forced migration.
- **[Risk] Empty-string fallback hides a real misconfiguration** → Mitigation: backend already returns `400 "API Key 未配置"` if the active config has no key, which the user will hit before they hit a model issue. The empty-string fallback is only a model concern; the API key check is upstream.
- **[Risk] Backend someday starts honoring the request's `model` field** → Mitigation: that's the moment this change pays off — the frontend will already be sending the user's saved selection, not a hardcoded value. (Documented as the design's main motivator.)
- **[Trade-off] `Writing.test.tsx` and `Outlines.test.tsx` don't currently exist** → Need to create them. That's expected for a new behavior coverage area; the existing `Writing.test.tsx` file is a smoke test for render, not behavior. The new files focus on model-sourcing behavior.
- **[Trade-off] Vite/Vitest frontend test suite is slower than pytest** → TDD iteration in the frontend takes longer per cycle. Acceptable given the small scope of the change.

## Migration Plan

1. Land the proposal + design + specs + tasks + tests.
2. The code changes are already in the working tree (this change was driven from a working implementation; the test pass is the green confirmation).
3. No deployment step — the change is a static asset rebuild. Frontend devs run `npm run build` (or whatever the existing build command is — TBD from `package.json`) and the Vite bundle picks up the new model strings.
4. Rollback: revert the commit. No data migration, no user state changes.

## Open Questions

- **Q1: Should the dropdown show *only* V3, or keep V2.7 / DeepSeek V4 Pro / V4 Flash as legacy options?** Current code keeps all four; this change just updates the V3 option's value/label. Keeping legacy options is consistent with the existing UX and lets users with custom-API endpoints (DeepSeek) keep their setup. **Decision: keep as-is.**
- **Q2: Does the frontend test suite run in CI?** TBD — if not, the test coverage in this change won't actually block regressions. Worth checking before claiming done.
- **Q3: Is there a `package.json` script for "typecheck" or "lint" the frontend?** TBD — should run alongside pytest to catch any TS errors introduced by the new `useConfigStore` imports.
