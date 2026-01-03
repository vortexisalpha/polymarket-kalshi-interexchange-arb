from run_engine import Engine
from dataclasses import dataclass
from datetime import datetime
import json
import os
import hashlib
from typing import Dict, List, Tuple, Optional

# ---- Embedding deps ----
# pip install openai numpy
import numpy as np
from openai import OpenAI


# -----------------------------
# Config you can tweak quickly
# -----------------------------
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
EMBED_CACHE_PATH = os.getenv("EMBED_CACHE_PATH", "title_embedding_cache.json")
EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "128"))
# raise to reduce more (e.g. 0.85)
SIM_THRESHOLD = float(os.getenv("SIM_THRESHOLD", "0.80"))


# -----------------------------
# Embedding + caching helpers
# -----------------------------
def _normalize_text(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


class EmbeddingCache:
    """
    Disk-backed cache keyed by sha1(normalized_title).
    Stored as JSON: { key: [float, float, ...], ... }
    """

    def __init__(self, path: str):
        self.path = path
        self.data: Dict[str, List[float]] = {}
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                # If cache is corrupted, start fresh
                self.data = {}

    def get(self, text: str) -> Optional[List[float]]:
        key = _sha1(_normalize_text(text))
        return self.data.get(key)

    def set(self, text: str, vec: List[float]) -> None:
        key = _sha1(_normalize_text(text))
        self.data[key] = vec

    def save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f)
        os.replace(tmp, self.path)


def embed_texts_openai(texts: List[str], model: str = EMBED_MODEL) -> List[List[float]]:
    """
    Embeds a batch of strings using OpenAI embeddings endpoint.
    Requires: export OPENAI_API_KEY=...
    """
    client = OpenAI()
    resp = client.embeddings.create(model=model, input=texts)
    # Ensure order matches input order
    return [item.embedding for item in resp.data]


def _batched(items: List[str], batch_size: int) -> List[List[str]]:
    return [items[i: i + batch_size] for i in range(0, len(items), batch_size)]


def build_title_embedding_map(
    titles: List[str],
    cache: EmbeddingCache,
    batch_size: int = EMBED_BATCH_SIZE,
    model: str = EMBED_MODEL,
) -> Dict[str, np.ndarray]:
    """
    Returns dict: title -> unit-normalized embedding vector (np.ndarray)
    Uses disk cache so you only pay once per unique title.
    """
    # unique titles, stable order
    seen = set()
    uniq_titles = []
    for t in titles:
        if t and t not in seen:
            seen.add(t)
            uniq_titles.append(t)

    # find which titles need embedding
    need = [t for t in uniq_titles if cache.get(t) is None]

    # embed uncached in batches
    if need:
        for chunk in _batched(need, batch_size):
            vecs = embed_texts_openai(chunk, model=model)
            for t, v in zip(chunk, vecs):
                cache.set(t, v)
        cache.save()

    # build normalized vectors
    out: Dict[str, np.ndarray] = {}
    for t in uniq_titles:
        v = cache.get(t)
        if v is None:
            continue
        arr = np.asarray(v, dtype=np.float32)
        n = np.linalg.norm(arr)
        if n > 0:
            arr = arr / n
        out[t] = arr
    return out


def cosine_sim_unit(u: np.ndarray, v: np.ndarray) -> float:
    # u and v should already be unit-normalized
    return float(np.dot(u, v))


# -----------------------------
# Your structures
# -----------------------------
@dataclass
class Market:
    title: str
    category: str
    yes_price: float
    no_price: float
    close_time: str
    market_type: str
    exchange: str
    strike_lb: float
    strike_ub: float


class MatchingEngine(Engine):
    def __init__(self):
        super().__init__()
        self.complex_matcher = ComplexMatcher()

    def get_matching_markets(self):
        poly_ttm = self.poly_extractor.title_to_markets
        kalshi_ttm = self.kalshi_extractor.title_to_markets

        self.matching_pairs = self.complex_matcher.get_matching_pairs(
            poly_ttm, kalshi_ttm)

    def run_engine(self, poly_category, kalshi_category, kalshi_tags):
        self.get_markets(poly_category, kalshi_category, kalshi_tags)
        self.get_matching_markets()


class ComplexMatcher:
    def __init__(self):
        pass

    def format_ttms(self, poly_ttm, kalshi_ttm):
        kalshi_market_ttm = {}

        exchange = "kalshi"
        for market in kalshi_ttm.values():
            title = f"{market['title']} {market['yes_sub_title']}"
            category = market.get("category", "")
            yes_price = float(market["yes_ask"])
            no_price = float(market["no_ask"])
            close_time = market["close_time"]

            try:
                strike_lb = float(market["floor_strike"])
            except Exception:
                strike_lb = None

            try:
                strike_ub = float(market["cap_strike"])
            except Exception:
                strike_ub = None

            market_type = market["market_type"]
            kalshi_market_ttm[title] = Market(
                title, category, yes_price, no_price, close_time, market_type, exchange, strike_lb, strike_ub
            )

        poly_market_ttm = {}

        exchange = "poly"
        for market in poly_ttm.values():
            title = market["question"]
            category = market.get("category", "")
            outcome_prices = json.loads(market.get("outcomePrices", "[]"))
            yes_price = float(outcome_prices[0]) if outcome_prices else 0.0
            no_price = float(outcome_prices[1]) if len(
                outcome_prices) > 1 else 0.0
            close_time = market.get("endDate", "")

            try:
                strike_lb = float(market["lowerBound"])
            except Exception:
                strike_lb = None

            try:
                strike_ub = float(market["upperBound"])
            except Exception:
                strike_ub = None

            market_type = market.get("marketType", "")
            poly_market_ttm[title] = Market(
                title, category, yes_price, no_price, close_time, market_type, exchange, strike_lb, strike_ub
            )

        return kalshi_market_ttm, poly_market_ttm

    def match_pairs_by_close_time(self, kalshi_ttm, poly_ttm):
        matched_pairs = []
        for k_market in kalshi_ttm.values():
            for p_market in poly_ttm.values():
                try:
                    k_close = datetime.fromisoformat(k_market.close_time)
                    p_close = datetime.fromisoformat(p_market.close_time)
                except Exception:
                    continue
                # check if close times are within 3 hours
                if abs((k_close - p_close).total_seconds()) <= 3 * 3600:
                    matched_pairs.append((k_market, p_market))
        return matched_pairs

    def eliminate_pairs_by_lb_ub(self, matched_pairs):
        passed_matched_pairs = []

        for k_market, p_market in matched_pairs:
            if k_market.strike_lb is not None and p_market.strike_lb is not None:
                if k_market.strike_lb != p_market.strike_lb:
                    continue
            if k_market.strike_ub is not None and p_market.strike_ub is not None:
                if k_market.strike_ub != p_market.strike_ub:
                    continue

            passed_matched_pairs.append((k_market, p_market))

        return passed_matched_pairs

    def eliminate_pairs_by_embedding_similarity(
        self,
        matched_pairs: List[Tuple[Market, Market]],
        title_vecs: Dict[str, np.ndarray],
        threshold: float = SIM_THRESHOLD,
    ) -> List[Tuple[Market, Market]]:
        """
        Keeps only pairs with cosine similarity >= threshold.
        If an embedding is missing for a title, the pair is dropped (aggressive reduction).
        """
        kept = []
        for k_market, p_market in matched_pairs:
            kv = title_vecs.get(k_market.title)
            pv = title_vecs.get(p_market.title)
            if kv is None or pv is None:
                continue
            sim = cosine_sim_unit(kv, pv)
            if sim >= threshold:
                kept.append((k_market, p_market))
        return kept

    def get_matching_pairs(self, poly_ttm, kalshi_ttm):
        kalshi_market_ttm, poly_market_ttm = self.format_ttms(
            poly_ttm, kalshi_ttm)

        matched_pairs = self.match_pairs_by_close_time(
            kalshi_market_ttm, poly_market_ttm)
        print(f"pairs after close_time filter: {len(matched_pairs)}")

        matched_pairs = self.eliminate_pairs_by_lb_ub(matched_pairs)
        print(f"pairs after strike filter: {len(matched_pairs)}")

        # ---- Embedding precompute (all titles) ----
        all_titles = list(kalshi_market_ttm.keys()) + \
            list(poly_market_ttm.keys())
        cache = EmbeddingCache(EMBED_CACHE_PATH)
        title_vecs = build_title_embedding_map(
            titles=all_titles,
            cache=cache,
            batch_size=EMBED_BATCH_SIZE,
            model=EMBED_MODEL,
        )

        # ---- Similarity elimination ----
        matched_pairs = self.eliminate_pairs_by_embedding_similarity(
            matched_pairs,
            title_vecs=title_vecs,
            threshold=SIM_THRESHOLD,
        )
        print(f"pairs after embedding sim >= {
              SIM_THRESHOLD}: {len(matched_pairs)}")

        for a, b in matched_pairs:
            print("kalshi:")
            print(a)
            print("poly:")
            print(b)
            print("\n"*3)

        # Return pairs if you want to use them downstream
        return matched_pairs


if __name__ == "__main__":
    # Make sure you have OPENAI_API_KEY set in your env.
    # export OPENAI_API_KEY="..."
    category_name = "Crypto"

    arb_engine = MatchingEngine()
    poly_category, kalshi_category, kalshi_tags = arb_engine.get_categories_from_file(
        category_name)
    arb_engine.run_engine(poly_category, kalshi_category, kalshi_tags)
