"""
Gyan AI Pipeline — Pydantic Schemas
====================================
Type-safe contracts between pipeline agents.
Every agent receives a Pydantic model and returns a Pydantic model.
If an LLM produces invalid JSON, the agent retries automatically.

Flow:
  TaxonomySlice
    └─► সর্বজ্ঞ  → RawExtract
          └─► চিত্রগুপ্ত  → ValidationReport
                └─► সূত্রধর  → StudyPackage
                      └─► Supabase ingestion_triage_queue
"""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class Segment(str, Enum):
    school      = "school"
    competitive = "competitive"   # backward compat — legacy alias for entrance+recruitment
    entrance    = "entrance"      # JEE, NEET, CAT, GATE, WBJEE, NDA, CLAT, CUET
    recruitment = "recruitment"   # WBPSC, SSC, UPSC, Railway, WBSSC
    it          = "it"

class Importance(str, Enum):
    critical = "critical"
    high     = "high"
    normal   = "normal"

class Scope(str, Enum):
    """Geographic scope of a content item."""
    central       = "central"       # CBSE, UPSC, SSC — national
    state         = "state"         # WBBSE, WBPSC — state-specific
    international = "international" # AWS, Azure — global IT certs

class Nature(str, Enum):
    """Classification of what kind of exam/content this is."""
    entrance    = "entrance"    # JEE, NEET, CAT — entrance to institutions
    recruitment = "recruitment" # WBCS, SSC CGL — govt job recruitment
    board       = "board"       # WBBSE Madhyamik, CBSE Class 10 — school boards
    cert        = "cert"        # AWS SAA, AZ-900 — professional certifications


class SourceType(str, Enum):
    """Provenance tier for a piece of seed material. Maps to web Trust Chips.

    Stronger tiers (near top) give stronger provenance claims on the MCQ card.
    This is the single source of truth — web UI badge colour + copy should
    switch on this enum, not on free-text guesses.

    Ranked high→low credibility:
      official_past       → actual past exam paper from the authority itself
                            (UPSC archive, JEE NTA archive, CBSE question-paper
                            section). Strongest signal — highest Trust Chip tier.
      official_sample     → sample / specimen / model paper from the authority
                            (CBSE SQP, CISCE specimen, board model papers).
                            Vendor-authored but not a real administered exam.
      ncert_exemplar      → NCERT Exemplar Problems (Class 6–12). Govt-published,
                            explicitly reusable, used nationally as de-facto prep.
      board_publication   → book/compilation bought directly from the board's
                            own publications department (CISCE Publications,
                            WBBSE Bhawan). Legit-to-reuse because paid to the
                            copyright holder with educational-use license.
      vendor_docs         → official vendor documentation for IT certs
                            (AWS Docs, Microsoft Learn, GCP Docs). Mostly
                            CC-licensed or explicitly permit educational reuse.
      vendor_sample       → official cert vendor sample questions / practice
                            assessments (AWS Skill Builder free, Microsoft Learn
                            knowledge checks, GCP Cloud Skills Boost).
                            **NOT brain dumps — those are banned.**
      teacher_upload      → PDF uploaded by a verified teacher partner via
                            /admin/teacher-upload (Phase 6.2). Trust depends
                            on which teacher — edit_log preserves the chain.
      llm_knowledge       → no source material; generated from the base model's
                            training knowledge. Weakest tier — Trust Chip
                            should explicitly disclose this to the student.

    Banned (documented in GAP_SOURCING.md, enforced in code-review, never
    acquires a SourceType value):
      - exam dumps (ExamTopics / BrainDumps / leaked cert questions) — NDA +
        DMCA liability, cert-vendor partnership disqualifier, student-cert
        invalidation risk.
      - third-party ed-tech compilations (PW / BYJU'S / Unacademy PYQ PDFs) —
        compilation copyright + ToS violations regardless of underlying
        question public-domain status.
    """
    official_past     = "official_past"
    official_sample   = "official_sample"
    ncert_exemplar    = "ncert_exemplar"
    board_publication = "board_publication"
    vendor_docs       = "vendor_docs"
    vendor_sample     = "vendor_sample"
    teacher_upload    = "teacher_upload"
    llm_knowledge     = "llm_knowledge"


# ── Pipeline Input ────────────────────────────────────────────────────────────

class TaxonomySlice(BaseModel):
    """The pipeline's starting point — describes exactly what to generate."""
    segment:   Segment
    # school
    board:     Optional[str] = None   # WBBSE | CBSE | ICSE | WBCHSE
    class_num: Optional[int] = None   # 1–12
    subject:   Optional[str] = None   # "Physical Science"
    chapter:   Optional[str] = None   # "electricity" (optional — chapter-level grounding)
    # competitive / entrance / recruitment
    authority: Optional[str] = None   # "WBPSC" | "NTA" | "IIM"
    exam:      Optional[str] = None   # "WBCS Prelims" | "JEE Main"
    topic:     Optional[str] = None   # "History of India"
    # it
    provider:  Optional[str] = None   # "AWS"
    count:     int = Field(default=5, ge=1, le=20)
    source_url: Optional[str] = None  # optional — raw content source
    source_pdf: Optional[str] = None  # optional — local PDF path
    # metadata classification (Phase 1.3)
    scope:     Optional[Scope]  = None  # central | state | international
    nature:    Optional[Nature] = None  # entrance | recruitment | board | cert

    @property
    def label(self) -> str:
        """Human-readable label for logging."""
        if self.segment == Segment.school:
            parts = [self.board, f"Class {self.class_num}", self.subject, self.chapter]
        elif self.segment in (Segment.competitive, Segment.entrance, Segment.recruitment):
            parts = [self.authority, self.exam, self.topic]
        else:
            parts = [self.provider, self.exam, self.topic]
        return " › ".join(p for p in parts if p)


# ── Scope + Nature derivation (Phase 1.3) ─────────────────────────────────────
# Auto-classify a TaxonomySlice into the geographic scope and pedagogical nature
# so downstream code (web tabs, admin triage filters, Ganak priority math) can
# query by these axes instead of the coarse `segment` column.
#
# Design:
#   - "scope"  answers  "who is this content FOR — one state, the whole country,
#                        or the global IT industry?"
#   - "nature" answers  "what KIND of content is it — a school board syllabus, a
#                        university entrance test, a govt-job recruitment exam,
#                        or a vendor certification?"
#
# Kept outside the Pydantic model so it's a pure function — trivial to test and
# to call from anywhere a TaxonomySlice exists.

# Boards recognised as state-specific. Anything else defaults to central.
_STATE_SCOPE_BOARDS   = {"WBBSE", "WBCHSE", "WBBPE"}
_CENTRAL_SCOPE_BOARDS = {"CBSE", "ICSE", "ISC", "NIOS"}
# Entrance exams that are state-specific (most are central).
_STATE_SCOPE_ENTRANCE_AUTHORITIES = {"WBJEE"}

# Recruitment — explicit whitelists, because prefix-matching mislabels UPSC
# (Union Public Service Commission → central) as state-UP. Update when adding
# a new authority to curriculum.RECRUITMENT_TREE.
_CENTRAL_RECRUITMENT_AUTHORITIES = {
    "UPSC", "SSC", "IBPS", "SBI", "RBI", "LIC", "EPFO",
    "RAILWAY", "RRB", "NTPC",     # Indian Railways variants
}
# State PSCs / SSCs — prefix-matched because they all follow the pattern
# {state-code}{PSC|SSC|PCS|SSSC|PRB|BPE}. Prefixes listed explicitly so we
# don't mis-classify central authorities that happen to start with those letters.
_STATE_RECRUITMENT_PATTERNS = (
    "WBPSC", "WBSSC", "WBPRB", "WBBPE",
    "UPPSC", "UPPCS", "UPSSSC",
    "MPPSC", "MPSSSB",
    "TNPSC", "TNMS",
    "KPSC",  "KAS",
    "GPSC",  "GSSSB",
    "OPSC",  "OSSC",
    "APPSC", "TSPSC",
    "BPSC",  "RPSC", "HPSC", "PPSC", "JKSSB",
)


def derive_scope_nature(taxonomy: "TaxonomySlice") -> tuple["Scope | None", "Nature | None"]:
    """
    Infer (scope, nature) for a TaxonomySlice.

    Rules:
      * segment=school   → nature=board, scope=state|central based on board
      * segment=entrance → nature=entrance, scope=state if authority∈_STATE_SCOPE_ENTRANCE_AUTHORITIES
                                              else central
      * segment=recruitment → nature=recruitment, scope=state if authority startswith any state prefix
                                                     else central
      * segment=competitive (legacy alias) → nature=recruitment (conservative default),
                                             scope derived as for recruitment
      * segment=it      → nature=cert, scope=international

    Returns (None, None) only if segment is genuinely unknown.
    """
    seg = taxonomy.segment

    if seg == Segment.school:
        board = (taxonomy.board or "").strip().upper()
        if board in _STATE_SCOPE_BOARDS:
            return Scope.state, Nature.board
        if board in _CENTRAL_SCOPE_BOARDS or board.startswith("CBSE") or board.startswith("ICSE"):
            return Scope.central, Nature.board
        # Unknown board — treat as state-specific (safer for regional filtering).
        return Scope.state, Nature.board

    if seg == Segment.entrance:
        auth = (taxonomy.authority or "").strip().upper()
        scope = Scope.state if auth in _STATE_SCOPE_ENTRANCE_AUTHORITIES else Scope.central
        return scope, Nature.entrance

    if seg in (Segment.recruitment, Segment.competitive):
        auth = (taxonomy.authority or "").strip().upper()
        if auth in _CENTRAL_RECRUITMENT_AUTHORITIES:
            return Scope.central, Nature.recruitment
        is_state = any(auth.startswith(p) for p in _STATE_RECRUITMENT_PATTERNS)
        scope = Scope.state if is_state else Scope.central
        return scope, Nature.recruitment

    if seg == Segment.it:
        return Scope.international, Nature.cert

    return None, None


def with_derived_scope_nature(taxonomy: "TaxonomySlice") -> "TaxonomySlice":
    """
    Return a copy of `taxonomy` with scope/nature filled in if they're missing.
    Callers who already set them explicitly are respected.
    """
    scope, nature = derive_scope_nature(taxonomy)
    updates: dict = {}
    if taxonomy.scope is None and scope is not None:
        updates["scope"] = scope
    if taxonomy.nature is None and nature is not None:
        updates["nature"] = nature
    if not updates:
        return taxonomy
    return taxonomy.model_copy(update=updates)


# ── সর্বজ্ঞ Output ─────────────────────────────────────────────────────────────

class RawExtract(BaseModel):
    """সর্বজ্ঞ's output — raw facts and concepts pulled from source material."""
    taxonomy:        TaxonomySlice
    raw_text:        str   = Field(description="Source text used (truncated to 8k chars)")
    key_facts:       list[str] = Field(description="Bullet-point facts extracted from source")
    core_concepts:   list[str] = Field(description="Named concepts central to this topic")
    formulas:        list[str] = Field(default_factory=list, description="Any formulas or equations")
    definitions:     dict[str, str] = Field(default_factory=dict, description="term → definition")
    source_type:     str  = Field(default="llm_knowledge", description="pdf | url | llm_knowledge")
    token_count_est: int  = Field(default=0)


# ── চিত্রগুপ্ত Output ──────────────────────────────────────────────────────────

class ValidationFlag(str, Enum):
    factual_error        = "factual_error"
    out_of_syllabus      = "out_of_syllabus"
    hallucination_risk   = "hallucination_risk"
    incomplete_content   = "incomplete_content"
    formula_error        = "formula_error"
    # ── Phase-2 additions (Vidushak v1) ─────────────────────────────────────
    language_mismatch    = "language_mismatch"     # Bengali board but English output (or vice versa)
    age_inappropriate    = "age_inappropriate"     # vocab/complexity wrong for target class
    source_disconnect    = "source_disconnect"     # MCQ not grounded in Sarbagya's extract
    # ── Phase-5 additions (Dharmarakshak safety) ─────────────────────────────
    safety_violation     = "safety_violation"      # Llama Guard 3 blocked (S1/S4/S10/S11/S12/S13)
    safety_review        = "safety_review"         # Llama Guard 3 flagged (S8) or heuristic flag
    passed               = "passed"

class ValidationReport(BaseModel):
    """চিত্রগুপ্ত's output — quality verdict on the extracted content."""
    extract:          RawExtract
    is_valid:         bool
    confidence:       int  = Field(ge=0, le=100, description="0–100 quality score")
    flags:            list[ValidationFlag] = Field(default_factory=list)
    corrections:      dict[str, str] = Field(default_factory=dict, description="what was corrected")
    rejection_reason: Optional[str]  = None


# ── সূত্রধর Output ──────────────────────────────────────────────────────────────

class MCQOption(BaseModel):
    A: str
    B: str
    C: str
    D: str

class MCQItem(BaseModel):
    """A single MCQ — সারং ততো গ্রাহ্যম্ — concise, conceptual, no trivia."""
    question:          str
    options:           MCQOption
    correct:           str  = Field(pattern="^[ABCD]$")
    reasoning_process: str  = Field(description="Chain-of-thought: step-by-step reasoning that leads to the answer, explaining why each distractor fails")
    explanation:       str  = Field(description="Concise 1-sentence summary of why the correct answer is right")
    difficulty:        str  = Field(default="medium", pattern="^(easy|medium|hard)$")
    bloom_level:       str  = Field(default="understand", description="remember|understand|apply|analyze")
    topic_tag:         str  = Field(description="Exact sub-topic this question tests")

class StudyNote(BaseModel):
    """Structured study material for one topic/chapter."""
    topic_title:     str
    summary:         str  = Field(description="2–3 sentence crisp summary")
    key_concepts:    list[str]
    formulas:        list[str]  = Field(default_factory=list)
    important_facts: list[str]
    examples:        list[str]  = Field(default_factory=list)
    memory_hooks:    list[str]  = Field(default_factory=list, description="Mnemonics or analogies")

class StudyPackage(BaseModel):
    """সূত্রধর's final output — ready for ingestion_triage_queue."""
    taxonomy:    TaxonomySlice
    notes:       list[StudyNote]
    mcqs:        list[MCQItem]
    metadata:    dict = Field(default_factory=dict)


# ── LLM Output Models (instructor response_model targets) ────────────────────
# These are the *LLM-generated* portions only — no pipeline-attached fields.
# Each agent calls call_llm(..., response_model=XxxOutput) and then assembles
# the full pipeline model by attaching taxonomy / extract / etc.

class ExtractOutput(BaseModel):
    """
    সর্বজ্ঞ LLM output.
    min_length validators enforce minimum content — instructor auto-retries if violated.
    Inspired by: github.com/jxnl/instructor (MIT)
    """
    key_facts:     list[str]       = Field(min_length=3,  description="Min 8 concrete facts")
    core_concepts: list[str]       = Field(min_length=2,  description="4-8 named concepts")
    formulas:      list[str]       = Field(default_factory=list)
    definitions:   dict[str, str]  = Field(default_factory=dict)
    source_type:   str             = Field(default="llm_knowledge")


class ValidationOutput(BaseModel):
    """চিত্রগুপ্ত LLM output."""
    is_valid:         bool
    confidence:       int              = Field(ge=0, le=100)
    flags:            list[str]        = Field(default_factory=list)
    corrections:      dict[str, str]   = Field(default_factory=dict)
    rejection_reason: Optional[str]    = None


class StudyOutput(BaseModel):
    """সূত্রধর LLM output — notes + MCQs before taxonomy is attached."""
    notes: list[StudyNote] = Field(min_length=1)
    mcqs:  list[MCQItem]   = Field(min_length=1)


class MCQVerification(BaseModel):
    """
    Self-critique verdict for a single MCQ.
    Inspired by Guardrails AI 'reask' pattern (Apache 2.0):
    the LLM is asked to audit its own outputs for quality issues.
    """
    index:   int            = Field(description="0-based index of the MCQ in the batch")
    verdict: str            = Field(description="ok | has_issue")
    issue:   Optional[str]  = Field(default=None, description="Specific issue if verdict=has_issue")


class MCQBatchVerification(BaseModel):
    """Self-critique result for the full MCQ batch."""
    verifications: list[MCQVerification]
    any_issues:    bool = Field(description="True if ANY MCQ has verdict=has_issue")


# ── Pipeline Result (stdout JSON for Next.js) ─────────────────────────────────

class PipelineResult(BaseModel):
    """Emitted as final JSON line to stdout — parsed by Streamlit / GitHub Actions."""
    type:       str  = "result"
    pyqs:       int  = 0
    notes:      int  = 0
    errors:     int  = 0
    elapsed_s:  float = 0.0
    queued_ids: list[str] = Field(default_factory=list)
    skipped:    bool = Field(default=False,
                             description="True when dedup memory decided no new content needed")
