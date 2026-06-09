# frontend-model-sourcing Specification

## Purpose
TBD - created by archiving change portal-default-model-v3. Update Purpose after archive.
## Requirements
### Requirement: No hardcoded model strings in frontend AI call sites

The system SHALL NOT contain any hardcoded model string (e.g. `MiniMax-M2.7`, `MiniMax-M3`, `deepseek-v4-pro`, etc.) as a literal argument at any frontend AI call site that posts to `/api/ai/chat` or `/api/ai/startStream`. Every such call site SHALL source the `model` field from `useConfigStore` at call time.

#### Scenario: Outlines AI generation reads model from store
- **WHEN** the user clicks the AI-generate button in Outlines with the config store holding `deepseek_model: "MiniMax-M3"`
- **THEN** the POST body to `/api/ai/chat` contains `model: "MiniMax-M3"` (not any hardcoded value)

#### Scenario: Writing stream calls read model from store
- **WHEN** the user triggers either the generate or the optimize-rewrite flow in Writing with the config store holding `deepseek_model: "MiniMax-M3"`
- **THEN** both `startStream` invocations pass `"MiniMax-M3"` as the model argument (read from the store, not hardcoded)

### Requirement: useConfigStore is the single source of truth for the frontend model

The system SHALL read the model from `useConfigStore.getState().deepseekConfig?.deepseek_model` at the call site, using empty string as the fallback when the store has not been populated. The system SHALL NOT introduce a new module-level constant, environment variable, or default string for the model in the frontend.

#### Scenario: Store is loaded
- **WHEN** `fetchConfig` has completed and the store holds `deepseek_model: "MiniMax-M3"`
- **THEN** the model passed to the AI call site is the string `"MiniMax-M3"`

#### Scenario: Store is not yet loaded
- **WHEN** the user triggers an AI call before `fetchConfig` has completed (store `deepseek_model` is `undefined`)
- **THEN** the model passed to the AI call site is the empty string `""` (not a hardcoded `MiniMax-M3` or `MiniMax-M2.7`)

#### Scenario: Grep audit finds no hardcoded model strings
- **WHEN** a developer runs `grep -rn "'MiniMax-\|'deepseek-" portal/frontend/src/pages/` against the working tree
- **THEN** the output contains zero matches (every call site reads from the store)

### Requirement: Backend model selection remains server-side

The system SHALL continue to determine the actual model used for generation from the server-side `get_active_deepseek_config()["model"]`, not from the request body's `model` field. The frontend's `model` field is sent for future-proofing but is ignored today. This requirement is unchanged from prior behavior and exists here to document the contract the frontend rule above depends on.

#### Scenario: Frontend sends configured model, backend uses server config
- **WHEN** the frontend posts `model: "MiniMax-M3"` to `/api/ai/stream` and the server-side active config has `model: "MiniMax-M2.7"`
- **THEN** the model actually used for generation is `MiniMax-M2.7` (server-side config wins)

