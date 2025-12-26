from run_engine import Engine
from dataclass import dataclass


@dataclass
class Market:
    title: str
    category: str
    yes_price: float
    no_price: float
    close_time: date
    market_type: str
    exchange: str
    # unsure of how to deal wth strikes but they are super valuable
    numeric_strike_lb: float
    numeric_strike_ub: float


class MatchingEngine(Engine):
    def __init__(self):
        super.__init__(self)
        self.complex_matcher = ComplexMatcher()

    def get_matching_markets(self):
        # this function takes in (from self) titles and outputs matching market titles
        # we need to change this to take in markets, give the markets to complex matching engine functions and return matching pairs

        poly_ttm = self.poly_extractor.title_to_markets
        kalshi_ttm = self.kalshi_extractor.title_to_markets

        self.matching_pairs = self.complex_matcher.get_matching_pairs(
            poly_ttm, kalshi_ttm)
        pass


class ComplexMatcher:
    def __init__(self):
        pass

    def format_ttms(self, poly_ttm, kalshi_ttm):
        # takes in title to market dictionary and returns a list of Market objects:
        #     title, yes_price, no_price, close_time
        kalshi_market_list = []

        exchange = "kalshi"
        for market in kalshi_ttm.values():
            title = market['title']
            category = market['catgeory']
            yes_price = float(market['yes_ask'])
            no_price = float(market['no_ask'])
            close_time = datetime(market['close_time'])

            try:
                strike_lb = float(market['floor_strike'])
            except:
                strike_lb = None
            try:
                strike_ub = float(market['cap_strike'])
            except:
                strike_ub = None

            market_type = market['market_type']
            kalshi_market_list.append(
                Market(title, yes_price, no_price, close_time, market_type, exchange, strike_lb, strike_ub))

        poly_market_list = []

        exchange = "poly"
        for market in poly_ttm.values():
            title = market['question']
            category = market['category']
            outcome_prices = json.loads(market.get("outcomePrices"))
            yes_price = float(outcomes_prices[0])
            no_price = float(outcome_prices[1])
            close_time = datetime(market['endDate'])

            try:
                strike_lb = float(market['lowerBound'])
            except:
                strike_lb = None

            try:
                strike_ub = float(market['upperBound'])
            except:
                strike_ub = None

            market_type = market['marketType']
            kalshi_market_list.append(
                Market(title, yes_price, no_price, close_time, market_type, exchange))

    def get_matching_pairs(self, poly_ttm, kalshi_ttm):
        kalshi_market_list, poly_market_list = self.format_ttms(
            poly_ttm, kalshi_ttm)
