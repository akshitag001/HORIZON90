# Solvent: Affordability Engine

A deterministic, code-only pipeline for the HackerRank Orchestrate "Buy or Wait?" challenge. For each request in `dataset/requests.csv`, it reconstructs the user's financial state, simulates their balance forward 90+ days, and produces a personalized affordability recommendation.

## Requirements

- Python 3.10+
- `pip install -r requirements.txt` (pandas, python-dateutil, tabulate)

## Layout

```
code/
  main.py          Entry point: runs the full pipeline over dataset/requests.csv
  data_loader.py   CSV loading and type coercion
  events.py        Builds each user's cash-flow timeline: image/message
                    amendments, cancellations, lifecycle collapsing, recurring-
                    expense detection
  forecast.py       90+ day balance simulation, recurring-event projection,
                    earliest-safe-date search
  currency.py       Fixed-date exchange-rate conversion
  decision.py       Enumerates payment options (full/partial/installments/
                    wait), applies the safety and ranking rules, picks the best
  explain.py        Generates decision_explanation text
  tests/
    test_sample_requests.py   Compares pipeline output against the known-
                               correct dataset/sample_requests.csv
  evaluation/
    usage_report.md           Token/cost accounting for the run that produced
                               output.csv
```

## Running the pipeline

The dataset is not bundled in this archive. Place this `code/` folder next to
a `dataset/` folder (the same layout as the original project:
`<project>/code/` and `<project>/dataset/`), or pass `--dataset` explicitly:

```bash
cd code
python main.py
# or
python main.py --dataset /path/to/dataset
```

This reads `dataset/requests.csv` and overwrites `dataset/output.csv` with one
row per request.

## Running the validation test

`sample_requests.csv` ships with known-correct outputs. To check the pipeline
against it:

```bash
cd code/tests
python test_sample_requests.py
```

This prints a per-field diff table. Note that `decision_explanation` is
freeform generated text and will not byte-match the hand-written reference
explanations — treat mismatches there as expected. As of this submission,
field-level agreement against the 25 sample requests (excluding
`decision_explanation`) is:

| Field | Match rate |
| --- | --- |
| `affordability_status` | 19/25 (76%) |
| `recommended_payment_method` | 19/25 (76%) |
| `spending_changes_needed` | 21/25 (84%) |
| `payment_plan` | 16/25 (64%) |
| `earliest_date_for_full_payment` | 16/25 (64%) |
| `amount_safe_to_pay` | 3/25 exact, but only 2/25 are still off by 100% (down from 9/25 before the fixes described below); most others are within ~15% of the reference value |

## How it works

1. **`data_loader`** reads all CSVs and coerces date/amount columns.
2. **`events.get_cash_flow_timeline`** builds a per-user list of cash-flow
   events: applies image-derived amounts for blank-amount events, parses
   message-based amendments (cancellations, delays, amount changes, salary
   raises) via regex, collapses linked event lifecycles (keeping the
   settled/cancelled/newest version), drops non-cash/pending-credit/variable-
   income rows per the spec, converts every amount to the user's home
   currency, and tags recurring events with an inferred cadence.
3. **`forecast.precompute_events`** projects each recurring category forward.
   It separates two concerns that are easy to conflate: *is this category
   still active* (judged from the true most-recent occurrence, so a category
   isn't wrongly treated as discontinued just because its latest instance had
   an unusual amount — a pay cut, a one-off discount) versus *what amount to
   project* (picked from the most recent *typical-amount* occurrence, so a
   one-off bonus or arrears payment landing near a regular payday isn't
   mistaken for the recurring amount). `simulate_balance` walks the calendar
   day by day, applying settled history, projected recurring events, and any
   hypothetical payments or spending changes.
4. **`decision.evaluate_request`** enumerates every payment option the user's
   preferences allow (full payment, partial payment, installments, wait),
   checks each against the 90-day minimum-balance safety rule, and — only
   when no option is safe without changes — searches combinations of
   stoppable/reducible flexible expenses. Valid options are ranked by the
   spec's tie-break order (meets deadline, no changes, lowest cost, earliest
   start, fewest payments, lowest option id) and the best is returned.
   `amount_safe_to_pay` and `earliest_date_for_full_payment` are computed
   independently of which payment method is chosen (or whether any is safe)
   — this is deliberate: a request can be `not_affordable` overall while
   still having a nonzero amount safe to pay today, since those two numbers
   answer different questions per the spec.
5. **`explain.generate_explanation`** turns the chosen option into a short,
   templated sentence.

## Known limitations

- `amount_safe_to_pay` can drift from the reference value by roughly 5-25% in
  cases where the 90-day forecast window interacts with month-length-
  dependent recurring projections. The direction and status of the
  recommendation are usually still correct even when the exact amount is
  off.
- When a category (e.g. `salary`) contains two genuinely concurrent recurring
  income streams (e.g. two household earners) as well as one-off payments in
  the same category, the anchor-selection heuristic picks one representative
  amount per category rather than tracking every concurrent sub-stream
  separately. A day-of-month clustering approach was prototyped to split
  these into separate series but measured net-negative on the sample set (it
  fixed the targeted case but regressed others) and was reverted rather than
  shipped.
- A small number of requests where the user's income has stopped entirely
  (e.g. a "final employer payroll") and the 90-day balance decline is driven
  by several overlapping recurring expenses can still show a larger gap in
  `amount_safe_to_pay` than the general case above.
