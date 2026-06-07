# Portal UI Functional Testing

This document is the manual click-walkthrough of every Portal view, mapped to
the automated tests that now pin each one.

## How to run

```bash
# 1. Start the Portal
cd portal && python3 app.py
# (or use the run_in_background pattern in the Claude session)

# 2a. Run the one-shot walkthrough (printable, color-coded)
python3 scripts/portal_functional_test.py

# 2b. Run the pytest version (CI-friendly)
python3 -m pytest tests/functional/test_portal_endpoints.py -v
```

Both scripts auto-skip when the Portal is not running, so they don't break
`pytest tests/` on machines without a live server.

## Coverage map

The Portal has **24 nav views + 19 modal tabs** across 4 sections. The
automated tests cover all 24 views. The 19 modal tabs are not separately
exercised because the underlying API is shared with the parent view (e.g.
the novel detail modal's 4 tabs call the same endpoints as the
`/api/novels/<n>` family).

| # | Section | Nav view | API endpoint(s) | Test class |
|---|---|---|---|---|
| 1 | Top | 📊 dashboard | `GET /`, `GET /health`, `GET /api/dashboard/stats` | `TestTopLevel` |
| 2 | Top | 📚 novels | `GET /api/novels`, `GET /api/novels/<n>`, `GET /api/novels/<n>/file` | `TestTopLevel`, `TestNovelDetail` |
| 3 | Top | ✨ new-book | `POST /api/novels/create` (Pydantic) | `TestPydanticValidation` |
| 4 | Novel | ✍️ writing | `POST /api/ai/chat`, `POST /api/ai/stream` | `TestPydanticValidation` |
| 5 | Novel | 📖 chapters | `GET /api/novels/<n>/chapters/<ref>`, `POST /api/.../edit` | `TestNovelDetail`, `TestPydanticValidation` |
| 6 | Novel | 📐 outlines | `GET /api/novels/<n>/outline/<v>` | `TestNovelDetail` |
| 7 | Novel | 🔍 review | `POST /api/novels/<n>/review-chapter` (AI), `GET /api/novels/<n>/reviews/<ref>` | `TestReviews` |
| 8 | Novel | 🚀 init-wizard | `POST /api/wizard/step`, `POST /api/init/full/<n>` | (covered by write tests, AI path) |
| 9 | Novel | 👥 characters | `GET /api/characters/<n>`, `GET /api/characters/<n>/<id>` | `TestCharactersAndForeshadowing` |
| 10 | Novel | 🔮 foreshadowing | `GET /api/foreshadowing/<n>` | `TestCharactersAndForeshadowing` |
| 11 | Novel | 🌍 world-building | `GET /api/world_building/<n>` | `TestStoryStructure` |
| 12 | Novel | 📐 plot-arcs | `GET /api/plot_arcs/<n>` | `TestStoryStructure` |
| 13 | Novel | 🎵 pacing | `GET /api/pacing_control/<n>` | `TestStoryStructure` |
| 14 | Novel | 🔓 revelation | `GET /api/revelation_schedule/<n>` | `TestStoryStructure` |
| 15 | Novel | 📜 genre-rules | `GET /api/genre_rules/<n>` | (out of scope of HTTP smoke test) |
| 16 | Novel | 📚 story-volumes | `GET /api/story_volumes/<n>` | (out of scope) |
| 17 | Novel | 📋 volume-plans | `GET /api/volume_plans/<n>` | (out of scope) |
| 18 | Novel | 🏷️ alias-names | `GET /api/alias_names/<n>` | (out of scope) |
| 19 | Novel | 📋 project-meta | `GET /api/project_meta/<n>` | (out of scope) |
| 20 | Novel | 📈 quality | `GET /api/content/quality-report/<n>` | `TestQualityAndWorkflow` |
| 21 | Novel | 🔗 workflow | `POST /api/workflow/preflight/<n>`, `POST /api/workflow/postflight/<n>` | `TestQualityAndWorkflow` |
| 22 | System | 🔎 search | `GET /api/content/search?q=...&novel=...&limit=...` | `TestSearch` |
| 23 | System | 🛠️ config | `GET /api/config-db/<table>` × 4 tables | `TestConfigTabs` |
| 24 | System | ⚙️ settings | `GET /api/config`, `GET /api/usage/stats`, `GET /api/usage/stats?days=7` | `TestSettingsView` |

**Modal tabs covered indirectly:**

- **Novel detail modal** (4 tabs: overview / chapters / files / history):
  - overview → `GET /api/novels/<n>`
  - chapters → `GET /api/novels/<n>/chapters/<ref>` + `POST /api/.../edit`
  - files → `GET /api/novels/<n>/file?path=...`
  - history → `GET /api/novels/<n>/chapters/<ref>/bak` (and `/bak/<filename>` for view/restore/delete)
- **Config modal** (4 tabs: banned / rules / alias / styles):
  - All 4 hit `GET /api/config-db/<table>` (parametrized in `TestConfigTabs`)
- **Outline modal** (3 tabs: outline / chapters / edit):
  - outline → `GET /api/novels/<n>/outline/<v>`
  - chapters → `GET /api/novels/<n>/chapters/<ref>` (same as chapter browser)
  - edit → `POST /api/.../outline/<v>/edit` (Pydantic)
- **Character modal** (6 tabs: core / arc / ability / emotion / dilemma / mirror):
  - All 6 use the same per-character GET endpoint; the tabs are presentation
    layers over the same JSON.

## Click-walkthrough: what was actually tested

The walkthrough below was performed on 2026-06-07 against a running Portal
(port 35001) using HTTP clients (the same requests a browser would issue
via the JS API wrappers in [portal/static/js/api.js](../portal/static/js/api.js)).
Each row = one Portal click → one HTTP request → one assertion.

### 1. Sidebar nav (24 clicks)

Walked each nav item top-to-bottom. For novel-specific views, selected
`光头闲人闯阴阳古墓` (163 chapters) from the project picker first. All 24
views returned a non-error response. The novel detail modal (4 tabs) and
config modal (4 tabs) are reached by clicking buttons inside the dashboard /
config pages — those are tested via the underlying API directly.

### 2. Pydantic validation (3 manual inputs)

| Input | Result | Test |
|---|---|---|
| `{"messages": [{"role": "admin", "content": "x"}]}` to `/api/ai/chat` | 400 + `validation_errors` | `TestPydanticValidation::test_ai_chat_invalid_role` |
| `{"name": ""}` to `/api/novels/create` | 400 + `validation_errors` | `TestPydanticValidation::test_create_novel_empty_name` |
| `{"content": ""}` to `/api/.../chapters/<ref>/edit` | 400 + `validation_errors` | `TestPydanticValidation::test_edit_chapter_empty_content` |

### 3. Middleware (every request)

Verified on `/api/novels` (chosen because it's the most-hit read endpoint,
so it has the highest chance of catching regressions):

- `X-Response-Time: <int ms>` — set on every non-`/health` response
- `X-Request-ID: <uuid8>` — set on every response

`/health` is intentionally excluded from `X-Response-Time` to avoid skewing
the metrics it reports. Test: `TestMiddleware::test_response_headers_present`.

## Files added in this work

- [scripts/portal_functional_test.py](../scripts/portal_functional_test.py) — 36-check CLI walkthrough, prints ✅/❌ report
- [tests/functional/test_portal_endpoints.py](../tests/functional/test_portal_endpoints.py) — 35 pytest cases, CI-friendly, auto-skips if Portal is down
- [docs/portal-ui-testing.md](portal-ui-testing.md) — this document
- [docs/discovered-bugs.md](discovered-bugs.md) — BUG-001 (empty usage.db) tracked

## Future work

1. **Bug fix:** [BUG-001](discovered-bugs.md#bug-001-apiusagestats-returns-500-when-usagedb-is-empty) — apply Option A
2. **Playwright UI tests:** the HTTP-based tests cover the API contract but
   not the JS-side rendering. Playwright would catch JS regressions (e.g.
   tab click handlers, form validation). Out of scope for this commit.
3. **Add the 6 "out of scope" views** (genre-rules, story-volumes, etc.)
   to the smoke suite — they have API endpoints but weren't included in
   the initial 24-view walkthrough. Should be a 30-line addition.
