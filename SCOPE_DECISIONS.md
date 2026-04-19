# Gyan AI — Scope Decisions

**Last updated:** 2026-04-19  
**Authority:** Arka (project lead)

---

## Board / Curriculum Inclusion Status

| Board / System | Status | Rationale |
|---|---|---|
| **CBSE** | ✅ IN | National board, ~60% of Indian students. Priority data source. |
| **ICSE / ISC** | ✅ IN | National board, strong in WB/metros. Used by significant minority. |
| **WBBSE** | ✅ IN | WB state board (Class 6–10 Madhyamik). Core launch market. |
| **WBCHSE** | ✅ IN | WB state board (Class 11–12 Uccha Madhyamik). Core launch market. |
| **WBBPE** | ✅ IN | WB primary board (Class 1–5). Extends WB coverage. |
| **NIOS** | ✅ IN (future) | National Institute of Open Schooling. Growing rapidly with remote learners and rural students who dropped out of formal schools. Future priority. |
| **Madrasa boards** | ❌ OUT | Different pedagogical framework (religious + secular combined). Requires separate content pipeline and domain expertise we don't currently have. Does not align with the general-purpose competitive exam / board exam vertical. May revisit with specialist partners. |
| **Anglo-Indian boards** | ⏸ PARKED | Tiny user base (~200 schools nationally, declining). Not worth the taxonomy overhead at this stage. |
| **IB (International Baccalaureate)** | ⏸ PARKED | International curriculum, English-only, affluent urban audience. Doesn't align with WB-first rural-inclusive mission. May add as a separate `international` segment later. |
| **Cambridge IGCSE** | ⏸ PARKED | Same reasoning as IB. |
| **UP Board (UPMSP)** | 🔜 FUTURE | Second-largest state board by enrollment. After WB ships. |
| **Maharashtra (MSBSHSE)** | 🔜 FUTURE | Third-largest. After WB + UP. |
| **Tamil Nadu (TN Board)** | 🔜 FUTURE | Regional priority. Requires Tamil language support. |
| **Karnataka (KSEEB)** | 🔜 FUTURE | Regional priority. Requires Kannada language support. |

---

## Entrance Exam Scope

| Exam | Scope | Status |
|---|---|---|
| JEE Main / Advanced | Central | ✅ IN — `ENTRANCE_TREE` |
| NEET UG / PG | Central | ✅ IN — `ENTRANCE_TREE` |
| CAT / XAT / MAT | Central | ✅ IN — `ENTRANCE_TREE` |
| GATE | Central | ✅ IN — `ENTRANCE_TREE` |
| CUET | Central | ✅ IN — `ENTRANCE_TREE` |
| CLAT | Central | ✅ IN — `ENTRANCE_TREE` |
| NDA | Central | ✅ IN — `ENTRANCE_TREE` |
| WBJEE | State (WB) | ✅ IN — `ENTRANCE_TREE` (WB-first) |

---

## Recruitment Exam Scope

| Authority | Scope | Status |
|---|---|---|
| WBPSC (WBCS, Misc, Clerkship) | State (WB) | ✅ IN — `RECRUITMENT_TREE` |
| WBSSC (TET, SLST) | State (WB) | ✅ IN — `RECRUITMENT_TREE` |
| SSC (CGL, CHSL, MTS) | Central | ✅ IN — `RECRUITMENT_TREE` |
| UPSC (Prelims) | Central | ✅ IN — `RECRUITMENT_TREE` |
| Railway (NTPC, Group D) | Central | ✅ IN — `RECRUITMENT_TREE` |

---

## IT Certification Scope

All IT certifications are `scope = international`, `nature = cert`. Region-agnostic, forced English.

---

## Notes

- "IN" means active data pipeline feeding is expected.
- "PARKED" means no engineering work planned; may revisit if user demand materializes.
- "FUTURE" means engineering work is planned but sequenced after WB launch.
- All decisions can be revisited. Edit this file when they change.
