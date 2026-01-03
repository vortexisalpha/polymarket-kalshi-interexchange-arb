from dataclasses import dataclass
import json
import re


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
    link: str


class Formatter:
    def __init__(self):
        self.enable_logs = True
        # ai generated regex
        self._AMOUNT_RE = re.compile(
            r"""
            (?P<prefix>\$)?
            (?P<num>\d{1,3}(?:,\d{3})*|\d+)
            (?P<suffix>[kKmMbB])?
            """,
            re.VERBOSE
        )

        self._UP_RE = re.compile(
            r"\b(reach|hit|touch|tag|rise\s*to|rally\s*to|climb\s*to|surge\s*to|jump\s*to|pump\s*to|break\s*above|above)\b",
            re.IGNORECASE
        )

        self._DOWN_RE = re.compile(
            r"\b(dip\s*to|drop\s*to|fall\s*to|crash\s*to|sink\s*to|dump\s*to|plunge\s*to|break\s*below|below)\b",
            re.IGNORECASE
        )

    def LOG(self, msg):
        if self.enable_logs == True:
            print(msg)

    # ai generated functions to return upper and lower bound from title:
    def _all_amounts_with_pos(self, text):
        """
        Returns list of (pos, value) for each amount-like token in text.
        """
        out = []
        for m in self._AMOUNT_RE.finditer(text):
            out.append((m.start(), self._normalize_amount(m.group(0))))
        return out

    def bounds_from_title(self, title):
        """
        Returns (upper_bound, lower_bound).

        Rules:
        - If the title contains an "up" cue (reach/hit/break above/etc), numbers near that cue are treated as upper targets.
        - If the title contains a "down" cue (dip/drop/break below/etc), numbers near that cue are treated as lower targets.
        - If both appear (e.g., "hit 80k or 150k first"), we infer:
            upper_bound = max(numbers), lower_bound = min(numbers)
        (because it’s explicitly comparing two price levels).
        - If cues are absent, returns (None, None).
        """
        t = title.lower()
        amounts = self._all_amounts_with_pos(title)
        if not amounts:
            return None, None

        up_hits = [(m.start(), m.end()) for m in self._UP_RE.finditer(t)]
        down_hits = [(m.start(), m.end()) for m in self._DOWN_RE.finditer(t)]

        # Helper: choose nearest number after a cue (prefer) else nearest before
        def pick_number_near(cue_span):
            cue_start, cue_end = cue_span
            after = [(pos, val) for (pos, val) in amounts if pos >= cue_end]
            if after:
                # first number after cue
                return min(after, key=lambda x: x[0])[1]
            before = [(pos, val) for (pos, val) in amounts if pos < cue_start]
            if before:
                # closest number before cue
                return max(before, key=lambda x: x[0])[1]
            return None

        upper = None
        lower = None

        # If both directions are clearly present, but not necessarily tied to separate cues,
        # and there are >=2 numbers, treat them as bounds (common "X or Y first" style).
        if up_hits and down_hits and len(amounts) >= 2:
            vals = [v for _, v in amounts]
            return max(vals), min(vals)

        # Otherwise, assign by detected cues
        if up_hits:
            # If multiple up cues, take the max of their associated targets
            uppers = [pick_number_near(span) for span in up_hits]
            uppers = [u for u in uppers if u is not None]
            if uppers:
                upper = max(uppers)

        if down_hits:
            # If multiple down cues, take the min of their associated targets
            lowers = [pick_number_near(span) for span in down_hits]
            lowers = [l for l in lowers if l is not None]
            if lowers:
                lower = min(lowers)

        # Special-case: "hit X or Y first?" with only "hit" (treated as up cue)
        # In that case, set bounds from the two levels.
        if upper is not None and lower is None and len(amounts) >= 2:
            # If the title looks comparative, infer bounds.
            if re.search(r"\b(or|vs|versus|first)\b", t):
                vals = [v for _, v in amounts]
                return max(vals), min(vals)

        return upper, lower

    def _normalize_amount(self, raw):
        s = raw.replace("$", "").replace(",", "").strip()
        mult = 1
        if s and s[-1] in "kKmMbB":
            suffix = s[-1].lower()
            s = s[:-1]
            mult = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[suffix]
        return int(float(s) * mult)

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

            series_ticker = market['event_ticker'].split('-')[0]

            link = f"https://kalshi.com/markets/{series_ticker.lower()}"
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
                title, category, yes_price, no_price, close_time, market_type, exchange, strike_lb, strike_ub, link)

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
            slug = market['slug']
            link = f"https://polymarket.com/market/{slug}"

            group_item_title = market.get('groupItemTitle', '')
            if len(group_item_title) > 0:
                group_item_title = group_item_title.replace(
                    ",", "").replace("$", "")
                if group_item_title[0] == '<':
                    strike_ub = int(group_item_title[1:])
                    strike_lb = None

                elif group_item_title[0] == '>':
                    strike_ub = None
                    strike_lb = int(group_item_title[1:])

                elif '-' in group_item_title and group_item_title[0].isdigit():
                    prices = group_item_title.split('-')
                    strike_lb = int(prices[0])
                    strike_ub = int(prices[1])

                elif group_item_title.isdigit():
                    strike_ub = int(group_item_title)
                    strike_lb = None

                else:
                    strike_ub, strike_lb = self.bounds_from_title(
                        title)
            else:
                strike_ub, strike_lb = self.bounds_from_title(title)

            #
            # self.LOG(f"title = {title}")
            # self.LOG(f"group_item_title = {group_item_title}")
            # self.LOG(f"lower_bound = {strike_lb}")
            # self.LOG(f"upper_bound = {strike_ub}")
            # self.LOG("\n\n\n")

            market_type = market.get('marketType', '')
            poly_market_ttm[title] = Market(
                title, category, yes_price, no_price, close_time, market_type, exchange, strike_lb, strike_ub, link)

        return kalshi_market_ttm, poly_market_ttm
