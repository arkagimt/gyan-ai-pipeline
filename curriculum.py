"""
Gyan AI — Curriculum Data
==========================
Single source of truth for all curriculum constants used across the pipeline.

Scope decisions: see SCOPE_DECISIONS.md at this repo root for board
inclusion/exclusion rationale (NIOS=IN, Madrasa=OUT, IB/IGCSE=PARKED, etc.)

Consumers:
  - agents/ganak.py      (topic priority analysis)
  - admin/streamlit_app.py (coverage map + smart pipeline UI)
  - gyan_pipeline.py      (taxonomy validation)

Structure:
  CURRICULUM         — school boards   : {board: {class_num: [subjects]}}
  CLASS_PRIORITY     — class urgency   : {class_num: priority_int}
  ENTRANCE_TREE      — entrance exams  : {authority: {exam: [topics]}}
  RECRUITMENT_TREE   — recruitment     : {authority: {exam: [topics]}}
  COMPETITIVE_TREE   — combined alias  : ENTRANCE_TREE + RECRUITMENT_TREE (backward compat)
  IT_TREE            — IT certs        : {provider: {cert: [domains]}}
  BENGALI_BOARDS     — boards needing Bengali-language MCQs
"""

from __future__ import annotations

# ── School curriculum ─────────────────────────────────────────────────────────
# Scope decisions:
#   ✅ IN: CBSE, ICSE, WBBSE, WBCHSE, NIOS (future)
#   ❌ OUT: Madrasa boards (different pedagogical framework)
#   ⏸ PARKED: Anglo-Indian boards, IB/Cambridge IGCSE
#   🔜 FUTURE: UP, Maharashtra, Tamil Nadu, Karnataka state boards
# See SCOPE_DECISIONS.md for full rationale.

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

# Higher value = higher urgency to fill first (board exam classes rank top)
CLASS_PRIORITY: dict[int, int] = {
    10: 10, 12: 9, 9: 8, 11: 7, 8: 6, 7: 5,
    6:  4,  5:  3, 4: 2, 3:  2, 2: 1, 1:  1,
}

# These boards require Bengali-language MCQs (used by llm.py routing)
BENGALI_BOARDS: set[str] = {"WBBSE", "WBCHSE"}

# Target MCQs per (board, class, subject) slot before moving on
MCQ_TARGET_PER_SLOT: int = 10


# ── Entrance exams (national-level, not govt recruitment) ─────────────────────
# JEE/NEET/CAT etc. — these are entrance exams for higher education / courses,
# NOT government job recruitment. Shared across all states (central scope).

ENTRANCE_TREE: dict[str, dict[str, list[str]]] = {
    "NTA": {
        "JEE Main": [
            "Mathematics — Algebra & Trigonometry",
            "Mathematics — Calculus & Coordinate Geometry",
            "Physics — Mechanics & Waves",
            "Physics — Electromagnetism & Optics",
            "Physics — Modern Physics & Thermodynamics",
            "Chemistry — Physical Chemistry",
            "Chemistry — Organic Chemistry",
            "Chemistry — Inorganic Chemistry",
        ],
        "JEE Advanced": [
            "Mathematics — Advanced Algebra",
            "Mathematics — Differential Equations & Calculus",
            "Physics — Classical Mechanics",
            "Physics — Electrodynamics & Optics",
            "Chemistry — Physical & Organic Combined",
            "Chemistry — Inorganic & Analytical",
        ],
        "NEET UG": [
            "Physics — Mechanics",
            "Physics — Electrostatics & Magnetism",
            "Physics — Optics & Modern Physics",
            "Chemistry — Physical Chemistry",
            "Chemistry — Organic Chemistry",
            "Chemistry — Inorganic Chemistry",
            "Biology — Botany (Plant Physiology, Genetics)",
            "Biology — Zoology (Human Physiology, Evolution)",
        ],
        "CUET UG": [
            "General Awareness & Current Affairs",
            "English Language",
            "Quantitative Aptitude",
            "Logical Reasoning",
            "Domain Subjects (varies)",
        ],
    },
    "IIM": {
        "CAT": [
            "Quantitative Aptitude",
            "Data Interpretation & Logical Reasoning",
            "Verbal Ability & Reading Comprehension",
        ],
        "XAT": [
            "Verbal & Logical Ability",
            "Decision Making",
            "Quantitative Ability & Data Interpretation",
            "General Knowledge",
        ],
    },
    "GATE": {
        "GATE (CS/IT)": [
            "Engineering Mathematics",
            "Digital Logic & Computer Organization",
            "Data Structures & Algorithms",
            "Operating Systems",
            "Databases",
            "Computer Networks",
            "Theory of Computation",
            "Compiler Design",
        ],
        "GATE (ECE)": [
            "Engineering Mathematics",
            "Networks, Signals & Systems",
            "Electronic Devices & Circuits",
            "Analog & Digital Circuits",
            "Communications & Electromagnetics",
        ],
    },
    "WBJEE": {
        "WBJEE (Engineering)": [
            "Mathematics — Algebra & Trigonometry",
            "Mathematics — Calculus & Coordinate Geometry",
            "Physics — Mechanics & Thermodynamics",
            "Physics — Electromagnetism & Optics",
            "Chemistry — Physical & Organic",
            "Chemistry — Inorganic",
        ],
    },
    "NDA": {
        "NDA (Mathematics)": [
            "Algebra",
            "Matrices & Determinants",
            "Trigonometry",
            "Calculus",
            "Statistics & Probability",
        ],
        "NDA (General Ability)": [
            "Physics",
            "Chemistry",
            "General Science",
            "History",
            "Geography",
            "Current Affairs",
        ],
    },
    "CLAT": {
        "CLAT UG": [
            "English Language",
            "Current Affairs & General Knowledge",
            "Legal Reasoning",
            "Logical Reasoning",
            "Quantitative Techniques",
        ],
    },
}


# ── Recruitment exams (govt job recruitment) ──────────────────────────────────
# WBPSC/SSC/UPSC/Railway etc. — these are for government job recruitment.
# State-level exams are scoped by region; central exams (SSC, UPSC, Railway)
# are shared across all states.

RECRUITMENT_TREE: dict[str, dict[str, list[str]]] = {
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

# Backward-compatible combined alias — scripts referencing COMPETITIVE_TREE still work
COMPETITIVE_TREE: dict[str, dict[str, list[str]]] = {**ENTRANCE_TREE, **RECRUITMENT_TREE}


# ── IT certifications ─────────────────────────────────────────────────────────

#
# IT_TREE keys MUST match what `sources/llm_seed/load_to_supabase.py` writes to
# `pyq_bank_v2.question_payload`:
#   - provider: matches `TaxonomySlice.provider` exactly (e.g. "Microsoft",
#     "AWS", "Google Cloud", "Cisco" — note: NOT "Google", which was the old
#     IT_TREE key — fixed in Wave 4 / 2026-04-26).
#   - exam:     short code matching `TaxonomySlice.exam` ("AZ-900", "AI-900",
#     "DP-900", "AZ-104", "DP-600", etc.). Was previously verbose names like
#     "AZ-900 Azure Fundamentals" → coverage lookups always returned 0.
#   - topic:    the loader writes the first-MCQ-of-batch's `topic_tag` for
#     all MCQs in a 25-batch package (see load_to_supabase.py:174). With
#     100 MCQs / 25 batch = 4 distinct topic_tags actually persist per exam.
#     The lists below enumerate the topic_tag values present in each
#     committed seed (extracted by inspecting `mcqs[*].topic_tag` from each
#     `<exam>-v1.json`). Topics not in the first-of-batch position will not
#     match coverage — that's a known loader sparsity issue, queued as
#     Wave 4.5: per-MCQ topic taxonomy in load_to_supabase.py.
#
IT_TREE: dict[str, dict[str, list[str]]] = {
    "AWS": {
        # No AWS seeds loaded to Supabase yet — these are the official
        # blueprint domain names from each exam guide. Coverage will show 0
        # until AWS seeds are generated. After Wave 2.8, retired SOA-C02 and
        # MLS-C01 are dropped; CloudOps Engineer (SOA-C03), ML Engineer
        # Associate (MLA-C01), and AI Practitioner (AIF-C01) added.
        "CLF-C02": [
            "Cloud Concepts",
            "Security and Compliance",
            "Cloud Technology and Services",
            "Billing, Pricing, and Support",
        ],
        "SAA-C03": [
            "Design Secure Architectures",
            "Design Resilient Architectures",
            "Design High-Performing Architectures",
            "Design Cost-Optimized Architectures",
        ],
        "DVA-C02": [
            "Development with AWS Services",
            "Security",
            "Deployment",
            "Troubleshooting and Optimization",
        ],
        "SOA-C03": [
            "Monitoring, Logging, and Remediation",
            "Reliability and Business Continuity",
            "Deployment, Provisioning, and Automation",
            "Security and Compliance",
            "Networking and Content Delivery",
            "Cost and Performance Optimization",
        ],
        "MLA-C01": [
            "Data Preparation for ML",
            "ML Model Development",
            "Deployment and Orchestration of ML Workflows",
            "ML Solution Monitoring, Maintenance, and Security",
        ],
        "AIF-C01": [
            "Fundamentals of AI and ML",
            "Fundamentals of Generative AI",
            "Applications of Foundation Models",
            "Guidelines for Responsible AI",
            "Security, Compliance, and Governance for AI Solutions",
        ],
    },
    "Microsoft": {
        # All five Microsoft seeds loaded to Supabase 2026-04-22 → 2026-04-26.
        # Topics are the actual `topic_tag` values present in each seed
        # JSON. With 25-batch packaging, ~4 of these match coverage data
        # per exam; the rest will show 0 until Wave 4.5 lands.
        "AZ-900": [
            "Describe cloud computing",
            "Describe the benefits of using cloud services",
            "Describe cloud service types",
            "Describe the core architectural components of Azure",
            "Describe Azure compute and networking services",
            "Describe Azure storage services",
            "Describe Azure identity, access, and security",
            "Describe cost management in Azure",
            "Describe features and tools in Azure for governance and compliance",
            "Describe features and tools for managing and deploying Azure resources",
            "Describe monitoring tools in Azure",
        ],
        "AI-900": [
            "Identify features of common AI workloads",
            "Identify guiding principles for responsible AI",
            "Describe core machine learning concepts",
            "Identify common machine learning techniques",
            "Describe Azure Machine Learning capabilities",
            "Identify common types of computer vision solutions",
            "Identify Azure tools and services for computer vision tasks",
            "Identify features of common NLP workload scenarios",
            "Identify Azure tools and services for NLP workloads",
            "Identify features of generative AI solutions",
            "Identify generative AI services and capabilities in Microsoft Azure",
        ],
        "DP-900": [
            "Identify roles and responsibilities for data workloads",
            "Describe common data workloads",
            "Describe ways to represent data",
            "Identify options for data storage",
            "Describe relational concepts",
            "Describe relational Azure data services",
            "Describe capabilities of Azure storage",
            "Describe capabilities and features of Azure Cosmos DB",
            "Describe common elements of large-scale analytics",
            "Describe considerations for real-time data analytics",
            "Describe data visualization in Microsoft Power BI",
        ],
        "AZ-104": [
            "Manage Microsoft Entra users and groups",
            "Manage access to Azure resources",
            "Manage Azure subscriptions and governance",
            "Configure Azure Files and Azure Blob Storage",
            "Configure Azure Storage security",
            "Configure access to storage",
            "Create and configure VMs",
            "Configure and manage virtual networks",
            "Configure secure access to virtual networks",
            "Configure load balancing",
            "Monitor virtual networking",
            "Automate deployment of resources by using ARM templates or Bicep files",
            "Provision and manage containers",
            "Create and configure Azure App Service",
            "Monitor resources by using Azure Monitor",
            "Implement backup and recovery",
        ],
        "DP-600": [
            "Plan a data analytics environment",
            "Implement and manage a data analytics environment",
            "Manage the analytics development lifecycle",
            "Get data from data sources",
            "Transform data",
            "Design and build semantic models",
            "Implement and manage semantic models",
            "Optimize enterprise-scale semantic models",
            "Perform exploratory analytics",
            "Use Microsoft Fabric to expand data analytics capabilities",
        ],
        # DP-700 in flight 2026-04-26 — taxonomy ready, content arriving.
    },
    "Google Cloud": {
        # Was "Google" → renamed to match TaxonomySlice convention. No GCP
        # seeds loaded yet; topics from official guides.
        "ACE": [
            "Setting up a cloud solution environment",
            "Planning and configuring a cloud solution",
            "Deploying and implementing a cloud solution",
            "Ensuring successful operation of a cloud solution",
            "Configuring access and security",
        ],
        "PDE": [
            "Designing data processing systems",
            "Ingesting and processing the data",
            "Storing the data",
            "Preparing and using data for analysis",
            "Maintaining and automating data workloads",
        ],
    },
    "Cisco": {
        "CCNA": [
            "Network Fundamentals",
            "IP Addressing & Subnetting",
            "Routing Protocols",
            "Switching & VLANs",
            "WAN Technologies",
            "Network Security Basics",
        ],
    },
}
