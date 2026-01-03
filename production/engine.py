from api_interface import KalshiExtractor, PolyExtractor, ArbitragePair
from matching_engine import ComplexMatcher
import json


class Engine:
    def __init__(self):
        self.POLY_TAG_FILE = "poly_tags.json"
        self.KALSHI_CATEGORY_TO_TAGS_FILE = "kalshi_categories_to_tags.json"
        self.poly_extractor = PolyExtractor()
        self.kalshi_extractor = KalshiExtractor()
        self.complex_matcher = ComplexMatcher()

    def get_markets(self, poly_category, kalshi_category,
                    kalshi_tags):
        poly_events = self.poly_extractor.get_events(poly_category)
    # returns all poly and kalshi markets related to the input params
        kalshi_series = []
        if kalshi_tags is None:
            kalshi_series.extend(self.kalshi_extractor.get_series(
                category=kalshi_category, tag=None))
        else:
            for tag in kalshi_tags:
                kalshi_series.extend(self.kalshi_extractor.get_series(
                    category=kalshi_category, tag=tag))

        self.poly_markets = []
        self.kalshi_markets = []

        # populate poly and kalshi market lists
        for event in poly_events:
            markets = self.poly_extractor.get_markets(event)
            for market in markets:
                self.poly_markets.append(market['question'])

        for series in kalshi_series:
            markets = self.kalshi_extractor.get_markets(series['ticker'])
            for market in markets:
                self.kalshi_markets.append(
                    f"{market['title']} {market['yes_sub_title']}")

        print(f"found {len(self.poly_markets)} poly markets")
        print(f"found {len(self.kalshi_markets)} kalshi markets")

        return self.poly_markets, self.kalshi_markets

    def get_matching_markets(self):
        poly_ttm = self.poly_extractor.title_to_markets
        kalshi_ttm = self.kalshi_extractor.title_to_markets

        self.matching_pairs = self.complex_matcher.get_matching_pairs(
            poly_ttm, kalshi_ttm)
        return self.matching_pairs

        # this function needs to fill self.arbitrage_pair_list
    def get_arb_pair_list(self):
        # get all arb pairs and sort by the edge
        self.arbitrage_pair_list = [
            pair for pair in self.pair_list if pair.arbitrage != "none"]
        self.arbitrage_pair_list.sort(key=lambda x: x.edge)

    def print_arb_pairs(self):
        print('Arb Pairs:')
        for arb_pair in self.arbitrage_pair_list:
            if arb_pair is not None:
                arb_pair.print()

    def get_categories_from_file(self, category_name):
        with open("../poly_kalshi_grouped_tags.json") as f:
            categories = json.load(f)

        poly_category = categories[category_name]['poly_tag']
        kalshi_category = categories[category_name]['kalshi_category']
        kalshi_tags = categories[category_name]['kalshi_tags']

        return poly_category, kalshi_category, kalshi_tags

    def run_engine(self, poly_category, kalshi_category, kalshi_tags):
        self.get_markets(poly_category, kalshi_category, kalshi_tags)
        self.arbitrage_pair_list = self.get_matching_markets()
        print(self.arbitrage_pair_list)
        self.print_arb_pairs()


if __name__ == "__main__":
    category_name = "Crypto"

    arb_engine = Engine()
    poly_category, kalshi_category, kalshi_tags = arb_engine.get_categories_from_file(
        category_name)
    arb_engine.run_engine(poly_category, kalshi_category, kalshi_tags)
