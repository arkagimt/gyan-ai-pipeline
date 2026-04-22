# CLF-C02 — AWS Certified Cloud Practitioner

**Exam code:** CLF-C02
**Full name:** AWS Certified Cloud Practitioner
**Outline revision:** 2023-09 (current as of 2026-04)
**Outline URL:** <https://d1.awsstatic.com/training-and-certification/docs-cloud-practitioner/AWS-Certified-Cloud-Practitioner_Exam-Guide.pdf>

## Domain split (fill into PROMPT_TEMPLATE)

| Batch | Domain                                 | Weight | Target MCQs |
|-------|----------------------------------------|--------|-------------|
| A     | Cloud Concepts                         | 24%    | 24          |
| B     | Security and Compliance                | 30%    | 30          |
| C     | Cloud Technology and Services          | 34%    | 34          |
| D     | Billing, Pricing, and Support          | 12%    | 12          |

**Total target: 100 MCQs.** Note: CLF-C02 has 4 domains (vs AZ-900's 3),
so the Gemini session runs 5 messages (priming + 4 domain batches) rather
than 4. Update `merge_seed.py` flatten order to `A → B → B-EXT → C →
C-EXT → D → D-EXT`.

## Sub-objectives to list inline (from exam guide v1.3)

### Domain A — Cloud Concepts (24%)
- 1.1 Define the benefits of the AWS Cloud
- 1.2 Identify design principles of the AWS Cloud
- 1.3 Understand the benefits of and strategies for migration to the AWS Cloud
- 1.4 Understand concepts of cloud economics

### Domain B — Security and Compliance (30%)
- 2.1 Understand the AWS shared responsibility model
- 2.2 Understand AWS Cloud security, governance, and compliance concepts
- 2.3 Identify AWS access management capabilities
- 2.4 Identify components and resources for security

### Domain C — Cloud Technology and Services (34%)
- 3.1 Define methods of deploying and operating in the AWS Cloud
- 3.2 Define the AWS global infrastructure
- 3.3 Identify AWS compute services
- 3.4 Identify AWS database services
- 3.5 Identify AWS network services
- 3.6 Identify AWS storage services
- 3.7 Identify AWS artificial intelligence (AI) and machine learning (ML) services
- 3.8 Identify services from other in-scope AWS service categories

### Domain D — Billing, Pricing, and Support (12%)
- 4.1 Compare AWS pricing models
- 4.2 Understand resources for billing, budget, and cost management
- 4.3 Identify AWS technical resources and AWS Support options

## Beyond-outline watchlist (for `merge_seed.py`)

CLF-C02 is unusually clean because AWS publishes detailed exam guides,
but these adjacents do show up on real exams:

- **AWS Well-Architected Framework pillars** — six pillars tested more
  often than the Domain A weight suggests. In-scope for Domain A as
  "design principles" but the framework itself is rarely named there.
- **AWS Organizations SCPs (Service Control Policies)** — tested in
  governance contexts under Domain B but SCPs are named only once in
  the exam guide.

Seed `BEYOND_OUTLINE_STEMS` in `merge_seed.py` with one stem substring
per watchlist item actually used in the Gemini output.

## Taxonomy registration for `audit.py`

Add to `EXAM_TAXONOMIES`:

```python
"clf-c02": TaxonomySlice(
    segment  = Segment.it,
    provider = "AWS",
    exam     = "CLF-C02",
    topic    = "AWS Certified Cloud Practitioner",
    count    = 1,
),
```

## Checklist

- [ ] Fresh Gemini 2.5 Pro session
- [ ] PROMPT_TEMPLATE Message 1 sent (priming)
- [ ] Batch A generated → save to `raw-round-1.json`
- [ ] Batch B generated → append
- [ ] Batch C generated → append
- [ ] Batch D generated → append
- [ ] Top-up round 2 if any batch short → `raw-round-2.json`
- [ ] Copy `az-900/merge_seed.py`, edit flatten order + watchlist + fix targets
- [ ] `python merge_seed.py` → `clf-c02-v1.json`
- [ ] Register taxonomy in `audit.py`
- [ ] `python -m sources.llm_seed.audit clf-c02`
- [ ] Commit + push when verdict is `"passed"`
