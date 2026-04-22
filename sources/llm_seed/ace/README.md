# ACE — Google Cloud Associate Cloud Engineer

**Exam code:** ACE (sometimes written as GCP-ACE)
**Full name:** Associate Cloud Engineer
**Outline revision:** 2024-03 (current as of 2026-04)
**Outline URL:** <https://cloud.google.com/learn/certification/guides/cloud-engineer>

## Domain split (fill into PROMPT_TEMPLATE)

| Batch | Domain                                          | Weight | Target MCQs |
|-------|-------------------------------------------------|--------|-------------|
| A     | Setting up a cloud solution environment         | ~17.5% | 18          |
| B     | Planning and configuring a cloud solution       | ~17.5% | 18          |
| C     | Deploying and implementing a cloud solution     | ~25%   | 25          |
| D     | Ensuring successful operation of a cloud solution | ~20% | 20          |
| E     | Configuring access and security                 | ~20%   | 19          |

**Total target: 100 MCQs.** GCP publishes section percentages as
qualitative bands ("approximately X%") rather than exact weights, so
the numbers above are our best read. Adjust if they refresh the
guide. ACE has 5 domains → 6-message Gemini session.

## Sub-objectives to list inline (from exam guide v1.2)

### Domain A — Setting up a cloud solution environment
- 1.1 Setting up cloud projects and accounts
- 1.2 Managing billing configuration
- 1.3 Installing and configuring the command-line interface (CLI)

### Domain B — Planning and configuring a cloud solution
- 2.1 Planning and estimating GCP product use using the Pricing Calculator
- 2.2 Planning and configuring compute resources
- 2.3 Planning and configuring data storage options
- 2.4 Planning and configuring network resources

### Domain C — Deploying and implementing a cloud solution
- 3.1 Deploying and implementing Compute Engine resources
- 3.2 Deploying and implementing Google Kubernetes Engine resources
- 3.3 Deploying and implementing Cloud Run and Cloud Functions resources
- 3.4 Deploying and implementing data solutions
- 3.5 Deploying and implementing networking resources
- 3.6 Deploying a solution using Cloud Marketplace
- 3.7 Implementing resources via infrastructure as code

### Domain D — Ensuring successful operation of a cloud solution
- 4.1 Managing Compute Engine resources
- 4.2 Managing Google Kubernetes Engine resources
- 4.3 Managing Cloud Run and Cloud Functions resources
- 4.4 Managing storage and database solutions
- 4.5 Managing networking resources
- 4.6 Monitoring and logging

### Domain E — Configuring access and security
- 5.1 Managing Identity and Access Management (IAM)
- 5.2 Managing service accounts
- 5.3 Viewing audit logs

## Beyond-outline watchlist (for `merge_seed.py`)

ACE is the dirtiest of the three because GCP exams lean hard on
operational scenarios that reference services only mentioned in
passing in the guide:

- **gcloud command flags** — students see specific `gcloud` invocations
  on the exam. The guide says "installing and configuring the CLI" but
  doesn't list which flags are fair game. MCQs testing exact flags are
  technically beyond-outline but unavoidable.
- **Organization policies vs IAM policies** — the distinction is tested
  but the guide only lists "IAM" as the sub-objective.
- **VPC peering vs Shared VPC** — consistently tested but neither is
  named in the guide's networking sub-objective.

Seed `BEYOND_OUTLINE_STEMS` accordingly once the Gemini output lands.

## Taxonomy registration for `audit.py`

Add to `EXAM_TAXONOMIES`:

```python
"ace": TaxonomySlice(
    segment  = Segment.it,
    provider = "Google Cloud",
    exam     = "ACE",
    topic    = "Google Cloud Associate Cloud Engineer",
    count    = 1,
),
```

## Checklist

- [ ] Fresh Gemini 2.5 Pro session
- [ ] PROMPT_TEMPLATE Message 1 sent (priming)
- [ ] Batches A / B / C / D / E generated → `raw-round-1.json`
- [ ] Top-up round if any batch short → `raw-round-2.json`
- [ ] Copy `az-900/merge_seed.py`, edit flatten order (`A → B → B-EXT → C → C-EXT → D → D-EXT → E → E-EXT`) + watchlist + fix targets
- [ ] `python merge_seed.py` → `ace-v1.json`
- [ ] Register taxonomy in `audit.py`
- [ ] `python -m sources.llm_seed.audit ace`
- [ ] Commit + push when verdict is `"passed"`
