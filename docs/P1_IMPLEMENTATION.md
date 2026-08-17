# P1 Implementation

Phase: Threat Library + Red Team Controller.  
Does not implement P2 (graph/geo), agents, or closed-loop retrain.

## Inspected P0 (reuse)

| Component | Path | P1 use |
|---|---|---|
| IEEE ingest + schema | `backend/app/data/` | Source population |
| Legit generator | `backend/app/simulation/legit.py` | Base rows for every attack |
| Five P0 overlays | `backend/app/simulation/attacks.py` | Kept for P0 tests; adapter calls mutation engine for P1 IDs |
| Blue Team | `backend/app/fraud/pipeline.py` | Score only; `FEATURE_COLUMNS` unchanged (no leakage) |
| Policy + SHAP | `backend/app/risk/` | Decisions + missed-row explanations |
| Fidelity | `backend/app/evaluation/fidelity.py` | Attack fidelity vs IEEE/legit |
| P0 report + FastAPI | `backend/app/evaluation/report.py`, `main.py` | Kept; P1 adds Red Team routes |
| Next.js shell | `frontend/` | Red Team Lab replaces the thin P0 form |

Do not rewrite working P0 apply_* functions. P0 `generate_attacks(family, intensity)` stays.

## Architecture

```
Threat YAML (threats/)
  → schema validate
  → registry
  → AttackContract (id, variant, difficulty, seed, mutation)
  → MutationEngine on legit rows
  → Blue Team score
  → fidelity + metrics
  → Red Team report + leaderboard
```

## New modules

```
threats/*.yaml                         14 executable definitions
backend/app/threats/schema.py         Pydantic threat + mutation + variant
backend/app/threats/loader.py         YAML load + validate
backend/app/threats/registry.py       lookup, coverage, variants
backend/app/redteam/mutations.py      parameterized overlays
backend/app/redteam/difficulty.py     LOW / MEDIUM / HIGH → mutation
backend/app/redteam/contract.py       AttackContract
backend/app/redteam/controller.py     run + replay
backend/app/redteam/report.py         RED TEAM ATTACK REPORT
backend/app/evaluation/leakage.py     feature-column audit
evaluation/run_phase_benchmark.py     `python -m evaluation.run_phase_benchmark p1`
evaluation/benchmarks/p1/test_*.py
```

## Threat set (14)

P0: ATO-001, VEL-001, AMT-001, BEN-001, SLOW-001.  
P1 surfaces (transaction overlays only, no GNN): DEV-001, IP-001, MUL-001, MER-001, FRAG-001, GEO-001, SEQ-001, AGT-001, INT-001.

Each family ships ≥5 variants (70 total). Network-ish families share identifiers (device/IP/merchant/beneficiary) and record entity counts; they do not add a graph product.

## Difficulty

LOW = loud (easy). HIGH = subtle (hard). Opposite of P0’s old intensity scale, which only amplified magnitude. P0 intensity strings still map to the old APPLY path.

## Constraints

Deterministic seeds. No LLM transaction generation. No label columns in `FEATURE_COLUMNS`. Metrics always computed. Synthetic data only.

## Benchmark (computed)

```
python -m evaluation.run_phase_benchmark p1
```

P1 STATUS: PASS (14 threats, 70 variants, 1k/10k/100k generation, no leakage).

