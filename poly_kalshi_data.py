import requests

class PolyExtractor:
    def __init__(self):
        self.BASE = "https://gamma-api.polymarket.com/"

    def get_tag_id(self, tag_name : str):
        all_tags = requests.get(f"{self.BASE}/tags").json()
        for tag in all_tags:
            if tag['label'].lower() == tag_name.lower():
                tag_id = tag['id']
                print(f"found tag {tag_name}, with id {tag_id}")
                return tag_id
            
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



if __name__ == "__main__":
    poly_extractor = PolyExtractor()

    bitcoin_events = poly_extractor.get_events("Bitcoin")
    for bitcoin_event in bitcoin_events:
        print(bitcoin_event['title'])
    