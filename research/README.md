# Research materials

Materials of the paper *Explainable Detection of Anomalous Unit Prices in Public Procurement: Unsupervised
Screening Calibrated on Review Verdicts*.

```
paper/         LaTeX source (main.tex, refs.bib)
annotation/    annotation protocol, cards and labels of 400 CPV 15 items
experiments/   experiment code and result tables
```

## Annotation

The reference selection is CPV division 15 (food products), items published 1 August – 30 September 2026
(16,103 items with price and quantity). The sample of 400 items is stratified by the decision of the first
system version (`strata.json`: 50 highest-risk flagged, 100 other flagged, 250 unflagged; population sizes
for Horvitz–Thompson weights are included).

| Files | Round | What the annotator saw |
|---|---|---|
| `review_cards*.json`, `decisions*.json` | sighted | item record and the v1 decision and risk score |
| `blind_cards.json`, `blind_decisions_*.json` | blind | item record and neutral reference prices only (`blind_protocol.md`) |
| `human_sample.json`, `human_labels.json` | human check | 80 blind cards, annotation hidden |

The sighted and blind rounds were annotated by a large language model (Claude, Anthropic) under the written
protocol; the human check was performed by a non-expert annotator. Labels: `confirmed`, `not_anomaly`
(`false_positive` in the sighted round), `needs_review` (cannot judge, excluded from evaluation). Each label
carries a reason code and a short comment in Ukrainian.

Scripts: `blind_cards.py` builds blind cards from the database, `blind_compare.py` compares the sighted and
blind rounds, `human_check.py` builds the offline page for the human check, `human_agreement.py` computes
agreement.

Item records are taken from the public Prozorro API; they contain names of procuring entities (public
organisations) and no personal data. Annotation data are licensed under CC BY 4.0.

## Experiments

Run from `backend/` with the application environment and the databases populated by the synchronisation
job (`docker compose up -d postgres mongo`):

```bash
cd backend
uv run python ../research/experiments/train_blind.py blind      # calibrator on blind labels
uv run python ../research/experiments/exp_labels.py blind       # Table: annotated quality (also: sighted, adjusted)
uv run python ../research/experiments/exp_synthetic.py          # Table: injected errors, CPV 15 and 03
uv run python ../research/experiments/exp_explain.py            # Table: Shapley explanation quality
```

`adjusted` denotes the blind labels with the 80 human labels substituted. Results are written to
`experiments/results/`. `calibrator_deployed_old.joblib` is the calibrator trained on the sighted round
(the system's earlier default); `calibrator_blind.joblib` is the monotone calibrator trained on the blind
round and is identical to `backend/src/tendoor/ml/models/calibrator_v2.joblib`.
