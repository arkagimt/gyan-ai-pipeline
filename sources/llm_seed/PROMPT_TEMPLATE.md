# Gemini-session prompt template for LLM-knowledge seeds

Reusable across AZ-900, CLF-C02, ACE, and any future vendor cert. Fill in
the 5 blanks (bracketed ALL-CAPS tokens) and paste the prompts verbatim
into a fresh Google AI Studio session (Gemini 2.5 Pro, free tier).

> **Why a template and not per-cert prompts?** The generation rules,
> schema constraints, and self-audit discipline are identical across
> certs. Only the exam metadata changes. A template keeps the quality
> bar identical cert-to-cert and makes 5-minute per-cert templating
> possible.

---

## Before you start

Open a **fresh** Gemini 2.5 Pro chat. Do not reuse a chat that has been
running other work — context pollution degrades MCQ quality noticeably
by message 3 or 4.

You will send **4 messages in order** within one chat session:

1. **Message 1** — System priming (rules, schema, output format). Expect
   a short acknowledgment from Gemini.
2. **Messages 2, 3, 4** — One per domain. Each asks for ~N/3 MCQs +
   3 notes + a coverage table + a SELF_AUDIT JSON block.

Save the three responses verbatim as `raw-round-1.json` — concatenated
into a single JSON array with 3 objects.

If any batch comes back short of its target count (token ceilings fire
around MCQ 22-25 for dense domains), open a follow-up message asking
for a regenerate-these patch list + top-up batch. Save as
`raw-round-2.json`.

Then: adapt `merge_seed.py` (copy AZ-900's — only 2 constants change)
and run it. Run the audit CLI. Ship.

---

## The 5 blanks

| Token | Example |
|---|---|
| `[EXAM_CODE]` | `AZ-900` / `CLF-C02` / `ACE` |
| `[EXAM_FULL_NAME]` | `Microsoft Azure Fundamentals` / `AWS Certified Cloud Practitioner` |
| `[OUTLINE_REVISION]` | `2024-09` / `2023-09` / `2024-03` |
| `[OUTLINE_URL]` | `https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/az-900` |
| `[DOMAIN_TABLE]` | See per-exam README for the domain list + weights |

---

## Message 1 — System priming (paste verbatim)

```
You are generating MCQs + study notes for an Indian education platform
(gyanagent.in) that serves [EXAM_FULL_NAME] ([EXAM_CODE]) candidates.
This is the [OUTLINE_REVISION] skills outline.

Authoritative outline: [OUTLINE_URL]

Hard rules (violating any = regenerate that MCQ):

  1. SCHEMA — each MCQ must be a JSON object with exactly these fields:
     question (string), options (object with A/B/C/D string values),
     correct ("A"|"B"|"C"|"D"), reasoning_process (string — why each
     option right/wrong), explanation (single sentence), difficulty
     ("easy"|"medium"|"hard"), bloom_level ("remember"|"understand"|
     "apply"|"analyze"), topic_tag (string — official sub-objective).

  2. STEM CLARITY — no "all of the above", no "none of the above",
     no double-negatives. Every distractor plausible to a weak student
     (a real thing that could be confused with the right answer).

  3. DOMAIN FIDELITY — topic_tag must be an exact sub-objective from
     the skills outline. No made-up sub-objectives.

  4. DIFFICULTY MIX per batch: ~30% easy / 50% medium / 20% hard.
     Bloom mix: at least 40% at apply or analyze level across the batch.

  5. ANTI-TRIVIA — test concepts and decision-making, not version
     numbers or UI ribbon layouts. The goal is exam readiness, not
     product-knowledge trivia.

  6. BEYOND-OUTLINE WATCHLIST — you may include MCQs on topics that
     sit just outside the skills outline BUT are known to appear on
     real proctored exams (e.g. in AZ-900's case: Azure Landing Zones,
     Cloud Adoption Framework). If you do, set topic_tag to the
     nearest in-outline sub-objective and mention the adjacency in
     reasoning_process so a human reviewer can flag it.

  7. NOTES — each batch includes 3 StudyNote objects covering distinct
     sub-objectives within that domain. Schema: topic_title, summary
     (2-3 sentences), key_concepts (list), formulas (list, usually
     empty for IT certs), important_facts (list), examples (list),
     memory_hooks (list, optional).

  8. OUTPUT FORMAT — one JSON object per domain, with keys:
     batch (single letter "A"/"B"/"C"), domain (full domain name),
     syllabus_revision_date ("[OUTLINE_REVISION]"), mcqs (array),
     notes (array), coverage_table (array of {sub_objective,
     mcq_count, notes_count}).

     Append a SELF_AUDIT JSON block AFTER the main object:
       { "self_audit": { "target_mcq_count": N, "actual_mcq_count": n,
                         "shortfall": N - n, "notes": "..." } }

When I send you the first domain request, reply with just that one
domain's JSON object (+ SELF_AUDIT). I'll send you the next domain in
my next message.

Ready?
```

Gemini will reply with something like "Ready. Send the first domain."

---

## Messages 2, 3, 4 — One per domain (paste verbatim, swap the italics)

```
Generate Batch [A/B/C] for [EXAM_CODE].

Domain: [DOMAIN_FULL_NAME_FROM_OUTLINE]
Target MCQ count: [33 or N*weight/100, whichever gives ~33]
Notes: 3 (one per major sub-objective within this domain)

Sub-objectives in scope (exactly as listed in the outline):
  - [SUB_OBJECTIVE_1]
  - [SUB_OBJECTIVE_2]
  - [SUB_OBJECTIVE_3]
  ...

Return: the JSON object + SELF_AUDIT block. Nothing else.
```

---

## Top-up prompt (only if a batch was short)

```
Batch [X] came back with [N] MCQs against a target of [TARGET]. Need
[SHORTFALL] more.

Also, these [N] MCQs from earlier batches need regeneration (reason in
brackets):
  - Batch [X] stem head "[FIRST_60_CHARS_OF_STEM]" — [REASON]
  - Batch [Y] stem head "[FIRST_60_CHARS_OF_STEM]" — [REASON]
  ...

Return:
  1. Batch "[X]-EXT" JSON object with [SHORTFALL] new MCQs +
     notes (optional) + coverage_table covering the SAME sub-objectives
     as the original (don't drift to new territory).
  2. Batch "FIXES" JSON object with the regenerated MCQs. Each FIX's
     question stem must match an existing MCQ closely enough that
     merge_seed.py can find the target by substring — if the rewrite
     changes the scenario entirely, note it explicitly in the SELF_AUDIT
     so we can add a hard-coded map entry.

Append SELF_AUDIT confirming final total hits [TOTAL_TARGET].
```

---

## Adapting `merge_seed.py`

Copy `az-900/merge_seed.py` → `<exam>/merge_seed.py`. Only two things
change:

```python
# 1. Beyond-outline watchlist (cert-specific — list of (stem_substring, reason))
BEYOND_OUTLINE_STEMS: list[tuple[str, str]] = [
    # ("distinctive stem substring", "why it's beyond outline + why we ship it"),
]

# 2. Hard-coded fix targets (only if Gemini rewrote a stem beyond substring-recognizability)
HARD_CODED_FIX_TARGETS: dict[int, tuple[str, int]] = {
    # fix_index_in_FIXES_batch: ("target_batch_letter", mcq_index_in_batch)
}
```

Everything else — the flatten order, the meta block shape, the domain
rollup math — stays identical and derives from whatever batch names
Gemini produced (A / B / B-EXT / C / C-EXT). This is deliberate: fewer
knobs, fewer places to drift.

---

## Then: audit

```
export GROQ_API_KEY=<your key>
python -m sources.llm_seed.audit <exam>
```

Zero issues → status flips to `"passed"`, seed clears pilot gate.
Any issues → status stays `"needs-review"`, audit report details each
finding for human fix.
