## Why

The backend's `MINIMAX_MODEL` default was already bumped from `MiniMax-M2.7` to `MiniMax-M3` in commit `2386210`, and the V2.7 model is no longer the recommended generation target. But the **frontend** still presents M2.7 as the default in three places — the ConfigPage dropdown, the ConfigPage default form value, and the API base label. Three more files (`Outlines.tsx`, `Writing.tsx` × 2) hardcode `'MiniMax-M2.7'` as a fallback model string passed to the streaming/chat endpoints. The hardcoded frontend string is actually dead code (the backend `/api/ai/stream` and `deepseek_chat` both ignore the request's `model` field and always use the server-side `cfg["model"]`), but it leaves a misleading default in the UI and creates a maintenance hazard: anyone reading the frontend would think V2.7 is in use, and any future change to make the backend honor the request's model would silently break for the configured model.

## What Changes

- **ConfigPage.tsx** — `MODEL_OPTIONS` entry for MiniMax updated: value `MiniMax-M2.7` → `MiniMax-M3`, label `MiniMax M2.7` → `MiniMax V3`. Default form `model` field updated to `MiniMax-M3` (and `max_tokens` default raised from `8192` to `65536` to match the recent backend bump in commit `223a9d5`). API base URL option label updated from `MiniMax M2.7 (Anthropic兼容)` → `MiniMax V3 (Anthropic兼容)`.
- **Outlines.tsx** (1 site) and **Writing.tsx** (2 sites) — Remove hardcoded `'MiniMax-M2.7'` model string. Read model from `useConfigStore.getState().deepseekConfig?.deepseek_model` at call time, with `''` fallback. Add the `useConfigStore` import.
- **No backend changes.** No API changes. No DB migration. No change to existing saved configs (users with an M2.7 saved value must re-select V3 in the UI — intentional to avoid silently changing the model for users with custom configs).

## Capabilities

### New Capabilities

- `portal-config-page`: Defines the model selection UI on the ConfigPage (options, default selection, API base label) and the rule that the default model must match the backend's `MINIMAX_MODEL` default (`MiniMax-M3`).
- `frontend-model-sourcing`: Defines the rule that frontend pages calling AI streaming/chat endpoints must source the model from the `useConfigStore` (the user's saved selection) and must not hardcode any model string as a fallback. The store is the single source of truth on the frontend; the server-side config remains the source of truth on the backend.

### Modified Capabilities

<!-- No existing spec covers the portal frontend. Leaving empty. -->

## Impact

- `portal/frontend/src/pages/ConfigPage.tsx` — 3 lines changed (option value/label, default form value + max_tokens, API base label).
- `portal/frontend/src/pages/Outlines.tsx` — 1 import added, 1 line changed (model source).
- `portal/frontend/src/pages/Writing.tsx` — 1 import added, 2 lines changed (model source).
- `portal/config.py` — unchanged (already on V3).
- `portal/app.py` — unchanged (already ignores request `model` and uses server-side config).
- No `openspec/specs/` files pre-exist for the frontend — both capabilities land as new spec files under `specs/`.
- No user-visible migration: existing saved M2.7 configs continue to work; users opt in to V3 by re-selecting in the UI.
