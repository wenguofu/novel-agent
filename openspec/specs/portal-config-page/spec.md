# portal-config-page Specification

## Purpose
TBD - created by archiving change portal-default-model-v3. Update Purpose after archive.
## Requirements
### Requirement: Model selector exposes MiniMax V3 as the recommended default

The system SHALL include a MiniMax option in the ConfigPage's `MODEL_OPTIONS` array whose `value` is the string `MiniMax-M3` and whose `label` is the user-facing string `MiniMax V3`. The `desc` field SHALL describe it as the flagship writing model.

#### Scenario: MiniMax V3 option is present
- **WHEN** the ConfigPage is rendered with no saved config
- **THEN** the model selector dropdown contains an option with value `MiniMax-M3` and label `MiniMax V3`

#### Scenario: MiniMax V2.7 option is NOT present
- **WHEN** the ConfigPage is rendered with no saved config
- **THEN** the model selector dropdown does NOT contain an option with value `MiniMax-M2.7` (V2.7 has been retired from the options)

### Requirement: Default form model is MiniMax V3

The system SHALL initialize the ConfigPage form `model` field to `MiniMax-M3` when no saved config is present. The form SHALL also initialize `max_tokens` to `65536` (matching the backend's `DEFAULT_MAX_TOKENS` after commit `223a9d5`).

#### Scenario: First-time visit to ConfigPage
- **WHEN** the user opens the ConfigPage for the first time (no saved config)
- **THEN** the form's `model` field is `MiniMax-M3` and `max_tokens` is `65536`

#### Scenario: Saved config populates the form
- **WHEN** the user has previously saved a config with `model: "MiniMax-M3"` and `max_tokens: 65536`
- **THEN** the form fields reflect the saved values (the defaults are not shown in this case — the saved values take precedence)

### Requirement: API base selector labels MiniMax endpoint with V3

The system SHALL label the `https://api.minimaxi.com/anthropic` option in the API base selector as `MiniMax V3 (Anthropic兼容)`. The label MUST NOT reference "M2.7" anywhere.

#### Scenario: API base dropdown labels
- **WHEN** the ConfigPage is rendered
- **THEN** the API base selector contains an option for the MiniMax endpoint whose label includes the substring "MiniMax V3" and does NOT include the substring "M2.7"

