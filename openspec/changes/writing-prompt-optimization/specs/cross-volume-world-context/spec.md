## ADDED Requirements

### Requirement: World building layer returns local + global entries

Layer 5 (世界观) SHALL call `get_world_building_volume_plus_global(novel, volume, local_limit=5, global_limit=5)` instead of the previous `get_world_building_for_volume(novel, volume, limit=10)`. The new method returns up to 5 local entries (related_vol ∈ [vol-1, vol+1] or 0) followed by up to 5 global entries (related_vol > vol+1, excluding IDs already in local).

#### Scenario: Local entries exist
- **WHEN** the novel has 10 world_building rows with related_vol ∈ [0, 1, 2] and the current volume is 1
- **THEN** Layer 5 returns 5 of those 10 rows, tagged `[本卷|domain]` in the output

#### Scenario: Global entries fill remaining slots
- **WHEN** the novel has 8 world_building rows with related_vol > 2 and the local query returned 5
- **THEN** Layer 5 returns the 5 local rows + 5 global rows (total 10), with the 5 global rows tagged `[全局|domain]`

#### Scenario: Global pool is smaller than limit
- **WHEN** the novel has only 3 world_building rows with related_vol > 2
- **THEN** Layer 5 returns 5 local + 3 global = 8 rows (no padding)

#### Scenario: Local pool is empty
- **WHEN** the novel has no world_building rows with related_vol ∈ [vol-1, vol+1]
- **THEN** Layer 5 returns 0 local + 5 global = 5 rows; the layer still renders (does not short-circuit to empty)

### Requirement: Tag world entries by scope

Each world_building entry rendered in Layer 5 SHALL be prefixed with `[本卷|{domain}]` if `related_vol ∈ [0, vol-1, vol, vol+1]`, or `[全局|{domain}]` if `related_vol > vol+1`. The `domain` field is the original `WorldBuilding.domain` column.

#### Scenario: Local entry tag
- **WHEN** a row has `related_vol=1`, `domain="设定"`, `name="乐园规则"`
- **THEN** the rendered line is `- [本卷|设定] 乐园规则: {content}`

#### Scenario: Global entry tag
- **WHEN** a row has `related_vol=4`, `domain="外星种族"`, `name="泽格族"`
- **THEN** the rendered line is `- [全局|外星种族] 泽格族: {content}`

### Requirement: Layer 5 budget remains 1500 tokens

The system SHALL keep Layer 5 budget at 1500 tok. The local+global split is internal; the layer's total allocation is unchanged from the previous spec.
