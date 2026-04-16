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
    competitive = "competitive"
    it          = "it"

class Importance(str, Enum):
    critical = "critical"
    high     = "high"
    normal   = "normal"


# ── Pipeline Input ────────────────────────────────────────────────────────────

class TaxonomySlice(BaseModel):
    """The pipeline's starting point — describes exactly what to generate."""
    segment:   Segment
    # school
    board:     Optional[str] = None   # WBBSE | CBSE | ICSE | WBCHSE
    class_num: Optional[int] = None   # 1–12
    subject:   Optional[str] = None   # "Physical Science"
    chapter:   Optional[str] = None   # "electricity" (optional — chapter-level grounding)
    # competitive
    authority: Optional[str] = None   # "WBPSC"
    exam:      Optional[str] = None   # "WBCS Prelims"
    topic:     Optional[str] = None   # "History of India"
    # it
    provider:  Optional[str] = None   # "AWS"
    count:     int = Field(default=5, ge=1, le=20)
    source_url: Optional[str] = None  # optional — raw content source
    source_pdf: Optional[str] = None  # optional — local PDF path

    @property
    def label(self) -> str:
        """Human-readable label for logging."""
        if self.segment == Segment.school:
            parts = [self.board, f"Class {self.class_num}", self.subject, self.chapter]
        elif self.segment == Segment.competitive:
            parts = [self.authority, self.exam, self.topic]
        else:
            parts = [self.provider, self.exam, self.topic]
        return " › ".join(p for p in parts if p)


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
    """Emitted as final JSON line to stdout — parsed by /api/pipeline/run."""
    type:       str = "result"
    pyqs:       int = 0
    notes:      int = 0
    errors:     int = 0
    elapsed_s:  float = 0.0
    queued_ids: list[str] = Field(default_factory=list)
