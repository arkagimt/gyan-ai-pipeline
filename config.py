"""
Gyan AI Pipeline — Config & Agent Prompt Loader
=================================================
Loads env vars and fetches agent system prompts from Supabase.
Prompts are NEVER stored in code — they live in public.agent_prompts table.
This is the "Vault Pattern" keeping our secret sauce off GitHub.
"""

from __future__ import annotations
import os
import sys
import json
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

# ── Required env vars ─────────────────────────────────────────────────────────

SUPABASE_URL         = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
GROQ_API_KEY         = os.environ.get("GROQ_API_KEY", "")
SARVAM_API_KEY       = os.environ.get("SARVAM_API_KEY", "")

GROQ_MODEL           = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_URL         = "https://api.groq.com/openai/v1/chat/completions"

MAX_RETRIES          = 3
LLM_TIMEOUT_S        = 45


def check_required_env() -> None:
    missing = [k for k in ["SUPABASE_URL", "SUPABASE_SERVICE_KEY", "GROQ_API_KEY"] if not os.environ.get(k)]
    if missing:
        emit_error(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)


# ── Stdout emitter (JSON lines — parsed by Next.js /api/pipeline/run) ─────────

def emit(msg_type: str, agent: str | None = None, msg: str = "") -> None:
    payload: dict = {"type": msg_type}
    if agent:
        payload["agent"] = agent
    payload["msg"] = msg
    print(json.dumps(payload, ensure_ascii=False), flush=True)

def emit_agent(agent: str, msg: str) -> None:
    emit("agent", agent=agent, msg=msg)

def emit_progress(msg: str) -> None:
    emit("progress", msg=msg)

def emit_error(msg: str) -> None:
    emit("error", msg=msg)


# ── Agent Prompt Dataclass ────────────────────────────────────────────────────

@dataclass
class AgentPrompt:
    agent_id:      str
    role:          str
    goal:          str
    backstory:     str
    system_prompt: str
    temperature:   float = 0.1
    max_tokens:    int   = 4096


# ── Fetch prompts from Supabase (runtime — not hardcoded) ─────────────────────

_prompt_cache: dict[str, AgentPrompt] = {}

def get_agent_prompt(agent_id: str) -> AgentPrompt:
    """
    Fetches the agent's prompt from Supabase agent_prompts table.
    Cached in-process so we only hit the DB once per agent per run.
    Falls back to hardcoded defaults if Supabase is unreachable.
    """
    if agent_id in _prompt_cache:
        return _prompt_cache[agent_id]

    try:
        import requests
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/agent_prompts",
            params={"agent_id": f"eq.{agent_id}", "is_active": "eq.true", "limit": "1"},
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            rows = resp.json()
            if rows:
                r = rows[0]
                prompt = AgentPrompt(
                    agent_id      = r["agent_id"],
                    role          = r["role"],
                    goal          = r["goal"],
                    backstory     = r["backstory"],
                    system_prompt = r["system_prompt"],
                    temperature   = float(r.get("temperature", 0.1)),
                    max_tokens    = int(r.get("max_tokens", 4096)),
                )
                _prompt_cache[agent_id] = prompt
                return prompt
    except Exception as e:
        emit_progress(f"[config] Supabase prompt fetch failed for {agent_id}: {e} — using defaults")

    # ── Hardcoded fallback (safe defaults, no secret sauce) ──────────────────
    defaults: dict[str, AgentPrompt] = {
        "sarbagya": AgentPrompt(
            agent_id      = "sarbagya",
            role          = "Scout Agent & Knowledge Extractor",
            goal          = "Extract raw accurate educational content from source material.",
            backstory     = "You are সর্বজ্ঞ — the All-Knowing extractor.",
            system_prompt = (
                "You are an expert Indian curriculum content extractor. "
                "Extract key facts, concepts, definitions, and formulas from the provided text "
                "for the given taxonomy slice. Output ONLY valid JSON. Do not hallucinate."
            ),
            temperature = 0.0,
        ),
        "chitragupta": AgentPrompt(
            agent_id      = "chitragupta",
            role          = "Triage Agent & Quality Verification Engine",
            goal          = "Validate extracted content for accuracy and syllabus alignment.",
            backstory     = "You are চিত্রগুপ্ত — the Record Keeper who misses nothing.",
            system_prompt = (
                "You are an expert Indian curriculum validator. "
                "Check the extracted content for factual correctness, syllabus alignment, "
                "and hallucinations. Output ONLY valid JSON validation report."
            ),
            temperature = 0.1,
        ),
        "sutradhar": AgentPrompt(
            agent_id      = "sutradhar",
            role          = "Content Creator Agent & Study Material Synthesizer",
            goal          = "Transform validated content into study notes and MCQs.",
            backstory     = "You are সূত্রধর — the Storyteller. সারং ততো গ্রাহ্যম্.",
            system_prompt = (
                "You are an expert Indian educational content creator. "
                "Create crisp study notes and high-quality MCQs from the validated content. "
                "Output ONLY valid JSON following the exact schema provided."
            ),
            temperature = 0.2,
        ),
    }
    prompt = defaults.get(agent_id, defaults["sutradhar"])
    _prompt_cache[agent_id] = prompt
    return prompt
