"""
Gyan AI — Curriculum Data
==========================
Single source of truth for all curriculum constants used across the pipeline.

Consumers:
  - agents/ganak.py      (topic priority analysis)
  - admin/streamlit_app.py (coverage map + smart pipeline UI)
  - gyan_pipeline.py      (taxonomy validation)

Structure:
  CURRICULUM        — school boards  : {board: {class_num: [subjects]}}
  CLASS_PRIORITY    — class urgency  : {class_num: priority_int}
  COMPETITIVE_TREE  — competitive    : {authority: {exam: [topics]}}
  IT_TREE           — IT certs       : {provider: {cert: [domains]}}
  BENGALI_BOARDS    — boards needing Bengali-language MCQs
"""

from __future__ import annotations

# ── School curriculum ─────────────────────────────────────────────────────────

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


# ── Competitive exams ─────────────────────────────────────────────────────────

COMPETITIVE_TREE: dict[str, dict[str, list[str]]] = {
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


# ── IT certifications ─────────────────────────────────────────────────────────

IT_TREE: dict[str, dict[str, list[str]]] = {
    "AWS": {
        "Cloud Practitioner": [
            "Cloud Concepts",
            "AWS Core Services",
            "Security & Compliance",
            "Billing & Pricing",
        ],
        "Solutions Architect Associate": [
            "EC2 & Compute",
            "S3 & Storage",
            "VPC & Networking",
            "RDS & Databases",
            "IAM & Security",
            "High Availability & Fault Tolerance",
        ],
        "Developer Associate": [
            "Lambda & Serverless",
            "DynamoDB",
            "API Gateway",
            "CodePipeline & DevOps",
            "SQS / SNS / EventBridge",
        ],
    },
    "Microsoft": {
        "AZ-900 Azure Fundamentals": [
            "Cloud Concepts",
            "Azure Core Services",
            "Azure Pricing & SLA",
            "Security & Governance",
        ],
        "AZ-104 Azure Administrator": [
            "Azure AD & Identity",
            "Virtual Machines",
            "Storage & Blob",
            "Virtual Networks",
            "Monitoring & Backup",
        ],
    },
    "Google": {
        "Associate Cloud Engineer": [
            "GCP Core Infrastructure",
            "Compute Engine",
            "Kubernetes Engine",
            "Cloud Storage",
            "IAM & Security",
        ],
        "Professional Data Engineer": [
            "BigQuery",
            "Dataflow & Pub/Sub",
            "Cloud Spanner & Bigtable",
            "ML on GCP",
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
