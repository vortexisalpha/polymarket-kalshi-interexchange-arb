import requests

BASE = "https://gamma-api.polymarket.com/" #?tag_id=100381&limit=1&closed=false"

tags = requests.get(f"{BASE}/tags").json()
#you can only filter events by tag so get bitcoin tag (i dont think there is a crypto one) and then add that as a param for events
for tag in tags:
    if tag["label"] == "Bitcoin":
        print(f"label: {tag['label']} | slug: {tag['slug']}")
        print(tag["id"])
        bitcoin_tag = tag["id"]

event_params = {"limit" : 10000,
                 "tag_id" : bitcoin_tag,
                 "closed" : "false"}

response = requests.get(f"{BASE}/events", params=event_params).json()

crypto_markets = response

print(crypto_markets[0].keys())
print("\n"*3)

for market in crypto_markets:
    print(market["title"])


with open("poly_btc_events.txt", "w") as f:
    for market in crypto_markets:
        f.write(f"{market['title']}\n")