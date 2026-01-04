import requests
import time
import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

# rate limiting constants
# Kalshi has strict rate limits; use conservative defaults and backoff.
KALSHI_RATE_LIMIT = 0.5  # base delay between successful requests (lowered for speed)
KALSHI_MAX_RETRIES = 5
KALSHI_BACKOFF_BASE = 0.8
KALSHI_BACKOFF_FACTOR = 1.8

POLY_RATE_LIMIT = 0.05  # Polymarket is more lenient
REQUEST_TIMEOUT = 10


class PolyExtractor:
    def __init__(self):
        self.BASE = "https://gamma-api.polymarket.com"
        self.title_to_markets = {}
        self.session = requests.Session()
        self._tag_cache = {}
        self._all_tags = None

    def _fetch_all_tags(self):
        if self._all_tags is not None:
            return self._all_tags
        try:
            response = self.session.get(
                f"{self.BASE}/tags", timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            self._all_tags = response.json()
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch tags: {e}")
            self._all_tags = []
        return self._all_tags

    def get_tag_id(self, tag_name: str):
        if tag_name in self._tag_cache:
            return self._tag_cache[tag_name]

        all_tags = self._fetch_all_tags()
        for tag in all_tags:
            if tag['label'].lower() == tag_name.lower():
                self._tag_cache[tag_name] = tag['id']
                return tag['id']

        print(f"[ERROR] Did not find tag: {tag_name}")
        self._tag_cache[tag_name] = None
        return None

    def get_events(self, tag_name=None, closed="false", limit=1000):
        event_params = {"limit": limit,
                        "closed": closed}
        if tag_name:
            tag_id = self.get_tag_id(tag_name)
            if tag_id is None:
                return []
            event_params["tag_id"] = tag_id

        all_events = []
        while True:
            try:
                response = self.session.get(
                    f"{self.BASE}/events",
                    params=event_params,
                    timeout=REQUEST_TIMEOUT
                )
                response.raise_for_status()
                events = response.json()
            except requests.exceptions.RequestException as e:
                print(f"[ERROR] Failed to fetch events: {e}")
                break

            if not events:
                break

            all_events.extend(events)

            if len(events) < limit:
                break

            event_params["offset"] = len(all_events)
            time.sleep(POLY_RATE_LIMIT)

        for event in all_events:
            markets = event.get('markets', [])
            for market in markets:
                self.title_to_markets[market["question"]] = market

        return all_events

    def get_markets(self, events):
        return events['markets']

    def print_market(self, market):
        if not market:
            return
        outcomes = json.loads(market.get("outcomes"))
        outcome_prices = json.loads(market.get("outcomePrices"))
        question = market.get("question")
        if 1 not in outcome_prices:
            print(f"Poly: {question}")
            for outcome, price in zip(outcomes, outcome_prices):
                print(f"{outcome}: {price}")

    # this assumes yes/no market
    # returns yes price, no price and link to market
    def get_market_yn_link(self, market):
        if not market:
            return None, None, None
        outcome_prices = json.loads(market.get("outcomePrices"))
        if not outcome_prices or len(outcome_prices) < 2:
            return None, None, None
        slug = market['slug']
        if not slug:
            return None, None, None
        link = f"https://polymarket.com/market/{slug}"
        return outcome_prices[0], outcome_prices[1], link


class KalshiExtractor:
    def __init__(self):
        self.BASE = "https://api.elections.kalshi.com/trade-api/v2"
        self.title_to_ticker = {}
        self.title_to_markets = {}
        self.event_to_series = {}
        self.session = requests.Session()
        self.series_to_markets = {}
        self._last_request_ts = 0.0
        self._category_markets_cache = {}
        self._seen_market_tickers = set()

    def _compute_backoff_delay(self, attempt: int, retry_after_header=None):
        """
        attempt is zero-based; retry_after_header (str) may come from Kalshi.
        """
        if retry_after_header:
            try:
                retry_after = float(retry_after_header)
                return max(retry_after, KALSHI_RATE_LIMIT)
            except ValueError:
                pass
        return max(KALSHI_BACKOFF_BASE * (KALSHI_BACKOFF_FACTOR ** attempt), KALSHI_RATE_LIMIT)

    def _get_with_backoff(self, url, params=None):
        """
        Centralized GET with retry/backoff to handle Kalshi 429s gracefully.
        """
        for attempt in range(KALSHI_MAX_RETRIES + 1):
            # enforce a minimum spacing between calls to avoid burst 429s
            now = time.time()
            wait = self._last_request_ts + KALSHI_RATE_LIMIT - now
            if wait > 0:
                time.sleep(wait)
            try:
                response = self.session.get(
                    url, params=params, timeout=REQUEST_TIMEOUT)
                self._last_request_ts = time.time()
            except requests.exceptions.RequestException as e:
                self._last_request_ts = time.time()
                if attempt >= KALSHI_MAX_RETRIES:
                    print(f"[ERROR] Kalshi request failed after retries for {url}: {e}")
                    return None
                sleep_for = self._compute_backoff_delay(attempt)
                print(f"[WARN] Kalshi request error. Retrying in {sleep_for:.2f}s... ({attempt+1}/{KALSHI_MAX_RETRIES})")
                time.sleep(sleep_for)
                continue

            if response.status_code == 429:
                self._last_request_ts = time.time()
                if attempt >= KALSHI_MAX_RETRIES:
                    print(f"[ERROR] Kalshi rate limit reached repeatedly for {url}")
                    return None
                sleep_for = self._compute_backoff_delay(
                    attempt, response.headers.get("Retry-After"))
                sleep_for += random.uniform(0, 0.3)
                print(f"[WARN] Kalshi rate limited (429) on {url}. Sleeping {sleep_for:.2f}s before retry {attempt+1}.")
                time.sleep(sleep_for)
                continue

            try:
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                self._last_request_ts = time.time()
                if attempt >= KALSHI_MAX_RETRIES:
                    print(f"[ERROR] Kalshi request failed after retries for {url}: {e}")
                    return None
                sleep_for = self._compute_backoff_delay(attempt)
                print(f"[WARN] Kalshi request HTTP error. Retrying in {sleep_for:.2f}s... ({attempt+1}/{KALSHI_MAX_RETRIES})")
                time.sleep(sleep_for)

        return None

    def get_series(self, category, tag):
        if tag is not None:
            series_params = {"limit": 1000, "category": category, "tags": tag}
        else:
            series_params = {"limit": 1000, "category": category}

        all_series = []
        while True:
            response = self._get_with_backoff(
                f"{self.BASE}/series", params=series_params)
            if response is None:
                print(f"[ERROR] Failed to fetch series after retries for params {series_params}")
                break
            series_data = response.json()

            series = series_data.get("series", [])
            all_series.extend(series)

            cursor = series_data.get("cursor")
            if not cursor:
                break

            series_params["cursor"] = cursor
            time.sleep(KALSHI_RATE_LIMIT)

        for series in all_series:
            self.title_to_ticker[series['title']] = series['ticker']

        return all_series

    def get_all_markets_for_category(self, category, limit=200):
        """Fetch ALL open markets for a category in one paginated call (much faster)."""
        if category in self._category_markets_cache:
            return self._category_markets_cache[category]

        market_params = {
            "limit": limit,
            "status": "open"
        }

        all_markets = []
        print(f"[INFO] Fetching all Kalshi markets (open, paginated)...")
        while True:
            response = self._get_with_backoff(
                f"{self.BASE}/markets", params=market_params)
            if response is None:
                print(f"[ERROR] Failed to fetch all markets after retries")
                break
            data = response.json()
            page_markets = data.get('markets', [])
            all_markets.extend(page_markets)
            print(f"[INFO] Kalshi markets fetched so far: {len(all_markets)}")

            cursor = data.get("cursor")
            if not cursor:
                break
            market_params["cursor"] = cursor

        # Deduplicate and update caches
        unique_markets = []
        for market in all_markets:
            ticker = market.get('ticker', '')
            if ticker not in self._seen_market_tickers:
                self._seen_market_tickers.add(ticker)
                unique_markets.append(market)
                title = f"{market['title']} {market.get('yes_sub_title', '')}"
                self.title_to_markets[title.strip()] = market

        self._category_markets_cache[category] = unique_markets
        print(f"[INFO] Total unique Kalshi markets: {len(unique_markets)}")
        return unique_markets

    def get_markets(self, ticker, limit=100, force_refresh=False):
        market_params = {
            "series_ticker": ticker,
            "limit": limit,
            "status": "open"
        }

        if not force_refresh and ticker in self.series_to_markets:
            return self.series_to_markets[ticker]

        all_markets = []
        while True:
            response = self._get_with_backoff(
                f"{self.BASE}/markets", params=market_params)
            if response is None:
                print(f"[ERROR] Failed to fetch markets for {ticker} after retries")
                break
            data = response.json()
            page_markets = data.get('markets', [])
            all_markets.extend(page_markets)

            cursor = data.get("cursor")
            if not cursor:
                break
            market_params["cursor"] = cursor
            time.sleep(KALSHI_RATE_LIMIT)

        for market in all_markets:
            title = f"{market['title']} {market.get('yes_sub_title', '')}"
            self.title_to_markets[title.strip()] = market
        self.series_to_markets[ticker] = all_markets

        return all_markets

    def print_market(self, market):
        if not market:
            return
        print(f"Kalshi: {market['title']} {market['yes_sub_title']}")
        print(f"yes ask: {market['yes_ask']}")
        print(f"no ask: {market['no_ask']}")

    def get_series_ticker_for_event(self, event_ticker):
        if event_ticker in self.event_to_series:
            return self.event_to_series[event_ticker]

        response = self._get_with_backoff(
            f"{self.BASE}/events/{event_ticker}")
        if response is None:
            print(f"[ERROR] Failed to fetch event {event_ticker} after retries")
            return None
        try:
            series_ticker = response.json()["event"]["series_ticker"]
        except KeyError:
            print(f"[ERROR] Event {event_ticker} has no series_ticker")
            return None

        time.sleep(KALSHI_RATE_LIMIT)
        self.event_to_series[event_ticker] = series_ticker
        return series_ticker

    def get_market_yn_link(self, market):
        if not market:
            return None, None, None

        event_ticker = market.get('event_ticker')
        if not event_ticker:
            return None, None, None
        series_ticker = self.get_series_ticker_for_event(event_ticker)
        if not series_ticker:
            return None, None, None

        link = f"https://kalshi.com/markets/{series_ticker.lower()}"

        yes_ask = market.get('yes_ask')
        no_ask = market.get('no_ask')

        if yes_ask is None or no_ask is None:
            return None, None, None

        return yes_ask, no_ask, link


class ArbitragePair:
    def __init__(self, k_title, k_yes_price, k_no_price, k_link, p_title, p_yes_price, p_no_price, p_link):
        self.kalshi_title = k_title
        self.kalshi_yes_price = float(k_yes_price)/100
        self.kalshi_no_price = float(k_no_price)/100
        self.kalshi_link = k_link

        self.poly_title = p_title
        self.poly_yes_price = float(p_yes_price)
        self.poly_no_price = float(p_no_price)
        self.poly_link = p_link

        # none for no, pk for yes poly and no kalshi, kp for yes kalshi no poly, both for both
        self.arbitrage = "none"
        self.edge = 0.0
        self.check_arb()

    def check_arb(self):
        poly_yes_kalshi_no = self.poly_yes_price + self.kalshi_no_price
        kalshi_yes_poly_no = self.kalshi_yes_price + self.poly_no_price

        if poly_yes_kalshi_no < 1 and kalshi_yes_poly_no < 1:
            if poly_yes_kalshi_no < kalshi_yes_poly_no:
                self.arbitrage = "pk"
                self.edge = 1 - poly_yes_kalshi_no
            else:
                self.arbitrage = "kp"
                self.edge = 1 - kalshi_yes_poly_no
        elif poly_yes_kalshi_no < 1:
            self.arbitrage = "pk"
            self.edge = 1 - poly_yes_kalshi_no
        elif kalshi_yes_poly_no < 1:
            self.arbitrage = "kp"
            self.edge = 1 - kalshi_yes_poly_no

        return self.arbitrage

    def print(self):
        if self.arbitrage == "none":
            return

        print("=" * 80)

        print("\nKALSHI")
        print(f"  Title: {self.kalshi_title}")
        print(f"  YES:   {self.kalshi_yes_price:.4f}")
        print(f"  NO:    {self.kalshi_no_price:.4f}")
        print(f"  LINK:  {self.kalshi_link}")

        print("\nPOLYMARKET")
        print(f"  Title: {self.poly_title}")
        print(f"  YES:   {self.poly_yes_price:.4f}")
        print(f"  NO:    {self.poly_no_price:.4f}")
        print(f"  LINK:  {self.poly_link}")

        if (self.arbitrage == "kp"):
            print("\nBuy yes on Kalshi, No on Polymarket\n")
        else:
            print("\nBuy yes on Polymarket, No on Kalshi\n")
        print(f"Edge = {self.edge:.4%}\n")
        print("="*80)


def write_to_file(filepath, data):
    with open(filepath, "w") as f:
        for event in data:
            f.write(f"{event['title']}\n")


if __name__ == "__main__":
    poly_extractor = PolyExtractor()
    kalshi_extractor = KalshiExtractor()

    bitcoin_events = poly_extractor.get_events("Trump")
    bitcoin_series = []
    bitcoin_series.extend(kalshi_extractor.get_series(
        category="Politics", tag="Trump Agenda"))
    bitcoin_series.extend(kalshi_extractor.get_series(
        category="Politics", tag="Trump Policies"))

    # get list of all markets under all series/events related to category specified
    bitcoin_poly_markets = []
    bitcoin_kalshi_markets = []

    for event in bitcoin_events:
        markets = poly_extractor.get_markets(event)
        for market in markets:
            bitcoin_poly_markets.append(market['question'])

    for series in bitcoin_series:
        markets = kalshi_extractor.get_markets(series['ticker'])
        for market in markets:
            bitcoin_kalshi_markets.append(
                f"{market['title']} {market['yes_sub_title']}")

    print(f"len of poly markets {len(bitcoin_poly_markets)}")
    print(f"len of kalshi markets {len(bitcoin_kalshi_markets)}")

    matching_pairs = get_matching_pairs(
        poly_titles_in=bitcoin_poly_markets, kalshi_titles_in=bitcoin_kalshi_markets)
    #
    # with open("arb_pairs.json", "r") as f:
    #     matching_pairs = json.load(f)
    #
    pair_list = []
    # print matching arb pairs
    for matching_pair in matching_pairs:
        poly_title = matching_pair['poly_title']
        poly_market = poly_extractor.title_to_markets.get(poly_title, {})
        kalshi_title = matching_pair['kalshi_title']
        kalshi_market = kalshi_extractor.title_to_markets.get(kalshi_title, {})

        p_yes, p_no, p_link = poly_extractor.get_market_yn_link(poly_market)
        k_yes, k_no, k_link = kalshi_extractor.get_market_yn_link(
            kalshi_market)

        if None in (kalshi_title, k_yes, k_no, k_link, poly_title, p_yes, p_no, p_link):
            continue
        pair_list.append(ArbitragePair(kalshi_title, k_yes,
                         k_no, k_link, poly_title, p_yes, p_no, p_link))

        # poly_extractor.print_market(poly_market)
        # print("\n")
        # kalshi_extractor.print_market(kalshi_market)
        # print("\n"*3)

    arbitrage_pair_list = [
        pair for pair in pair_list if pair.arbitrage != "none"]

    arbitrage_pair_list.sort(key=lambda x: x.edge)
    print('Arb Pairs:')
    for arb_pair in arbitrage_pair_list:
        arb_pair.print()
