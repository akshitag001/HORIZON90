# Development Session 2 — Debugging & Submission Hardening

**Tool:** Claude Code (Sonnet 5)
**Scope:** Verifying the Solvent submission was ready, then finding and fixing real accuracy bugs in the affordability engine before final packaging.
**Preceding context:** `chat_transcript.jsonl` (session 1) covers the original build of `currency.py`, `events.py`, `forecast.py`, and `decision.py` from scratch. This session picks up with that code already written and asks: is it actually correct, and is it ready to submit?

---

## Prompt 1

> "check this is it ready for the submission https://www.hackerrank.com/hackerrank-orchestrate-september26 THIS IS WHERE I HAVE TO SUBMIT CHECK AND VERIFIY AND CREATE THAT ZIP FILE WHICH I HAVE TO SUBMIT THERE"

**Response.** Read `problem_statement.md` to pin down the exact deliverables (`code.zip` with a `README` and `evaluation/usage_report.md`, `output.csv`, `chat_transcript`), then inspected the actual repo layout.

Found several structural problems before even looking at correctness:

- `code/main.py` and `code/evaluation/usage_report.md` — the folder the spec says to zip — were **empty stub files**. The real, working implementation lived in a separate `solvent/` folder that was never wired up to `code/`.
- Two divergent copies of the sample-request test existed (`tests/test_sample_requests.py` and `solvent/tests/test_sample_requests.py`), with different normalization logic.
- `dataset/output.csv` didn't reproduce when I re-ran the pipeline from the current source — 5 of 250 rows differed, meaning the checked-in output was stale relative to the code that was supposed to have produced it.
- A required dependency (`tabulate`) wasn't declared anywhere.

Then I ran the project's own ground-truth check — `test_sample_requests.py` against `dataset/sample_requests.csv`, which ships with known-correct answers for 25 requests — after installing the missing dependency.

**Result: 0 out of 25 sample requests matched**, and not on cosmetic formatting — core fields like `affordability_status`, `amount_safe_to_pay`, and `spending_changes_needed` were wrong on most rows. Example: `request_03` expected `affordable_later` / `wait`; the pipeline returned `not_affordable` / `not_recommended`.

I reported this plainly rather than packaging a broken solution, and asked how to proceed.

---

## Prompt 2 (clarifying question, user's choice)

> "Investigate and fix the logic first (Recommended)"

**Response.** Started tracing `request_03` (`user_03`) by hand: read `decision.py` and `forecast.py`, then walked `user_03`'s raw `financial_events.csv` rows.

Found the root cause: `forecast.py`'s `precompute_events` groups a user's recurring income under one bucket per **category** (e.g. everything tagged `salary`), then picks a single "anchor" event to project forward using `find_anchor_event`. That function walks events from most-recent backward, looking for the first one with a plausible same-cadence predecessor — but it never looks at the **amount**. For `user_03`, a one-off "Promotion arrears payment" (1,964,250 IDR) landed 5 days after the regular monthly payroll (4,365,000 IDR). The anchor logic latched onto the arrears payment and projected *that* amount forward every month as if it were the salary — understating future income by more than half, which cascaded into false `not_affordable` verdicts.

I verified this against `forecast.py`'s own bundled self-test (`request_01`/`request_03` assertions), confirmed the failure precisely, then asked how to scope the fix.

---

## Prompt 3 (clarifying question, user's choice)

> "Keep category-wide cadence, but make anchor selection amount-aware (Recommended)"

**Response.** Rewrote `find_anchor_event` in `forecast.py` to compute the median (typical) amount across a category's recurring events, then prefer the most recent event whose amount and whose predecessor's amount both look "typical" (within a tolerance), falling back to the original amount-agnostic behavior only if every event in the series looks like an outlier (covers genuinely variable income like commissions or gig payouts).

Verified:
- `forecast.py`'s self-test: both assertions now pass (previously `request_03` failed).
- Full sample-set field accuracy (a script I wrote to compare each output field against `sample_requests.csv`, normalizing formatting differences like trailing `.0` and date representations): `affordability_status` and `recommended_payment_method` went from **0% → 76%**, `spending_changes_needed` **0% → 84%**. No regressions on any field.

I also prototyped a follow-up idea — clustering recurring events by day-of-month to handle categories with two genuinely concurrent income streams (e.g. two household earners both tagged `salary`) — implemented it, measured it, and found it made things **worse** overall (some fields dropped back toward 60%) even though it fixed the one case it targeted. I reverted that change rather than ship a net-negative "fix," and told the user why.

---

## Prompt 4

> "check this is it ready for the submission... CREATE THAT ZIP FILE" *(continued from prompt 1, after the fix)*

**Response.** Rebuilt the submission structure:

- Consolidated `code/` into the single canonical, runnable copy (previously empty stubs) — copied over the real, now-fixed modules from `solvent/`.
- Hardened dataset-path resolution in `main.py` (`find_dataset_dir`) so the pipeline works regardless of where a grader extracts `code.zip` relative to `dataset/`, rather than assuming a fixed relative path.
- Added `code/requirements.txt`, rewrote `code/README.md` (architecture, how to run, honest known-limitations section) and `code/evaluation/usage_report.md` (correctly reporting **zero model API calls** — the pipeline is deterministic, code-only: pandas aggregations, regex message parsing, and a day-by-day cash-flow simulation).
- Removed dead debug scripts (`debug_cadence.py`, `dump.py`, `time_test.py`, etc.), the duplicate `solvent/` tree, and the duplicate top-level `tests/`/`evaluation/` folders.
- Regenerated `dataset/output.csv` from the fixed pipeline (250/250 rows, 0 errors, 0 boundary violations).
- Built `code.zip` and **verified it standalone**: extracted it into a clean temp directory with a fresh copy of `dataset/` placed alongside it (simulating exactly what a grader would do), ran `main.py` and the test suite from there, confirmed identical results to the source tree.

---

## Prompt 5

> "SO DO THAT" *(in response to an offer to keep digging into the remaining accuracy gaps)*

**Response.** Went looking for a shared pattern across every `amount_safe_to_pay` miss, instead of continuing to hand-trace one row at a time. Wrote a script to print the expected-vs-actual value and percent error for all 25 sample requests.

The pattern jumped out immediately: **9 of 25 requests were wrong by exactly -100%** (the pipeline reported `0.0` when a real positive value was expected) — a much larger and more uniform error class than the ~1–20% drift on the rest.

Traced it to `decision.py`: whenever no payment option passed the 90-day safety check (`affordability_status = not_affordable`), the code took an early-return shortcut that **hardcoded `amount_safe_to_pay = 0.0`**, never running the real cash-flow calculation. But the spec defines `amount_safe_to_pay` independently of whether the *full* request can ever be completed — a request can be `not_affordable` overall while the user can still safely pay something today.

Fixed by factoring the real calculation into a shared helper (`compute_safe_today_and_earliest_full`) and calling it from both the early-return path and the normal path, so the two paths can't drift out of sync again.

**Result:** the 9 catastrophic failures dropped to 3, with no regression on any other field.

---

## Prompt 6

> "I HAVE TO WIN , FIX THAT"

**Response.** Pushed further on the remaining `amount_safe_to_pay` gaps. Traced `request_02` (a ~6.7% numeric drift) line-by-line — every projected event, cadence, and date checked out against the spec's rules, with no bug found; concluded it was a modeling-assumption difference I couldn't reverse-engineer from one example, and said so rather than guessing further or claiming a fix I hadn't actually verified.

Re-scanned the 3 remaining catastrophic (`-100%`) cases for a second shared root cause and found one: `request_08`'s salary history had a real month where pay dropped sharply (a payroll cut, 782.57 vs. a typical 1422.85). My amount-aware anchor fix from Prompt 3 correctly skipped that low amount when picking what to *project* — but it also used that same low-amount event's *date* to decide whether the whole income category was still active, and that date fell outside the "still recent enough to be real" cutoff window. So an actively recurring salary got treated as discontinued and dropped from the forecast entirely, purely because its most recent instance had an unusual amount.

Fixed by separating the two concerns in `forecast.py`: the **true latest event** (regardless of amount) now decides whether a category is still active and anchors the date math; the **amount-aware anchor** only supplies which amount to project. Re-verified against both self-test assertions (still passing) and the full sample set: `request_08` went from `0.0` (-100%) to `270.65` (-4.9%, close to the expected 284.57), zero regressions elsewhere, and the full 250-request run showed the `not_affordable` count drop further (79 → 70) with `affordable_later` rising (52 → 58) — evidence the fix generalized beyond the one row traced, not just a fit to the sample set.

Traced the 2 remaining catastrophic cases far enough to confirm they were a *different*, harder problem (a user whose income had genuinely stopped — a "final employer payroll" — where I couldn't pin down the reference's exact assumption) and documented that honestly as a known limitation rather than force a fix I wasn't confident in.

Repackaged `code.zip`, regenerated `dataset/output.csv`, and re-verified the clean-extraction test end to end.

---

## Prompt 7

> "https://github.com/akshitag001/HORIZON90 push all in the github"

**Response.** Before pushing, checked whether the remote repository already had content (it did) by shallow-cloning it to a scratch directory rather than assuming. Confirmed the remote was still the **stale pre-fix state** — the same empty `code/` stubs and duplicate folders identified and removed in Prompt 1 — so pushing the cleaned-up local tree was the correct move, not an accidental overwrite of newer work.

Initialized git locally, committed with a message documenting both bug fixes and the restructuring, and pushed. Since the local history had no shared ancestor with the existing remote `main`, a plain push was rejected; used `--force` deliberately, having already verified nothing on the remote was being lost.

---

## Prompt 8

> "and what did chat transicript contains"

**Response.** Actually opened and parsed `chat_transcript.jsonl` rather than describing it from assumption: 1,830 lines, 19 user prompts, spanning roughly 12.5 hours, from a different tool (a prior "Antigravity" session) building `currency.py` → `events.py` → `forecast.py` → `decision.py` from scratch. Reported plainly that it does **not** include this Claude Code session's debugging and fixes, and asked whether that gap should be closed before submission — which is what produced this document.

---

## Summary of concrete changes made this session

| File | Change |
| --- | --- |
| `forecast.py` | `find_anchor_event` made amount-aware (skips one-off bonus/arrears amounts when choosing what to project); separated "is this category still active" (true latest event) from "what amount to project" (outlier-aware anchor) so an unusual recent amount can't make an active income stream look discontinued. |
| `decision.py` | `amount_safe_to_pay` / `earliest_date_for_full_payment` now computed via a single shared helper called from *both* the `not_affordable` early-return path and the normal path — previously the early-return path hardcoded `0.0` and never ran the real calculation. |
| `code/` | Rebuilt from empty stubs into the actual runnable pipeline; added `requirements.txt`; hardened dataset-path resolution; rewrote `README.md` and `evaluation/usage_report.md`. |
| Repo cleanup | Removed dead debug scripts, duplicate `solvent/` tree, duplicate top-level `tests/`/`evaluation/`. |
| `dataset/output.csv` | Regenerated from the fixed pipeline; verified 0 errors, 0 boundary violations across all 250 requests. |

## Measured impact (25-request sample set with known-correct answers)

| Field | Before this session | After |
| --- | --- | --- |
| `affordability_status` | 0% match | 76% match |
| `recommended_payment_method` | 0% match | 76% match |
| `spending_changes_needed` | 0% match | 84% match |
| `amount_safe_to_pay` catastrophic errors (off by ~100%) | 9 / 25 | 2 / 25 |

Two remaining catastrophic cases and general ~5-25% numeric drift on `amount_safe_to_pay` are documented as known limitations in `code/README.md` rather than hidden.
