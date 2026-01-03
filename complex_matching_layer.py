from run_engine import Engine
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class Market:
    title: str
    category: str
    yes_price: float
    no_price: float
    close_time: str
    market_type: str
    exchange: str
    # unsure of how to deal wth strikes but they are super valuable
    strike_lb: float
    strike_ub: float


class MatchingEngine(Engine):
    def __init__(self):
        super().__init__()
        self.complex_matcher = ComplexMatcher()

    def get_matching_markets(self):
        # this function takes in (from self) titles and outputs matching market titles
        # we need to change this to take in markets, give the markets to complex matching engine functions and return matching pairs

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
        # takes in title to market dictionary and returns a list of Market objects:
        #     title, yes_price, no_price, close_time
        kalshi_market_ttm = {}

        exchange = "kalshi"
        for market in kalshi_ttm.values():
            title = f"{market['title']} {market['yes_sub_title']}"
            category = market.get('category', '')
            yes_price = float(market['yes_ask'])
            no_price = float(market['no_ask'])
            close_time = market['close_time']

            try:
                strike_lb = float(market['floor_strike'])
            except:
                strike_lb = None

            try:
                strike_ub = float(market['cap_strike'])
            except:
                strike_ub = None

            market_type = market['market_type']
            kalshi_market_ttm[title] = Market(
                title, category, yes_price, no_price, close_time, market_type, exchange, strike_lb, strike_ub)

        poly_market_ttm = {}

        exchange = "poly"
        for market in poly_ttm.values():
            title = market['question']
            category = market.get('category', '')
            outcome_prices = json.loads(market.get("outcomePrices", "[]"))
            yes_price = float(outcome_prices[0]) if outcome_prices else 0.0
            no_price = float(outcome_prices[1]) if len(
                outcome_prices) > 1 else 0.0
            close_time = market.get('endDate', '')

            group_item_title = market.get('groupItemTitle', '')
            if len(group_item_title) > 0:
                group_item_title = group_item_title.replace(
                    ",", "").replace("$", "")
                if group_item_title[0] == '<':
                    strike_ub = float(group_item_title[1:])
                    strike_lb = None
                elif group_item_title[0] == '>':
                    strike_ub = None
                    strike_lb = float(group_item_title[1:])
                elif '-' in group_item_title and group_item_title[0].isdigit():
                    prices = group_item_title.split('-')
                    strike_lb = float(group_item_title[0])
                    strike_ub = float(group_item_title[1])
                else:
                    strike_lb = None
                    strike_ub = None
            else:
                strike_lb = None
                strike_ub = None

            market_type = market.get('marketType', '')
            poly_market_ttm[title] = Market(
                title, category, yes_price, no_price, close_time, market_type, exchange, strike_lb, strike_ub)

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
                if not (k_market.strike_lb < p_market.strike_lb + 5) and not (p_market.strike_lb < k_market.strike_lb + 5):
                    continue
            if k_market.strike_ub is not None and p_market.strike_ub is not None:
                if not (k_market.strike_ub < p_market.strike_ub + 5) and not (p_market.strike_ub < k_market.strike_ub + 5):
                    continue

            passed_matched_pairs.append((k_market, p_market))

        return passed_matched_pairs

    def get_matching_pairs(self, poly_ttm, kalshi_ttm):
        kalshi_market_ttm, poly_market_ttm = self.format_ttms(
            poly_ttm, kalshi_ttm)

        matched_pairs = self.match_pairs_by_close_time(
            kalshi_market_ttm, poly_market_ttm)

        print(f"num matched pairs after close time: {len(matched_pairs)}")

        matched_pairs = self.eliminate_pairs_by_lb_ub(matched_pairs)
        print(f"num matched pairs after strike: {len(matched_pairs)}")
        # print("Printing pairs")
        # for (k_market, p_market) in matched_pairs:
        #     print(k_market)
        #     print(p_market)

        print(f"number of matching pairs: {len(matched_pairs)}")


if __name__ == "__main__":

    category_name = "Crypto"

    arb_engine = MatchingEngine()
    poly_category, kalshi_category, kalshi_tags = arb_engine.get_categories_from_file(
        category_name)
    arb_engine.run_engine(poly_category, kalshi_category, kalshi_tags)
    pass
