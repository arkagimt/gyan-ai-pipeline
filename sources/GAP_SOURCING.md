# Gap Sourcing — Where the Web Can't Give You Real Past Papers

**Paired with:** `OFFICIAL_SOURCES.md` (the gold/silver/IT-gold sources the bootstrap script handles automatically).

This file covers the **🥉 Bronze** (buy-from-authority) and **🟥 Gap** (no free source) rows. These require human effort Claude cannot automate — Arka-owned.

---

## 🚫 Dumps Policy (non-negotiable)

**Banned sources — never acquire, never ingest, never reference as truth:**

| Source type | Examples | Why banned |
|---|---|---|
| IT cert brain dumps | ExamTopics, CertCollection, BrainDump.com, leaked Udemy PDFs | Vendor NDAs + DMCA + CFAA exposure; AWS/Microsoft/Google actively hunt these; dump-trained cert holders get revoked; taints any future vendor partnership |
| Third-party PYQ compilations | Physics Wallah / BYJU'S / Unacademy paid PYQ books | Compilation copyright (original questions may be public but the compilation is not); ToS forbids redistribution; watermarked and detectable |
| Leaked exam papers (mid-session) | Telegram group dumps, scraped from proctor leak sites | Criminal liability (unauthorised access / receipt of stolen material); trivially identifiable; immediate fatal optics for investors + regulators |
| Paywalled textbook ripped PDFs | Z-Library, LibGen copies of Sybex/O'Reilly certification guides | Copyright infringement; publishers actively litigate edtech users |

**Rule in code review:** if a PR introduces a data source, a reviewer must be able to point to its row in `OFFICIAL_SOURCES.md` or this file. No row = no merge.

---

## 🥉 Bronze — Buy directly from the copyright-holding authority

These are legitimate purchases. You're paying the copyright holder (not a third-party reseller), usually at low cost, with an implicit or explicit educational-reuse permission.

### CISCE (ICSE + ISC)

**What to order:**
- Subject-wise Previous Year Papers — Class 10 ICSE — English, Math, Physics, Chemistry, Biology, History-Civics, Geography
- Subject-wise Previous Year Papers — Class 12 ISC — same subjects
- Specimen paper booklets (if not on free site)

**How to order:**
- `https://www.cisce.org/Publications.aspx` → catalogue + order form
- Or write to: `publications@cisce.org`
- Physical address: CISCE, Pragati House, 3rd Floor, 47-48 Nehru Place, New Delhi 110019

**Estimated cost:** ₹100–250 per subject per class. Budget ~₹3000 for a 10-subject sweep.

**After receipt:**
- OCR via `ocr_textbook.yml` (already in pipeline)
- Tag `source_type=board_publication`, `source_label="CISCE PYQ · ICSE Class 10 Physics · 2019–2023"`
- Push through standard ingest flow

### WBBSE (Madhyamik) — West Bengal Board of Secondary Education

**What to order:**
- Model question papers (latest published)
- Previous year Madhyamik papers — at least 5 years × 6 subjects (Bengali, English, Math, Physical Sci, Life Sci, Geography, History)

**How to order:**
- Walk-in: WBBSE Headquarters, Nivedita Bhawan, DJ-8, Sector II, Salt Lake, Bidhannagar, Kolkata 700091
- Phone: Check wbbse.wb.gov.in for current sales counter number
- Online publications store: browse https://wbbse.wb.gov.in (if active)

**Estimated cost:** ₹30–80 per booklet. Budget ~₹1500 total.

**Arka-local advantage:** You're in Bengal. A single weekend visit solves this.

### WBCHSE (HS — Higher Secondary) — West Bengal Council of Higher Secondary Education

**What to order:**
- Same pattern as WBBSE — model + past papers for HS (Class 11+12) subjects

**How to order:**
- Walk-in: WBCHSE Bhawan, Vidyasagar Bhavan, DJ-8 Sector II, Salt Lake
- Same complex as WBBSE — one visit covers both

### WBPSC (West Bengal Public Service Commission) — WBCS

**What to order:**
- WBCS Prelim + Main past papers compilations
- Subject-wise past papers for other WBPSC exams

**How to order:**
- WBPSC Sales Counter, 161-A, S.P. Mukherjee Road, Kolkata 700026
- Or via wbpsc.gov.in publications link

---

## 🟥 Gap — No free/paid official source; need teacher partnership or RTI

### Teacher outreach (Phase 6.2 seed)

**Target:** 2 WB Madhyamik teachers + 1 HS teacher + 1 CBSE Class 10 teacher in your network.

**What to ask for (explicit scope so teachers don't overshare student data):**
- Last 3–5 years of their **school-internal test papers** they authored (they own the copyright; they can license these to you)
- **Published model answers** to WBBSE/CBSE past papers (teacher's own explanations, not board's)
- **Chapter-wise question banks** they compiled for their own students

**What NOT to ask for:**
- Student answer scripts (privacy-regulated — even if teacher has them, they can't share)
- Actual WBBSE/CBSE past paper PDFs (teacher has them but can't redistribute — buy from board instead)
- Marking schemes from board exams (board IP, teachers redistribute this at their own risk — don't accept)

**Formal teacher onboarding:**
- Once Phase 6.2 (`/admin/teacher-upload`) ships, this becomes structured.
- Until then: email PDFs with explicit subject line `"Permission to ingest into Gyan AI pipeline with attribution as `source_type=teacher_upload`"` — reply = consent.
- Keep the email chain as audit trail.

### RTI (Right to Information) requests — state boards

Under the RTI Act 2005, state boards are "public authorities" and must disclose records on request for a small fee (₹10 fee + photocopy costs).

**Template text (fill in authority):**

> To the Public Information Officer,
> [WBBSE / WBCHSE / other state board],
> [Address]
>
> Under Section 6(1) of the Right to Information Act 2005, I request the following information:
>
> 1. Photocopies of question papers for [subject] administered in [exam name] for the years [YYYY–YYYY].
> 2. Corresponding marking schemes / model answers officially released by the Board.
>
> I understand the fee is ₹10 per application plus ₹2 per page of photocopy. I enclose a postal order for ₹10 and undertake to pay the photocopy charges on intimation.
>
> Purpose: educational content preparation for a tuition platform serving West Bengal students.
>
> [Name, address, contact, signature]

**Reality check:** RTI responses take 30 days. Not a sprint-speed option. Consider it for filling coverage gaps AFTER pilot launch, not before.

---

## 🔴 Alternative acquisition routes (if bronze + gap both stuck)

These are second-best options — use only after attempting the official routes above.

| Route | Legal status | When to use |
|---|---|---|
| **Buy physical published books from the board's own publication unit** (CBSE Publications / NCERT Publications) | ✅ Legal — buying from copyright holder | Preferred fallback for Bronze rows if online ordering fails |
| **Public library scans** (Asiatic Society Kolkata, National Library, state central libraries have past board paper archives) | ✅ Legal under library-fair-use provisions for personal academic use — BUT commercial pipeline reuse is grey. Consult counsel before ingesting | Only for historical years (>10 yrs old) where board no longer sells |
| **University question paper archives** (WBUHS, VU, BU past papers for Life Sci, Physics, Chemistry content) | ✅ Legal — university exam papers once administered become public | Relevant for NEET/JEE/GATE practice enrichment |
| **Old newspapers** (Anandabazar, Telegraph, Statesman publish Madhyamik papers day-after every year) | ✅ Fact-of-exam reporting is newspaper's own reporting — but you'd need physical newspaper archives. Very manual. | Deep-archive historical years only |

**Never use:** Telegram groups claiming "leaked past paper PDFs", PW/BYJU's paid content as source, YouTube channels' "last 10 year PYQ compilations" (almost always ripped from PW).

---

## 🧭 Recommended sequencing

**Week 1 (parallel with Day 5 seeding sprint):**
1. Download all Gold/Silver/IT-Gold sources automatically via `bootstrap_official_corpus.py`.
2. Email 3 teacher contacts asking for their self-authored internal test papers. Start now — teachers take days to respond.

**Week 2–3 (pilot running):**
3. Visit WBBSE/WBCHSE/WBPSC Bhawan sales counters — one Kolkata weekend afternoon.
4. Order CISCE publications online (expect 10–14 day shipping).

**Week 4 (post-pilot expansion):**
5. If state coverage still thin, file RTI applications for historical years.
6. Onboard teacher partners into `/admin/teacher-upload` once Phase 6.2 ships.

---

## Tracking

Each row below starts `[ ]` — tick when the source is in hand and ingested with correct `source_type` tag.

**🥉 Bronze purchases:**
- [ ] CISCE subject-wise PYQ booklets — ICSE Class 10 (Physics, Chem, Bio, Math, English, Hist-Civics, Geog)
- [ ] CISCE ISC Class 12 booklets (same subject set)
- [ ] WBBSE Madhyamik model papers (current year)
- [ ] WBBSE Madhyamik past papers — 2020, 2021, 2022, 2023, 2024 × 7 subjects
- [ ] WBCHSE HS past papers — 3 years × key subjects
- [ ] WBPSC WBCS Prelim + Main compilations

**🟥 Teacher outreach:**
- [ ] Madhyamik teacher #1 — named: ________ — contacted: _______ — received: _______
- [ ] Madhyamik teacher #2 — named: ________ — contacted: _______ — received: _______
- [ ] HS teacher #1 — named: ________ — contacted: _______ — received: _______
- [ ] CBSE Class 10 teacher #1 — named: ________ — contacted: _______ — received: _______

**Post-pilot RTI (track here):**
- [ ] RTI #1 — authority: ______ — filed: ______ — response due: ______
- [ ] RTI #2 — authority: ______ — filed: ______ — response due: ______
