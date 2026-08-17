"""P1 baseline diagnostic. Read-only on the frozen BLUE-0.1.0 detector.

python -m evaluation.diagnostics.p1_baseline
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_recall_curve

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import (  # noqa: E402
    FEATURE_COLUMNS,
    LEAKAGE_FORBIDDEN,
    MODELS_DIR,
    PAYMENTS_PATH,
    RANDOM_STATE,
)
from app.data.ingest import add_behavior_features, load_payments  # noqa: E402
from app.evaluation.leakage import leakage_paths  # noqa: E402
from app.fraud.pipeline import BlueTeam, compute_metrics, feature_matrix, prepare_split  # noqa: E402
from app.redteam.controller import RedTeamController  # noqa: E402
from app.simulation.attacks import generate_mixed_attacks  # noqa: E402
from app.threats.registry import get_registry  # noqa: E402

OUT = ROOT / "docs" / "evaluation"
FIG = OUT / "figures"
SNAP = MODELS_DIR / "BLUE-0.1.0"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def freeze_model() -> dict:
    src = MODELS_DIR / "blue_team.joblib"
    if not src.exists():
        raise FileNotFoundError(src)
    SNAP.mkdir(parents=True, exist_ok=True)
    dest = SNAP / "blue_team.joblib"
    shutil.copy2(src, dest)
    metrics_src = MODELS_DIR / "metrics.json"
    if metrics_src.exists():
        shutil.copy2(metrics_src, SNAP / "metrics.json")
    digest = _sha256(dest)
    version = {
        "model_version": "BLUE-0.1.0",
        "artifact": str(dest),
        "sha256": digest,
        "source": str(src),
        "bytes": dest.stat().st_size,
        "note": "Frozen snapshot of the current detector. No retrain. Do not overwrite without a new version id.",
    }
    (SNAP / "VERSION.json").write_text(json.dumps(version, indent=2))
    return version


def summarize(s: pd.Series) -> dict:
    arr = pd.to_numeric(s, errors="coerce").dropna().to_numpy(dtype=float)
    if len(arr) == 0:
        return {"n": 0}
    return {
        "n": int(len(arr)),
        "mean": float(arr.mean()),
        "std": float(arr.std()),
        "p10": float(np.quantile(arr, 0.10)),
        "p50": float(np.quantile(arr, 0.50)),
        "p90": float(np.quantile(arr, 0.90)),
        "min": float(arr.min()),
        "max": float(arr.max()),
        "frac_eq_1": float((arr == 1.0).mean()),
        "frac_gt_0_5": float((arr > 0.5).mean()),
    }


def threshold_sweep(y: np.ndarray, proba: np.ndarray) -> list[dict]:
    rows = []
    for t in np.round(np.linspace(0.01, 0.99, 99), 2):
        rows.append(compute_metrics(y, proba, threshold=float(t)))
    return rows


def shap_mean_abs(model, df: pd.DataFrame, n: int = 100) -> list[dict]:
    frame = feature_matrix(df.head(n))
    names = list(FEATURE_COLUMNS)
    try:
        import shap

        explainer = shap.TreeExplainer(model)
        sv = explainer.shap_values(frame)
        if isinstance(sv, list):
            sv = sv[1]
        values = np.abs(np.asarray(sv)).mean(axis=0)
        source = "TreeExplainer"
    except Exception as exc:  # noqa: BLE001
        if hasattr(model, "feature_importances_"):
            values = np.asarray(model.feature_importances_, dtype=float)
            source = f"native_fallback:{type(exc).__name__}"
        else:
            raise
    order = np.argsort(-values)
    return [{"feature": names[i], "mean_abs_shap": float(values[i]), "source": source} for i in order]


def diagnose_family(
    ctrl: RedTeamController,
    blue: BlueTeam,
    payments: pd.DataFrame,
    attack_id: str,
    n: int = 1000,
    seed: int = 424242,
) -> dict:
    result = ctrl.run(
        attack_id, difficulty="MEDIUM", transaction_count=n, seed=seed, persist=False, explain=False
    )
    rows = ctrl.generate(ctrl.build_contract(attack_id, difficulty="MEDIUM", transaction_count=n, seed=seed))
    proba = blue.score(rows)
    y_atk = rows["fraud_label"].to_numpy()
    legit = payments.loc[payments["fraud_label"] == 0]
    hold_n = min(len(legit), max(200, n // 5))
    hold = legit.sample(hold_n, random_state=seed)
    mix = pd.concat([rows.drop(columns=["attack_id", "variant_id"], errors="ignore"), hold], ignore_index=True)
    mix_proba = blue.score(mix)
    y_mix = mix["fraud_label"].to_numpy()
    precision, recall, _thr = precision_recall_curve(y_mix, mix_proba)
    ap = float(average_precision_score(y_mix, mix_proba))
    baseline = float(y_mix.mean())
    sweep = threshold_sweep(y_mix, mix_proba)
    attack_only = threshold_sweep(y_atk, proba)
    best_f1 = max(sweep, key=lambda r: r["f1"])
    at_01 = next(r for r in sweep if abs(r["threshold"] - 0.01) < 1e-9)
    at_50 = next(r for r in sweep if abs(r["threshold"] - 0.50) < 1e-9)

    recomputed = add_behavior_features(rows.copy())
    feat_cols = [
        "beneficiary_is_new",
        "destination_concentration",
        "account_age_days",
        "amount",
        "amount_deviation",
        "merchant_count_24h",
    ]
    feature_compare = {}
    for col in feat_cols:
        if col not in rows.columns:
            continue
        feature_compare[col] = {
            "attack_overlay": summarize(rows[col]),
            "recomputed_from_ids": summarize(recomputed[col]) if col in recomputed.columns else {},
            "legit_holdout": summarize(hold[col]) if col in hold.columns else {},
            "mean_abs_overlay_vs_recomputed": (
                float(np.abs(rows[col].to_numpy() - recomputed[col].to_numpy()).mean())
                if col in recomputed.columns
                else None
            ),
        }

    keep = [
        c
        for c in [
            "transaction_id",
            "customer_id",
            "beneficiary_id",
            "merchant_id",
            "amount",
            "beneficiary_is_new",
            "destination_concentration",
            "account_age_days",
            "fraud_label",
        ]
        if c in rows.columns
    ]
    sample = rows.head(100)[keep].copy()
    sample["fraud_probability"] = proba[: len(sample)]

    hubs = rows.groupby("beneficiary_id")["customer_id"].nunique().sort_values(ascending=False)
    return {
        "attack_id": attack_id,
        "ui_result": {
            "generated": result["generated"],
            "detected": result["detected"],
            "missed": result["missed"],
            "detection_rate": result["detection_rate"],
            "metrics": result["metrics"],
            "model_version": result["model_version"],
            "variant_id": result["variant_id"],
            "difficulty": result["difficulty"],
        },
        "eval_set": {
            "n_attack": int(len(rows)),
            "n_legit_holdout": int(len(hold)),
            "n_mix": int(len(mix)),
            "prevalence_mix": float(y_mix.mean()),
            "prevalence_attack_only": float(y_atk.mean()),
            "note": "Red-team Precision/F1/PR-AUC/FPR are computed on mix (attacks + legit holdout). Detection rate is attack-only recall at 0.5.",
        },
        "pr_auc": {
            "sklearn_average_precision_mix": ap,
            "no_skill_baseline_prevalence": baseline,
            "lift_over_baseline": float(ap - baseline),
            "attack_only_pr_auc": float(compute_metrics(y_atk, proba)["pr_auc"]),
            "attack_only_note": "Attack-only labels are all 1, so PR-AUC is degenerate.",
        },
        "score_distributions": {
            "attack": summarize(pd.Series(proba)),
            "legit_holdout": summarize(pd.Series(blue.score(hold))),
            "frac_attack_ge_0_5": float((proba >= 0.5).mean()),
            "frac_attack_ge_0_3": float((proba >= 0.3).mean()),
            "frac_attack_ge_0_1": float((proba >= 0.1).mean()),
            "frac_legit_ge_0_5": float((blue.score(hold) >= 0.5).mean()),
        },
        "threshold_sweep_mix": sweep,
        "threshold_sweep_attack": attack_only,
        "operating_points": {"policy_0_50": at_50, "near_allow_0_01": at_01, "best_f1_mix": best_f1},
        "pr_curve": {
            "recall": [float(x) for x in recall.tolist()[:: max(1, len(recall) // 80)]],
            "precision": [float(x) for x in precision.tolist()[:: max(1, len(precision) // 80)]],
        },
        "features": feature_compare,
        "shap": shap_mean_abs(blue.lgbm, rows, n=100),
        "graph_proxy": {
            "unique_customers": int(rows["customer_id"].nunique()),
            "unique_beneficiaries": int(rows["beneficiary_id"].nunique()),
            "max_customers_per_beneficiary": int(hubs.iloc[0]) if len(hubs) else 0,
            "beneficiaries_with_ge_2_customers": int((hubs >= 2).sum()),
        },
        "sample100": sample.to_dict(orient="records"),
        "mutation": ctrl.build_contract(attack_id, difficulty="MEDIUM", transaction_count=n, seed=seed).mutation.model_dump(),
    }


def _svg_line(path: Path, title: str, xlabel: str, ylabel: str, series: list[tuple[str, list[float], list[float]]], vline: float | None = None, y0: float = 0, y1: float = 1) -> None:
    w, h, l, r, t, b = 720, 420, 56, 16, 36, 48
    pw, ph = w - l - r, h - t - b

    def xy(x: float, y: float) -> tuple[float, float]:
        return l + x * pw, t + (1 - (y - y0) / (y1 - y0)) * ph

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect width="{w}" height="{h}" fill="#0a0a0a"/>',
        f'<text x="{l}" y="22" fill="#f5f5f5" font-size="14">{title}</text>',
        f'<text x="{w/2}" y="{h-10}" fill="#8a8a8a" font-size="11" text-anchor="middle">{xlabel}</text>',
        f'<text x="14" y="{h/2}" fill="#8a8a8a" font-size="11" transform="rotate(-90 14 {h/2})">{ylabel}</text>',
        f'<line x1="{l}" y1="{t}" x2="{l}" y2="{t+ph}" stroke="#333"/>',
        f'<line x1="{l}" y1="{t+ph}" x2="{l+pw}" y2="{t+ph}" stroke="#333"/>',
    ]
    colors = ["#ff5f00", "#f5f5f5", "#8a8a8a", "#c47a4a"]
    if vline is not None:
        x, _ = xy(vline, 0)
        parts.append(f'<line x1="{x}" y1="{t}" x2="{x}" y2="{t+ph}" stroke="#555" stroke-dasharray="4 3"/>')
    for i, (name, xs, ys) in enumerate(series):
        pts = " ".join(f"{xy(x, y)[0]:.1f},{xy(x, y)[1]:.1f}" for x, y in zip(xs, ys))
        parts.append(f'<polyline fill="none" stroke="{colors[i % len(colors)]}" stroke-width="1.6" points="{pts}"/>')
        parts.append(f'<text x="{l + 8 + i * 120}" y="{t + 14}" fill="{colors[i % len(colors)]}" font-size="11">{name}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts))


def plot(family: str, diag: dict) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    sweep = diag["threshold_sweep_mix"]
    ts = [r["threshold"] for r in sweep]
    _svg_line(
        FIG / f"{family}_threshold_sweep.svg",
        f"{family} mix-set metrics vs threshold (BLUE-0.1.0)",
        "Decision threshold",
        "Metric",
        [
            ("Precision", ts, [r["precision"] for r in sweep]),
            ("Recall", ts, [r["recall"] for r in sweep]),
            ("F1", ts, [r["f1"] for r in sweep]),
            ("FPR", ts, [r["fpr"] for r in sweep]),
        ],
        vline=0.5,
    )
    pr = diag["pr_curve"]
    xs = pr["recall"]
    _svg_line(
        FIG / f"{family}_pr_curve.svg",
        f"{family} PR curve on mix set · AP={diag['pr_auc']['sklearn_average_precision_mix']:.3f}",
        "Recall",
        "Precision",
        [("Precision-recall", xs, pr["precision"])],
    )


def plot_scores(family: str, attack: np.ndarray, legit: np.ndarray) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    bins = np.linspace(0, 1, 41)
    a_hist, _ = np.histogram(attack, bins=bins, density=True)
    l_hist, _ = np.histogram(legit, bins=bins, density=True)
    centers = 0.5 * (bins[:-1] + bins[1:])
    ymax = float(max(a_hist.max(), l_hist.max(), 1e-6)) * 1.1
    _svg_line(
        FIG / f"{family}_score_hist.svg",
        f"{family} score distributions (BLUE-0.1.0)",
        "Fraud probability",
        "Density",
        [("Legitimate holdout", centers.tolist(), l_hist.tolist()), ("Attack", centers.tolist(), a_hist.tolist())],
        vline=0.5,
        y0=0,
        y1=ymax,
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    freeze = freeze_model()
    blue = BlueTeam.load(SNAP / "blue_team.joblib")
    if not PAYMENTS_PATH.exists():
        raise FileNotFoundError(PAYMENTS_PATH)
    payments = load_payments()

    leak = {
        "forbidden_in_features": leakage_paths(),
        "feature_columns": list(FEATURE_COLUMNS),
        "beneficiary_is_new_in_features": "beneficiary_is_new" in FEATURE_COLUMNS,
        "destination_concentration_in_features": "destination_concentration" in FEATURE_COLUMNS,
        "leakage_forbidden": list(LEAKAGE_FORBIDDEN),
    }

    attacks = generate_mixed_attacks(payments, n_each=400, seed=RANDOM_STATE)
    train, test = prepare_split(payments, attacks, seed=RANDOM_STATE)
    split = {
        "payments_n": int(len(payments)),
        "payments_fraud_rate": float(payments["fraud_label"].mean()),
        "train_n": int(len(train)),
        "test_n": int(len(test)),
        "train_pos": int(train["fraud_label"].sum()),
        "test_pos": int(test["fraud_label"].sum()),
        "train_fraud_rate": float(train["fraud_label"].mean()),
        "test_fraud_rate": float(test["fraud_label"].mean()),
        "train_attack_families": (
            train["attack_family"].fillna("").value_counts().to_dict() if "attack_family" in train.columns else {}
        ),
        "merchant_risk_train_only": True,
        "note": "prepare_split: 80/20 stratify on IEEE fraud_label, then half of P0 synthetic attacks into train and half into test. merchant_risk fitted on train slice only.",
        "holdout_metrics_frozen": blue.metrics.get("lightgbm"),
        "per_attack_frozen": blue.metrics.get("per_attack"),
        "backend": blue.metrics.get("backend"),
    }

    ieee_ben = {
        "beneficiary_is_new": summarize(payments["beneficiary_is_new"]),
        "destination_concentration": summarize(payments["destination_concentration"]),
        "legit_beneficiary_is_new": summarize(payments.loc[payments["fraud_label"] == 0, "beneficiary_is_new"]),
        "ieee_fraud_beneficiary_is_new": summarize(payments.loc[payments["fraud_label"] == 1, "beneficiary_is_new"]),
        "legit_destination_concentration": summarize(payments.loc[payments["fraud_label"] == 0, "destination_concentration"]),
        "ieee_fraud_destination_concentration": summarize(payments.loc[payments["fraud_label"] == 1, "destination_concentration"]),
    }

    registry = get_registry()
    ctrl = RedTeamController(payments, blue, registry)
    ben = diagnose_family(ctrl, blue, payments, "BEN-001")
    mul = diagnose_family(ctrl, blue, payments, "MUL-001")

    ben_rows = ctrl.generate(ctrl.build_contract("BEN-001", difficulty="MEDIUM", transaction_count=1000, seed=424242))
    mul_rows = ctrl.generate(ctrl.build_contract("MUL-001", difficulty="MEDIUM", transaction_count=1000, seed=424242))
    legit = payments.loc[payments["fraud_label"] == 0].sample(200, random_state=424242)
    plot_scores("BEN-001", blue.score(ben_rows), blue.score(legit))
    plot_scores("MUL-001", blue.score(mul_rows), blue.score(legit))
    plot("BEN-001", ben)
    plot("MUL-001", mul)

    native = []
    if hasattr(blue.lgbm, "feature_importances_"):
        raw = np.asarray(blue.lgbm.feature_importances_, dtype=float)
        tot = float(raw.sum()) or 1.0
        native = sorted(
            [{"feature": name, "importance": float(val / tot)} for name, val in zip(FEATURE_COLUMNS, raw)],
            key=lambda r: -r["importance"],
        )

    payload = {
        "freeze": freeze,
        "leakage": leak,
        "split": split,
        "ieee_beneficiary_features": ieee_ben,
        "native_feature_importance": native,
        "BEN-001": {k: v for k, v in ben.items() if k != "sample100"},
        "MUL-001": {k: v for k, v in mul.items() if k != "sample100"},
        "BEN-001_sample100_path": "docs/evaluation/ben001_sample100.csv",
        "MUL-001_sample100_path": "docs/evaluation/mul001_sample100.csv",
    }
    pd.DataFrame(ben["sample100"]).to_csv(OUT / "ben001_sample100.csv", index=False)
    pd.DataFrame(mul["sample100"]).to_csv(OUT / "mul001_sample100.csv", index=False)
    slim = json.loads(json.dumps(payload, default=str))
    for key in ("BEN-001", "MUL-001"):
        slim[key].pop("threshold_sweep_mix", None)
        slim[key].pop("threshold_sweep_attack", None)
    (OUT / "p1_baseline_diagnostic.json").write_text(json.dumps(slim, indent=2))
    (OUT / "p1_baseline_sweeps.json").write_text(
        json.dumps(
            {
                "BEN-001": {"mix": ben["threshold_sweep_mix"], "attack": ben["threshold_sweep_attack"]},
                "MUL-001": {"mix": mul["threshold_sweep_mix"], "attack": mul["threshold_sweep_attack"]},
            },
            indent=2,
        )
    )
    print(
        json.dumps(
            {
                "freeze": freeze,
                "ben_detect": ben["ui_result"]["detection_rate"],
                "mul_detect": mul["ui_result"]["detection_rate"],
                "ben_ap": ben["pr_auc"],
                "mul_ap": mul["pr_auc"],
                "ben_scores": ben["score_distributions"],
                "mul_scores": mul["score_distributions"],
                "ben_features": {k: v.get("mean_abs_overlay_vs_recomputed") for k, v in ben["features"].items()},
                "mul_graph": mul["graph_proxy"],
                "ben_shap_top": ben["shap"][:6],
                "mul_shap_top": mul["shap"][:6],
                "native_top": native[:8],
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
