"""
গণক — The Analyst
==================
Bengali:  গণক
Website:  gyanagent.in/about  →  "The Analyst"
          "প্রতিটি টপিকের সম্ভাবনা গণনা করে আমি বলতে পারি কোনটায় আগে
           মনোযোগ দেওয়া দরকার।"
          (I calculate the probability for each topic and tell you
           which one needs attention first.)

Role:   Curriculum Coverage Analyst & Topic Priority Engine
Input:  Coverage dict {(board, class_num, subject): count} from Supabase
Output: list[TopicPriority] — ordered highest → lowest priority

No LLM. Pure heuristic + data-driven scoring.
Scoring factors (weighted sum → 0–100):
  1. Gap urgency    — how far below MCQ target (max 40 pts)
  2. Class priority — board exam classes rank higher (max 25 pts)
  3. Zero coverage  — bonus for completely empty slots (max 20 pts)
  4. Board weight   — WB boards prioritised (home market) (max 15 pts)

Consumers:
  - admin/streamlit_app.py  — "Pipeline Recommendations" panel
  - agents/acharya.py       — future curriculum orchestrator (Phase 9)
  - gyan_pipeline.py        — auto-fill lowest-priority topics in batch mode
"""

from __future__ import annotations

from dataclasses import dataclass, field

from curriculum import (
    CURRICULUM, CLASS_PRIORITY,
    ENTRANCE_TREE, RECRUITMENT_TREE, COMPETITIVE_TREE,  # COMPETITIVE_TREE kept for back-compat
    IT_TREE, MCQ_TARGET_PER_SLOT,
)
from models.schemas import TaxonomySlice, Segment, with_derived_scope_nature
from config import emit_agent


# ── Output model ──────────────────────────────────────────────────────────────

@dataclass
class TopicPriority:
    """Priority recommendation for a single taxonomy slot."""
    # Identification
    segment:    str
    board:      str | None = None
    class_num:  int | None = None
    subject:    str | None = None
    authority:  str | None = None    # competitive
    exam:       str | None = None
    topic:      str | None = None
    provider:   str | None = None    # IT

    # Metrics
    current_mcqs:  int   = 0
    target_mcqs:   int   = MCQ_TARGET_PER_SLOT
    gap:           int   = 0
    priority_score: float = 0.0
    reason:        str   = ""

    @property
    def taxonomy_slice(self) -> TaxonomySlice:
        """Convert to a runnable TaxonomySlice for gyan_pipeline.py.
        Scope + nature are auto-derived so downstream consumers (supabase_loader,
        web filters) get the classification for free.
        """
        slice = TaxonomySlice(
            segment   = Segment(self.segment),
            board     = self.board,
            class_num = self.class_num,
            subject   = self.subject,
            authority = self.authority,
            exam      = self.exam,
            topic     = self.topic,
            provider  = self.provider,
            count     = min(self.gap, 10),  # cap at 10 per run
        )
        return with_derived_scope_nature(slice)


# ── Scoring helpers ───────────────────────────────────────────────────────────

def _gap_score(current: int, target: int) -> float:
    """40 pts for gap ≥ target, scales down linearly."""
    gap = max(0, target - current)
    return min(40.0, (gap / target) * 40.0)


def _class_score(class_num: int | None) -> float:
    """25 pts for Class 10/12, scales down by CLASS_PRIORITY."""
    if class_num is None:
        return 12.0  # mid-range default for competitive/IT
    max_prio = max(CLASS_PRIORITY.values())   # 10
    prio     = CLASS_PRIORITY.get(class_num, 1)
    return (prio / max_prio) * 25.0


def _zero_bonus(current: int) -> float:
    """20 pt bonus for completely empty slots — ensures no topic is 0 forever."""
    return 20.0 if current == 0 else 0.0


def _board_weight(board: str | None) -> float:
    """15 pts for WB boards (primary market), 10 for others."""
    if board in ("WBBSE", "WBCHSE"):
        return 15.0
    if board in ("CBSE",):
        return 10.0
    return 7.0


def _score(current: int, target: int, class_num: int | None, board: str | None) -> float:
    return (
        _gap_score(current, target)
        + _class_score(class_num)
        + _zero_bonus(current)
        + _board_weight(board)
    )


def _reason(current: int, target: int, class_num: int | None, board: str | None) -> str:
    parts = []
    if current == 0:
        parts.append("zero coverage")
    elif current < target:
        parts.append(f"{target - current} MCQs below target of {target}")
    if class_num in (10, 12):
        parts.append("board exam year")
    if board in ("WBBSE", "WBCHSE"):
        parts.append("primary WB market")
    return "; ".join(parts) if parts else "normal coverage"


# ── Main API ──────────────────────────────────────────────────────────────────

def analyze(
    coverage:          dict,
    target_per_slot:   int  = MCQ_TARGET_PER_SLOT,
    top_n:             int  = 20,
    segment_filter:    str  | None = None,   # "school" | "competitive" | "it"
    board_filter:      str  | None = None,
    class_filter:      int  | None = None,
) -> list[TopicPriority]:
    """
    গণক's main function.

    Args:
        coverage:        {(board, class_num, subject): count} from fetch_coverage()
                         OR {(authority, exam, topic): count} for competitive
        target_per_slot: MCQs needed before a slot is considered "covered"
        top_n:           return only the top N priorities
        segment_filter:  optional — restrict to one segment
        board_filter:    optional — restrict to one board
        class_filter:    optional — restrict to one class

    Returns list of TopicPriority sorted high → low.
    """
    emit_agent("গণক", "Calculating topic priorities...")

    priorities: list[TopicPriority] = []

    # ── School segment ────────────────────────────────────────────────────────
    if segment_filter in (None, "school"):
        for board, classes in CURRICULUM.items():
            if board_filter and board != board_filter:
                continue
            for cls, subjects in classes.items():
                if class_filter and cls != class_filter:
                    continue
                for subject in subjects:
                    key     = (board, cls, subject)
                    current = coverage.get(key, 0)
                    gap     = max(0, target_per_slot - current)
                    if gap == 0:
                        continue  # already covered — skip
                    score = _score(current, target_per_slot, cls, board)
                    priorities.append(TopicPriority(
                        segment       = "school",
                        board         = board,
                        class_num     = cls,
                        subject       = subject,
                        current_mcqs  = current,
                        target_mcqs   = target_per_slot,
                        gap           = gap,
                        priority_score = round(score, 1),
                        reason        = _reason(current, target_per_slot, cls, board),
                    ))

    # ── Entrance segment (JEE, NEET, CAT, GATE, WBJEE, NDA, CLAT, CUET) ───────
    # `segment_filter="competitive"` is kept as a combined alias (legacy) and
    # pulls from both entrance + recruitment — so existing callers keep working.
    if segment_filter in (None, "entrance", "competitive"):
        for authority, exams in ENTRANCE_TREE.items():
            for exam, topics in exams.items():
                for topic in topics:
                    key     = (authority, exam, topic)
                    current = coverage.get(key, 0)
                    gap     = max(0, target_per_slot - current)
                    if gap == 0:
                        continue
                    score = _score(current, target_per_slot, None, None) + 5.0  # entrance boost
                    priorities.append(TopicPriority(
                        segment        = "entrance",
                        authority      = authority,
                        exam           = exam,
                        topic          = topic,
                        current_mcqs   = current,
                        target_mcqs    = target_per_slot,
                        gap            = gap,
                        priority_score = round(score, 1),
                        reason         = _reason(current, target_per_slot, None, None),
                    ))

    # ── Recruitment segment (WBPSC, WBSSC, SSC, UPSC, Railway) ────────────────
    if segment_filter in (None, "recruitment", "competitive"):
        for authority, exams in RECRUITMENT_TREE.items():
            for exam, topics in exams.items():
                for topic in topics:
                    key     = (authority, exam, topic)
                    current = coverage.get(key, 0)
                    gap     = max(0, target_per_slot - current)
                    if gap == 0:
                        continue
                    score = _score(current, target_per_slot, None, None) + 5.0  # recruitment boost
                    priorities.append(TopicPriority(
                        segment        = "recruitment",
                        authority      = authority,
                        exam           = exam,
                        topic          = topic,
                        current_mcqs   = current,
                        target_mcqs    = target_per_slot,
                        gap            = gap,
                        priority_score = round(score, 1),
                        reason         = _reason(current, target_per_slot, None, None),
                    ))

    # ── IT segment ────────────────────────────────────────────────────────────
    if segment_filter in (None, "it"):
        for provider, certs in IT_TREE.items():
            for cert, domains in certs.items():
                for domain in domains:
                    key     = (provider, cert, domain)
                    current = coverage.get(key, 0)
                    gap     = max(0, target_per_slot - current)
                    if gap == 0:
                        continue
                    score = _score(current, target_per_slot, None, None)
                    priorities.append(TopicPriority(
                        segment        = "it",
                        provider       = provider,
                        exam           = cert,
                        topic          = domain,
                        current_mcqs   = current,
                        target_mcqs    = target_per_slot,
                        gap            = gap,
                        priority_score = round(score, 1),
                        reason         = _reason(current, target_per_slot, None, None),
                    ))

    # ── Sort + slice ──────────────────────────────────────────────────────────
    priorities.sort(key=lambda p: p.priority_score, reverse=True)
    result = priorities[:top_n]

    emit_agent("গণক", f"Found {len(priorities)} gaps — returning top {len(result)}")
    return result


def summary_stats(coverage: dict) -> dict:
    """
    Returns high-level stats for the Command Centre dashboard.
    {total_slots, covered_slots, coverage_pct, board_breakdown}
    """
    total   = 0
    covered = 0
    by_board: dict[str, dict] = {}

    for board, classes in CURRICULUM.items():
        b_total   = 0
        b_covered = 0
        for cls, subjects in classes.items():
            for subject in subjects:
                total   += 1
                b_total += 1
                if coverage.get((board, cls, subject), 0) >= MCQ_TARGET_PER_SLOT:
                    covered   += 1
                    b_covered += 1
        by_board[board] = {
            "total":   b_total,
            "covered": b_covered,
            "pct":     round(b_covered / b_total * 100, 1) if b_total else 0,
        }

    return {
        "total_slots":    total,
        "covered_slots":  covered,
        "coverage_pct":   round(covered / total * 100, 1) if total else 0,
        "board_breakdown": by_board,
    }
