from api_interface import KalshiExtractor, PolyExtractor, ArbitragePair
from matching_engine import ComplexMatcher
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import time


class Engine:
    def __init__(self):
        self.POLY_TAG_FILE = "poly_tags.json"
        self.KALSHI_CATEGORY_TO_TAGS_FILE = "kalshi_categories_to_tags.json"
        self.poly_extractor = PolyExtractor()
        self.kalshi_extractor = KalshiExtractor()
        self.complex_matcher = ComplexMatcher()
        self.start_time = None

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

        seen_series_tickers = set()
        for series in kalshi_series:
            ticker = series['ticker']
            if ticker in seen_series_tickers:
                continue
            seen_series_tickers.add(ticker)
            markets = self.kalshi_extractor.get_markets(ticker)
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
        
        self.matching_pairs = sorted(self.matching_pairs, key=lambda x: x.edge)
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
        with open("../poly_kalshi_categories.json") as f:
            categories = json.load(f)

        poly_category = categories[category_name].get('poly_category')   
        kalshi_category = categories[category_name]['kalshi_category']
        kalshi_tags = categories[category_name]['kalshi_tags']

        return poly_category, kalshi_category, kalshi_tags

    def _fetch_poly_for_category(self, poly_category):
        events = self.poly_extractor.get_events(poly_category)
        markets = []
        for event in events:
            for m in self.poly_extractor.get_markets(event):
                markets.append(m['question'])
        return markets

    def _fetch_kalshi_for_category(self, kalshi_category, kalshi_tags):
        kalshi_series = []
        if kalshi_tags is None:
            kalshi_series.extend(self.kalshi_extractor.get_series(
                category=kalshi_category, tag=None))
        else:
            for tag in kalshi_tags:
                kalshi_series.extend(self.kalshi_extractor.get_series(
                    category=kalshi_category, tag=tag))

        markets = []
        seen_tickers = set()
        for series in kalshi_series:
            ticker = series['ticker']
            if ticker in seen_tickers:
                continue
            seen_tickers.add(ticker)
            for m in self.kalshi_extractor.get_markets(ticker):
                markets.append(f"{m['title']} {m['yes_sub_title']}")
        return markets

    def run_all_categories(self, use_kalshi_tags: bool = False):
        self.start_time = time.time()
        with open("../poly_kalshi_categories.json") as f:
            categories = json.load(f)

        poly_cats = []
        for name, cfg in categories.items():
            poly_cats.append((name, cfg.get('poly_category')))

        agg_poly = []

        print("[INFO] Fetching Polymarket categories concurrently...")
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(self._fetch_poly_for_category, pc): name for name, pc in poly_cats}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    markets = future.result()
                    print(f"[INFO] Poly {name}: {len(markets)} markets")
                    agg_poly.extend(markets)
                except Exception as e:
                    print(f"[ERROR] Poly {name}: {e}")

        # Deduplicate poly markets
        agg_poly = list(set(agg_poly))
        print(f"[INFO] Total unique Poly markets: {len(agg_poly)} in {time.time() - self.start_time:.1f}s")

        # Fetch ALL Kalshi markets in one paginated call (much faster than per-series)
        print("[INFO] Fetching all Kalshi markets in one call...")
        all_kalshi = self.kalshi_extractor.get_all_markets_for_category("all")
        agg_kalshi = []
        seen_titles = set()
        for m in all_kalshi:
            title = f"{m['title']} {m.get('yes_sub_title', '')}"
            if title not in seen_titles:
                seen_titles.add(title)
                agg_kalshi.append(title)

        print(f"[INFO] Total unique Kalshi markets: {len(agg_kalshi)} in {time.time() - self.start_time:.1f}s")

        self.poly_markets = agg_poly
        self.kalshi_markets = agg_kalshi
        print(f"found {len(self.poly_markets)} poly markets")
        print(f"found {len(self.kalshi_markets)} kalshi markets")
        self.arbitrage_pair_list = self.get_matching_markets()
        self.print_arb_pairs()
        print(f"[INFO] Total time: {time.time() - self.start_time:.1f}s")

    def run_engine(self, poly_category, kalshi_category, kalshi_tags):
        self.get_markets(poly_category, kalshi_category, kalshi_tags)
        self.arbitrage_pair_list = self.get_matching_markets()
        self.print_arb_pairs()


if __name__ == "__main__":
    arb_engine = Engine()
    category_name = "ALL"

    if category_name == "ALL":
        arb_engine.run_all_categories(use_kalshi_tags=False)
    else:
        poly_category, kalshi_category, kalshi_tags = arb_engine.get_categories_from_file(
            category_name)
        arb_engine.run_engine(poly_category, kalshi_category, kalshi_tags)
