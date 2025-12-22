import requests
import time
class PolyExtractor:
    def __init__(self):
        self.BASE = "https://gamma-api.polymarket.com/"

    def get_tag_id(self, tag_name : str):
        all_tags = requests.get(f"{self.BASE}/tags").json()
        for tag in all_tags:
            if tag['label'].lower() == tag_name.lower():
                tag_id = tag['id']
                return tag_id
        print("[ERROR] did not find tag") 
        return None
    
    def get_events(self, tag_name = None, closed = "false", limit = 1000):
       event_params = {"limit" : limit,
                 "closed" : closed}
       if tag_name:
           event_params["tag_id"] = self.get_tag_id(tag_name)

       return requests.get(f"{self.BASE}/events", params=event_params).json()


class KalshiExtractor:
    def __init__(self):
        self.BASE = "https://api.elections.kalshi.com/trade-api/v2"

    def get_series(self, category, tags):
        series_params = {"limit" : 1000, "category" : category, "tags" : tags}

        all_series = []
        while True:
            series_data = requests.get(f"{self.BASE}/series", params=series_params).json()
            series = series_data.get("series", [])
            all_series.extend(series)

            cursor = series_data.get("cursor")
            if not cursor:
                break

            series_params["cursor"] = cursor
            time.sleep(1/19) 
        return all_series



if __name__ == "__main__":
    poly_extractor = PolyExtractor()

    bitcoin_events = poly_extractor.get_events("Bitcoin")
    print("Poly series data:")
    for bitcoin_event in bitcoin_events:
        print(bitcoin_event['title'])

    kalshi_extractor = KalshiExtractor()    

    bitcoin_series = kalshi_extractor.get_series(category="Crypto", tags="BTC")
    print("\n"*3 + "Kalshi series data:")
    for bitcoin_event in bitcoin_series:
        print(bitcoin_event['title'])