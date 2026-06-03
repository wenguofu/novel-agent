# Novel Agent — System Functional Spec

> Machine-generated + manual supplements. Source of truth: `portal/app.py` AST.
> Auto-generated: {{ generated_at }}. Inventory: {{ endpoint_count }} endpoints.
>
> Regenerate: `python3 scripts/inventory_endpoints.py && python3 scripts/render_spec.py`
> Verify: `python3 scripts/verify_spec.py` (5 checks).

---

## 1. Architecture Overview

Flask + React portal. Unified SQLite/MySQL DB. 12-layer system prompt. DeepSeek SSE.
See [README.md](../../README.md) for stack details and
[openspec/specs/context-builder.md](../../openspec/specs/context-builder.md) for
the layer architecture.

### 1.1 Inventory Coverage

This spec is data-driven: every endpoint section is auto-generated from an AST
scan of `portal/app.py`. The scanner detects:

- **Route + methods** (per `@app.route(...)` decorator)
- **Function name + line number**
- **Docstring (first line)**
- **Direct `repo.<method>()` calls** in the endpoint body
- **Direct `db.<method>()` / `session.<method>()` calls** in the endpoint body
- **Tables read** (inferred from repository method names via the
  `get_X` / `list_X` / `upsert_X` heuristic)

### 1.2 Known AST Limitations

The scanner only inspects the endpoint function body directly. It does NOT
follow:

- Calls inside helper methods of wrapper classes (e.g.
  `WizardHandler.step()` invoked from a regular function endpoint).
- Bare function calls to module-level imports (this codebase mostly uses
  `repo = get_repo(); repo.method()` instead, which is detected).
- Decorators that aren't `@app.route(...)` (e.g. `@app.get`, `@app.post`
  shortcut decorators — not used in this codebase).

For high-value endpoints not detected automatically, see the Manual Notes.

---

## 2. Data Model ({{ endpoint_count }} tables)

See [`portal/models_orm.py`](../../portal/models_orm.py) for canonical
definitions. Brief grouping:

| Group | Tables |
|-------|--------|
| Project | `novels`, `project_meta`, `alias_names`, `style_presets` |
| Story structure | `story_volumes`, `volume_plans`, `chapter_outlines`, `outlines`, `chapters`, `reviews` |
| Domain | `characters`, `foreshadowing`, `world_building`, `plot_arcs`, `pacing_control`, `revelation_schedule`, `genre_rules` |
| Workflow | `story_tracking`, `stage_gates`, `danger_issues` |
| Config (separate DB on MySQL) | `banned_words`, `compliance_rules`, `style_presets` |

---

## 3. Repository Layer ({{ repo_index_size }} methods)

Auto-extracted from `portal/repository.py`. Each method listed with its
parameter list, defaults, docstring, and inferred table name.

{% for method, info in repo_index.items() %}
- `repo.{{ method }}({{ info.params | join(', ') }})` → reads/writes `{{ info.tables | join(', ') }}` — {{ info.docstring }}
{% endfor %}

---

## 4. Context Building (12 layers)

See [openspec/specs/context-builder.md](../../openspec/specs/context-builder.md).
The 12 layers and their token budgets are documented there.

---

## 5. API Endpoints ({{ endpoint_count }})

{% set ns = namespace(current_section="") %}
{% for ep in endpoints %}
{% set section = ep.route.split('/', 3)[1] if '/' in ep.route else '(root)' %}
{% if section != ns.current_section %}
{% set ns.current_section = section %}
### 5.{{ loop.index0 }} {{ section }}
{% endif %}
#### Endpoint: {{ ep.methods[0] }} {{ ep.route }}

- **Function**: `{{ ep.func_name }}` (line {{ ep.line_no }})
- **Description**: {{ ep.docstring or '_No docstring yet — add one in `portal/app.py`._' }}
- **Repository calls**: {% if ep.repo_calls %}`{{ ep.repo_calls | join('`, `') }}`{% else %}none detected{% endif %}
- **DB calls**: {% if ep.db_calls %}`{{ ep.db_calls | join('`, `') }}`{% else %}none detected{% endif %}
- **Tables read**: {% if ep.tables_read %}`{{ ep.tables_read | join('`, `') }}`{% else %}_inferred from repo calls (none detected)_{% endif %}
- **Side effects**: {% if ep.db_calls %}writes to DB{% else %}read-only (per AST scan){% endif %}

{% if ep.key in manual_notes %}
<!-- MANUAL: {{ ep.key }} -->
{{ manual_notes[ep.key] }}
<!-- /MANUAL -->
{% else %}
<!-- MANUAL: {{ ep.key }} -->
<!-- (no manual notes yet — empty placeholder; renderer will preserve on re-render) -->
<!-- /MANUAL -->
{% endif %}

{% endfor %}

---

## Appendix A: Endpoint Index

| Method | Route | Function |
|--------|-------|----------|
{% for ep in endpoints -%}
| `{{ ep.methods[0] }}` | `{{ ep.route }}` | `{{ ep.func_name }}` |
{% endfor %}
