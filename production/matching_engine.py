from format import Formatter, Market
from dataclasses import dataclass, asdict
from datetime import datetime
import json
from api_interface import ArbitragePair
from datetime import timezone
from text_embeddings import TextSimilarity, TextEmbedder
from gpt_layer import GPTMarketJudge


class ComplexMatcher:
    def __init__(self):
        self.formatter = Formatter()
        self.text_similarity = TextSimilarity(threshold=0.30)
        self.embedder = self.text_similarity.embedder
        self.gpt_judge = GPTMarketJudge()

    def _parse_datetime(self, dt_str):
        """Parse ISO8601 strings that may include Z; return None on failure."""
        if not dt_str:
            return None
        if isinstance(dt_str, str):
            cleaned = dt_str.replace("Z", "+00:00").replace("z", "+00:00")
        else:
            return None

        try:
            parsed = datetime.fromisoformat(cleaned)
        except Exception:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    def match_pairs_by_close_time(self, kalshi_ttm, poly_ttm):

        matched_pairs = []
        for k_market in kalshi_ttm.values():
            for p_market in poly_ttm.values():
                k_close = self._parse_datetime(k_market.close_time)
                p_close = self._parse_datetime(p_market.close_time)
                if not k_close or not p_close:
                    continue
                # check if close times are within 3 hours
                if abs((k_close - p_close).total_seconds()) <= 3 * 3600:
                    matched_pairs.append((k_market, p_market))
        return matched_pairs

    def within_tolerance(self, val1, val2, tolerance_pct=0.005):
        if val1 == 0 and val2 == 0:
            return True
        avg = (abs(val1) + abs(val2)) / 2
        return abs(val1 - val2) <= avg * tolerance_pct

    def eliminate_pairs_by_strike(self, matched_pairs):
        passed_matched_pairs = []

        for k_market, p_market in matched_pairs:
            k_lb = k_market.strike_lb
            k_ub = k_market.strike_ub
            p_lb = p_market.strike_lb
            p_ub = p_market.strike_ub

            # If either side lacks strike info, keep the pair and let title similarity filter later.
            if (k_lb is None and k_ub is None) or (p_lb is None and p_ub is None):
                passed_matched_pairs.append((k_market, p_market))
                continue

            # check if strikes match same bound type or cross matched lb/ub
            match_found = False

            # same type matches: lb-lb or ub-ub
            if k_lb is not None and p_lb is not None:
                if self.within_tolerance(k_lb, p_lb):
                    match_found = True
            if k_ub is not None and p_ub is not None:
                if self.within_tolerance(k_ub, p_ub):
                    match_found = True

            # cross type matches: k_lb ≈ p_ub or k_ub ≈ p_lb (same target, different parsing)
            if k_lb is not None and p_ub is not None and p_lb is None and k_ub is None:
                if self.within_tolerance(k_lb, p_ub):
                    match_found = True
            if k_ub is not None and p_lb is not None and p_ub is None and k_lb is None:
                if self.within_tolerance(k_ub, p_lb):
                    match_found = True

            if not match_found:
                continue

            passed_matched_pairs.append((k_market, p_market))

        return passed_matched_pairs

    def filter_by_similarity(self, matched_pairs):
        if not matched_pairs:
            return []

        all_texts = []
        for k_market, p_market in matched_pairs:
            all_texts.append(k_market.title or "")
            all_texts.append(p_market.title or "")

        print(f"[INFO] Batch embedding {len(all_texts)} titles...")
        embeddings = self.embedder.embed_batch(all_texts)

        filtered = []
        scores = []
        for i, (k_market, p_market) in enumerate(matched_pairs):
            va = embeddings[i * 2]
            vb = embeddings[i * 2 + 1]
            score = TextEmbedder.cosine(va, vb)
            if score >= self.text_similarity.threshold:
                filtered.append((k_market, p_market, score))
                scores.append(score)

        if scores:
            top = sorted(scores, reverse=True)[:5]
            print(f"top title similarity scores: {top}")
        return filtered

    def filter_by_gpt(self, matched_pairs_with_scores):
        filtered = []
        for k_market, p_market, score in matched_pairs_with_scores:
            # If titles are already very close, skip GPT to avoid over-filtering.
            if score >= 0.65:
                filtered.append((k_market, p_market))
                continue
            if self.gpt_judge.is_same_market(k_market.title, p_market.title):
                filtered.append((k_market, p_market))
        return filtered

    def get_matching_pairs(self, poly_ttm, kalshi_ttm):

        kalshi_market_ttm, poly_market_ttm = self.formatter.format_ttms(
            poly_ttm, kalshi_ttm)

        matched_pairs = self.match_pairs_by_close_time(
            kalshi_market_ttm, poly_market_ttm)

        print(f"num matched pairs after close time: {len(matched_pairs)}")

        matched_pairs = self.eliminate_pairs_by_strike(matched_pairs)
        print(f"num matched pairs after strike: {len(matched_pairs)}")

        matched_pairs_with_scores = self.filter_by_similarity(matched_pairs)
        print(f"num matched pairs after title similarity: {len(matched_pairs_with_scores)}")

        matched_pairs = self.filter_by_gpt(matched_pairs_with_scores)
        print(f"num matched pairs after GPT check: {len(matched_pairs)}")

        pair_list = []
        for k, p in matched_pairs:
            arb_pair = ArbitragePair(
                k.title, k.yes_price, k.no_price, k.link, p.title, p.yes_price, p.no_price, p.link)
            pair_list.append(arb_pair)
            print(arb_pair)

        return pair_list
