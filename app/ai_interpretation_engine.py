"""
TradeLayer AI Interpretation Engine

Uses Claude (Anthropic) to translate TradeLayer structured data into a concise
human-readable briefing. The AI does not place trades or override risk rules.

Drop-in replacement for the OpenAI version — same function signature,
same return keys, same fallback behavior.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict


def _compact_json(data: Dict[str, Any], max_chars: int = 9000) -> str:
    try:
        text = json.dumps(data, indent=2, default=str)
    except Exception:
        text = str(data)

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n...TRUNCATED..."


def _fallback_briefing(context: Dict[str, Any], reason: str) -> Dict[str, Any]:
    command = context.get("command_center", {}) or {}
    recommendation = context.get("trade_recommendation", {}) or {}
    performance = context.get("performance", {}) or {}
    top_trade = context.get("top_trade", {}) or {}

    trade_symbol = (
        recommendation.get("symbol")
        or recommendation.get("top_symbol")
        or top_trade.get("symbol")
        or "current top setup"
    )

    permission = (
        command.get("new_trade_permission")
        or command.get("today_action")
        or "SELECTIVE"
    )

    confidence = performance.get("confidence_label", "Early Sample")

    briefing = (
        f"TradeLayer is operating in {permission} mode. "
        f"The current primary setup is {trade_symbol}, but position sizing and risk controls should remain conservative. "
        f"Performance validation is still classified as {confidence}, so current recommendations should be treated as decision support rather than statistical proof."
    )

    return {
        "status": "fallback",
        "engine": "TradeLayer AI Interpretation Engine V1",
        "generated_at": datetime.now().isoformat(),
        "provider": "local_fallback",
        "briefing": briefing,
        "trade_status": str(permission),
        "risk_note": "Risk engine and position sizing controls remain the source of truth.",
        "key_conflicts": [
            "AI provider was unavailable, so TradeLayer returned a local rules-based briefing.",
            reason,
        ],
        "next_action": "Review the setup, confirm risk size, and avoid treating the AI summary as an execution instruction.",
        "disclaimer": "This is decision-support commentary only. It is not financial advice and does not place trades.",
    }


def build_ai_interpretation(context: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        return _fallback_briefing(
            context,
            "ANTHROPIC_API_KEY is not set in the environment.",
        )

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        system_prompt = """You are TradeLayer's AI interpretation layer.

You summarize structured trading-system data for a human operator.

Rules:
- Do not place trades.
- Do not claim certainty.
- Do not override the risk engine.
- Do not invent probabilities or unseen data.
- Be concise, practical, and risk-aware.
- Mention conflicts between signals when present.
- Treat this as decision support, not financial advice.

Return valid JSON only with these exact keys:
status, engine, provider, generated_at, briefing, trade_status, risk_note, key_conflicts, next_action, disclaimer.

No markdown, no code fences, no explanation outside the JSON."""

        user_prompt = f"""Analyze this TradeLayer context and produce a concise briefing.

Context:
{_compact_json(context)}

Output requirements:
- status must be "ok"
- engine must be "TradeLayer AI Interpretation Engine V1"
- provider must be "anthropic"
- generated_at should be an ISO-style timestamp
- briefing should be 2-4 sentences describing what the market is telling the trader today
- trade_status should be a short phrase such as SELECTIVE, RISK-ON, DEFENSIVE, or MANAGE ONLY
- risk_note should explain sizing/caution in one sentence
- key_conflicts should be an array of 0-4 strings flagging any signal disagreements
- next_action should be one practical operating instruction
- disclaimer should say this is decision-support commentary, not financial advice"""

        message = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            max_tokens=1000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = message.content[0].text.strip()

        # Strip markdown fences if the model wraps anyway
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            parsed = json.loads(text)
        except Exception:
            # Model returned prose instead of JSON — wrap it gracefully
            return {
                "status": "ok",
                "engine": "TradeLayer AI Interpretation Engine V1",
                "generated_at": datetime.now().isoformat(),
                "provider": "anthropic",
                "briefing": text,
                "trade_status": "SELECTIVE",
                "risk_note": "Risk engine and position sizing controls remain the source of truth.",
                "key_conflicts": [],
                "next_action": "Use this briefing as context only; confirm the setup and risk plan before acting.",
                "disclaimer": "This is decision-support commentary only. It is not financial advice and does not place trades.",
            }

        # Ensure required keys are always present
        parsed.setdefault("status", "ok")
        parsed.setdefault("engine", "TradeLayer AI Interpretation Engine V1")
        parsed.setdefault("generated_at", datetime.now().isoformat())
        parsed.setdefault("provider", "anthropic")
        parsed.setdefault("disclaimer", "This is decision-support commentary only. It is not financial advice and does not place trades.")

        return parsed

    except Exception as error:
        return _fallback_briefing(
            context,
            f"Anthropic request failed: {error}",
        )