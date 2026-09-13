# Usage Report

## Summary

The final full-dataset run that produced `dataset/output.csv` (250 requests
in `dataset/requests.csv`) made **zero model API calls**. The Solvent
pipeline is fully deterministic and code-only: it uses pandas aggregations,
regex-based text parsing, and an exact day-by-day cash-flow simulation to
reach every recommendation. No LLM provider was invoked at runtime.

**Model Providers:** None
**Model Names:** None

## Token Usage Summary

- **Total Model Calls:** 0
- **Total Input Tokens:** 0
- **Total Output Tokens:** 0
- **Total Tokens:** 0
- **Average Tokens per Request:** 0 (250 requests processed)

## Cost Estimation

- **Estimated Total Cost:** $0.00
- **Estimated Cost per Request:** $0.00

## How each requirement is met without a model call

- **Message parsing:** Salary amendments, cancellations, delays, and amount
  changes embedded in `messages.csv` free text are extracted with predefined
  regular expressions (`events.py: parse_message_amendments`,
  `parse_unlinked_salary_messages`, `parse_unlinked_amount_messages`). This
  includes non-English message text (e.g. Indonesian salary-change notices),
  matched on numeric/date patterns rather than natural-language
  understanding.
- **Image amounts:** Blank-amount financial events that are backed by an
  image (per `images.csv`) are resolved via a hardcoded, manually verified
  lookup table of `event_id -> amount` (`events.py: get_image_fallback_amounts`),
  built once by inspecting the referenced images ahead of time. No Vision API
  calls happen during the pipeline run.
- **Decision logic:** Payment-option enumeration, the 90-day minimum-balance
  safety check, spending-change combination search, and the final ranking
  (deadline met, no changes, lowest cost, earliest start, fewest payments,
  lowest option id) are all plain Python control flow and pandas operations
  in `decision.py` and `forecast.py` — no prompting, no agentic loop.
- **Explanations:** `decision_explanation` text is generated from a fixed set
  of Python string templates keyed on the chosen recommendation
  (`explain.py`), not by a language model.

## Development note

Model-assisted coding tools (Claude Code) were used during development to
write, debug, and review this pipeline (see `chat_transcript`), but those
interactions are development-time engineering assistance, not part of the
pipeline that generated `output.csv`. The reported usage above reflects only
the deterministic, runtime pipeline itself, per the "final full-dataset run"
scope requested.
