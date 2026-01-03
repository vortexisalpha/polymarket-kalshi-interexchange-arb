from poly_kalshi_data import KalshiExtractor, PolyExtractor, ArbitragePair
from openai_matching_layer import get_matching_pairs
import json


class Engine:
    def __init__(self):
        self.POLY_TAG_FILE = "poly_tags.json"
        self.KALSHI_CATEGORY_TO_TAGS_FILE = "kalshi_categories_to_tags.json"
        self.poly_extractor = PolyExtractor()
        self.kalshi_extractor = KalshiExtractor()

    def get_markets(self, poly_category, kalshi_category, kalshi_tags):
        poly_events = self.poly_extractor.get_events(poly_category)

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
        matching_pairs = get_matching_pairs(
            poly_titles_in=self.poly_markets, kalshi_titles_in=self.kalshi_markets)

        self.pair_list = []
        for matching_pair in matching_pairs:
            poly_title = matching_pair['poly_title']
            poly_market = self.poly_extractor.title_to_markets.get(
                poly_title, {})
            kalshi_title = matching_pair['kalshi_title']
            kalshi_market = self.kalshi_extractor.title_to_markets.get(
                kalshi_title, {})

            p_yes, p_no, p_link = self.poly_extractor.get_market_yn_link(
                poly_market)
            k_yes, k_no, k_link = self.kalshi_extractor.get_market_yn_link(
                kalshi_market)

            if None in (kalshi_title, k_yes, k_no, k_link, poly_title, p_yes, p_no, p_link):
                continue
            self.pair_list.append(ArbitragePair(
                kalshi_title, k_yes, k_no, k_link, poly_title, p_yes, p_no, p_link))

        return self.pair_list

    def get_arb_pair_list(self):
        # get all arb pairs and sort by the edge
        self.arbitrage_pair_list = [
            pair for pair in self.pair_list if pair.arbitrage != "none"]
        self.arbitrage_pair_list.sort(key=lambda x: x.edge)

    def print_arb_pairs(self):
        print('Arb Pairs:')
        for arb_pair in self.arbitrage_pair_list:
            arb_pair.print()

    def get_categories_from_file(self, category_name):
        with open("poly_kalshi_grouped_tags.json") as f:
            categories = json.load(f)

        poly_category = categories[category_name]['poly_tag']
        kalshi_category = categories[category_name]['kalshi_category']
        kalshi_tags = categories[category_name]['kalshi_tags']

        return poly_category, kalshi_category, kalshi_tags

    def run_engine(self, poly_category, kalshi_category, kalshi_tags):
        self.get_markets(poly_category, kalshi_category, kalshi_tags)
        self.get_matching_markets()
        self.get_arb_pair_list()
        self.print_arb_pairs()


if __name__ == "__main__":
    category_name = "Crypto"

    arb_engine = Engine()
    poly_category, kalshi_category, kalshi_tags = arb_engine.get_categories_from_file(
        category_name)
    arb_engine.run_engine(poly_category, kalshi_category, kalshi_tags)
