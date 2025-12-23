"""
AI matching layer: Polymarket ↔ Kalshi market title matching for potential arbitrage.

- Reads two text files (one title per line).
- Calls an OpenAI model with a function/tool call that MUST return pairs:
    [{"poly_title": "...", "kalshi_title": "...", "reason": "...", "confidence": 0.0-1.0}, ...]
- Prints the matched pairs.

Prereqs:
  pip install openai

Env:
  export OPENAI_API_KEY="..."

Usage:
  python ai_match_layer.py
"""

from __future__ import annotations

import json
import os
from dotenv import load_dotenv
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import OpenAI


# ---------- config ----------
POLY_FILE = "poly_btc_events.txt"
KALSHI_FILE = "kalshi_crypto_series.txt"

MODEL = "gpt-4.1-mini"  # pick your preferred tool-capable model
MAX_POLY = 400          # cap to control token usage; increase as needed
MAX_KALSHI = 400


# ---------- helpers ----------
def load_titles(path: str, max_lines: Optional[int] = None) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f.readlines()]
    lines = [ln for ln in lines if ln]
    if max_lines is not None:
        lines = lines[:max_lines]
    return lines


def normalize_title(t: str) -> str:
    t = t.strip()
    t = re.sub(r"\s+", " ", t)
    return t


# ---------- tool schema ----------
MATCH_TOOL = {
    "type": "function",
    "function": {
        "name": "emit_arbitrage_pairs",
        "description": (
            "Return pairs of Polymarket and Kalshi titles that correspond to the exact same underlying market "
            "resolution condition (or a trivially equivalent transformation: same threshold/date/time window). "
            "Only output pairs you believe represent the same market. No extra text."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pairs": {
                    "type": "array",
                    "description": "List of matched title pairs.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "poly_title": {"type": "string"},
                            "kalshi_title": {"type": "string"},
                            "reason": {
                                "type": "string",
                                "description": "Short explanation of why these are the same market."
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                                "description": "Model confidence that these are the same market."
                            }
                        },
                        "required": ["poly_title", "kalshi_title", "reason", "confidence"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["pairs"],
            "additionalProperties": False
        }
    }
}


def match_titles_with_ai(poly_titles: List[str], kalshi_titles: List[str]) -> List[Dict[str, Any]]:
    client = OpenAI()

    system = (
        "You are an expert at prediction market contract matching and arbitrage discovery.\n"
        "Your job: match Polymarket titles to Kalshi titles ONLY if they represent the SAME resolution criteria.\n"
        "Be strict: avoid loose correlations. Prefer exact matches on:\n"
        "- same asset (BTC)\n"
        "- same threshold (e.g. 100k)\n"
        "- same time window / date / timezone reference\n"
        "- same directionality (above/below, up/down)\n"
        "If uncertain, do NOT include the pair.\n"
        "Return ONLY via the provided function call." \
        "Note that the date today is Tuesday 23rd December 2025"
    )

    user = {
        "poly_titles": poly_titles,
        "kalshi_titles": kalshi_titles,
        "output_requirements": {
            "strict_same_market_only": True,
            "max_pairs": 100,
            "dedupe": True,
            "prefer_high_confidence": True
        }
    }

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        tools=[MATCH_TOOL],
        tool_choice={"type": "function", "function": {"name": "emit_arbitrage_pairs"}},
        temperature=0.2,
    )

    # Extract tool call arguments (SDK returns parsed structure; handle defensively)
    tool_calls = resp.choices[0].message.tool_calls or []
    if not tool_calls:
        raise RuntimeError("Model did not produce a tool call. Try a different model or loosen constraints.")

    args = tool_calls[0].function.arguments
    if isinstance(args, str):
        args = json.loads(args)

    pairs = args.get("pairs", [])
    return pairs


def get_matching_pairs(poly_titles_in = None, kalshi_titles_in = None) -> List[Dict[str,Any]]:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set.")

    poly_titles = [normalize_title(t) for t in load_titles(POLY_FILE, MAX_POLY)] if not poly_titles_in else poly_titles_in
    kalshi_titles = [normalize_title(t) for t in load_titles(KALSHI_FILE, MAX_KALSHI)] if not kalshi_titles_in else kalshi_titles_in

    pairs = match_titles_with_ai(poly_titles, kalshi_titles)

    print(f"\nFound {len(pairs)} potential same-market pairs:\n")
    with open("arb_pairs.json", "w", encoding="utf-8") as f:
        json.dump(pairs, f, ensure_ascii=False, indent=2)
    print("Saved: arb_pairs.json\n")
    
    return pairs 

if __name__ == "__main__":
    get_matching_pairs()
