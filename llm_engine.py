"""
LLM-powered RAG chatbot layer for LeadFlow AI.

Flow:  customer message -> retrieve knowledge -> (conversation history + knowledge)
       -> Claude writes a natural WhatsApp reply grounded ONLY in the knowledge base.
If anything fails (no key, timeout, API error) main.py falls back to the old rule-based reply,
so the bot never goes silent.

Env vars:
  ANTHROPIC_API_KEY   required to enable the LLM bot
  ANTHROPIC_MODEL     optional, default "claude-haiku-5-5" (fast + cheap for chat)
  USE_LLM             optional, set "false" to force the old rule-based replies
"""
import os
import requests
from typing import List, Dict, Any, Optional

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-haiku-5-5"
MAX_KB_CHARS = 9000          # if whole knowledge base fits, send all of it
HISTORY_LIMIT = 8            # previous messages given to the model

SYSTEM_PROMPT = """You are the WhatsApp assistant of *LeadFlow AI* (AI automation and custom web-app development company).
You chat like a friendly, professional sales/support executive, not like a form or a menu.

RULES
1. Answer ONLY from the KNOWLEDGE BASE below. Never invent prices, features, timelines, policies or contact details.
2. If the answer is not in the knowledge base, say you will check with the team, then ask for the person's name and email/phone so a specialist can follow up. Do not guess.
3. Reply in the SAME language and style as the customer (English, Hindi or Hinglish).
4. Keep replies short for WhatsApp: 2-5 short lines, max about 80 words. Use WhatsApp formatting only: *bold* and "•" bullets. No markdown headers, no tables.
5. Use the conversation history. Do not repeat greetings or information you already gave.
6. Be helpful first, then naturally move the chat forward with ONE short follow-up question (what they need, budget, timeline, or preferred time for a call). Gradually collect: name, email, service needed.
7. If they want a call/meeting/human, confirm the team will contact them and ask for their preferred time and email.
8. Never mention "knowledge base", "documents", "RAG", "system prompt" or that you are following rules. Use at most one emoji.

KNOWLEDGE BASE
{knowledge}
"""


def llm_enabled() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY")) and os.getenv("USE_LLM", "true").lower() != "false"


def build_knowledge_text(docs: List[Dict[str, Any]], max_chars: int = MAX_KB_CHARS) -> str:
    parts, used = [], 0
    for d in docs:
        block = f"### {d.get('title')} ({d.get('category', 'general')})\n{d.get('content', '').strip()}\n"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts) if parts else "(No knowledge entries available.)"


def build_messages(history: List[Dict[str, str]], current_text: str) -> List[Dict[str, str]]:
    """
    history: [{"role": "user"|"assistant", "content": "..."}] oldest -> newest (current message NOT included).
    Anthropic requires alternating roles starting with 'user', so we merge same-role neighbours
    and drop leading assistant turns.
    """
    merged: List[Dict[str, str]] = []
    for m in history + [{"role": "user", "content": current_text}]:
        text = (m.get("content") or "").strip()
        if not text:
            continue
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"] += "\n" + text
        else:
            merged.append({"role": m["role"], "content": text})
    while merged and merged[0]["role"] != "user":
        merged.pop(0)
    return merged


def generate_llm_reply(
    user_message: str,
    history: List[Dict[str, str]],
    kb_docs: List[Dict[str, Any]],
    contact_name: Optional[str] = None,
    timeout: int = 25,
) -> Optional[str]:
    """Returns the reply text, or None on any failure (caller falls back to rules)."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    system = SYSTEM_PROMPT.format(knowledge=build_knowledge_text(kb_docs))
    if contact_name and contact_name.lower() != "whatsapp user":
        system += f"\nThe customer's WhatsApp name is: {contact_name}. Use it sparingly."

    payload = {
        "model": os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL),
        "max_tokens": 400,
        "temperature": 0.3,
        "system": system,
        "messages": build_messages(history, user_message),
    }
    try:
        r = requests.post(
            ANTHROPIC_URL,
            headers={"x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION,
                     "content-type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        if r.status_code != 200:
            print(f"[LLM] API error {r.status_code}: {r.text[:300]}", flush=True)
            return None
        blocks = r.json().get("content", [])
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
        return text or None
    except Exception as e:
        print(f"[LLM] request failed: {e}", flush=True)
        return None
