# Solvent: Affordability Engine

A submission for the HackerRank Orchestrate "Buy or Wait?" challenge: an
AI-style financial agent that decides, for each user request, whether to pay
in full, pay partially, use installments, wait, or not proceed — based on a
90-day forward simulation of the user's cash flow.

The submittable solution lives in [code/](code/) (see [code/README.md](code/README.md)
for full documentation of how it works). This repository root also includes
a demo frontend and the raw dataset used to produce `dataset/output.csv`.

## Repository layout

- [code/](code/) — the runnable pipeline (this is what `code.zip` is built
  from): `main.py`, the decision/forecast/events modules, `tests/`, and the
  required `evaluation/usage_report.md`.
- [dataset/](dataset/) — challenge input files plus the generated
  `output.csv`.
- [frontend/](frontend/) — a React/Vite demo UI that visualizes the sample
  requests and their recommendations (uses mock data, not a live backend).
- `problem_statement.md` — the original challenge brief.
- `chat_transcript.jsonl` — development conversation transcript.

## Running the engine

```bash
cd code
pip install -r requirements.txt
python main.py
```

This reads `dataset/requests.csv` and (re)generates `dataset/output.csv`.

To validate against the 25 known-correct sample requests:

```bash
cd code/tests
python test_sample_requests.py
```

## Running the frontend

The frontend uses mock data corresponding to the sample requests for
demonstration purposes; it does not call the Python pipeline.

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173/` in your browser.

## Submission details

- **Challenge**: HackerRank Orchestrate (September 2025) — Buy or Wait?
- **Goal**: Reconstruct user financial profiles to produce deterministic
  payment recommendations.
- **Rules obeyed**: no non-cash events treated as available balance, no
  pending credits counted as income, minimum balance strictly protected
  throughout the 90-day forecast.
- **Approach**: fully deterministic, code-only (no LLM calls at runtime) —
  see [code/evaluation/usage_report.md](code/evaluation/usage_report.md).
