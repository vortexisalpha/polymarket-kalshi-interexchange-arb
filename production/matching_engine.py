from format import Formatter, Market
from dataclasses import dataclass, asdict
from datetime import datetime
import json
from api_interface import ArbitragePair


class ComplexMatcher:
    def __init__(self):
        self.formatter = Formatter()

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

            # reject pairs where both have no strikes (unrelated markets)
            if k_lb is None and k_ub is None and p_lb is None and p_ub is None:
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

    def get_matching_pairs(self, poly_ttm, kalshi_ttm):

        kalshi_market_ttm, poly_market_ttm = self.formatter.format_ttms(
            poly_ttm, kalshi_ttm)

        matched_pairs = self.match_pairs_by_close_time(
            kalshi_market_ttm, poly_market_ttm)

        print(f"num matched pairs after close time: {len(matched_pairs)}")

        with open('poly_market_ttm.json', 'w') as f:
            json.dump({k: asdict(v) for k, v in poly_market_ttm.items()}, f)
        with open('kalshi_market_ttm.json', 'w') as f:
            json.dump({k: asdict(v) for k, v in kalshi_market_ttm.items()}, f)

        matched_pairs = self.eliminate_pairs_by_strike(matched_pairs)
        print(f"num matched pairs after strike: {len(matched_pairs)}")

        pair_list = []
        for k, p in matched_pairs:
            arb_pair = ArbitragePair(
                k.title, k.yes_price, k.no_price, k.link, p.title, p.yes_price, p.no_price, p.link)
            pair_list.append(arb_pair)
            print(arb_pair)

        return pair_list
