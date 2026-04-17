"""
Gyan AI — Admin Command Centre v2
===================================
5-page Streamlit dashboard for the Gyan AI data pipeline.

Pages:
  📊 Command Centre  — metrics, curriculum completion %, top recommendations
  🗺️ Coverage Map    — board × class × subject heatmap, click-to-run pipeline
  🔍 Triage Queue    — approve / reject MCQs + study notes (approval FK bug FIXED)
  🚀 Smart Pipeline  — curriculum-aware trigger with coverage preview
  🤖 Agent Prompts   — view / edit agent system prompts (Supabase Vault)

Secrets required (Streamlit Cloud → App settings → Secrets):
  SUPABASE_URL         = "https://xxx.supabase.co"
  SUPABASE_SERVICE_KEY = "eyJ..."
  GITHUB_PAT           = "github_pat_..."
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

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Gyan AI — Command Centre",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stSidebar"] { background: #1a1a2e; min-width: 210px; }
  [data-testid="stSidebar"] * { color: #e0e0e0 !important; }
  .block-container {
    padding-top: 1.2rem;
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 1240px;
  }
  div[data-testid="metric-container"] {
    background: white;
    border: 1px solid #e8e8e8;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }
  div[data-testid="metric-container"] label { font-size: 0.7rem !important; }
  h1 { font-size: 1.6rem !important; }
  h2 { font-size: 1.2rem !important; }
  .stRadio > div { gap: 0.5rem; }
  .rec-card { background: #f0fdf4; border-left: 3px solid #16a34a;
              padding: 0.5rem 0.75rem; border-radius: 6px; margin-bottom: 4px; }
  .rec-card-empty { background: #fff7ed; border-left: 3px solid #f59e0b;
                    padding: 0.5rem 0.75rem; border-radius: 6px; margin-bottom: 4px; }
</style>
""", unsafe_allow_html=True)

# ── Session state defaults ────────────────────────────────────────────────────
st.session_state.setdefault("prefill", None)
st.session_state.setdefault("page", "📊 Command Centre")

# ═══════════════════════════════════════════════════════════════════════════════
# CURRICULUM DATA
# ═══════════════════════════════════════════════════════════════════════════════

CURRICULUM: dict[str, dict[int, list[str]]] = {
    "WBBSE": {
        1:  ["Bengali", "English", "Mathematics"],
        2:  ["Bengali", "English", "Mathematics"],
        3:  ["Bengali", "English", "Mathematics", "Paribesh O Parichiti"],
        4:  ["Bengali", "English", "Mathematics", "Paribesh O Parichiti"],
        5:  ["Bengali", "English", "Mathematics", "Paribesh O Parichiti"],
        6:  ["Bengali", "English", "Mathematics", "History", "Geography", "Life Science"],
        7:  ["Bengali", "English", "Mathematics", "History", "Geography", "Life Science"],
        8:  ["Bengali", "English", "Mathematics", "History", "Geography",
             "Life Science", "Physical Science"],
        9:  ["Bengali", "English", "Mathematics", "History", "Geography",
             "Life Science", "Physical Science"],
        10: ["Bengali", "English", "Mathematics", "History", "Geography",
             "Life Science", "Physical Science"],
    },
    "WBCHSE": {
        11: ["Bengali", "English", "Mathematics", "Physics", "Chemistry",
             "Biology", "History", "Geography", "Economics",
             "Accountancy", "Business Studies"],
        12: ["Bengali", "English", "Mathematics", "Physics", "Chemistry",
             "Biology", "History", "Geography", "Economics",
             "Accountancy", "Business Studies"],
    },
    "CBSE": {
        1:  ["English", "Hindi", "Mathematics", "Environmental Studies"],
        2:  ["English", "Hindi", "Mathematics", "Environmental Studies"],
        3:  ["English", "Hindi", "Mathematics", "Environmental Studies"],
        4:  ["English", "Hindi", "Mathematics", "Environmental Studies"],
        5:  ["English", "Hindi", "Mathematics", "Environmental Studies"],
        6:  ["English", "Hindi", "Mathematics", "Science", "Social Science"],
        7:  ["English", "Hindi", "Mathematics", "Science", "Social Science"],
        8:  ["English", "Hindi", "Mathematics", "Science", "Social Science"],
        9:  ["English", "Hindi", "Mathematics", "Science", "Social Science"],
        10: ["English", "Hindi", "Mathematics", "Science", "Social Science"],
        11: ["Physics", "Chemistry", "Mathematics", "Biology", "English",
             "Economics", "Accountancy", "Business Studies"],
        12: ["Physics", "Chemistry", "Mathematics", "Biology", "English",
             "Economics", "Accountancy", "Business Studies"],
    },
    "ICSE": {
        1:  ["English", "Mathematics", "Environmental Education"],
        2:  ["English", "Mathematics", "Environmental Education"],
        3:  ["English", "Mathematics", "Environmental Education"],
        4:  ["English", "Mathematics", "Environmental Education"],
        5:  ["English", "Mathematics", "Environmental Education"],
        6:  ["English", "Mathematics", "Science", "Social Studies"],
        7:  ["English", "Mathematics", "Science", "Social Studies"],
        8:  ["English", "Mathematics", "Science", "History & Civics", "Geography"],
        9:  ["English", "Mathematics", "Physics", "Chemistry", "Biology",
             "History & Civics", "Geography"],
        10: ["English", "Mathematics", "Physics", "Chemistry", "Biology",
             "History & Civics", "Geography"],
    },
}

# Higher = more important to fill first
CLASS_PRIORITY: dict[int, int] = {
    10: 10, 12: 9, 9: 8, 11: 7, 8: 6, 7: 5, 6: 4, 5: 3, 4: 2, 3: 2, 2: 1, 1: 1,
}

COMPETITIVE_TREE: dict[str, dict[str, list[str]]] = {
    "WBPSC": {
        "WBCS Prelims": [
            "Indian History — Ancient & Medieval",
            "Indian History — Modern & Independence Movement",
            "West Bengal — History & Culture",
            "Indian & WB Geography",
            "Indian Constitution & Polity",
            "Indian Economy & Planning",
            "General Science — Physics",
            "General Science — Chemistry",
            "General Science — Biology",
            "Environment & Ecology",
            "Current Affairs & General Knowledge",
            "Mathematics — Arithmetic & Reasoning",
        ],
        "WBCS Mains": [
            "General Studies Paper I — History",
            "General Studies Paper I — Geography",
            "General Studies Paper II — Polity & Governance",
            "General Studies Paper II — Economy",
            "English Essay & Comprehension",
            "Bengali Language & Literature",
        ],
        "Miscellaneous Services": [
            "General Knowledge & Current Affairs",
            "English Grammar",
            "Bengali Grammar",
            "Arithmetic & Numerical Ability",
            "General Science",
        ],
    },
    "SSC": {
        "CGL (Tier 1)": [
            "Quantitative Aptitude — Algebra",
            "Quantitative Aptitude — Geometry",
            "Quantitative Aptitude — Arithmetic",
            "English — Comprehension & Grammar",
            "General Intelligence & Reasoning",
            "General Awareness — History",
            "General Awareness — Geography",
            "General Awareness — Polity",
            "General Awareness — Economy",
            "General Awareness — Science",
        ],
        "CHSL": [
            "Quantitative Aptitude — Basic Maths",
            "English — Grammar & Vocabulary",
            "General Intelligence & Reasoning",
            "General Awareness",
        ],
        "MTS": [
            "Numerical Aptitude — Basic",
            "General English",
            "General Awareness — Basic",
            "Reasoning — Non-Verbal",
        ],
    },
    "UPSC": {
        "Prelims (GS Paper 1)": [
            "Ancient & Medieval Indian History",
            "Modern Indian History",
            "Indian & World Geography",
            "Indian Polity & Constitution",
            "Indian Economy",
            "Environment & Ecology",
            "Science & Technology",
            "Current Affairs",
        ],
    },
    "Railway": {
        "NTPC": [
            "Mathematics — Arithmetic",
            "General Intelligence & Reasoning",
            "General Awareness — Static GK",
            "General Awareness — Current Affairs",
            "English Grammar",
        ],
        "Group D": [
            "Mathematics — Basic",
            "General Science — Physics & Chemistry",
            "General Science — Biology",
            "General Awareness",
            "Reasoning — Basic",
        ],
    },
    "WBSSC": {
        "TET (Primary)": [
            "Child Development & Pedagogy",
            "Language I — Bengali",
            "Language II — English",
            "Mathematics — Primary Level",
            "Environmental Studies — Primary",
        ],
        "SLST": [
            "Subject Knowledge — Core",
            "Pedagogy & Teaching Methods",
            "General Studies & Current Affairs",
        ],
    },
}

IT_TREE: dict[str, dict[str, list[str]]] = {
    "AWS": {
        "Cloud Practitioner (CLF-C02)": [
            "Cloud Concepts & Value Proposition",
            "AWS Global Infrastructure",
            "Core Services — EC2 & Compute",
            "Core Services — S3 & Storage",
            "Core Services — RDS & Databases",
            "Core Services — VPC & Networking",
            "Security — IAM & Shared Responsibility",
            "Security — AWS Security Services",
            "Cloud Economics & Pricing",
            "AWS Billing & Cost Management",
        ],
        "Solutions Architect Associate (SAA-C03)": [
            "Resilient Architectures",
            "High-Performance Architectures",
            "Secure Architectures",
            "Cost-Optimized Architectures",
        ],
        "Developer Associate (DVA-C02)": [
            "Development with AWS Services",
            "Security in AWS Applications",
            "Deployment & Testing",
            "Refactoring & Monitoring",
        ],
    },
    "Microsoft": {
        "Azure Fundamentals (AZ-900)": [
            "Cloud Concepts",
            "Azure Architecture & Services",
            "Azure Management & Governance",
        ],
        "Azure Administrator (AZ-104)": [
            "Manage Azure Identities & Governance",
            "Implement & Manage Storage",
            "Deploy & Manage Compute Resources",
            "Implement Virtual Networking",
            "Monitor & Backup Azure Resources",
        ],
    },
    "Google": {
        "Cloud Digital Leader": [
            "Digital Transformation with Google Cloud",
            "Innovating with Data & AI",
            "Infrastructure & App Modernisation",
            "Google Cloud Security & Operations",
        ],
        "Associate Cloud Engineer": [
            "Setting up Cloud Environment",
            "Planning & Configuring Cloud Solution",
            "Deploying & Implementing Cloud Solution",
            "Configuring Access & Security",
        ],
    },
    "Cisco": {
        "CCNA (200-301)": [
            "Network Fundamentals",
            "Network Access — VLANs & Trunking",
            "IP Connectivity — Routing Protocols",
            "IP Services — DHCP, DNS, NAT",
            "Security Fundamentals",
            "Automation & Programmability",
        ],
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _norm_score(score) -> float:
    """Backward-compat: old data stored 0.0–1.0, new data 0–100."""
    if score is None:
        return 0.0
    s = float(score)
    return round(s * 100, 1) if s <= 1.0 else round(s, 1)


@st.cache_resource
def get_supabase() -> Client:
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_SERVICE_KEY"],
    )


@st.cache_data(ttl=300)
def fetch_coverage(_cache_key: str) -> dict:
    """
    Returns {(board, class_num, subject): count}.
    Queries triage queue (non-rejected) + pyq_bank_v2.
    _cache_key rotates every 5 min to auto-expire.
    """
    db = get_supabase()
    coverage: dict[tuple, int] = {}

    # 1. Triage queue (pending + approved)
    try:
        rows = (
            db.table("ingestion_triage_queue")
            .select("raw_data")
            .eq("payload_type", "pyq")
            .neq("status", "rejected")
            .execute()
        ).data or []
        for row in rows:
            raw     = row.get("raw_data") or {}
            board   = str(raw.get("board") or "").strip()
            cls     = raw.get("class_num")
            subject = str(raw.get("subject") or "").strip()
            if board and cls is not None and subject:
                key = (board, int(cls), subject)
                coverage[key] = coverage.get(key, 0) + 1
    except Exception:
        pass

    # 2. Live approved content
    try:
        rows = (
            db.table("pyq_bank_v2")
            .select("question_payload")
            .execute()
        ).data or []
        for row in rows:
            payload = row.get("question_payload") or {}
            board   = str(payload.get("board") or "").strip()
            cls     = payload.get("class_num")
            subject = str(payload.get("subject") or "").strip()
            if board and cls is not None and subject:
                key = (board, int(cls), subject)
                coverage[key] = coverage.get(key, 0) + 1
    except Exception:
        pass

    return coverage


def _cache_key() -> str:
    """Rotates every 5 minutes — forces fetch_coverage to refresh."""
    now = datetime.now()
    return f"{now.date()}-{now.hour}-{now.minute // 5}"


def get_recommendations(coverage: dict, limit: int = 10) -> list[dict]:
    """Top-N school curriculum nodes with fewest MCQs, ranked by class priority."""
    recs = []
    for board, classes in CURRICULUM.items():
        for class_num, subjects in classes.items():
            priority = CLASS_PRIORITY.get(class_num, 1)
            for subject in subjects:
                count = coverage.get((board, class_num, subject), 0)
                recs.append({
                    "board":     board,
                    "class_num": class_num,
                    "subject":   subject,
                    "count":     count,
                    "priority":  priority,
                    "label":     f"{board} · Class {class_num} · {subject}",
                })
    # 0 MCQ nodes first, then lowest count, then highest class priority
    recs.sort(key=lambda x: (x["count"] > 0, -x["priority"], x["count"]))
    return recs[:limit]


def _dispatch_workflow(workflow: str, inputs: dict):
    pat  = st.secrets.get("GITHUB_PAT", "")
    repo = st.secrets.get("GITHUB_REPO", "arkagimt/gyan-ai-pipeline")
    if not pat:
        st.error("GITHUB_PAT not set in Streamlit secrets.")
        return
    url = (
        f"https://api.github.com/repos/{repo}"
        f"/actions/workflows/{workflow}/dispatches"
    )
    resp = requests.post(
        url,
        headers={
            "Authorization":        f"Bearer {pat}",
            "Accept":               "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"ref": "main", "inputs": {k: v for k, v in inputs.items() if v}},
        timeout=15,
    )
    repo_url = f"https://github.com/{repo}"
    if resp.status_code == 204:
        st.success(
            f"✅ Pipeline dispatched!  "
            f"[🔗 Watch on GitHub]({repo_url}/actions/workflows/{workflow})"
        )
    else:
        st.error(f"GitHub API error {resp.status_code}: {resp.text[:300]}")


def _coverage_badge(count: int) -> str:
    if count == 0:   return "🔴 0"
    if count < 5:    return f"🟡 {count}"
    if count < 10:   return f"🟢 {count}"
    return f"✅ {count}"


# ═══════════════════════════════════════════════════════════════════════════════
# SANJAYA MILESTONE TRACKER
# ═══════════════════════════════════════════════════════════════════════════════

_SANJAYA_MILESTONES = [
    (100,  "🎯 100 MCQs",   "Pilot cohort ready. Track first student completions."),
    (500,  "🚀 DSPy Time",  "SC-001: Implement DSPy optimizer. See SANJAYA_CHRONICLES.md."),
    (1000, "🔍 pgvector",   "SC-002: Enable semantic search for অন্বেষক."),
    (2500, "🤖 PydanticAI", "SC-003: Build বেতাল + নারদ student-facing agents."),
    (5000, "🌟 Full WB",    "Full West Bengal curriculum coverage approaching."),
]


def _render_sanjaya_milestone(live_mcq_count: int) -> None:
    if live_mcq_count >= 500:
        st.success(
            "🚀 **[SANJAYA — SC-001 TRIGGERED]** You have **500+ live MCQs!**  \n"
            "**Action**: Implement the **DSPy optimizer** to auto-tune agent prompts.  \n"
            "See `SANJAYA_CHRONICLES.md → Entry SC-001` for the full plan.",
            icon="🧠",
        )

    crossed, next_milestone = [], None
    for threshold, label, action in _SANJAYA_MILESTONES:
        if live_mcq_count >= threshold:
            crossed.append((threshold, label, action))
        elif next_milestone is None:
            next_milestone = (threshold, label, action)

    if next_milestone:
        threshold, label, action = next_milestone
        prev = crossed[-1][0] if crossed else 0
        pct  = min((live_mcq_count - prev) / max(threshold - prev, 1), 1.0)
        cols = st.columns([4, 1])
        with cols[0]:
            st.caption(
                f"**Sanjaya** · Next milestone: **{label}** at {threshold} MCQs"
                f" — {action}"
            )
            st.progress(pct)
        with cols[1]:
            st.caption(f"{live_mcq_count} / {threshold}  \n({threshold - live_mcq_count} to go)")
    elif crossed:
        st.success("🏆 **All Sanjaya milestones reached!** Gyan AI is fully battle-tested.")


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

st.sidebar.markdown("## 🧠 Gyan AI")
st.sidebar.markdown("**Admin Command Centre**")
st.sidebar.markdown("---")

PAGES = [
    "📊 Command Centre",
    "🗺️ Coverage Map",
    "🔍 Triage Queue",
    "🚀 Smart Pipeline",
    "📚 Textbooks",
    "🤖 Agent Prompts",
]

# Support programmatic navigation via session_state["page"]
if st.session_state["page"] not in PAGES:
    st.session_state["page"] = PAGES[0]

page = st.sidebar.radio(
    "Navigate",
    PAGES,
    index=PAGES.index(st.session_state["page"]),
    label_visibility="collapsed",
)
st.session_state["page"] = page

st.sidebar.markdown("---")
st.sidebar.caption(f"📅 {datetime.now().strftime('%d %b %Y')}")
st.sidebar.caption("⚡ Pipeline: Public Repo · Streamlit: Free Tier")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — COMMAND CENTRE
# ═══════════════════════════════════════════════════════════════════════════════

def page_command_centre():
    st.title("📊 Command Centre")
    st.caption("Big picture — live metrics, curriculum completion, and what to run next.")

    db       = get_supabase()
    coverage = fetch_coverage(_cache_key())

    # ── Fetch counts ──────────────────────────────────────────────────────────
    with st.spinner("Loading metrics..."):
        try:
            pyq_count      = db.table("pyq_bank_v2").select("*", count="exact", head=True).execute().count or 0
            mat_count      = db.table("study_materials").select("*", count="exact", head=True).execute().count or 0
            pending_count  = (db.table("ingestion_triage_queue").select("*", count="exact", head=True)
                               .eq("status", "pending").execute().count or 0)
            approved_count = (db.table("ingestion_triage_queue").select("*", count="exact", head=True)
                               .eq("status", "approved").execute().count or 0)
            rejected_count = (db.table("ingestion_triage_queue").select("*", count="exact", head=True)
                               .eq("status", "rejected").execute().count or 0)
        except Exception as e:
            st.error(f"Supabase connection failed: {e}")
            return

    # ── Metric cards ──────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Live MCQs",       pyq_count,      help="Approved in pyq_bank_v2")
    c2.metric("Study Notes",     mat_count,       help="Approved in study_materials")
    c3.metric("Pending Review",  pending_count,   help="Awaiting human review")
    c4.metric("Total Approved",  approved_count)
    c5.metric("Total Rejected",  rejected_count)

    if pending_count > 0:
        st.warning(
            f"⚠️ **{pending_count} items** waiting in Triage Queue. "
            f"Go to **🔍 Triage Queue** to review.",
            icon="📬",
        )

    # ── Sanjaya milestone ─────────────────────────────────────────────────────
    _render_sanjaya_milestone(pyq_count)

    st.markdown("---")

    # ── Curriculum completion + Recommendations ───────────────────────────────
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("📚 Curriculum Completion")
        st.caption("% of nodes with ≥ 5 MCQs per board")

        for board, classes in CURRICULUM.items():
            total, covered = 0, 0
            for class_num, subjects in classes.items():
                for subject in subjects:
                    total  += 1
                    count   = coverage.get((board, class_num, subject), 0)
                    covered += (1 if count >= 5 else 0)
            pct = (covered / total) if total else 0
            col_b, col_p = st.columns([1, 3])
            col_b.caption(f"**{board}**")
            col_p.progress(pct, text=f"{covered}/{total} nodes  ({pct:.0%})")

    with col_right:
        st.subheader("🎯 Top Recommendations")
        st.caption("Highest-priority nodes with fewest MCQs")

        recs = get_recommendations(coverage, limit=8)
        for rec in recs:
            count = rec["count"]
            icon  = "🔴" if count == 0 else "🟡"
            cols  = st.columns([5, 2])
            with cols[0]:
                st.markdown(f"{icon} **{rec['label']}**  \n`{count} MCQs`")
            with cols[1]:
                if st.button("▶ Run", key=f"rec_{rec['board']}_{rec['class_num']}_{rec['subject']}"):
                    st.session_state["prefill"] = {
                        "board":     rec["board"],
                        "class_num": rec["class_num"],
                        "subject":   rec["subject"],
                    }
                    st.session_state["page"] = "🚀 Smart Pipeline"
                    st.rerun()

    st.markdown("---")

    # ── Charts ────────────────────────────────────────────────────────────────
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.subheader("Triage Queue Status")
        total_triage = pending_count + approved_count + rejected_count
        if total_triage > 0:
            fig = px.pie(
                names=["Pending", "Approved", "Rejected"],
                values=[pending_count, approved_count, rejected_count],
                color_discrete_map={"Pending": "#f59e0b", "Approved": "#10b981", "Rejected": "#ef4444"},
                hole=0.5,
            )
            fig.update_traces(textposition="outside", textinfo="percent+label")
            fig.update_layout(showlegend=False, margin=dict(t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No triage data yet. Run the pipeline first.")

    with col_chart2:
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
                df["ai_accuracy_score"] = df["ai_accuracy_score"].apply(
                    lambda s: float(s) * 100 if s is not None and float(s) <= 1.0
                    else (float(s) if s is not None else 0.0)
                )
                fig2 = px.histogram(
                    df, x="ai_accuracy_score", color="payload_type", nbins=20,
                    labels={"ai_accuracy_score": "Accuracy %", "payload_type": "Type"},
                    color_discrete_map={"pyq": "#6366f1", "material": "#10b981"},
                    barmode="overlay",
                )
                fig2.update_layout(margin=dict(t=20, b=20))
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No accuracy data yet.")
        except Exception as e:
            st.warning(f"Could not load accuracy chart: {e}")

    # ── Recent batches ────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Recent Pipeline Batches")
    try:
        recent = (
            db.table("ingestion_triage_queue")
            .select("batch_id, segment, payload_type, status, created_at")
            .order("created_at", desc=True)
            .limit(60)
            .execute()
        ).data or []

        if recent:
            df_r = pd.DataFrame(recent)
            summary = (
                df_r.groupby(["batch_id", "segment", "status"])
                .size()
                .reset_index(name="count")
                .sort_values("batch_id", ascending=False)
            )
            st.dataframe(summary, use_container_width=True, hide_index=True)
        else:
            st.info("No batches yet.")
    except Exception as e:
        st.warning(f"Could not load batch data: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — COVERAGE MAP
# ═══════════════════════════════════════════════════════════════════════════════

def page_coverage_map():
    st.title("🗺️ Coverage Map")
    st.caption("Visual heatmap of MCQ coverage across the curriculum. Red = empty, green = well-covered.")

    coverage = fetch_coverage(_cache_key())

    col_board, col_refresh = st.columns([3, 1])
    with col_board:
        board = st.radio(
            "Board", list(CURRICULUM.keys()), horizontal=True,
        )
    with col_refresh:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh data"):
            st.cache_data.clear()
            st.rerun()

    classes  = sorted(CURRICULUM[board].keys())
    # All subjects that appear in this board across any class
    all_subjects = sorted({s for cls in CURRICULUM[board].values() for s in cls})

    # Build matrix: rows=classes, cols=subjects
    # Value: -1 = not in curriculum, 0 = in curriculum but 0 MCQs, N = N MCQs
    z_matrix, hover_matrix = [], []
    y_labels = [f"Class {c}" for c in classes]

    for c in classes:
        row_z, row_h = [], []
        curriculum_subjects = CURRICULUM[board][c]
        for s in all_subjects:
            if s not in curriculum_subjects:
                row_z.append(-1)
                row_h.append(f"Class {c} | {s}<br>Not in curriculum")
            else:
                count = coverage.get((board, c, s), 0)
                row_z.append(count)
                status = ("🔴 Empty" if count == 0
                          else "🟡 Low" if count < 5
                          else "🟢 Good" if count < 10
                          else "✅ Great")
                row_h.append(f"Class {c} | {s}<br>{count} MCQs — {status}")
        z_matrix.append(row_z)
        hover_matrix.append(row_h)

    # Custom colorscale: grey=-1, red=0, orange=1-4, light-green=5-9, dark-green=10+
    # We cap display at 15 for colour range
    colorscale = [
        [0.000, "#f1f5f9"],  # -1 → light grey (not in curriculum)
        [0.001, "#ef4444"],  # 0  → red
        [0.25,  "#f97316"],  # ~3  → orange
        [0.45,  "#fbbf24"],  # ~6  → yellow
        [0.65,  "#86efac"],  # ~9  → light green
        [1.000, "#15803d"],  # 15+ → dark green
    ]

    fig = go.Figure(go.Heatmap(
        z=z_matrix,
        x=all_subjects,
        y=y_labels,
        text=hover_matrix,
        hovertemplate="%{text}<extra></extra>",
        colorscale=colorscale,
        zmin=-1,
        zmax=15,
        showscale=True,
        colorbar=dict(
            title="MCQs",
            tickvals=[-1, 0, 5, 10, 15],
            ticktext=["N/A", "0", "5", "10", "15+"],
            thickness=12,
        ),
    ))
    fig.update_layout(
        title=f"{board} Curriculum Coverage",
        xaxis=dict(tickangle=-35, tickfont=dict(size=11)),
        yaxis=dict(tickfont=dict(size=11)),
        height=max(350, len(classes) * 42 + 120),
        margin=dict(t=50, b=10, l=10, r=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Gap analysis below heatmap ────────────────────────────────────────────
    empty_nodes, low_nodes = [], []
    for c in classes:
        for s in CURRICULUM[board][c]:
            count = coverage.get((board, c, s), 0)
            node  = {"board": board, "class_num": c, "subject": s, "count": count}
            if count == 0:
                empty_nodes.append(node)
            elif count < 5:
                low_nodes.append(node)

    # Sort by priority
    for lst in (empty_nodes, low_nodes):
        lst.sort(key=lambda x: -CLASS_PRIORITY.get(x["class_num"], 1))

    col_empty, col_low = st.columns(2)

    with col_empty:
        st.subheader(f"🔴 Empty Nodes ({len(empty_nodes)})")
        st.caption("0 MCQs — highest priority to fill")
        if not empty_nodes:
            st.success("No empty nodes! Great coverage.")
        else:
            for node in empty_nodes[:20]:
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"Class **{node['class_num']}** · {node['subject']}")
                with c2:
                    if st.button("▶ Run",
                                 key=f"empty_{board}_{node['class_num']}_{node['subject']}"):
                        st.session_state["prefill"] = {
                            "board":     board,
                            "class_num": node["class_num"],
                            "subject":   node["subject"],
                        }
                        st.session_state["page"] = "🚀 Smart Pipeline"
                        st.rerun()
            if len(empty_nodes) > 20:
                st.caption(f"… and {len(empty_nodes) - 20} more")

    with col_low:
        st.subheader(f"🟡 Low Coverage ({len(low_nodes)})")
        st.caption("1–4 MCQs — needs top-up")
        if not low_nodes:
            st.success("All started nodes have ≥ 5 MCQs!")
        else:
            for node in low_nodes[:20]:
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"Class **{node['class_num']}** · {node['subject']} `({node['count']})`")
                with c2:
                    if st.button("▶ Top-up",
                                 key=f"low_{board}_{node['class_num']}_{node['subject']}"):
                        st.session_state["prefill"] = {
                            "board":     board,
                            "class_num": node["class_num"],
                            "subject":   node["subject"],
                        }
                        st.session_state["page"] = "🚀 Smart Pipeline"
                        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — TRIAGE QUEUE
# ═══════════════════════════════════════════════════════════════════════════════

def page_triage():
    st.title("🔍 Triage Queue")
    st.caption("Review AI-generated content. Approved items go live to students.")

    db = get_supabase()

    col_type, col_refresh, col_bulk = st.columns([2, 1, 2])
    with col_type:
        data_type = st.radio(
            "Content type", ["pyq", "material"], horizontal=True,
            format_func=lambda x: "📝 MCQs" if x == "pyq" else "📚 Study Notes",
        )
    with col_refresh:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
            st.rerun()

    # Fetch pending
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

    with col_bulk:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(f"✅ Approve All {len(rows)}", type="primary"):
            _bulk_approve(db, rows, data_type)
            st.cache_data.clear()
            st.rerun()

    st.markdown("---")

    for row in rows:
        raw      = row.get("raw_data") or {}
        accuracy = _norm_score(row.get("ai_accuracy_score"))
        flags    = row.get("validation_flags") or []
        segment  = row.get("segment", "")
        batch_id = row.get("batch_id", "")
        taxonomy = raw.get("taxonomy_label", "—")

        with st.container(border=True):
            h1, h2, h3 = st.columns([3, 1, 2])
            with h1:
                if data_type == "pyq":
                    st.markdown(f"**{raw.get('question', '—')}**")
                else:
                    st.markdown(f"**📚 {raw.get('topic_title', '—')}**")
                st.caption(f"📌 {taxonomy}")
            with h2:
                score_color = "🟢" if accuracy >= 70 else "🟡" if accuracy >= 50 else "🔴"
                st.markdown(f"{score_color} **{accuracy:.0f}%**")
            with h3:
                st.caption(f"`{segment}` · `{batch_id[-12:]}`")
                if flags:
                    st.caption(f"⚠️ {', '.join(str(f) for f in flags)}")

            if data_type == "pyq":
                _render_mcq(raw)
            else:
                _render_note(raw)

            a1, a2, _ = st.columns([1, 1, 4])
            with a1:
                if st.button("✅ Approve", key=f"approve_{row['id']}"):
                    _approve_item(db, row, data_type)
                    st.cache_data.clear()
                    st.rerun()
            with a2:
                if st.button("❌ Reject", key=f"reject_{row['id']}"):
                    _reject_item(db, row["id"])
                    st.rerun()


def _render_mcq(raw: dict):
    options = raw.get("options") or {}
    correct = raw.get("correct", "")
    cols    = st.columns(2)

    with cols[0]:
        for key in ["A", "B", "C", "D"]:
            val = options.get(key, "—")
            if key == correct:
                st.success(f"**{key}:** {val}  ✓")
            else:
                st.markdown(f"**{key}:** {val}")

    with cols[1]:
        reasoning   = raw.get("reasoning_process", "")
        explanation = raw.get("explanation", "")
        if reasoning:
            with st.expander("🧠 Reasoning Process"):
                st.write(reasoning)
        if explanation:
            st.info(f"💡 **Explanation:** {explanation}")

        mc = st.columns(3)
        mc[0].caption(f"🎯 {raw.get('difficulty', '—')}")
        mc[1].caption(f"🌱 {raw.get('bloom_level', '—')}")
        mc[2].caption(f"🏷 {raw.get('topic_tag', '—')}")


def _render_note(raw: dict):
    st.write(raw.get("summary", ""))
    c1, c2 = st.columns(2)
    with c1:
        for concept in (raw.get("key_concepts") or []):
            st.markdown(f"- {concept}")
    with c2:
        for fact in (raw.get("important_facts") or []):
            st.markdown(f"- {fact}")
    if raw.get("formulas"):
        with st.expander("📐 Formulas"):
            for f in raw["formulas"]:
                st.code(f)
    if raw.get("memory_hooks"):
        with st.expander("🧲 Memory Hooks"):
            for h in raw["memory_hooks"]:
                st.markdown(f"💡 {h}")


def _approve_item(db: Client, row: dict, data_type: str):
    """
    Move triage item to pyq_bank_v2 or study_materials.

    RCA notes — why columns are kept separate:
      pyq_bank_v2    → has question_payload, NOT data_payload
      study_materials → has data_payload, NOT question_payload
    Sending a column name that doesn't exist in the target table causes
    PGRST204 even when the value is None. Build per-table dicts.
    """
    raw     = row.get("raw_data") or {}
    segment = row.get("segment", "school")
    region  = "global" if segment == "it" else "wb"
    score   = _norm_score(row.get("ai_accuracy_score")) or 70.0
    subject = (
        raw.get("subject") or raw.get("topic_tag") or
        raw.get("topic_title") or raw.get("taxonomy_label") or segment
    )

    # Common fields present in BOTH tables
    # hierarchy_node_id → FK to exam_hierarchy (nullable) → None
    # region_id         → FK to regions table (nullable) → None
    #                     "wb"/"global" are NOT valid FK values
    _common = {
        "hierarchy_node_id": None,
        "region_id":         None,
        "subject_or_topic":  subject,
        "probability_score": score,
        "verified_by_human": True,
    }

    if data_type == "pyq":
        target     = "pyq_bank_v2"
        insert_row = {
            **_common,
            "question_payload": raw,
            "ai_accuracy_score": score,
            "validation_flags":  row.get("validation_flags") or [],
        }
    else:
        target     = "study_materials"
        insert_row = {
            **_common,
            "data_payload": raw,
            # ai_accuracy_score / validation_flags only added to study_materials
            # if the column exists — omit to avoid PGRST204
        }

    try:
        db.table(target).insert(insert_row).execute()
        db.table("ingestion_triage_queue").update({"status": "approved"}).eq("id", row["id"]).execute()
        st.toast(f"✅ Approved → {target}", icon="✅")
    except Exception as e:
        st.error(f"❌ Approve failed: {e}")
        st.caption("The error above is the exact DB message — use it to identify any missing column.")


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
    st.toast(f"Bulk: {success} approved, {fail} failed.", icon="✅")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — SMART PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def page_pipeline():
    st.title("🚀 Smart Pipeline")
    st.caption(
        "Curriculum-aware pipeline trigger. "
        "Coverage counts shown before you submit — no more guessing what to run."
    )

    coverage = fetch_coverage(_cache_key())

    # ── Pre-fill banner ───────────────────────────────────────────────────────
    prefill = st.session_state.get("prefill")
    if prefill:
        st.info(
            f"📌 **Pre-filled from Coverage Map:** "
            f"{prefill.get('board')} · Class {prefill.get('class_num')} · {prefill.get('subject')}  "
            f"— scroll down to review and submit.",
            icon="🗺️",
        )

    tab_school, tab_comp, tab_it = st.tabs(["🏫 School", "🏆 Competitive", "💻 IT / Cloud"])

    # ── SCHOOL TAB ────────────────────────────────────────────────────────────
    with tab_school:
        col_b, col_c = st.columns(2)

        # Default from prefill
        pf_board = prefill.get("board", "WBBSE") if prefill else "WBBSE"
        pf_class = prefill.get("class_num", 10)  if prefill else 10
        pf_subj  = prefill.get("subject", "")    if prefill else ""

        board_options = list(CURRICULUM.keys())
        board_idx     = board_options.index(pf_board) if pf_board in board_options else 0
        board = col_b.selectbox("Board", board_options, index=board_idx, key="school_board")

        class_options = sorted(CURRICULUM[board].keys())
        class_idx     = class_options.index(pf_class) if pf_class in class_options else 0
        class_num = col_c.selectbox("Class", class_options, index=class_idx,
                                    format_func=lambda x: f"Class {x}", key="school_class")

        # Coverage preview for this board+class
        st.markdown(f"**Coverage for {board} · Class {class_num}:**")
        preview_cols = st.columns(4)
        subjects_for_class = CURRICULUM[board][class_num]
        for i, s in enumerate(subjects_for_class):
            count = coverage.get((board, class_num, s), 0)
            preview_cols[i % 4].metric(s, _coverage_badge(count))

        st.markdown("---")

        # Subject dropdown (from curriculum)
        subj_idx = subjects_for_class.index(pf_subj) if pf_subj in subjects_for_class else 0
        subject  = st.selectbox("Subject", subjects_for_class, index=subj_idx, key="school_subject")

        existing = coverage.get((board, class_num, subject), 0)
        if existing > 0:
            status_text = (
                f"🟢 Good coverage" if existing >= 5
                else f"🟡 Low coverage — top-up recommended"
            )
            st.info(f"**Currently:** {existing} MCQs for this node · {status_text}")
        else:
            st.warning("**Currently:** 0 MCQs — this node is empty. Run the pipeline!")

        if class_num <= 4 and not source_url:
            st.error(
                f"⚠️ **Class {class_num} without a source PDF will produce poor results.**  \n"
                f"LLM doesn't know the actual {board} Class {class_num} textbook content.  \n"
                f"→ Upload the official textbook in **📚 Textbooks** first, "
                f"or paste a source URL above.",
                icon="📖",
            )

        chapter    = st.text_input("Chapter (optional)", placeholder="e.g. Electricity", key="school_chapter")
        source_url = st.text_input("Source URL (optional)", key="school_url")
        count      = st.slider("MCQ count", 3, 20, 5, key="school_count")
        force      = st.checkbox("⚡ Force regenerate (skip dedup check)", key="school_force")

        if st.button("🚀 Run School Pipeline", type="primary", key="school_submit"):
            if not subject:
                st.warning("Select a subject.")
            else:
                inputs = {
                    "board":     board,
                    "class_num": str(class_num),
                    "subject":   subject,
                    "count":     str(count),
                }
                if chapter:    inputs["chapter"]    = chapter
                if source_url: inputs["source_url"] = source_url
                if force:      inputs["force"]      = "true"
                _dispatch_workflow("ingest_school.yml", inputs)
                # Clear prefill after dispatch
                st.session_state["prefill"] = None

    # ── COMPETITIVE TAB ───────────────────────────────────────────────────────
    with tab_comp:
        authority = st.selectbox("Authority", list(COMPETITIVE_TREE.keys()), key="comp_authority")
        exams     = list(COMPETITIVE_TREE[authority].keys())
        exam      = st.selectbox("Exam", exams, key="comp_exam")
        topics    = COMPETITIVE_TREE[authority][exam]
        topic     = st.selectbox("Topic", topics, key="comp_topic")

        # Show existing count
        comp_key = (authority, exam, topic)
        existing_comp = sum(
            v for (a, e, t), v in {}.items()  # placeholder — competitive coverage not tracked yet
        )
        st.caption(f"ℹ️ Competitive coverage tracking coming soon. Check Supabase manually for now.")

        source_url_c = st.text_input("Source URL (optional)", key="comp_url")
        count_c      = st.slider("MCQ count", 3, 20, 8, key="comp_count")
        force_c      = st.checkbox("⚡ Force regenerate", key="comp_force")

        if st.button("🚀 Run Competitive Pipeline", type="primary", key="comp_submit"):
            inputs = {
                "authority": authority,
                "exam":      exam,
                "topic":     topic,
                "count":     str(count_c),
            }
            if source_url_c: inputs["source_url"] = source_url_c
            if force_c:      inputs["force"]      = "true"
            _dispatch_workflow("ingest_competitive.yml", inputs)

    # ── IT TAB ────────────────────────────────────────────────────────────────
    with tab_it:
        provider = st.selectbox("Provider", list(IT_TREE.keys()), key="it_provider")
        certs    = list(IT_TREE[provider].keys())
        cert     = st.selectbox("Certification", certs, key="it_cert")
        domains  = IT_TREE[provider][cert]
        domain   = st.selectbox("Domain / Topic", domains, key="it_domain")

        st.caption("ℹ️ IT coverage tracking coming soon. Check Supabase manually for now.")

        source_url_it = st.text_input("Source URL (optional)", key="it_url")
        count_it      = st.slider("MCQ count", 3, 20, 6, key="it_count")
        force_it      = st.checkbox("⚡ Force regenerate", key="it_force")

        if st.button("🚀 Run IT Pipeline", type="primary", key="it_submit"):
            inputs = {
                "provider": provider,
                "exam":     cert,
                "topic":    domain,
                "count":    str(count_it),
            }
            if source_url_it: inputs["source_url"] = source_url_it
            if force_it:      inputs["force"]      = "true"
            _dispatch_workflow("ingest_it.yml", inputs)

    # ── Recent runs ───────────────────────────────────────────────────────────
    st.markdown("---")
    repo = st.secrets.get("GITHUB_REPO", "arkagimt/gyan-ai-pipeline")
    st.caption(f"[📋 View all GitHub Actions runs →](https://github.com/{repo}/actions)")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — AGENT PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

def page_prompts():
    st.title("🤖 Agent Prompts")
    st.caption(
        "View and edit agent system prompts stored in Supabase (Vault Pattern). "
        "Changes take effect on the next pipeline run."
    )

    db = get_supabase()

    try:
        rows = db.table("agent_prompts").select("*").order("agent_id").execute().data or []
    except Exception as e:
        st.error(f"Could not load agent prompts: {e}")
        return

    if not rows:
        st.warning("No agent prompts found. Seed the `agent_prompts` table in Supabase first.")
        return

    agent_labels = {
        "sarbagya":    "সর্বজ্ঞ — Scout / Extractor",
        "chitragupta": "চিত্রগুপ্ত — Validator",
        "sutradhar":   "সূত্রধর — Content Creator",
    }

    selected = st.selectbox(
        "Select agent",
        [r["agent_id"] for r in rows],
        format_func=lambda x: agent_labels.get(x, x),
    )

    row = next((r for r in rows if r["agent_id"] == selected), None)
    if not row:
        return

    st.markdown("---")

    col_meta, col_ctrl = st.columns([3, 1])
    with col_meta:
        st.markdown(
            f"**Role:** {row.get('role', '—')}  \n"
            f"**Temp:** `{row.get('temperature', '—')}` &nbsp;|&nbsp; "
            f"**Max tokens:** `{row.get('max_tokens', '—')}`"
        )
    with col_ctrl:
        edit_mode = st.toggle("✏️ Edit mode")

    if edit_mode:
        new_prompt = st.text_area(
            "System Prompt",
            value=row.get("system_prompt", ""),
            height=420,
            help="Exact system prompt sent to the LLM at runtime.",
        )
        new_temp   = st.number_input("Temperature", 0.0, 2.0,
                                     float(row.get("temperature", 0.3)), step=0.05)
        new_tokens = st.number_input("Max Tokens", 256, 8192,
                                     int(row.get("max_tokens", 4096)), step=256)
        if st.button("💾 Save to Supabase", type="primary"):
            try:
                db.table("agent_prompts").update({
                    "system_prompt": new_prompt,
                    "temperature":   new_temp,
                    "max_tokens":    new_tokens,
                }).eq("agent_id", selected).execute()
                st.success(f"✅ `{selected}` prompt updated. Next run will use this.")
                st.rerun()
            except Exception as e:
                st.error(f"Save failed: {e}")
    else:
        st.text_area(
            "System Prompt (read-only)",
            value=row.get("system_prompt", ""),
            height=420,
            disabled=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — TEXTBOOKS (Supabase Storage)
# ═══════════════════════════════════════════════════════════════════════════════

def _subject_slug(subject: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")


def page_textbooks():
    st.title("📚 Textbooks")
    st.caption(
        "Upload official textbook PDFs to Supabase Storage. "
        "The pipeline auto-fetches them when running for that board/class/subject — "
        "no manual URL needed."
    )

    db      = get_supabase()
    BUCKET  = "textbook-pdfs"
    SB_URL  = st.secrets["SUPABASE_URL"]
    SB_KEY  = st.secrets["SUPABASE_SERVICE_KEY"]

    # ── Fetch existing sources ────────────────────────────────────────────────
    try:
        sources = db.table("curriculum_sources").select("*").order("board").order("class_num").execute().data or []
    except Exception as e:
        st.error(f"Could not load curriculum_sources: {e}")
        st.info("Run `scripts/setup_textbook_storage.sql` in Supabase SQL Editor first.")
        return

    # ── Coverage: which curriculum nodes have a PDF? ──────────────────────────
    sourced = {(r["board"], r["class_num"], r["subject"]) for r in sources if r.get("is_active")}

    col_upload, col_status = st.columns([1, 1])

    # ── UPLOAD PANEL ──────────────────────────────────────────────────────────
    with col_upload:
        st.subheader("⬆️ Upload Textbook PDF")

        board_u    = st.selectbox("Board",    list(CURRICULUM.keys()), key="tb_board")
        classes_u  = sorted(CURRICULUM[board_u].keys())
        class_u    = st.selectbox("Class",    classes_u, format_func=lambda x: f"Class {x}", key="tb_class")
        subjects_u = CURRICULUM[board_u][class_u]
        subject_u  = st.selectbox("Subject",  subjects_u, key="tb_subject")
        chapter_u  = st.text_input("Chapter (optional — leave blank for full textbook)",
                                   placeholder="e.g. Electricity", key="tb_chapter")
        display_u  = st.text_input("Display name (optional)",
                                   placeholder=f"e.g. WBBSE Class {class_u} {subject_u} Textbook",
                                   key="tb_display")

        uploaded_file = st.file_uploader(
            "Choose PDF",
            type=["pdf"],
            help="Upload the official textbook PDF. Max 50MB.",
            key="tb_file",
        )

        # Warn if node already has a PDF
        existing_key = (board_u, class_u, subject_u)
        if existing_key in sourced:
            st.warning("⚠️ A PDF already exists for this node. Uploading will replace it.")

        if st.button("⬆️ Upload to Supabase Storage", type="primary",
                     disabled=uploaded_file is None):
            if uploaded_file:
                slug      = _subject_slug(subject_u)
                path      = f"{board_u.lower()}/{class_u}/{slug}.pdf"
                file_size = len(uploaded_file.getvalue()) // 1024

                with st.spinner(f"Uploading {file_size} KB..."):
                    # Upload via Supabase Storage REST API
                    upload_url = f"{SB_URL}/storage/v1/object/{BUCKET}/{path}"
                    resp = requests.post(
                        upload_url,
                        headers={
                            "Authorization": f"Bearer {SB_KEY}",
                            "Content-Type":  "application/pdf",
                            "x-upsert":      "true",  # overwrite if exists
                        },
                        data=uploaded_file.getvalue(),
                        timeout=60,
                    )

                if resp.status_code in (200, 201):
                    # Upsert curriculum_sources row
                    row = {
                        "board":        board_u,
                        "class_num":    class_u,
                        "subject":      subject_u,
                        "chapter":      chapter_u or None,
                        "storage_path": path,
                        "display_name": display_u or f"{board_u} Class {class_u} {subject_u}",
                        "file_size_kb": file_size,
                        "is_active":    True,
                        "uploaded_by":  "admin",
                    }
                    try:
                        db.table("curriculum_sources").upsert(row,
                            on_conflict="board,class_num,subject" + (",chapter" if chapter_u else "")
                        ).execute()
                        st.success(f"✅ Uploaded → `{path}` ({file_size} KB)")
                        st.info("Pipeline will now auto-use this PDF for future runs on this node.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Upload succeeded but DB record failed: {e}")
                else:
                    st.error(f"Storage upload failed {resp.status_code}: {resp.text[:300]}")
                    if resp.status_code == 404:
                        st.caption(
                            "Bucket `textbook-pdfs` not found. "
                            "Create it in Supabase Dashboard → Storage → New Bucket (private)."
                        )

    # ── STATUS PANEL ──────────────────────────────────────────────────────────
    with col_status:
        st.subheader("📋 Uploaded Textbooks")

        if not sources:
            st.info("No textbooks uploaded yet. Use the upload form.")
        else:
            for row in sources:
                active = row.get("is_active", True)
                icon   = "✅" if active else "⏸️"
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(
                        f"{icon} **{row.get('display_name') or row['subject']}**  \n"
                        f"`{row['board']} · Class {row['class_num']}` · "
                        f"{row.get('file_size_kb', '?')} KB · "
                        f"`{row.get('storage_path', '—')}`"
                    )
                with c2:
                    if active:
                        if st.button("⏸", key=f"deact_{row['id']}",
                                     help="Deactivate — pipeline won't use this PDF"):
                            db.table("curriculum_sources").update({"is_active": False}).eq("id", row["id"]).execute()
                            st.rerun()
                    else:
                        if st.button("▶", key=f"act_{row['id']}",
                                     help="Activate — pipeline will use this PDF"):
                            db.table("curriculum_sources").update({"is_active": True}).eq("id", row["id"]).execute()
                            st.rerun()

    st.markdown("---")

    # ── Coverage gap: which nodes LACK a PDF? ────────────────────────────────
    st.subheader("🔴 Nodes Without a Textbook PDF")
    st.caption("These nodes will use LLM knowledge only — lower quality, especially for Class 1–5.")

    missing = []
    for board, classes in CURRICULUM.items():
        for class_num, subjects in classes.items():
            for subject in subjects:
                if (board, class_num, subject) not in sourced:
                    missing.append((board, class_num, subject))

    missing.sort(key=lambda x: (-CLASS_PRIORITY.get(x[1], 1), x[0], x[1], x[2]))

    if not missing:
        st.success("🎉 All curriculum nodes have a textbook PDF!")
    else:
        # Show as a compact table
        df_missing = pd.DataFrame(missing, columns=["Board", "Class", "Subject"])
        df_missing["Class"] = df_missing["Class"].apply(lambda x: f"Class {x}")
        df_missing["Priority"] = df_missing["Class"].apply(
            lambda x: CLASS_PRIORITY.get(int(x.split()[-1]), 1)
        )
        st.dataframe(
            df_missing[["Board", "Class", "Subject"]],
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            f"{len(missing)} nodes without PDFs. "
            "Download official textbooks from WBBSE / CBSE / ICSE websites and upload above."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

if page == "📊 Command Centre":
    page_command_centre()
elif page == "🗺️ Coverage Map":
    page_coverage_map()
elif page == "🔍 Triage Queue":
    page_triage()
elif page == "🚀 Smart Pipeline":
    page_pipeline()
elif page == "📚 Textbooks":
    page_textbooks()
elif page == "🤖 Agent Prompts":
    page_prompts()
