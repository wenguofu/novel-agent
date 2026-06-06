# M5.2 — Server-Side Re-Review Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the post-optimization re-review from the React client to the Flask server. After `api_optimize_chapter` produces a new chapter version, the server will:
1. Save the optimized content to the chapter file (replacing the prior content; the .bak backup keeps the previous version).
2. Persist the pre-optimization review row at `chapter_ref="vol-01/ch-001"`.
3. Run the review pipeline again and persist a second row at `chapter_ref="vol-01/ch-001-post-rev{N}"`, where `N` matches the .bak revision number that was just created.
4. Return both review rows in a single response so the client can render the "✅ 复审全部通过" / "⚠️ 复审仍有问题" verdict without making a second round-trip.

A new `?preview=true` query param on `optimize-chapter` opts out of all side effects (no save, no backup, no re-review, no second-row write) so existing clients/CLI tools that only want the LLM output keep working.

**Architecture:**

- **One round-trip, two `reviews` rows.** The `reviews` table already keys on `UNIQUE(novel_id, chapter_ref)`. Each post-optimization pass uses a distinct `chapter_ref` suffix (`-post-rev1`, `-post-rev2`, …) so we never collide with the original row or with prior post-rev rows. The `ON CONFLICT(novel_id, chapter_ref) DO UPDATE` clause becomes the safe default for both: pre-review upserts the original ref; post-review inserts a brand-new ref on first write (or updates it on retry).
- **One review helper, two callers.** Extract `_run_review(novel_name, chapter_ref, ch_content)` from `api_review_chapter`. The helper returns the structured dict (script_results, ai_review, word_count, bcontrast_count, etc.) and the upsert logic. Both `api_review_chapter` and the new post-optimize flow call it. `api_review_chapter` becomes a thin wrapper that reads the chapter content and calls the helper; the optimize path writes the new content first, then calls the helper twice (pre + post).
- **Counter coupling.** The post-rev{N} suffix is the .bak rev number (1, 2, 3, …). We compute `rev` **once** in `api_optimize_chapter`, copy the chapter to `.bak/{chapter_ref.replace('/','-')}.rev{rev}.md`, save the new content, then run the helper twice with `chapter_ref_post = f"{chapter_ref}-post-rev{rev}"`. This guarantees the backup file, the post-rev row, and the user-visible revision number are in lockstep.
- **Preview mode.** `?preview=true` (or any case-insensitive truthy value: `1`, `yes`, `on`) bypasses the backup, the save, and both review calls. The response carries `preview: true` and omits `pre_review`/`post_review`/`diff`. This preserves the current contract: optimized content is returned, nothing on disk is changed.

**Tech Stack:** Backend: Flask 2.x + sqlite3 (raw `content_db.get_db()` for the `reviews` upsert) + subprocess (3 review scripts) + httpx (DeepSeek chat). Frontend: vanilla JS in `portal/static/js/app.js` (no bundler; uses global `App` namespace and `API.*` methods). Test framework: pytest with `tests/functional/conftest.py` fixtures (`client`, `sample_novel`, `tmp_db`, monkeypatched `app.deepseek_chat`).

---

## File Map

| File | Role |
|---|---|
| `/Users/wgfu/Desktop/novel-agent/portal/app.py` | Add `_run_review` helper; refactor `api_review_chapter`; rewrite `api_optimize_chapter` |
| `/Users/wgfu/Desktop/novel-agent/portal/content_db.py` | No schema change. The `reviews` table already supports what we need. |
| `/Users/wgfu/Desktop/novel-agent/portal/static/js/app.js` | Stop calling `API.editChapter` and the second `API.reviewChapter` from the optimize success path; consume `pre_review`/`post_review`/`diff` from the new response |
| `/Users/wgfu/Desktop/novel-agent/tests/functional/test_writing_api.py` | New tests for `?preview=true`, `_run_review` extraction, two-row persistence, response shape |
| `/Users/wgfu/Desktop/novel-agent/tests/functional/_helpers.py` | New helper `fake_deepseek_review_chat` (returns a YAML-shaped review) and `make_post_rev_ref(chapter_ref, n)` if needed |

---

## Response Shapes

**Current `optimize-chapter` response (unchanged for preview):**
```json
{"success": true, "content": "...", "chapter_ref": "vol-01/ch-001",
 "word_count": 2731, "usage": {...}}
```

**New `optimize-chapter` default response:**
```json
{
  "success": true,
  "content": "...",
  "chapter_ref": "vol-01/ch-001",
  "post_review_ref": "vol-01/ch-001-post-rev1",
  "backup": "vol-01-ch-001.rev1.md",
  "word_count": 2731,
  "usage": {...},
  "pre_review": {
    "ai_review": "...",
    "wc_ok": false,
    "compliance_ok": false,
    "forbidden_ok": true,
    "bcontrast_count": 2,
    "tell_count": 4,
    "script_results": {"analyze": {...}, "compliance": {...}, "forbidden": {...}}
  },
  "post_review": {
    "ai_review": "...",
    "wc_ok": true,
    "compliance_ok": true,
    "forbidden_ok": true,
    "bcontrast_count": 4,
    "tell_count": 1,
    "script_results": {"analyze": {...}, "compliance": {...}, "forbidden": {...}}
  },
  "diff": {
    "wc_ok": [false, true],
    "compliance_ok": [false, true],
    "forbidden_ok": [true, true],
    "bcontrast_count": [2, 4],
    "tell_count": [4, 1],
    "all_pass": true
  }
}
```

**New `optimize-chapter?preview=true` response:**
```json
{
  "success": true,
  "content": "...",
  "chapter_ref": "vol-01/ch-001",
  "word_count": 2731,
  "usage": {...},
  "preview": true
}
```

---

## Design Decisions (from the 8 open questions)

1. **Preview detection:** `request.args.get("preview", "").lower() in ("1","true","yes","on")`. Anything else (including missing param) means full server-side re-review.
2. **Pre-review caching:** Always re-run. Simplicity wins. The pre-review is against the **on-disk chapter file** (the un-optimized version), which is a fresh read. A TTL cache would have to also invalidate on file mtime, and the chapter file is about to be overwritten by the optimization — caching the pre-review across a save is the kind of subtle bug we don't want.
3. **Backup revision interaction:** Share the counter. Compute `rev` once at the top of `api_optimize_chapter`, use it for the .bak copy and the `post-rev{N}` chapter_ref. Single source of truth.
4. **ON CONFLICT on the original ref:** The original `vol-01/ch-001` row continues to be a normal pre-review. If `api_review_chapter` is called again later (e.g., a different user session, or a `?force=1` re-review from the UI), it will `ON CONFLICT … DO UPDATE` the pre-review row. That is the existing behavior and is what we want — the pre-review row is "the latest pre-optimization review". The post-rev{N} rows are immutable history.
5. **Response shape:** Defined above. The `diff` block is the client-ready summary; the full `pre_review`/`post_review` blocks are present for the AI Detail panel and for debugging.
6. **Idempotency / error handling:**
   - **Backup succeeds, save fails:** restore from .bak, return 500 with `success: false, error: "save failed"`. No review row was written, so state is unchanged.
   - **Save succeeds, pre-review fails:** content is already on disk (this is acceptable — the user invoked optimize, the new content exists). Return 200 with `success: false, error: "pre-review failed", content: <new>`. Client treats it as "optimize ok, re-review failed" (yellow toast). No rollback.
   - **Save succeeds, pre-review ok, post-review fails:** pre-review row is persisted. Return 200 with `success: false, error: "post-review failed"`, plus the persisted pre-review. Accept the half-state — the post-review is the *new* version's review, not a destructive op. Client can re-trigger the optimize to get a fresh pre+post.
   - **All succeed, post-rev row insert fails on retry:** this is what `ON CONFLICT DO UPDATE` protects against. The row is still there or updated.
7. **Helper extraction:** Yes, extract `_run_review(novel_name, chapter_ref, ch_content) -> dict`. The helper runs the 3 scripts, calls DeepSeek for the AI review, parses the analyze stdout, and returns a flat dict. The persistence (writing the markdown file + upserting the `reviews` row) can stay inline in `api_review_chapter` for now, or be a second helper `_persist_review(novel_name, chapter_ref, helper_result) -> None` that both call. Recommended: extract both. The optimize path calls `_run_review` twice and `_persist_review` twice.
8. **Client compatibility:** Change the client to NOT call `API.editChapter` after `API.optimizeChapter` (the server already saved). Use `optResp.post_review` to render the verdict. Keep `App._optimizeFromReview` and `App._autoReviewOptimize` flows working — they already call `API.reviewChapter` first, then `API.optimizeChapter`. The new optimize response replaces the second `API.reviewChapter` call. The `_reOptimize` and `_continueAutoOptimize` flows (optimize → re-review → maybe re-optimize) keep working because each optimize call returns a fresh post-rev{N}.

---

## Open Questions Worth Surfacing to the User

1. **`-post-rev{N}` vs `-r{N}` vs `<chapter_ref>.r{N}`:** the user spec said `-post-rev{N}` so we use that, but the dash in `ch-001-post-rev1` may look like a different chapter to future regex parsers (e.g., `_sync_review_from_file` joins on `chapter_ref`). Confirm this naming is safe with the existing regexes in `content_db.py` line 642 (`f"{chapter_ref}-review.md"`).
2. **Should the pre-review row be **inserted** when optimize runs, or only if pre-review actually finds issues?** Simpler: always insert. But if the chapter was already clean, we end up with two identical rows.
3. **Should we add an `optimized_at` column to `reviews` so clients can show "last optimized at …"?** Out of scope for M5.2 but worth noting.
4. **Concurrency:** if two clients optimize the same chapter simultaneously, we end up with two competing rev numbers (both compute the same N from the empty .bak dir) and the second save wins. Acceptable for now (the project is single-user) but worth flagging.
5. **Should `api_optimize_chapter` continue to write the legacy `reviews/{ch_id}-review.md` markdown file?** It does today. We can drop it or keep it. The plan keeps it for backward compat with the existing sync path in `_sync_review_from_file`.

---

## Task Index

- T1: `?preview=true` opt-out (4 tests, no behavior change to default)
- T2: Extract `_run_review` + `_persist_review` helpers (4 tests, refactor only)
- T3: Server-side pre+post review in `api_optimize_chapter` (5 tests, two-row persistence)
- T4: New response shape: `pre_review`, `post_review`, `diff` (3 tests)
- T5: Update client to consume new response (manual smoke test)

---

### Task 1: Add `?preview=true` opt-out to `api_optimize_chapter`

**Files:**
- Modify: `/Users/wgfu/Desktop/novel-agent/portal/app.py` (`api_optimize_chapter`, lines 1883-1940)
- Test: `/Users/wgfu/Desktop/novel-agent/tests/functional/test_writing_api.py` (extend `TestOptimizeChapter`)

- [ ] **Step 1: Failing test — preview mode returns 200, no side effects.** In `TestOptimizeChapter`, add `test_preview_true_does_not_save`. Pre-create `manuscript/vol-01-ch-001.md` with content `"# 第一章\n\n原文。\n"`. `fake_deepseek_chat(monkeypatch, content="优化后章节。")`. POST to `/api/novels/test_novel/optimize-chapter?preview=true` with `{chapter_ref: "vol-01/ch-001", ...}`. Assert: status 200, `success=True`, `preview=True`, `content="优化后章节。"`, and — the on-disk file still equals the original `"原文。"`. Also assert no `.bak` file was created.

- [ ] **Step 2: Failing test — preview=false (or missing) still works as before.** Add `test_preview_false_or_missing_keeps_old_contract`. Default POST (no query param) and explicit `?preview=false` POST should both proceed past the LLM call. Assert `preview` key is absent (or `False`).

- [ ] **Step 3: Failing test — preview with unknown chapter still 404.** Add `test_preview_unknown_chapter_404`. The 404 happens before the preview check, so this should still work. Assert 404 + success=False.

- [ ] **Step 4: Impl.** Edit `api_optimize_chapter` to read `request.args.get("preview", "").lower() in ("1","true","yes","on")` after the chapter read step. If `True`, return the original 4-key response plus `"preview": True`.

- [ ] **Step 5: Run tests.** All four should pass: `pytest tests/functional/test_writing_api.py::TestOptimizeChapter -v`. Existing 4 tests in `TestOptimizeChapter` must still pass unchanged.

- [ ] **Step 6: Manual smoke test.** `curl -X POST 'http://localhost:5000/api/novels/<n>/optimize-chapter?preview=true' -H 'Content-Type: application/json' -d '{"chapter_ref":"vol-01/ch-001"}'` and verify the file is untouched.

- [ ] **Step 7: Commit.** `git commit -m "feat(optimize): add ?preview=true opt-out (T1)"`.

---

### Task 2: Extract `_run_review` helper from `api_review_chapter`

**Files:**
- Modify: `/Users/wgfu/Desktop/novel-agent/portal/app.py` (add helper, refactor `api_review_chapter`)
- Test: `/Users/wgfu/Desktop/novel-agent/tests/functional/test_writing_api.py` (new `TestReviewChapter` happy-path test that exercises the helper; existing chapter-lifecycle tests must still pass)

- [ ] **Step 1: Failing test — explicit `TestReviewChapter` happy path.** The current `tests/functional/test_chapter_lifecycle.py` may not directly test the endpoint. Add a `TestReviewChapter` class to `test_writing_api.py` with one happy-path test: pre-create a chapter file, monkeypatch both `app.deepseek_chat` and (if necessary) the 3 script subprocess calls. POST and assert 200, `success=True`, `wc_ok`, `compliance_ok`, `forbidden_ok`, `bcontrast_count`, `script_results.analyze` all present.

- [ ] **Step 2: Failing test — unknown novel still 404.** Add `test_not_found_unknown_chapter_404`. POST without a chapter file → 404 + success=False.

- [ ] **Step 3: Failing test — wrong method 405.** Add `test_wrong_method_405`. GET → 405.

- [ ] **Step 4: Impl — extract `_run_review` and `_persist_review`.** See code sketch in plan body above. `_run_review` runs scripts + LLM, returns flat dict. `_persist_review` writes the reviews table row and the legacy `.md` file.

- [ ] **Step 5: Refactor `api_review_chapter`** to call `_run_review` then `_persist_review`. Public endpoint behavior is unchanged: same response keys, same status codes, same on-disk file.

- [ ] **Step 6: Run tests.** `pytest tests/functional/test_writing_api.py -v` — the new `TestReviewChapter` tests pass, all `TestOptimizeChapter` tests still pass, and `pytest tests/functional/test_chapter_lifecycle.py` still passes.

- [ ] **Step 7: Commit.** `git commit -m "refactor(review): extract _run_review + _persist_review helpers (T2)"`.

---

### Task 3: Server-side pre-review + post-review in `api_optimize_chapter`

**Files:**
- Modify: `/Users/wgfu/Desktop/novel-agent/portal/app.py` (`api_optimize_chapter`)
- Test: `/Users/wgfu/Desktop/novel-agent/tests/functional/test_writing_api.py` (new `TestOptimizeReReview` class)

- [ ] **Step 1: Failing test — optimize without preview writes a pre-review row and a post-review row.** Add `TestOptimizeReReview::test_default_writes_pre_and_post_review_rows`. Pre-create `manuscript/vol-01-ch-001.md` with content `# 原文\n\n` (under 2500 chars, so `wc_ok=False` in the pre-review; LLM stub returns a YAML review). `fake_deepseek_chat(monkeypatch, content="优化后。")`. Use `point_content_db_at_tmp` from `_helpers` so the `reviews` table write goes to a tmp DB. POST without `?preview`. Assert: status 200, `success=True`, `pre_review.wc_ok` is present, `post_review.wc_ok` is present, and that the tmp DB has TWO rows in `reviews` for chapter_ref LIKE `vol-01/ch-001%`. The pre row is `vol-01/ch-001`; the post row is `vol-01/ch-001-post-rev1`.

- [ ] **Step 2: Failing test — backup file matches the post-rev number.** Add `test_bak_filename_matches_post_rev`. After optimize, assert that `manuscript/.bak/vol-01-ch-001.rev1.md` exists and contains the original pre-optimization text. Assert `diff.post_review_ref == "vol-01/ch-001-post-rev1"`.

- [ ] **Step 3: Failing test — second optimize increments rev to 2.** Add `test_second_optimize_increments_rev`. Run the optimize twice. Assert the first post-ref is `vol-01/ch-001-post-rev1` and the second is `vol-01/ch-001-post-rev2`. Assert `manuscript/.bak/vol-01-ch-001.rev1.md` and `manuscript/.bak/vol-01-ch-001.rev2.md` both exist.

- [ ] **Step 4: Failing test — full-state rollback if save fails.** Add `test_save_failure_restores_from_bak`. Monkeypatch `app.write_novel_file` to raise `OSError("disk full")` on the save call (not on the .bak copy). Assert: status 500, `success=False`, the on-disk file still contains the original content, and no new row was added to the `reviews` table.

- [ ] **Step 5: Impl.** Replace the backup block in `api_optimize_chapter` with the full server-side re-review flow (see plan body above for code sketch). Pre-review uses `ch_content` (the original). Post-review runs against `result["content"]` (the new optimized content). Both persisted via `_persist_review`.

- [ ] **Step 6: Run tests.** `pytest tests/functional/test_writing_api.py::TestOptimizeReReview -v`. The 4 tests pass; the T1 tests in `TestOptimizeChapter` still pass (preview mode is a short-circuit and never reaches the new code).

- [ ] **Step 7: Commit.** `git commit -m "feat(optimize): server-side pre+post review with two rows (T3)"`.

---

### Task 4: New response shape: `pre_review`, `post_review`, `diff`

**Files:**
- Modify: `/Users/wgfu/Desktop/novel-agent/portal/app.py` (response builder in `api_optimize_chapter`)
- Test: `/Users/wgfu/Desktop/novel-agent/tests/functional/test_writing_api.py` (extend `TestOptimizeReReview` with response-shape assertions)

- [ ] **Step 1: Failing test — response includes `pre_review`, `post_review`, `diff`.** Add `TestOptimizeReReview::test_response_shape_includes_pre_post_and_diff`. Run the default optimize. Assert the JSON body has keys: `success`, `content`, `chapter_ref`, `post_review_ref`, `backup`, `word_count`, `usage`, `pre_review`, `post_review`, `diff`. Assert `pre_review` and `post_review` are dicts with `wc_ok`, `compliance_ok`, `forbidden_ok`, `bcontrast_count`, `tell_count`, `script_results`. Assert `diff` has `wc_ok: [bool, bool]`, `compliance_ok: [bool, bool]`, `forbidden_ok: [bool, bool]`, `bcontrast_count: [int, int]`, `tell_count: [int, int]`, `all_pass: bool`.

- [ ] **Step 2: Failing test — preview response does NOT include `pre_review`/`post_review`/`diff`.** Add `test_preview_response_omits_review_blocks`. POST with `?preview=true`. Assert: `preview is True`, `pre_review` and `post_review` keys are absent (or null), `diff` is absent.

- [ ] **Step 3: Failing test — `diff.all_pass` is True iff all three checks flipped from false to true OR stayed true.** Add `test_diff_all_pass_logic`. Use a stubbed `deepseek_chat` that returns a YAML review with `conclusion: 通过`. Force the pre-review's `wc_ok` to be False (under-2500 char content) and the post-review's `wc_ok` to be True. Assert `diff.wc_ok == [False, True]` and `diff.all_pass is False`. Then with all three True, `diff.all_pass is True`.

- [ ] **Step 4: Impl — build the response and the diff.** Add `_diff_reviews(pre, post)` helper. Build the response dict with the keys defined in the response shape spec.

- [ ] **Step 5: Run tests.** `pytest tests/functional/test_writing_api.py -v`. All T1, T2, T3, T4 tests pass. Coverage stays ≥96%.

- [ ] **Step 6: Commit.** `git commit -m "feat(optimize): return pre_review/post_review/diff in response (T4)"`.

---

### Task 5: Update client to consume new response

**Files:**
- Modify: `/Users/wgfu/Desktop/novel-agent/portal/static/js/app.js` (`_optimizeFromReview` at line 1212, `_autoReviewOptimize` at line 1254)
- Test: manual smoke test (no JS test framework in this repo)

- [ ] **Step 1: Impl — refactor `_optimizeFromReview` (line 1212-1252).** Replace the `API.editChapter` call and the inner `API.reviewChapter` call with direct consumption of `optResp.pre_review` and `optResp.post_review`. See plan body for the diff sketch.

- [ ] **Step 2: Impl — refactor `_autoReviewOptimize` (line 1254-1288).** Same change: remove the `API.editChapter` call and the inner `API.reviewChapter` call. Use `optResp.post_review` and `optResp.diff` to render the verdict. Render the `diff.all_pass` line directly.

- [ ] **Step 3: Manual smoke test.** Open the UI, click 审稿+优化, verify: the chapter file on disk contains the new content; the .bak file in `manuscript/.bak/` exists with the original content; the "✅ 复审全部通过" or "⚠️ 复审仍有问题" message renders from the response; the reviews table has two rows: `vol-01/ch-001` and `vol-01/ch-001-post-rev1`.

- [ ] **Step 4: Manual smoke test — preview.** Force `?preview=true` in the URL. Verify the chapter file is unchanged, the toast says "预览模式", and the post-review block is absent.

- [ ] **Step 5: Commit.** `git commit -m "feat(client): consume pre_review/post_review from optimize response (T5)"`.

---

## Self-Review Checklist

- [ ] All 1015 existing tests still pass (pytest -q shows 1015 passed, 0 failed). No regression in chapter lifecycle, content, or workflow tests.
- [ ] Coverage stays ≥96%. `pytest --cov=portal --cov-report=term-missing` shows ≥96% line coverage.
- [ ] Default optimize is fully server-side. Manual test: click 审稿+优化, then check Flask logs. There should be exactly **one** POST to `/optimize-chapter` and **zero** subsequent POSTs to `/chapters/.../edit` or `/review-chapter` (the server returned the post-review inline).
- [ ] Two `reviews` rows per default optimize. `sqlite3 portal/content.db "SELECT chapter_ref FROM reviews WHERE novel_id=(SELECT id FROM novels WHERE name='<name>') ORDER BY created_at DESC LIMIT 5;"` shows both `vol-01/ch-001` and `vol-01/ch-001-post-rev1` after one optimize.
- [ ] `?preview=true` is a no-op on disk. `sha256sum novels/<name>/manuscript/vol-01/ch-001.md` before and after a `?preview=true` POST returns the same hash. `ls novels/<name>/manuscript/.bak/` shows no new file.
- [ ] Second optimize increments rev. After two default optimizes, `ls novels/<name>/manuscript/.bak/` shows `vol-01-ch-001.rev1.md` AND `vol-01-ch-001.rev2.md`. The reviews table has `vol-01/ch-001-post-rev1` and `vol-01/ch-001-post-rev2`.
- [ ] Rollback works on save failure. Monkeypatch the disk full, run optimize, assert the chapter file is restored from .bak and no review row was written. (The T3 `test_save_failure_restores_from_bak` covers this.)
- [ ] Backward compat for old clients. An older client that still calls `optimize-chapter` + `editChapter` + `review-chapter` still works: the server-side optimize now saves the file (so `editChapter` becomes a no-op overwrite of identical content), and the server-side post-review row means the client's subsequent `reviewChapter` returns the post-review state (good UX, not broken).
- [ ] Response shape is consistent. `optResp.pre_review` and `optResp.post_review` are always the same shape (same keys), whether they came from a stub or a real LLM call. The `_run_review` helper enforces this by returning a fixed dict structure.
- [ ] No N+1 in `_run_review`. Each helper call runs 3 scripts + 1 LLM call. The optimize path runs the helper twice = 6 scripts + 2 LLM calls. This is the same cost as the old client-driven flow (which ran review-chapter twice) but is now a single round-trip. No hidden additional calls.
