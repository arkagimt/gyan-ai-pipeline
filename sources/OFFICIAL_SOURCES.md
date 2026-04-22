# Official Source Registry — Gyan AI Seed Corpus

**Purpose:** Tier-tagged list of legally reusable sources per authority. This replaces third-party ed-tech (PW / BYJU'S / Unacademy) + IT cert dumps (ExamTopics etc.) with pristine-provenance material from the authorities themselves.

**Related files:**
- `GAP_SOURCING.md` — action plan for tier-bronze/gap rows.
- `../scripts/bootstrap_official_corpus.py` — consumes this registry.
- `../models/schemas.py::SourceType` — enum each row maps into.

---

## Tier definitions

| Tier | Symbol | Meaning | Maps to `SourceType` |
|---|---|---|---|
| **Gold** | 🥇 | Actual past exam papers, officially hosted, free download | `official_past` |
| **Silver** | 🥈 | Sample/specimen/model papers + exemplar problems, officially hosted, free | `official_sample` / `ncert_exemplar` |
| **Bronze** | 🥉 | Buy directly from the copyright-holding authority (not third-party). Small fee, legal reuse. | `board_publication` |
| **IT-Gold** | 🏆 | Vendor-published exam guides with sample questions + docs + whitepapers | `vendor_sample` / `vendor_docs` |
| **Gap** | 🟥 | No free official source. Use teacher outreach or RTI (see GAP_SOURCING.md) | `teacher_upload` |

**URL confidence:** Each row is flagged `[VERIFIED]` (URL structure known stable) or `[CHECK]` (URL may have drifted — verify on first run). Treat `[CHECK]` as the top TODO of `bootstrap_official_corpus.py` first pass.

---

## Segment: School

### 🥈 NCERT Exemplar Problems (nationwide, de-facto prep standard)

| Class | Subject | URL root | Confidence |
|---|---|---|---|
| 6–12 | All subjects | https://ncert.nic.in/exemplar-problems.php | [VERIFIED] |
| 10 | Science | https://ncert.nic.in/textbook.php?jeep1=0-13 *(browse exemplar PDFs here)* | [CHECK] |
| 10 | Mathematics | https://ncert.nic.in/textbook.php?jeep1=0-13 *(math exemplar)* | [CHECK] |

**Legal status:** NCERT exemplars are Govt of India publications intended for educational reuse. Ingest freely, tag `source_type=ncert_exemplar`.

### 🥇/🥈 CBSE (cbseacademic.nic.in + cbse.gov.in)

| Content | URL root | Tier | Confidence |
|---|---|---|---|
| Sample Question Papers + marking schemes | https://cbseacademic.nic.in/SQP_CLASSX_2024-25.html | 🥈 | [CHECK — path changes annually] |
| Sample Question Papers + marking schemes | https://cbseacademic.nic.in/SQP_CLASSXII_2024-25.html | 🥈 | [CHECK] |
| Previous year board papers (Class 10/12) | https://www.cbse.gov.in/cbsenew/question-paper.html | 🥇/🥈 | [CHECK — coverage partial, last ~3 yrs most reliable] |

**Note:** CBSE's actual-past-paper hosting is patchy beyond 3 years back. Combine with NCERT exemplar for coverage depth.

### 🥇/🥉 CISCE (ICSE + ISC) — cisce.org

| Content | URL root | Tier | Confidence |
|---|---|---|---|
| Specimen papers (current syllabus) | https://www.cisce.org/SpecimenPaper.aspx | 🥈 | [VERIFIED] |
| Previous year papers | Not free online — order via CISCE Publications | 🥉 | [VERIFIED] |
| CISCE Publications ordering | https://www.cisce.org/Publications.aspx | 🥉 | [CHECK] |

**Action:** Buy 5–10 subject-wise PYQ booklets direct from CISCE. ~₹100–200 each. See `GAP_SOURCING.md`.

### 🥈/🟥 WBBSE (Madhyamik) — wbbse.wb.gov.in

| Content | URL root | Tier | Confidence |
|---|---|---|---|
| Model question papers | https://wbbse.wb.gov.in/ *(browse Publications section)* | 🥈 | [CHECK — site restructures often] |
| Actual past Madhyamik papers | Not comprehensively free online | 🟥 | [VERIFIED gap] |
| WBBSE Bhawan physical publications | Salt Lake sector III, Bidhannagar (walk-in or phone order) | 🥉 | [VERIFIED — Arka local to region] |

**Action:** WBBSE physical bookstore visit OR teacher outreach (2 Madhyamik teachers can scan last 5 years). See `GAP_SOURCING.md`.

### 🥈/🟥 WBCHSE (HS) — wbchse.wb.gov.in

Same pattern as WBBSE — model papers available online, actual papers require WBCHSE publications purchase or teacher scans.

---

## Segment: Entrance (national exams)

### 🥇 JEE Main — NTA (jeemain.nta.nic.in)

| Content | URL root | Tier | Confidence |
|---|---|---|---|
| Session-wise past papers + answer keys | https://jeemain.nta.nic.in/ *(Previous Question Papers section)* | 🥇 | [VERIFIED — NTA archives every session] |
| Information bulletin + exam pattern | https://jeemain.nta.nic.in/information-bulletin/ | — | [CHECK] |

**Volume estimate:** ~400+ MCQs per session × 3–4 sessions/year × 5+ years = 6000+ raw questions across Physics/Chemistry/Math.

### 🥇 NEET UG — NTA (neet.nta.nic.in)

| Content | URL root | Tier | Confidence |
|---|---|---|---|
| Past papers + answer keys | https://neet.nta.nic.in/ *(Previous Question Papers)* | 🥇 | [VERIFIED] |

### 🥇 WBJEE — wbjeeb.nic.in

| Content | URL root | Tier | Confidence |
|---|---|---|---|
| Previous year question papers | https://wbjeeb.nic.in/ *(Question Papers / Previous Papers section)* | 🥇 | [CHECK] |

### 🥇 GATE — Hosted by rotating IIT (gate.iitb.ac.in, gate.iisc.ac.in, etc.)

| Content | URL root | Tier | Confidence |
|---|---|---|---|
| Past papers by discipline (20+ years) | https://gate.iitk.ac.in/, https://gate.iisc.ac.in/, rotates annually | 🥇 | [CHECK — host rotates] |
| IIT Kanpur archive (historical) | http://gate.iitk.ac.in/gate2024/old_qp/ | 🥇 | [CHECK] |

**Note:** Each year's host IIT mirrors a past-paper archive. Check https://www.gate.iisc.ac.in/ → "Previous Years' Question Papers".

---

## Segment: Recruitment

### 🥇 UPSC — upsc.gov.in (Civil Services Exam)

| Content | URL root | Tier | Confidence |
|---|---|---|---|
| Previous year Prelim papers (10+ years) | https://upsc.gov.in/examinations/previous-question-papers | 🥇 | [VERIFIED — rock solid] |
| Previous year Mains papers | Same URL, per-paper split | 🥇 | [VERIFIED] |
| Answer keys (post-exam release) | https://upsc.gov.in/examinations/question-papers-and-answer-keys-of-exams | 🥇 | [CHECK] |

**This is the single strongest free source in the entire registry.** Treat as top priority for bootstrap.

### 🥇 SSC — ssc.nic.in

| Content | URL root | Tier | Confidence |
|---|---|---|---|
| CGL / CHSL / MTS previous papers | https://ssc.nic.in/ *(Previous Year Papers section)* | 🥇 | [CHECK — coverage varies by tier] |

### 🥇/🥈 IBPS / SBI / RBI

| Content | URL root | Tier | Confidence |
|---|---|---|---|
| IBPS previous papers | https://www.ibps.in/ | 🥇/🥈 | [CHECK] |
| SBI recruitment papers | https://sbi.co.in/careers | 🥇/🥈 | [CHECK] |
| RBI Grade B papers | https://opportunities.rbi.org.in/ | 🥇/🥈 | [CHECK] |

### 🥇/🥈 WBPSC — wbpsc.gov.in (WBCS)

| Content | URL root | Tier | Confidence |
|---|---|---|---|
| WBCS previous papers | https://wbpsc.gov.in/ *(Archive / Previous Papers)* | 🥈 | [CHECK] |
| Physical publications | WBPSC Bhawan sales counter | 🥉 | [VERIFIED] |

### 🥇 Railway (RRB) — rrbcdg.gov.in (and zone-specific)

RRB past papers are aggregated across zonal sites. Coverage is uneven — worth a narrow first pass.

---

## Segment: IT Certifications (international) — vendor-official only

> **No dumps. Ever.** See MASTER_TODO Day 1.75 policy and `GAP_SOURCING.md` "Dumps policy" section. This is not negotiable — violates NDAs, disqualifies Gyan AI from vendor partnerships, and risks student cert invalidation.

### 🏆 AWS (aws.amazon.com/certification)

| Content | URL root | SourceType |
|---|---|---|
| Exam guides (PDF) per cert — includes 5–10 official sample questions each | https://aws.amazon.com/certification/certification-prep/ (each cert has its own page) | `vendor_sample` |
| Sample question PDFs (separate download) | Linked from each cert page | `vendor_sample` |
| AWS Documentation (unlimited source material) | https://docs.aws.amazon.com/ | `vendor_docs` |
| AWS Whitepapers | https://aws.amazon.com/whitepapers/ | `vendor_docs` |
| AWS Skill Builder (free tier practice assessments) | https://skillbuilder.aws/ | `vendor_sample` |
| AWS Well-Architected Framework | https://docs.aws.amazon.com/wellarchitected/ | `vendor_docs` |

**IT_TREE certs in scope:** Cloud Practitioner (CLF-C02), SAA-C03, DVA-C02. Per cert: exam guide has 10 sample Qs + AWS publishes a longer sample question PDF.

### 🏆 Microsoft / Azure (learn.microsoft.com)

| Content | URL root | SourceType |
|---|---|---|
| Certification exam skills outlines (sample questions embedded) | https://learn.microsoft.com/en-us/credentials/certifications/ | `vendor_sample` |
| Practice Assessments (free, official) | https://learn.microsoft.com/en-us/certifications/exams/ *(per exam page)* | `vendor_sample` |
| Microsoft Learn free learning paths (knowledge checks) | https://learn.microsoft.com/en-us/training/ | `vendor_sample` |
| Azure Documentation | https://learn.microsoft.com/en-us/azure/ | `vendor_docs` |
| Cloud Adoption Framework | https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ | `vendor_docs` |

**IT_TREE certs in scope:** AZ-900, AZ-104.

### 🏆 Google Cloud (cloud.google.com/learn)

| Content | URL root | SourceType |
|---|---|---|
| Exam guides per cert | https://cloud.google.com/learn/certification *(each cert has its own page)* | `vendor_sample` |
| Sample question sets | Linked from each cert page | `vendor_sample` |
| Google Cloud Skills Boost (free tier — practice) | https://www.cloudskillsboost.google/ | `vendor_sample` |
| Google Cloud Documentation | https://cloud.google.com/docs | `vendor_docs` |
| GCP Architecture Framework | https://cloud.google.com/architecture/framework | `vendor_docs` |

**IT_TREE certs in scope:** Associate Cloud Engineer, Professional Data Engineer.

### 🏆 Cisco (cisco.com/go/certifications)

| Content | URL root | SourceType |
|---|---|---|
| Exam topics (blueprint) per cert | https://learningnetwork.cisco.com/s/topics/ *(per cert)* | `vendor_sample` |
| Cisco Learning Network practice questions (free tier) | https://learningnetwork.cisco.com/ | `vendor_sample` |
| Cisco DevNet / docs | https://developer.cisco.com/, https://www.cisco.com/c/en/us/support/index.html | `vendor_docs` |

**IT_TREE certs in scope:** CCNA.

---

## What to do first (ordered execution)

Rank by (coverage-value × confidence × legal-safety):

1. **UPSC Prelims** — download all 10 years of papers from upsc.gov.in/examinations/previous-question-papers. Rock-solid 🥇. Expected raw yield: ~2000 questions.
2. **NCERT Exemplars Class 10 Science + Math + SST** — download from ncert.nic.in/exemplar-problems.php. 🥈. Expected raw yield: ~500 problems per class per subject.
3. **JEE Main** — NTA archive, last 3 years, all sessions. 🥇. Expected yield: ~4000 questions across Physics/Chem/Math.
4. **NEET UG** — NTA archive, last 3 years. 🥇. Expected yield: ~2000 questions.
5. **CBSE SQPs + marking schemes** — cbseacademic.nic.in current-year SQPs for Class 10 + 12. 🥈.
6. **AWS SAA-C03 exam guide + sample question PDF + Well-Architected whitepaper** — aws.amazon.com/certification. 🏆. Expected yield: ~30 sample questions + unlimited doc-grounded regeneration.
7. **Azure AZ-900 exam skills outline + free practice assessment** — learn.microsoft.com. 🏆.
8. **GCP Associate Cloud Engineer exam guide + sample questions** — cloud.google.com/learn/certification. 🏆.
9. **WBBSE Madhyamik** — teacher outreach for scans (see `GAP_SOURCING.md`) + physical WBBSE Bhawan visit for official publications.
10. **CISCE/ICSE** — order subject-wise PYQ compilations from cisce.org/Publications.aspx.

After steps 1–5 alone: ~8000 raw exam questions ingestible through the pipeline. More than enough for SC-001 (500 live MCQs) even accounting for pipeline filter-out.

---

## What bootstrap_official_corpus.py does with this registry

For each Tier-Gold + Tier-Silver + IT-Gold row in this file:
1. Download PDF/HTML to `/tmp/gyan_corpus/<segment>/<authority>/<year>/<subject>.pdf`.
2. Fire `ocr_textbook.yml` workflow (or local OCR fallback) to extract text.
3. Fire `ingest_*.yml` per topic-slice, passing `--source-pdf` or `--source-url`.
4. Stamp `package.metadata["provenance_tier"]` with the correct `SourceType` enum value.
5. Stamp `package.metadata["source_label"]` with human-readable (e.g. "UPSC CSE Prelim Paper 1 · 2023").
6. `supabase_loader` forwards both into `raw_data.metadata.*` per the Day 1 fix.
7. Admin triage shows the provenance tier inline; web Trust Chip uses the strongest-tier badge for that MCQ.

Tier-Bronze rows (board publications requiring purchase) and Tier-Gap rows (teacher outreach) are listed in `GAP_SOURCING.md` with explicit action items.
