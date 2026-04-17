"""
Gyan AI — Admin Control Room
=============================
Streamlit dashboard for the Gyan AI data pipeline.

Pages:
  📊 Dashboard       — live metrics + charts
  🔍 Triage Queue    — approve / reject pending MCQs + study notes
  🚀 Pipeline Control — trigger GitHub Actions ingestion workflows
  🤖 Agent Prompts   — view / edit সর্বজ্ঞ, চিত্রগুপ্ত, সূত্রধর prompts

Secrets required (set in Streamlit Cloud → App settings → Secrets):
  SUPABASE_URL         = "https://xxx.supabase.co"
  SUPABASE_SERVICE_KEY = "eyJ..."
  GITHUB_PAT           = "gho_..."
  GITHUB_REPO          = "arkagimt/gyan-ai-pipeline"
"""

from __future__ import annotations
import json
import requests
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client
from datetime import datetime

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Gyan AI — Control Room",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Style ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stSidebar"] { background: #1a1a2e; min-width: 200px; }
    [data-testid="stSidebar"] * { color: #e0e0e0 !important; }
    .block-container { padding-top: 1.2rem; padding-left: 2rem; padding-right: 2rem; max-width: 1200px; }
    div[data-testid="metric-container"] {
        background: white;
        border: 1px solid #e8e8e8;
        border-radius: 10px;
        padding: 0.8rem 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    div[data-testid="metric-container"] label { font-size: 0.7rem !important; }
    .stRadio > div { gap: 0.5rem; }
    h1 { font-size: 1.6rem !important; }
    h2 { font-size: 1.2rem !important; }
</style>
""", unsafe_allow_html=True)


# ── Accuracy score helper ─────────────────────────────────────────────────────
def _norm_score(score) -> float:
    """
    Backward-compat: old data stored accuracy as 0.0–1.0 ratio (bug).
    New data stores as 0–100. Detect and convert old format.
    """
    if score is None:
        return 0.0
    s = float(score)
    return round(s * 100, 1) if s <= 1.0 else round(s, 1)


# ── Sanjaya Milestone Renderer ────────────────────────────────────────────────
# Mirror of MILESTONES in db/memory.py — keep in sync if you add milestones.
_SANJAYA_MILESTONES = [
    (100,  "🎯 100 MCQs",   "Pilot cohort ready. Track first student completions."),
    (500,  "🚀 DSPy Time",  "SC-001: Implement DSPy optimizer. See SANJAYA_CHRONICLES.md."),
    (1000, "🔍 pgvector",   "SC-002: Enable semantic search for অন্বেষক."),
    (2500, "🤖 PydanticAI", "SC-003: Build বেতাল + নারদ student-facing agents."),
    (5000, "🌟 Full WB",    "Full West Bengal curriculum coverage approaching."),
]

def _render_sanjaya_milestone(live_mcq_count: int) -> None:
    """
    Render a Sanjaya milestone progress banner in the dashboard.
    Shows progress toward the next upcoming milestone, and celebrates crossed ones.
    """
    # Find next uncrossed milestone
    next_milestone = None
    crossed = []
    for threshold, label, action in _SANJAYA_MILESTONES:
        if live_mcq_count >= threshold:
            crossed.append((threshold, label, action))
        else:
            if next_milestone is None:
                next_milestone = (threshold, label, action)

    # ── Active milestone alert (DSPy specifically) ────────────────────────────
    if live_mcq_count >= 500:
        st.success(
            "🚀 **[SANJAYA — SC-001 TRIGGERED]** You have **500+ live MCQs!**  \n"
            "**Action**: Implement the **DSPy optimizer** to auto-tune agent prompts.  \n"
            "See `SANJAYA_CHRONICLES.md → Entry SC-001` for the full implementation plan.",
            icon="🧠",
        )

    # ── Progress bar toward next milestone ────────────────────────────────────
    if next_milestone:
        threshold, label, action = next_milestone
        prev_threshold = crossed[-1][0] if crossed else 0
        progress_in_band = live_mcq_count - prev_threshold
        band_size        = threshold - prev_threshold
        progress_pct     = min(progress_in_band / band_size, 1.0)

        with st.container():
            cols = st.columns([3, 1])
            with cols[0]:
                st.caption(
                    f"**Sanjaya** · Next milestone: **{label}** at {threshold} MCQs "
                    f"— {action}"
                )
                st.progress(progress_pct)
            with cols[1]:
                st.caption(
                    f"{live_mcq_count} / {threshold} MCQs  \n"
                    f"({threshold - live_mcq_count} to go)"
                )
    elif crossed:
        # All milestones crossed — celebrate
        st.balloons()
        st.success("🏆 **All Sanjaya milestones reached!** Gyan AI is fully battle-tested.")


# ── Supabase client ───────────────────────────────────────────────────────────
@st.cache_resource
def get_supabase() -> Client:
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_SERVICE_KEY"],
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.markdown("## 🧠 Gyan AI")
st.sidebar.markdown("**Admin Control Room**")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    ["📊 Dashboard", "🔍 Triage Queue", "🚀 Pipeline Control", "🤖 Agent Prompts"],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.caption(f"Today: {datetime.now().strftime('%d %b %Y')}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

def page_dashboard():
    st.title("📊 Dashboard")
    st.caption("Live snapshot of your Gyan AI data pipeline.")

    db = get_supabase()

    # ── Fetch metrics ────────────────────────────────────────────────────────
    with st.spinner("Loading metrics..."):
        try:
            pyq_count    = db.table("pyq_bank_v2").select("*", count="exact", head=True).execute().count or 0
            mat_count    = db.table("study_materials").select("*", count="exact", head=True).execute().count or 0
            pending_count = (
                db.table("ingestion_triage_queue")
                .select("*", count="exact", head=True)
                .eq("status", "pending")
                .execute().count or 0
            )
            approved_count = (
                db.table("ingestion_triage_queue")
                .select("*", count="exact", head=True)
                .eq("status", "approved")
                .execute().count or 0
            )
            rejected_count = (
                db.table("ingestion_triage_queue")
                .select("*", count="exact", head=True)
                .eq("status", "rejected")
                .execute().count or 0
            )
        except Exception as e:
            st.error(f"Supabase connection failed: {e}")
            return

    # ── Metric Cards ──────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Live MCQs",        pyq_count,     help="Approved in pyq_bank_v2")
    c2.metric("Study Notes",      mat_count,     help="Approved in study_materials")
    c3.metric("Pending Review",   pending_count, help="In ingestion_triage_queue (pending)")
    c4.metric("Total Approved",   approved_count)
    c5.metric("Total Rejected",   rejected_count)

    # ── Sanjaya Milestone Tracker ─────────────────────────────────────────────
    _render_sanjaya_milestone(pyq_count)

    st.markdown("---")

    # ── Triage Queue Status Chart ─────────────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Triage Queue Status")
        if (pending_count + approved_count + rejected_count) > 0:
            fig = px.pie(
                names=["Pending", "Approved", "Rejected"],
                values=[pending_count, approved_count, rejected_count],
                color=["Pending", "Approved", "Rejected"],
                color_discrete_map={
                    "Pending":  "#f59e0b",
                    "Approved": "#10b981",
                    "Rejected": "#ef4444",
                },
                hole=0.5,
            )
            fig.update_traces(textposition="outside", textinfo="percent+label")
            fig.update_layout(showlegend=False, margin=dict(t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No triage data yet. Run the pipeline first.")

    # ── Recent Accuracy Scores ────────────────────────────────────────────────
    with col_right:
        st.subheader("AI Accuracy Distribution")
        try:
            score_data = (
                db.table("ingestion_triage_queue")
                .select("ai_accuracy_score, payload_type")
                .not_.is_("ai_accuracy_score", "null")
                .limit(200)
                .execute()
            ).data or []

            if score_data:
                df = pd.DataFrame(score_data)
                # Normalize old ratio format (0.0–1.0) to percentage (0–100)
                df["ai_accuracy_score"] = df["ai_accuracy_score"].apply(
                    lambda s: float(s) * 100 if s is not None and float(s) <= 1.0 else (float(s) if s is not None else 0.0)
                )
                fig2 = px.histogram(
                    df,
                    x="ai_accuracy_score",
                    color="payload_type",
                    nbins=20,
                    labels={"ai_accuracy_score": "Accuracy Score", "payload_type": "Type"},
                    color_discrete_map={"pyq": "#6366f1", "material": "#10b981"},
                    barmode="overlay",
                )
                fig2.update_layout(margin=dict(t=20, b=20))
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No accuracy scores yet.")
        except Exception as e:
            st.warning(f"Could not load accuracy data: {e}")

    # ── Recent Pipeline Batches ───────────────────────────────────────────────
    st.subheader("Recent Batches")
    try:
        recent = (
            db.table("ingestion_triage_queue")
            .select("batch_id, segment, payload_type, status, created_at")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        ).data or []

        if recent:
            df_recent = pd.DataFrame(recent)
            # Group by batch_id
            batch_summary = (
                df_recent.groupby(["batch_id", "segment", "status"])
                .size()
                .reset_index(name="count")
                .sort_values("batch_id", ascending=False)
            )
            st.dataframe(batch_summary, use_container_width=True, hide_index=True)
        else:
            st.info("No batches yet.")
    except Exception as e:
        st.warning(f"Could not load batch data: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — TRIAGE QUEUE
# ═══════════════════════════════════════════════════════════════════════════════

def page_triage():
    st.title("🔍 Triage Queue")
    st.caption("Review AI-generated content. Approved items go live to students.")

    db = get_supabase()

    # ── Controls ──────────────────────────────────────────────────────────────
    col_type, col_refresh, col_bulk = st.columns([2, 1, 2])
    with col_type:
        data_type = st.radio("Content type", ["pyq", "material"], horizontal=True,
                             format_func=lambda x: "📝 MCQs" if x == "pyq" else "📚 Study Notes")
    with col_refresh:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
            st.rerun()

    # ── Fetch pending items ───────────────────────────────────────────────────
    try:
        rows = (
            db.table("ingestion_triage_queue")
            .select("*")
            .eq("status", "pending")
            .eq("payload_type", data_type)
            .order("created_at", desc=True)
            .limit(30)
            .execute()
        ).data or []
    except Exception as e:
        st.error(f"Failed to fetch queue: {e}")
        return

    if not rows:
        st.success("✅ Inbox zero — no pending items for this content type.")
        return

    st.markdown(f"**{len(rows)} items** awaiting review")

    # ── Bulk Approve ──────────────────────────────────────────────────────────
    with col_bulk:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(f"✅ Approve All {len(rows)}", type="primary"):
            _bulk_approve(db, rows, data_type)
            st.rerun()

    st.markdown("---")

    # ── Item Cards ────────────────────────────────────────────────────────────
    for row in rows:
        raw = row.get("raw_data") or {}
        accuracy = _norm_score(row.get("ai_accuracy_score"))
        flags    = row.get("validation_flags") or []
        segment  = row.get("segment", "")
        batch_id = row.get("batch_id", "")

        # Card container
        with st.container(border=True):
            # Header row
            h1, h2, h3 = st.columns([3, 1, 2])
            with h1:
                if data_type == "pyq":
                    st.markdown(f"**{raw.get('question', '—')}**")
                else:
                    st.markdown(f"**📚 {raw.get('topic_title', '—')}**")
            with h2:
                score_color = "🟢" if accuracy >= 70 else "🟡" if accuracy >= 50 else "🔴"
                st.markdown(f"{score_color} **{accuracy:.0f}%**")
            with h3:
                st.caption(f"`{segment}` · `{batch_id[-12:]}`")
                if flags:
                    st.caption(f"⚠️ {', '.join(flags)}")

            # Content
            if data_type == "pyq":
                _render_mcq(raw)
            else:
                _render_note(raw)

            # Action buttons
            a1, a2, _ = st.columns([1, 1, 4])
            with a1:
                if st.button("✅ Approve", key=f"approve_{row['id']}"):
                    _approve_item(db, row, data_type)
                    st.rerun()
            with a2:
                if st.button("❌ Reject", key=f"reject_{row['id']}"):
                    _reject_item(db, row["id"])
                    st.rerun()


def _render_mcq(raw: dict):
    options = raw.get("options") or {}
    correct = raw.get("correct", "")

    cols = st.columns(2)
    with cols[0]:
        for key in ["A", "B", "C", "D"]:
            val = options.get(key, "—")
            if key == correct:
                st.success(f"**{key}:** {val}  ✓")
            else:
                st.markdown(f"**{key}:** {val}")

    with cols[1]:
        reasoning = raw.get("reasoning_process", "")
        explanation = raw.get("explanation", "")
        if reasoning:
            with st.expander("🧠 Reasoning Process"):
                st.write(reasoning)
        if explanation:
            st.info(f"💡 **Explanation:** {explanation}")

        meta_cols = st.columns(3)
        meta_cols[0].caption(f"🎯 {raw.get('difficulty','—')}")
        meta_cols[1].caption(f"🌱 {raw.get('bloom_level','—')}")
        meta_cols[2].caption(f"🏷 {raw.get('topic_tag','—')}")


def _render_note(raw: dict):
    st.write(raw.get("summary", ""))

    c1, c2 = st.columns(2)
    with c1:
        concepts = raw.get("key_concepts") or []
        if concepts:
            st.markdown("**Key Concepts**")
            for c in concepts:
                st.markdown(f"- {c}")
    with c2:
        facts = raw.get("important_facts") or []
        if facts:
            st.markdown("**Important Facts**")
            for f in facts:
                st.markdown(f"- {f}")

    formulas = raw.get("formulas") or []
    if formulas:
        with st.expander("📐 Formulas"):
            for f in formulas:
                st.code(f)

    hooks = raw.get("memory_hooks") or []
    if hooks:
        with st.expander("🧲 Memory Hooks"):
            for h in hooks:
                st.markdown(f"💡 {h}")


def _approve_item(db: Client, row: dict, data_type: str):
    """Move a triage item to pyq_bank_v2 or study_materials."""
    raw     = row.get("raw_data") or {}
    segment = row.get("segment", "school")
    region  = "global" if segment == "it" else "wb"

    target_table = "pyq_bank_v2" if data_type == "pyq" else "study_materials"
    insert_row = {
        "hierarchy_node_id": "",
        "region_id":         region,
        "subject_or_topic":  (
            raw.get("subject") or raw.get("topic_tag") or
            raw.get("topic_title") or raw.get("taxonomy_label") or segment
        ),
        "question_payload":  raw if data_type == "pyq"      else None,
        "data_payload":      raw if data_type == "material"  else None,
        "probability_score": _norm_score(row.get("ai_accuracy_score")) or 70.0,
        "ai_accuracy_score": _norm_score(row.get("ai_accuracy_score")) or 70.0,
        "validation_flags":  row.get("validation_flags") or [],
        "verified_by_human": True,
    }

    try:
        db.table(target_table).insert(insert_row).execute()
        db.table("ingestion_triage_queue").update({"status": "approved"}).eq("id", row["id"]).execute()
        st.toast("✅ Approved and pushed live!", icon="✅")
    except Exception as e:
        st.error(f"Approve failed: {e}")


def _reject_item(db: Client, item_id: str):
    try:
        db.table("ingestion_triage_queue").update({"status": "rejected"}).eq("id", item_id).execute()
        st.toast("❌ Item rejected.", icon="❌")
    except Exception as e:
        st.error(f"Reject failed: {e}")


def _bulk_approve(db: Client, rows: list, data_type: str):
    success, fail = 0, 0
    for row in rows:
        try:
            _approve_item(db, row, data_type)
            success += 1
        except Exception:
            fail += 1
    st.toast(f"Bulk approved {success} items. {fail} failed.", icon="✅")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — PIPELINE CONTROL
# ═══════════════════════════════════════════════════════════════════════════════

def page_pipeline():
    st.title("🚀 Pipeline Control")
    st.caption("Trigger the সর্বজ্ঞ → চিত্রগুপ্ত → সূত্রধর pipeline via GitHub Actions.")

    segment = st.radio("Segment", ["school", "competitive", "it"], horizontal=True,
                       format_func=lambda x: {"school": "🏫 School", "competitive": "🏆 Competitive", "it": "💻 IT / Cloud"}[x])

    st.markdown("---")

    with st.form("pipeline_form"):
        count = st.slider("MCQ count", 3, 20, 5)

        if segment == "school":
            c1, c2 = st.columns(2)
            board     = c1.selectbox("Board", ["WBBSE", "WBCHSE", "CBSE", "ICSE"])
            class_num = c2.selectbox("Class", list(range(6, 13)))
            subject   = st.text_input("Subject", placeholder="Physical Science")
            chapter   = st.text_input("Chapter (optional)", placeholder="Electricity")
            source_url = st.text_input("Source URL (optional)")
            inputs = {
                "board": board, "class_num": str(class_num),
                "subject": subject, "chapter": chapter,
                "count": str(count), "source_url": source_url,
            }
            workflow = "ingest_school.yml"
            valid = bool(subject)

        elif segment == "competitive":
            authority  = st.text_input("Authority", placeholder="WBPSC")
            exam       = st.text_input("Exam", placeholder="WBCS Prelims")
            topic      = st.text_input("Topic", placeholder="History of India")
            source_url = st.text_input("Source URL (optional)")
            inputs = {
                "authority": authority, "exam": exam,
                "topic": topic, "count": str(count), "source_url": source_url,
            }
            workflow = "ingest_competitive.yml"
            valid = bool(authority and exam and topic)

        else:  # it
            provider   = st.text_input("Provider", placeholder="AWS")
            exam       = st.text_input("Exam / Cert", placeholder="Cloud Practitioner (CLF-C02)")
            topic      = st.text_input("Topic", placeholder="Security & Compliance")
            source_url = st.text_input("Source URL (optional)")
            inputs = {
                "provider": provider, "exam": exam,
                "topic": topic, "count": str(count), "source_url": source_url,
            }
            workflow = "ingest_it.yml"
            valid = bool(provider and exam and topic)

        # ── Dedup memory override ─────────────────────────────────────────────
        st.markdown("---")
        force = st.checkbox(
            "⚡ Force regenerate (skip dedup memory check)",
            value=False,
            help="By default, the pipeline skips topics that already have enough MCQs. "
                 "Check this to regenerate even if content exists — useful after a bad batch.",
        )
        if force:
            inputs["force"] = "true"

        submitted = st.form_submit_button("🚀 Run Pipeline", type="primary", disabled=not valid)

    if submitted:
        if not valid:
            st.warning("Please fill in all required fields.")
        else:
            _dispatch_workflow(workflow, inputs)

    # ── Recent workflow runs ──────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Recent runs")
    st.caption("Check GitHub Actions for live run status →")
    repo = st.secrets.get("GITHUB_REPO", "arkagimt/gyan-ai-pipeline")
    st.markdown(f"[📋 View all runs on GitHub](https://github.com/{repo}/actions)")


def _dispatch_workflow(workflow: str, inputs: dict):
    pat  = st.secrets.get("GITHUB_PAT", "")
    repo = st.secrets.get("GITHUB_REPO", "arkagimt/gyan-ai-pipeline")

    if not pat:
        st.error("GITHUB_PAT not set in Streamlit secrets.")
        return

    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"ref": "main", "inputs": {k: v for k, v in inputs.items() if v}},
        timeout=15,
    )

    if resp.status_code == 204:
        st.success(f"✅ Pipeline dispatched! Workflow: `{workflow}`")
        st.info(f"[🔗 Watch it run →](https://github.com/{repo}/actions/workflows/{workflow})")
    else:
        st.error(f"GitHub API error {resp.status_code}: {resp.text[:300]}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — AGENT PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

def page_prompts():
    st.title("🤖 Agent Prompts")
    st.caption("View and edit the system prompts stored in Supabase (Vault Pattern). Changes take effect on next pipeline run.")

    db = get_supabase()

    try:
        rows = db.table("agent_prompts").select("*").order("agent_id").execute().data or []
    except Exception as e:
        st.error(f"Could not load agent prompts: {e}")
        return

    if not rows:
        st.warning("No agent prompts found in Supabase. Run `scripts/setup.sql` first.")
        return

    agent_ids = [r["agent_id"] for r in rows]
    selected  = st.selectbox("Select agent", agent_ids,
                             format_func=lambda x: {
                                 "sarbagya":    "সর্বজ্ঞ — Scout / Extractor",
                                 "chitragupta": "চিত্রগুপ্ত — Validator",
                                 "sutradhar":   "সূত্রধর — Content Creator",
                             }.get(x, x))

    row = next((r for r in rows if r["agent_id"] == selected), None)
    if not row:
        return

    st.markdown("---")
    col_meta, col_controls = st.columns([3, 1])

    with col_meta:
        st.markdown(
            f"**Role:** {row.get('role','—')}  \n"
            f"**Temp:** `{row.get('temperature','—')}` &nbsp;|&nbsp; "
            f"**Max tokens:** `{row.get('max_tokens','—')}`"
        )

    with col_controls:
        edit_mode = st.toggle("✏️ Edit mode")

    if edit_mode:
        new_prompt = st.text_area(
            "System Prompt",
            value=row.get("system_prompt", ""),
            height=400,
            help="This is the exact system prompt the agent receives at runtime.",
        )
        new_temp   = st.number_input("Temperature", 0.0, 2.0, float(row.get("temperature", 0.3)), step=0.05)
        new_tokens = st.number_input("Max Tokens", 256, 8192, int(row.get("max_tokens", 4096)), step=256)

        if st.button("💾 Save to Supabase", type="primary"):
            try:
                db.table("agent_prompts").update({
                    "system_prompt": new_prompt,
                    "temperature":   new_temp,
                    "max_tokens":    new_tokens,
                }).eq("agent_id", selected).execute()
                st.success(f"✅ `{selected}` prompt updated. Next pipeline run will use this.")
                st.rerun()
            except Exception as e:
                st.error(f"Save failed: {e}")
    else:
        st.text_area(
            "System Prompt (read-only)",
            value=row.get("system_prompt", ""),
            height=400,
            disabled=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

if page == "📊 Dashboard":
    page_dashboard()
elif page == "🔍 Triage Queue":
    page_triage()
elif page == "🚀 Pipeline Control":
    page_pipeline()
elif page == "🤖 Agent Prompts":
    page_prompts()
