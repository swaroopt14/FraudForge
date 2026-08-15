"""FraudForge Streamlit console — Mastercard-branded red team / blue team workspace."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from attack_catalog import ATTACK_CATALOG, CORE_ATTACK_VECTORS, DIVERSITY_TARGET, IDENTITY_AUTH_FAMILY_IDS, SIMULATABLE_FAMILIES  # noqa: E402
from agents.hybrid_scorer import INTELLIGENCE_LAYERS  # noqa: E402
from config import ATTACK_FAMILIES, API_URL  # noqa: E402
from features import FAMILY_TEMPLATES, FAMILY_TO_HYPOTHESIS  # noqa: E402
from service import get_service, load_scenarios  # noqa: E402

RED = "#EB001B"
BLACK = "#000000"
WHITE = "#FFFFFF"
INK = "#111111"
MUTED = "#5C5C5C"
LINE = "#E6E6E6"

st.set_page_config(page_title="FraudForge", page_icon="FG", layout="wide")

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, .stApp, [data-testid="stAppViewContainer"] {{
  font-family: "IBM Plex Sans", sans-serif;
  background: {WHITE} !important;
  color: {INK} !important;
}}
[data-testid="stHeader"] {{
  background: {WHITE} !important;
}}
#MainMenu, footer {{visibility: hidden;}}
div[data-testid="stToolbar"] {{display: none;}}

section[data-testid="stSidebar"] {{
  background: {WHITE} !important;
  border-right: 1px solid {LINE};
}}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] li,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
  color: {INK} !important;
}}
section[data-testid="stSidebar"] .ff-kicker {{
  color: {RED} !important;
}}
section[data-testid="stSidebar"] a {{
  color: {RED} !important;
}}

.block-container {{
  padding-top: 1.2rem;
  padding-bottom: 3rem;
  max-width: 1180px;
}}
[data-testid="stWidgetLabel"],
[data-testid="stMarkdownContainer"] p,
label {{
  color: {INK} !important;
}}
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {{
  color: {MUTED} !important;
}}

div[role="radiogroup"] label,
div[role="radiogroup"] p,
div[role="radiogroup"] span {{
  color: {INK} !important;
  font-size: 0.95rem;
}}

textarea, .stTextArea textarea, [data-testid="stTextArea"] textarea {{
  background: {WHITE} !important;
  color: {INK} !important;
  border: 1px solid {LINE} !important;
  caret-color: {INK} !important;
}}
.stSelectbox div[data-baseweb="select"] > div,
.stSelectbox span {{
  color: {INK} !important;
  background: {WHITE} !important;
}}

.ff-rule {{
  height: 3px;
  width: 100%;
  background: {RED};
  margin: 0 0 1.25rem 0;
}}
.ff-kicker {{
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: {RED} !important;
  font-weight: 600;
  margin-bottom: 0.35rem;
}}
.ff-title {{
  font-size: 2.15rem;
  font-weight: 700;
  color: {BLACK} !important;
  line-height: 1.1;
  margin: 0 0 0.35rem 0;
}}
.ff-sub {{
  color: {MUTED} !important;
  font-size: 0.95rem;
  margin-bottom: 1.5rem;
}}
.ff-block {{
  background: {RED};
  color: {WHITE} !important;
  padding: 0.85rem 1rem;
  font-weight: 600;
  letter-spacing: 0.08em;
}}
.ff-ok {{
  border-top: 3px solid {BLACK};
  padding: 0.85rem 0;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: {INK} !important;
}}
hr {{
  border: none;
  border-top: 1px solid {LINE};
}}
.stButton>button {{
  background: {RED} !important;
  color: {WHITE} !important;
  border: 0 !important;
  border-radius: 0;
  font-weight: 600;
  letter-spacing: 0.04em;
  padding: 0.45rem 1.1rem;
}}
.stButton>button:hover {{
  background: #c40018 !important;
  color: {WHITE} !important;
}}
div[data-testid="stMetricValue"] {{
  font-family: "IBM Plex Mono", monospace;
  color: {INK} !important;
}}
div[data-testid="stMetricLabel"] {{
  color: {MUTED} !important;
}}
.ff-pipe {{
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0;
  border-top: 1px solid {LINE};
  margin: 0 0 1.75rem 0;
}}
.ff-pipe-item {{
  padding: 0.9rem 0.85rem 0.9rem 0;
  border-right: 1px solid {LINE};
}}
.ff-pipe-item:last-child {{ border-right: none; }}
.ff-pipe-num {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 11px;
  letter-spacing: 0.14em;
  color: {RED};
  margin-bottom: 0.25rem;
}}
.ff-pipe-side {{
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: {MUTED};
  margin-bottom: 0.2rem;
}}
.ff-pipe-title {{
  font-size: 0.95rem;
  font-weight: 600;
  color: {INK};
  line-height: 1.25;
}}
.ff-kv {{
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 0.35rem 1rem;
  margin: 0.4rem 0 1.1rem 0;
  font-size: 0.92rem;
}}
.ff-kv dt {{ color: {MUTED}; }}
.ff-kv dd {{ color: {INK}; margin: 0; }}
.ff-tag {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 11px;
  letter-spacing: 0.08em;
  color: {RED};
}}
.ff-tag-muted {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 11px;
  letter-spacing: 0.08em;
  color: {MUTED};
}}
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_resource
def _svc():
    svc = get_service()
    svc.load()
    return svc


def header(kicker: str, title: str, sub: str) -> None:
    st.markdown(
        f'<div class="ff-kicker">{kicker}</div>'
        f'<div class="ff-title">{title}</div>'
        f'<div class="ff-sub">{sub}</div>'
        f'<div class="ff-rule"></div>',
        unsafe_allow_html=True,
    )


def plotly_layout(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(family="IBM Plex Sans", size=16, color=BLACK)),
        paper_bgcolor=WHITE,
        plot_bgcolor=WHITE,
        font=dict(family="IBM Plex Sans", color=INK),
        margin=dict(l=10, r=10, t=48, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_xaxes(showgrid=False, linecolor=LINE)
    fig.update_yaxes(showgrid=True, gridcolor=LINE, zeroline=False)
    return fig


FLOW_STEPS = [
    ("01", "Red", "Threat intel"),
    ("02", "Red", "Hypothesis"),
    ("03", "Red", "Scenario overlay"),
    ("04", "Blue", "Detect + SHAP"),
    ("05", "Loop", "Retrain"),
]

OVERLAY_WHY = {
    "device_new": "New device after credential theft (ATO).",
    "velocity_1h": "Burst of payments in a short window.",
    "location_mismatch": "Session geo vs cardholder baseline.",
    "beneficiary_name_match": "UPI collect / APP payee mismatch.",
    "mule_account_risk": "Destination looks like a mule.",
    "constraint_violation": "Agent exceeded delegated amount or merchant.",
    "amount_vs_limit_ratio": "Spend vs typical or delegated cap.",
    "hour_of_day": "Timing vs the cardholder's usual hours.",
}


def _fmt_template(value) -> str:
    if isinstance(value, tuple) and len(value) == 2:
        lo, hi = value
        if isinstance(lo, float) or isinstance(hi, float):
            return f"{lo:g} – {hi:g}"
        return f"{lo} – {hi}"
    return str(value)


def view_flow(svc) -> None:
    header(
        "System flow",
        "How a scenario is built",
        "Identify emerging families, generate synthetic rows from a legitimate seed, defend with hybrid layers, then retrain on what slipped through.",
    )
    st.badge("Closed loop", icon=":material/sync:", color="red")
    with st.container(border=True):
        st.markdown("**Five attack vectors**")
        st.caption("Defensive overlays only — no phishing copy, no live rails, no stolen credentials.")
        for vec in CORE_ATTACK_VECTORS:
            st.markdown(f"- **{vec['name']}** · `{vec['family']}`")
    with st.container(border=True):
        st.markdown("**Intelligence layers (research stack)**")
        layer_rows = [
            {"Layer": "V0", "Name": "Transaction", "In this demo": "Tree / HistGB"},
            {"Layer": "V1", "Name": "Behavioral", "In this demo": "Rules (device, velocity, payee)"},
            {"Layer": "V4", "Name": "Intent", "In this demo": "Constraint / amount vs limit"},
            {"Layer": "V5", "Name": "Agent", "In this demo": "Graph head + hybrid blend"},
        ]
        st.dataframe(pd.DataFrame(layer_rows), width="stretch", hide_index=True)
        st.caption("BLOCK still follows the tree **or** the intent rule. Weak rules never block alone.")

    scenarios = [s for s in load_scenarios() if s.get("transaction")]
    if not scenarios:
        st.caption("No judge scenarios found in backend/data/demo/scenarios.json.")
        return

    titles = [s["title"] for s in scenarios]
    choice = st.selectbox("Walk a scenario", titles)
    item = next(s for s in scenarios if s["title"] == choice)
    txn = item["transaction"]
    family = txn.get("attack_family") or item.get("id")
    template = FAMILY_TEMPLATES.get(family, {})

    pipe = "".join(
        f'<div class="ff-pipe-item">'
        f'<div class="ff-pipe-num">{num}</div>'
        f'<div class="ff-pipe-side">{side}</div>'
        f'<div class="ff-pipe-title">{title}</div>'
        f"</div>"
        for num, side, title in FLOW_STEPS
    )
    st.markdown(f'<div class="ff-pipe">{pipe}</div>', unsafe_allow_html=True)

    step = st.radio(
        "Inspect step",
        [f"{num}  {title}" for num, _side, title in FLOW_STEPS],
        horizontal=True,
        label_visibility="collapsed",
    )
    step_id = step[:2]

    if step_id == "01":
        st.markdown("### 01  Threat intelligence")
        st.caption("Red team starts from a public threat note — not a live exploit.")
        st.markdown(
            f'<dl class="ff-kv">'
            f"<dt>Source note</dt><dd>{item.get('threat_intel', '—')}</dd>"
            f"<dt>Attack family</dt><dd><code>{family}</code></dd>"
            f"<dt>Expected call</dt><dd>{item.get('expected_decision', '—')}</dd>"
            f"</dl>",
            unsafe_allow_html=True,
        )
        st.markdown(item.get("narrative") or "")

    elif step_id == "02":
        st.markdown("### 02  Hypothesis")
        st.caption("Maps the intel into a detector-ready family with named signals.")
        st.markdown(
            f'<dl class="ff-kv">'
            f"<dt>Hypothesis</dt><dd>{FAMILY_TO_HYPOTHESIS.get(family, item['title'])}</dd>"
            f"<dt>Family id</dt><dd><code>{family}</code></dd>"
            f"<dt>Narrative</dt><dd>{item.get('narrative', '—')}</dd>"
            f"</dl>",
            unsafe_allow_html=True,
        )
        st.caption("Next: those signal names become overlay columns on a PCA credit-card row.")

    elif step_id == "03":
        st.markdown("### 03  Scenario overlay")
        st.caption(
            "ULB rows only have Time, V1–V28, Amount. We overlay readable fraud signals from the family template, then stamp them on this fixture."
        )
        rows = []
        for key, why in OVERLAY_WHY.items():
            raw = txn.get(key)
            shown = f"{raw:.3f}" if isinstance(raw, float) else str(raw)
            rows.append(
                {
                    "Signal": key,
                    "Why it exists": why,
                    "Family template": _fmt_template(template.get(key, "—")),
                    "This scenario": shown,
                }
            )
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Amount", f"{float(txn.get('Amount', 0)):.2f}")
        c2.metric("Hour of day", f"{float(txn.get('hour_of_day', 0)):.1f}")
        c3.metric("Class label", str(txn.get("Class", "—")))

    elif step_id == "04":
        st.markdown("### 04  Detect + SHAP")
        st.caption("Blue team scores the overlaid row. SHAP names which overlay features moved the call.")
        cache_key = f"flow_detect_{item.get('id')}"
        if cache_key not in st.session_state:
            with st.spinner("Scoring this scenario…"):
                st.session_state[cache_key] = svc.detect_rows(pd.DataFrame([txn]))
        out = st.session_state[cache_key]
        proba = out["fraud_probability"][0]
        risk = out["risk_score"][0]
        label = out["label"][0]
        _decision_banner(label, proba)
        c1, c2, c3 = st.columns(3)
        c1.metric("Fraud probability", f"{proba:.1%}")
        c2.metric("Risk score", f"{risk:.0f} / 100")
        c3.metric("Expected", item.get("expected_decision", "—"))
        expl = (out.get("explanations") or [[]])[0]
        if expl:
            edf = pd.DataFrame(expl)
            fig = go.Figure(
                go.Bar(
                    x=edf["shap_value"],
                    y=edf["feature"],
                    orientation="h",
                    marker_color=[RED if v > 0 else BLACK for v in edf["shap_value"]],
                )
            )
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(plotly_layout(fig, "SHAP — why this row scored"), width="stretch")

    else:
        st.markdown("### 05  Closed loop")
        st.caption("Hold-out attacks scored before and after the detector trains on that family.")
        try:
            result = svc.closed_loop(live=False)
        except FileNotFoundError as exc:
            st.error(str(exc))
            return
        before = result["attack_success_before"]["attack_success_rate"]
        after = result["attack_success_after"]["attack_success_rate"]
        f1_imp = result["improvement"]["f1"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Attack success before", f"{before:.1%}")
        c2.metric("Attack success after", f"{after:.1%}", delta=f"{(after - before):.1%}")
        c3.metric("Mixed F1 after", f"{f1_imp['after']:.3f}", delta=f"{f1_imp['improvement_pct']:.1f}%")
        fig = go.Figure(
            go.Bar(x=["Before", "After"], y=[before, after], marker_color=[BLACK, RED])
        )
        st.plotly_chart(plotly_layout(fig, "Attack success rate (lower is better)"), use_container_width=True)
        st.caption(result.get("failure_analysis") or "")


def view_discovery(svc) -> None:
    header(
        "Identify",
        "Attack discovery engine",
        "Retrieve threat intel, propose distinct attack families, and score diversity. Generation comes after this step.",
    )
    st.badge("Diversity", icon=":material/hub:", color="red")
    sources = svc.intel_sources()
    top1, top2, top3, top4 = st.columns(4)
    top1.metric("Intel notes", f"{len(sources)}")
    top2.metric("Catalog families", f"{len(ATTACK_CATALOG)}")
    top3.metric("Simulatable now", f"{len(SIMULATABLE_FAMILIES)}")
    top4.metric("Diversity target", f"{DIVERSITY_TARGET}")

    st.caption(
        "Identity and authentication families use payment-side overlays only. "
        "No GAN faces, forged ID images, phishing copy, or cloned audio."
    )
    pack_rows = []
    for fid in IDENTITY_AUTH_FAMILY_IDS:
        meta = ATTACK_CATALOG.get(fid) or {}
        pack_rows.append(
            {
                "Family": fid,
                "Attack": meta.get("name", fid),
                "Evidence": meta.get("evidence", "—"),
                "Surface": meta.get("attack_surface", "—"),
                "Feasibility": meta.get("feasibility", "—"),
                "Generate": "yes" if meta.get("simulatable") else "identify only",
            }
        )
    st.dataframe(pd.DataFrame(pack_rows), width="stretch", hide_index=True)

    threat = st.text_area(
        "Analyst query (optional)",
        value="",
        height=110,
        placeholder="Leave blank to ingest the full corpus. Or focus: deepfake UPI, agent constraint, QR swap…",
    )
    fetch_live = st.checkbox(
        "Also fetch allowlisted Mastercard / OWASP pages (titles and descriptions only)",
        value=False,
    )
    if st.button("Run attack discovery"):
        with st.spinner("Retrieving intel and ranking families…"):
            result = svc.discover(threat, fetch_live=fetch_live)
        st.session_state["discovery"] = result

    result = st.session_state.get("discovery")
    if not result:
        st.caption(
            "Local corpus is paraphrased public Mastercard, UPI, and OWASP notes. No phishing copy and no exploit steps."
        )
        for src in sources:
            families = ", ".join(src.get("families") or [])
            st.markdown(f"**{src['title']}**")
            st.caption(f"{src.get('date', '—')} · {families}")
            st.markdown(src.get("summary", ""))
            st.markdown("<hr/>", unsafe_allow_html=True)
        return

    if result.get("llm_used"):
        st.caption("Hypotheses ranked by the research LLM against retrieved notes.")
    else:
        st.caption("No LLM key — families ranked from retrieved notes against the catalog.")
    provider = result.get("provider") or "catalog"
    runtime = result.get("graph_runtime") or "sequential"
    st.badge(str(provider), icon=":material/psychology:", color="blue" if provider != "catalog" else "gray")
    st.badge(str(runtime), icon=":material/account_tree:", color="gray")

    live = result.get("live_fetch") or {}
    if live.get("attempted"):
        st.caption(f"Live fetch: {live.get('ok', 0)} pages · {live.get('failed', 0)} failed.")

    div = result.get("diversity") or {}
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Distinct families", f"{div.get('n_distinct_families', 0)}")
    c2.metric("Catalog coverage", f"{div.get('coverage', 0):.0%}")
    c3.metric("Categories", f"{div.get('n_categories', 0)}/{div.get('n_taxonomy', 0)}")
    c4.metric("Simulatable", f"{div.get('simulatable_count', 0)}")
    c5.metric("Vs target", f"{div.get('n_distinct_families', 0)}/{div.get('vs_target', DIVERSITY_TARGET)}")

    hyps = result.get("hypotheses") or []
    if hyps:
        fig = go.Figure(
            go.Bar(
                x=[h.get("confidence_score", 0) for h in hyps],
                y=[h.get("attack_family", "—") for h in hyps],
                orientation="h",
                marker_color=[
                    RED if h.get("catalog_status") == "simulatable" else BLACK for h in hyps
                ],
            )
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(plotly_layout(fig, "Family confidence — red = simulatable"), width="stretch")

    left, right = st.columns(2)
    with left:
        st.markdown("### Retrieved intel")
        for doc in result.get("retrieved") or []:
            origin = doc.get("origin", "corpus")
            st.markdown(f"**{doc.get('title', 'Untitled')}**")
            st.caption(
                f"{origin} · score {doc.get('score', 0):.2f} · "
                f"{', '.join(doc.get('families') or []) or 'untagged'}"
            )
            st.markdown((doc.get("summary") or "")[:420])
            st.markdown("<hr/>", unsafe_allow_html=True)
    with right:
        st.markdown("### Hypotheses")
        for hyp in hyps:
            status = hyp.get("catalog_status", "identified_only")
            tag_cls = "ff-tag" if status == "simulatable" else "ff-tag-muted"
            owasp = hyp.get("owasp_mapping") or []
            signals = hyp.get("detectable_signals") or []
            st.markdown(f"**{hyp.get('hypothesis_id', '')}  {hyp.get('attack_name', 'Unnamed')}**")
            st.markdown(
                f'<span class="{tag_cls}">{hyp.get("attack_family")} · {status}</span>',
                unsafe_allow_html=True,
            )
            st.caption(
                f"{hyp.get('category') or '—'} · {hyp.get('evidence') or '—'} · "
                f"{hyp.get('feasibility') or '—'} · tier {hyp.get('tier', '—')}"
            )
            st.markdown(f"**Surface.** {hyp.get('attack_surface', '—')}")
            st.markdown(f"**AI component.** {hyp.get('ai_component', '—')}")
            st.markdown(f"**Payment impact.** {hyp.get('payment_impact', '—')}")
            st.markdown(f"**Signals.** {', '.join(signals) if isinstance(signals, list) else signals}")
            if owasp:
                st.caption("OWASP " + " · ".join(owasp))
            st.markdown("<hr/>", unsafe_allow_html=True)


def view_generation(svc) -> None:
    header(
        "Generate",
        "Synthetic attack generator",
        "Legitimate seed, family mutation, then CTGAN or bootstrap refine. "
        "Identity and authentication families overlay KYC/auth risk flags on ULB rows — not faces, documents, or lure text.",
    )
    st.badge("Fidelity", icon=":material/equalizer:", color="red")
    discovered = st.session_state.get("discovery") or {}
    discovered_families = [
        h.get("attack_family")
        for h in (discovered.get("hypotheses") or [])
        if h.get("attack_family") in FAMILY_TO_HYPOTHESIS
    ]
    core_ids = [v.get("generate_as") or v["family"] for v in CORE_ATTACK_VECTORS]
    id_ids = [fid for fid in IDENTITY_AUTH_FAMILY_IDS if fid in FAMILY_TO_HYPOTHESIS and fid not in core_ids]
    rest = [fid for fid in FAMILY_TO_HYPOTHESIS if fid not in core_ids and fid not in id_ids]
    options = ["mixed"] + [fid for fid in core_ids if fid in FAMILY_TO_HYPOTHESIS] + id_ids + rest
    default_idx = 0
    if discovered_families:
        st.caption(
            f"Identify handed off {len(set(discovered_families))} families. Mixed will simulate all generatable families."
        )
    family = st.selectbox(
        "Attack family",
        options,
        index=default_idx,
        format_func=lambda x: (
            "mixed — all families"
            if x == "mixed"
            else next((v["name"] for v in CORE_ATTACK_VECTORS if (v.get("generate_as") or v["family"]) == x), None)
            or FAMILY_TO_HYPOTHESIS.get(x, x)
        ),
    )
    n = st.slider("Samples", min_value=100, max_value=2000, value=400, step=100)
    intensity = st.segmented_control(
        "Intensity",
        ["low", "medium", "high", "adaptive"],
        default="medium",
    )
    if st.button("Generate synthetic fraud"):
        with st.spinner("Mutating a legitimate seed and refining the overlay…"):
            result = svc.generate_attacks(
                n_samples=n,
                family=None if family == "mixed" else family,
                intensity=intensity or "medium",
            )
        st.session_state["gen"] = result

    result = st.session_state.get("gen")
    if not result:
        return

    st.markdown(result.get("scenario_card") or "")
    fid = result.get("fidelity") or {}
    ks = fid.get("ks_tests") or {}
    amt_ks = (ks.get("Amount") or {}).get("ks_statistic")
    success = result.get("attack_success") or {}
    sim = (fid.get("simulator") or {}).get("match_rate")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Rows", f"{result['n']:,}")
    m2.metric("Tabular method", result.get("method", "—"))
    m3.metric("KS Amount", f"{amt_ks:.3f}" if amt_ks is not None else "—")
    m4.metric("AFS", f"{fid['attack_fidelity_score']:.0f}" if fid.get("attack_fidelity_score") is not None else "—")
    m5.metric(
        "Attack success",
        f"{success['attack_success_rate']:.0%}" if success else "—",
        help="Share of synthetic rows scored below the detector threshold (bypassed).",
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Mean Wasserstein (scaled)", f"{fid['mean_wasserstein']:.3f}" if fid.get("mean_wasserstein") is not None else "—")
    c2.metric("Simulator match", f"{sim:.0%}" if sim is not None else "—")
    c3.metric("Mean fraud score", f"{success['mean_fraud_probability']:.1%}" if success else "—")

    mutation = result.get("mutation") or {}
    if mutation.get("before") or mutation.get("after"):
        st.caption(
            f"Intensity {result.get('intensity') or mutation.get('intensity') or 'medium'} · "
            f"{mutation.get('generation_method') or result.get('method')}"
        )
        contract = mutation.get("mutation_contract") or {}
        if contract.get("change"):
            st.caption(
                f"Change {', '.join(contract['change'])}. "
                f"Keep realistic {', '.join(contract.get('keep_realistic') or [])}."
            )
        before_col, after_col = st.columns(2)
        with before_col:
            st.markdown("**Legitimate seed**")
            st.dataframe(pd.DataFrame([mutation.get("before") or {}]), width="stretch", hide_index=True)
        with after_col:
            st.markdown("**Mutated row**")
            st.dataframe(pd.DataFrame([mutation.get("after") or {}]), width="stretch", hide_index=True)
        changed = mutation.get("changed_columns") or []
        if changed:
            st.caption("Changed columns: " + ", ".join(changed))

    real = result.get("amount_real") or []
    synth = result.get("amount_synthetic") or []
    fig = go.Figure()
    if real:
        fig.add_trace(go.Histogram(x=real, name="Real fraud", opacity=0.55, marker_color=BLACK, nbinsx=40))
    if synth:
        fig.add_trace(go.Histogram(x=synth, name="Synthetic", opacity=0.55, marker_color=RED, nbinsx=40))
    fig.update_layout(barmode="overlay")
    st.plotly_chart(plotly_layout(fig, "Amount — real vs synthetic (tabular fidelity)"), width="stretch")

    mule = result.get("mule_synthetic") or []
    vel = result.get("velocity_synthetic") or []
    if mule or vel:
        left, right = st.columns(2)
        with left:
            fig_m = go.Figure(go.Histogram(x=mule, marker_color=RED, nbinsx=24, name="mule_account_risk"))
            st.plotly_chart(plotly_layout(fig_m, "Overlay — mule_account_risk"), width="stretch")
        with right:
            fig_v = go.Figure(go.Histogram(x=vel, marker_color=BLACK, nbinsx=12, name="velocity_1h"))
            st.plotly_chart(plotly_layout(fig_v, "Overlay — velocity_1h"), width="stretch")

    counts = result.get("family_counts") or {}
    if counts:
        fig_c = go.Figure(
            go.Bar(
                x=list(counts.values()),
                y=list(counts.keys()),
                orientation="h",
                marker_color=RED,
            )
        )
        fig_c.update_yaxes(autorange="reversed")
        st.plotly_chart(plotly_layout(fig_c, "Rows per attack family"), width="stretch")

    if result.get("preview"):
        st.dataframe(pd.DataFrame(result["preview"]), width="stretch", hide_index=True)


def _decision_banner(label: int, proba: float) -> None:
    if label:
        st.markdown(
            f'<div class="ff-block">BLOCK  ·  fraud probability {proba:.1%}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="ff-ok">APPROVE  ·  fraud probability {proba:.1%}</div>',
            unsafe_allow_html=True,
        )


def view_detection(svc) -> None:
    header(
        "Defend",
        "Fraud classifier",
        "Hybrid layers: rules, tree, graph, and intent. BLOCK if the tree fires or the intent rule fires. Weak rules score only.",
    )
    st.badge("Efficacy", icon=":material/verified_user:", color="blue")
    metrics = svc.metrics()
    det = metrics.get("detector") or {}
    b1, b2, b3, b4, b5 = st.columns(5)
    b1.metric("Tree backend", str(metrics.get("tree_backend") or det.get("backend") or "—"))
    b2.metric("Holdout F1", f"{det.get('f1', 0):.3f}" if det else "—")
    b3.metric("Precision", f"{det.get('precision', 0):.3f}" if det else "—")
    b4.metric("ROC-AUC", f"{det.get('roc_auc', 0):.3f}" if det else "—")
    b5.metric("Relational", str(metrics.get("relational_backend") or "—"))

    scenarios = [s for s in load_scenarios() if s.get("transaction")]
    names = [s["title"] for s in scenarios]
    choice = st.selectbox("Judge scenario", names) if names else None
    uploaded = st.file_uploader("Or upload a one-row CSV", type=["csv"])

    frame = None
    narrative = None
    expected = None
    if uploaded is not None:
        frame = pd.read_csv(uploaded)
    elif choice:
        item = next(s for s in scenarios if s["title"] == choice)
        frame = pd.DataFrame([item["transaction"]])
        narrative = item.get("narrative")
        expected = item.get("expected_decision")

    if frame is None:
        return
    if narrative:
        st.caption(narrative)
    if st.button("Score transaction"):
        with st.spinner("Scoring tree + relational head…"):
            out = svc.detect_rows(frame)
        st.session_state["detect"] = out

    out = st.session_state.get("detect")
    if not out:
        return
    proba = out["fraud_probability"][0]
    risk = out["risk_score"][0]
    label = out["label"][0]
    _decision_banner(label, proba)
    if expected:
        st.caption(f"Expected call for this fixture: {expected}")

    ens = (out.get("ensemble_probability") or [proba])[0]
    rel = (out.get("relational") or {}).get("details") or [{}]
    rel0 = rel[0] if rel else {}
    layers = out.get("layers") or {}
    layer0 = {
        "rules": (layers.get("rules") or [0])[0],
        "ml": (layers.get("ml") or [proba])[0],
        "graph": (layers.get("graph") or [0])[0],
        "intent": (layers.get("intent") or [0])[0],
        "hybrid": (layers.get("hybrid") or [ens])[0],
    }
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Rules", f"{layer0['rules']:.1%}")
    c2.metric("ML", f"{layer0['ml']:.1%}")
    c3.metric("Graph", f"{layer0['graph']:.1%}")
    c4.metric("Intent", f"{layer0['intent']:.1%}")
    c5.metric("Hybrid", f"{layer0['hybrid']:.1%}")
    st.caption(
        f"Latency {out.get('inference_latency_ms', out.get('latency_ms', 0)):.1f} ms · "
        f"threshold {out['threshold']:.3f}"
    )
    intel = out.get("intelligence") or {}
    view = st.segmented_control(
        "Intelligence view",
        list(INTELLIGENCE_LAYERS.keys()),
        default="V5",
        help="Research stack readout. Decision is still tree or intent — this does not retrain.",
    )
    view = view or "V5"
    spec = INTELLIGENCE_LAYERS[view]
    view_score = (intel.get(view) or [layer0["hybrid"]])[0]
    st.metric(f"{view} · {spec['label']}", f"{view_score:.1%}")
    st.caption("Weights: " + ", ".join(f"{k} {w:.0%}" for k, w in spec["weights"].items()))

    fig_e = go.Figure(
        go.Bar(
            x=[layer0["rules"], layer0["ml"], layer0["graph"], layer0["intent"], layer0["hybrid"]],
            y=["Rules", "ML", "Graph", "Intent", "Hybrid"],
            orientation="h",
            marker_color=[BLACK, BLACK, RED, RED, RED],
        )
    )
    fig_e.update_yaxes(autorange="reversed")
    st.plotly_chart(plotly_layout(fig_e, "Hybrid layers — 0.50 ml + 0.20 graph + 0.15 rules + 0.15 intent"), width="stretch")

    st.markdown(
        f'<span class="ff-tag">payee degree {rel0.get("payee_degree", 0):.0f}</span>  '
        f'<span class="ff-tag-muted">device degree {rel0.get("device_degree", 0):.0f}</span>  '
        f'<span class="ff-tag-muted">payee mule mean {rel0.get("payee_mule_mean", 0):.2f}</span>',
        unsafe_allow_html=True,
    )
    if rel0.get("gcn_score") is not None:
        st.caption(f"Torch GCN payee score {rel0['gcn_score']:.1%}")

    if out.get("anomaly_score"):
        st.caption(f"Anomaly reconstruction error {out['anomaly_score'][0]:.4f}")

    expl = (out.get("explanations") or [[]])[0]
    if expl:
        edf = pd.DataFrame(expl)
        fig = go.Figure(
            go.Bar(
                x=edf["shap_value"],
                y=edf["feature"],
                orientation="h",
                marker_color=[RED if v > 0 else BLACK for v in edf["shap_value"]],
            )
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(plotly_layout(fig, "SHAP — why the tree moved"), width="stretch")
        st.dataframe(edf, width="stretch", hide_index=True)


def view_loop(svc) -> None:
    header(
        "Closed loop",
        "Evaluate and retrain",
        "Hold-out attacks scored before and after the detector sees the new family of rows.",
    )
    st.badge("Novelty", icon=":material/auto_awesome:", color="orange")
    live = st.checkbox("Recompute live (slow — retrains on this machine)", value=False)
    if st.button("Run evaluation"):
        with st.spinner("Evaluating…"):
            try:
                result = svc.closed_loop(live=live)
                st.session_state["loop"] = result
            except FileNotFoundError as exc:
                st.error(str(exc))
                return

    result = st.session_state.get("loop")
    if not result:
        st.caption("Loads backend/data/demo/closed_loop.json unless live recompute is checked.")
        return

    before = result["attack_success_before"]["attack_success_rate"]
    after = result["attack_success_after"]["attack_success_rate"]
    f1_imp = result["improvement"]["f1"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Attack success before", f"{before:.1%}")
    c2.metric("Attack success after", f"{after:.1%}", delta=f"{(after - before):.1%}")
    c3.metric("Mixed F1", f"{f1_imp['after']:.3f}", delta=f"{f1_imp['improvement_pct']:.1f}%")

    history = [
        {
            "iteration": 0,
            "attack_success_rate": before,
            "detection_f1": (result.get("mixed_test_before") or {}).get("f1", f1_imp.get("before")),
        },
        {
            "iteration": 1,
            "attack_success_rate": after,
            "detection_f1": (result.get("mixed_test_after") or {}).get("f1", f1_imp.get("after")),
        },
    ]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[h["iteration"] for h in history],
            y=[h["attack_success_rate"] for h in history],
            name="Attack success",
            mode="lines+markers",
            line=dict(color=RED),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[h["iteration"] for h in history],
            y=[h["detection_f1"] for h in history],
            name="Detection F1",
            mode="lines+markers",
            line=dict(color=BLACK),
        )
    )
    st.plotly_chart(plotly_layout(fig, "Closed-loop iterations (attack success down, F1 up)"), width="stretch")
    st.dataframe(pd.DataFrame(history), width="stretch", hide_index=True)

    st.markdown("**Failure analysis**")
    st.text(result.get("failure_analysis") or "—")
    hyps = result.get("new_hypotheses") or []
    if hyps:
        st.markdown("**Feedback hypotheses**")
        for h in hyps:
            st.markdown(f"- **{h.get('attack_name', 'Unnamed')}** — {h.get('evasion_strategy', h.get('attack_vector', ''))}")


RED_PLAY_STEPS = [
    "The shopping agent opens a merchant page. Device, customer, and category look normal. Amount stays under the ₹80,000 demo cap.",
    "The page is treated as untrusted tool output. Indirect prompt injection is hypothesized — the payload is not shown.",
    "A payment parameter changes: destination / beneficiary only. Amount, device, and MCC stay ordinary.",
    "Red team asks whether blue notices beneficiary mismatch, mule risk, and a broken intent constraint.",
]


def view_red_team(svc) -> None:
    header(
        "Red team",
        "Simulate a GenAI payment attack",
        "Backend mutates a legitimate ULB row. No live rails and no phishing copy.",
    )
    st.badge("Demo", icon=":material/play_arrow:", color="red")
    st.caption("Connected to `POST /demo/red` via the shared service.")

    families = SIMULATABLE_FAMILIES
    family = st.selectbox(
        "Attack family",
        families,
        index=families.index("prompt_injection_pay") if "prompt_injection_pay" in families else 0,
        format_func=lambda fid: ATTACK_CATALOG.get(fid, {}).get("name", fid),
    )
    intensity = st.segmented_control("Intensity", ["low", "medium", "high"], default="medium")
    with st.container(horizontal=True):
        run = st.button("Run red simulation", type="primary")
        reset = st.button("Reset")
    if reset:
        st.session_state.red_demo = None
        st.session_state.red_step = 0
        st.session_state.blue_demo = None

    if run:
        with st.status("Mutating a legitimate row…", expanded=False) as status:
            st.session_state.red_demo = svc.run_red_demo(family=family, intensity=intensity or "medium")
            st.session_state.red_step = 0
            st.session_state.blue_demo = None
            status.update(label="Simulation ready", state="complete")

    demo = st.session_state.get("red_demo")
    with st.expander("What this red team does not do", expanded=True):
        for line in (demo or {}).get("safety") or [
            "No live payment networks, UPI, card, or wallet calls",
            "No real phishing email or SMS",
            "No contact with victims",
            "No stolen credentials or real account takeover",
            "No unauthorized tests against third-party systems",
        ]:
            st.markdown(f"- {line}")

    if not demo:
        st.info("Run the simulation to generate a backend row for Blue team.")
        return

    st.session_state.setdefault("red_step", 0)
    step = int(st.session_state.red_step)
    with st.container(horizontal=True):
        if st.button("Next step", disabled=step >= len(RED_PLAY_STEPS) - 1):
            st.session_state.red_step = min(step + 1, len(RED_PLAY_STEPS) - 1)
            st.rerun()
        st.caption(f"Step {step + 1} of {len(RED_PLAY_STEPS)}")

    for i, text in enumerate(RED_PLAY_STEPS[: step + 1]):
        with st.chat_message("assistant"):
            st.markdown(f":red-badge[Red] {text}")

    left, right = st.columns(2)
    with left:
        st.markdown("**Legitimate seed**")
        st.dataframe(pd.DataFrame([demo.get("before") or {}]), width="stretch", hide_index=True)
    with right:
        st.markdown("**Mutated attack row**")
        st.dataframe(pd.DataFrame([demo.get("after") or {}]), width="stretch", hide_index=True)

    st.markdown(
        f":small[Method `{demo.get('generation_method')}` · changed "
        f"{', '.join(demo.get('changed_columns') or []) or 'none'}]"
    )
    st.caption("Open **Blue team** to score this row with the hybrid detector.")


def view_blue_team(svc) -> None:
    header(
        "Blue team",
        "Detect the generated attack",
        "Hybrid rules + ML + graph + intent. BLOCK if the tree or the intent rule fires.",
    )
    st.badge("Demo", icon=":material/shield:", color="blue")
    st.caption("Connected to `POST /demo/blue` via the shared service.")

    red = st.session_state.get("red_demo")
    txn = (red or {}).get("transaction")
    if not txn:
        st.warning("Run **Red team** first so Blue has a backend transaction to score.")
        if st.button("Score a fresh prompt-injection row"):
            st.session_state.red_demo = svc.run_red_demo()
            st.session_state.blue_demo = None
            st.rerun()
        return

    if st.button("Score with hybrid detector", type="primary"):
        st.session_state.blue_demo = svc.run_blue_demo(transaction=txn)

    blue = st.session_state.get("blue_demo")
    if not blue:
        st.info("Click score to run `/detect` with hybrid layers.")
        return

    decision = blue.get("decision", "APPROVE")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Decision", decision)
    layers = blue.get("layers") or {}
    c2.metric("ML", f"{float(layers.get('ml') or 0):.2f}")
    c3.metric("Intent", f"{float(layers.get('intent') or 0):.2f}")
    c4.metric("Latency", f"{float(blue.get('latency_ms') or 0):.1f} ms")

    if decision == "BLOCK":
        st.badge("Blocked", icon=":material/block:", color="red")
    else:
        st.badge("Approved", icon=":material/check_circle:", color="green")

    st.markdown("**What blue should detect**")
    for check in blue.get("checks") or []:
        hit = check.get("hit")
        icon = ":material/check_circle:" if hit else ":material/radio_button_unchecked:"
        color = "red" if hit else "gray"
        st.markdown(
            f":{color}-badge[{check.get('layer', '')}] {icon} {check.get('label')}"
        )

    st.markdown("**Hybrid layers**")
    layer_row = {
        "rules": [float(layers.get("rules") or 0)],
        "ml": [float(layers.get("ml") or 0)],
        "graph": [float(layers.get("graph") or 0)],
        "intent": [float(layers.get("intent") or 0)],
        "hybrid": [float(layers.get("hybrid") or 0)],
    }
    st.dataframe(pd.DataFrame(layer_row), width="stretch", hide_index=True)
    st.caption(
        f"Tree backend `{blue.get('backend')}` · threshold {float(blue.get('threshold') or 0):.3f} · "
        f"inference {float(blue.get('inference_latency_ms') or 0):.1f} ms"
    )
    expl = blue.get("explanations") or []
    if expl:
        st.markdown("**Top SHAP signals**")
        st.dataframe(pd.DataFrame(expl), width="stretch", hide_index=True)


def view_simulator(svc) -> None:
    header(
        "Payment simulator",
        "Watch the attack, then the defense",
        "Synthetic data only. No live messages, accounts, or settlement.",
    )
    st.badge("Simulation only", icon=":material/science:", color="orange")
    st.badge("Synthetic data", icon=":material/database:", color="gray")
    st.badge("No live payment execution", icon=":material/block:", color="red")

    scenarios = svc.list_sim_scenarios()
    names = {s["scenario_id"]: s["name"] for s in scenarios}
    ids = [s["scenario_id"] for s in scenarios] or ["agent_destination_substitution"]

    with st.container(border=True):
        st.markdown("**Run payment simulation**")
        scenario_id = st.selectbox(
            "Scenario",
            ids,
            format_func=lambda x: names.get(x, x),
        )
        rail = st.segmented_control("Payment rail", ["card", "upi", "wallet"], default="card")
        mode = st.segmented_control("Detector", ["full", "weak"], default="full")
        with st.container(horizontal=True):
            run_flagship = st.button("Run flagship demo", type="primary", icon=":material/play_arrow:")
            start = st.button("Start", icon=":material/flag:")
            step = st.button("Step forward", icon=":material/skip_next:")
            run_all = st.button("Run full simulation", icon=":material/fast_forward:")
            reset = st.button("Reset", icon=":material/refresh:")
            replay = st.button("Replay weak then full", icon=":material/compare_arrows:")

    if run_flagship:
        with st.spinner("Running flagship demo…"):
            st.session_state["sim_replay"] = svc.flagship_demo()
            after = (st.session_state["sim_replay"] or {}).get("after") or {}
            st.session_state["sim_state"] = after.get("state")
    if start:
        st.session_state["sim_replay"] = None
        st.session_state["sim_state"] = svc.start_simulation(
            scenario_id, mode=mode or "full", payment_rail=rail
        )
    if step:
        sid = (st.session_state.get("sim_state") or {}).get("simulation_id")
        if sid:
            st.session_state["sim_state"] = svc.step_simulation(sid)
        else:
            st.session_state["sim_state"] = svc.start_simulation(
                scenario_id, mode=mode or "full", payment_rail=rail
            )
            sid = st.session_state["sim_state"]["simulation_id"]
            st.session_state["sim_state"] = svc.step_simulation(sid)
    if run_all:
        sid = (st.session_state.get("sim_state") or {}).get("simulation_id")
        if not sid or (st.session_state["sim_state"] or {}).get("scenario", {}).get("scenario_id") != scenario_id:
            st.session_state["sim_state"] = svc.start_simulation(
                scenario_id, mode=mode or "full", payment_rail=rail
            )
            sid = st.session_state["sim_state"]["simulation_id"]
        st.session_state["sim_state"] = svc.run_simulation(sid)
    if reset:
        sid = (st.session_state.get("sim_state") or {}).get("simulation_id")
        st.session_state["sim_replay"] = None
        if sid:
            st.session_state["sim_state"] = svc.reset_simulation(sid)
        else:
            st.session_state["sim_state"] = None
    if replay:
        with st.spinner("Replaying amount-only miss, then intent BLOCK…"):
            st.session_state["sim_replay"] = svc.replay_simulation(scenario_id)
            after = (st.session_state["sim_replay"] or {}).get("after") or {}
            st.session_state["sim_state"] = after.get("state")

    state = st.session_state.get("sim_state")
    if not state:
        st.info("Start a simulation or run the flagship demo.")
        return

    prog = state.get("progress") or {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Simulation", state.get("simulation_id", "—"))
    c2.metric("Progress", f"{prog.get('done', 0)} / {prog.get('total', 10)}")
    c3.metric("Simulated clock", state.get("simulated_clock") or "12:00:00")
    c4.metric("Payment state", state.get("payment_state") or "CREATED")
    st.caption(f"Status: {state.get('status', '—')} · Customer `cust_019` · Agent `agent_042`")

    events = state.get("events") or []
    left, right = st.columns((1.35, 1))
    with left:
        st.markdown("**Attack timeline**")
        if not events:
            st.caption("No events yet. Step forward or run the full simulation.")
        labels = [f"{e.get('timestamp')}  {e.get('event_type')}" for e in events]
        picked = None
        if labels:
            picked = st.pills("Event", labels, selection_mode="single")
        for e in events:
            label = f"{e.get('timestamp')}  {e.get('event_type')}"
            with st.container(border=True):
                risk = (e.get("risk_signals") or {}).get("intent")
                tone = "red" if (risk or 0) >= 0.5 else "gray"
                st.markdown(
                    f":{tone}-badge[{e.get('stage')}] `{e.get('timestamp')}`  **{e.get('event_type')}**"
                )
                st.caption(e.get("summary") or "")
                if e.get("decision"):
                    st.badge(str(e["decision"]), color="red" if e["decision"] == "BLOCK" else "green")
        selected = None
        if picked:
            selected = next((e for e in events if f"{e.get('timestamp')}  {e.get('event_type')}" == picked), None)
        if selected is None and events:
            selected = events[-1]
        if selected:
            st.markdown("**Event detail**")
            with st.container(border=True):
                st.write(f"Type `{selected.get('event_type')}`")
                st.write(f"Actor {selected.get('actor_type')} `{selected.get('actor_id')}`")
                prov = selected.get("provenance") or {}
                if prov.get("original_destination"):
                    st.write(
                        f"Destination `{prov.get('original_destination')}` → `{prov.get('new_destination')}`"
                    )
                if selected.get("decision"):
                    st.write(f"Decision **{selected.get('decision')}**")
                st.json(
                    {
                        "risk_signals": selected.get("risk_signals"),
                        "provenance": prov,
                        "ground_truth": selected.get("ground_truth"),
                        "metadata": selected.get("metadata"),
                    }
                )

    with right:
        st.markdown("**Red vs blue**")
        red = state.get("red_team") or {}
        dec = (state.get("final_decision") or {}).get("decision")
        r1, r2 = st.columns(2)
        with r1:
            with st.container(border=True):
                st.markdown("**Red team**")
                st.caption(red.get("objective") or "destination_substitution")
                st.write("Latest action: modify destination")
                score = (state.get("final_decision") or {}).get("model_score")
                st.metric("Detector score", f"{score:.2f}" if score is not None else "—")
                bypassed = dec == "APPROVE"
                st.badge("Bypassed" if bypassed else ("Detected" if dec == "BLOCK" else "In play"), color="red" if bypassed else "blue")
        with r2:
            with st.container(border=True):
                st.markdown("**Blue team**")
                st.metric("Decision", dec or "MONITORING")
                reasons = (state.get("final_decision") or {}).get("reason_codes") or []
                st.caption(" · ".join(reasons) if reasons else "Waiting for authorization")
                if dec == "BLOCK":
                    st.badge("Block", icon=":material/block:", color="red")

        series = state.get("risk_series") or []
        if series:
            st.markdown("**Cumulative risk**")
            rdf = pd.DataFrame(series)
            chart = rdf.set_index("timestamp")[["transaction", "device", "graph", "intent", "anomaly"]]
            st.line_chart(chart)

        pay = state.get("payment") or {}
        ent = state.get("entities") or {}
        if dec:
            st.markdown("**Payment authorization**")
            with st.container(border=True):
                st.markdown(f"### ₹{float(pay.get('amount') or 0):,.0f} {pay.get('currency') or 'INR'}")
                st.caption(f"{pay.get('category')} · {ent.get('original_destination')} · agent `{ent.get('agent_id')}`")
                if dec == "BLOCK":
                    st.badge("Blocked", icon=":material/block:", color="red")
                elif dec == "APPROVE":
                    st.badge("Approved", icon=":material/check_circle:", color="green")
                else:
                    st.badge(str(dec), color="orange")
                st.write("Payment destination does not match authorized intent." if (state.get("intent_result") or {}).get("violated") else "Intent checks recorded.")
                st.caption(
                    f"Customer `{ent.get('customer_id')}` · device known · beneficiary "
                    f"{'new' if pay.get('beneficiary_is_new') else 'known'} · intent "
                    f"{'violated' if (state.get('intent_result') or {}).get('violated') else 'ok'}"
                )
                with st.expander("Reason codes and provenance"):
                    st.write((state.get("final_decision") or {}).get("reason_codes"))
                    st.json((state.get("intent_result") or {}))

        settle_ev = next((e for e in reversed(events) if e.get("event_type") == "settlement_simulated"), None)
        if settle_ev:
            st.markdown("**Simulated impact**")
            meta = settle_ev.get("metadata") or {}
            with st.container(border=True):
                st.badge("Simulated", color="orange")
                st.metric("Potential exposure", f"₹{float(pay.get('amount') or 0):,.0f}")
                st.metric("Settlement prevented", "Yes" if meta.get("prevented") else "No")
                if meta.get("prevented"):
                    st.caption("Blocked path: no settlement, no cash-out.")
                else:
                    st.caption("Approved path: simulated funds to the mule, then cash-out.")

    replay_state = st.session_state.get("sim_replay")
    if replay_state:
        st.markdown("**Before / after (simulated evaluation)**")
        st.caption("Same attack replayed. Weak = amount only. Full = intent destination.")
        b, a = st.columns(2)
        before = replay_state.get("before") or {}
        after = replay_state.get("after") or {}
        with b:
            with st.container(border=True):
                st.markdown(f"**{before.get('version')} amount-only**")
                st.metric("Bypass rate", f"{float(before.get('bypass_rate') or 0):.0%}")
                st.write(f"Destination substitution: {before.get('destination_substitution')}")
                st.write(f"Decision **{before.get('decision')}**")
        with a:
            with st.container(border=True):
                st.markdown(f"**{after.get('version')} intent + destination**")
                st.metric("Bypass rate", f"{float(after.get('bypass_rate') or 0):.0%}")
                st.write(f"Destination substitution: {after.get('destination_substitution')}")
                st.write(f"Decision **{after.get('decision')}**")
                st.caption(f"New signal: {after.get('signal') or (replay_state.get('improvement') or {}).get('new_signal')}")


def main() -> None:
    st.session_state.setdefault("red_demo", None)
    st.session_state.setdefault("blue_demo", None)
    st.session_state.setdefault("red_step", 0)
    st.session_state.setdefault("sim_state", None)
    st.session_state.setdefault("sim_replay", None)
    with st.sidebar:
        st.markdown(
            f'<div class="ff-kicker">Mastercard Innovation Challenge</div>'
            f'<div style="font-size:1.35rem;font-weight:700;color:{BLACK};margin:0.2rem 0 0.8rem;">FraudForge</div>',
            unsafe_allow_html=True,
        )
        page = st.radio(
            "View",
            [
                "System flow",
                "Payment simulator",
                "Red team",
                "Blue team",
                "Identify",
                "Generate",
                "Defend",
                "Closed-loop evaluation",
            ],
            label_visibility="collapsed",
        )
        svc = _svc()
        status = svc.metrics().get("models") or {}
        st.markdown("<hr/>", unsafe_allow_html=True)
        st.caption("Models")
        st.write(
            f"Detector {'ready' if status.get('detector') else 'missing'} · "
            f"CTGAN {'ready' if status.get('ctgan') else 'bootstrap'} · "
            f"Loop {'ready' if status.get('closed_loop') else 'missing'}"
        )
        det = svc.detector.metrics if svc.detector else {}
        if det:
            st.caption(f"Holdout F1 {det.get('f1', 0):.3f} · AUC {det.get('roc_auc', 0):.3f}")
        st.caption(f"API {API_URL}")

    if page == "System flow":
        view_flow(svc)
    elif page == "Payment simulator":
        view_simulator(svc)
    elif page == "Red team":
        view_red_team(svc)
    elif page == "Blue team":
        view_blue_team(svc)
    elif page == "Identify":
        view_discovery(svc)
    elif page == "Generate":
        view_generation(svc)
    elif page == "Defend":
        view_detection(svc)
    else:
        view_loop(svc)


if __name__ == "__main__":
    main()
