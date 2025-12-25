import requests



POLY = "https://gamma-api.polymarket.com/"
response = requests.get(f"{POLY}/tags").json()

for a in response:
    print(a['label'])

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"

response = requests.get(f"{KALSHI}/tags")
print(response)


