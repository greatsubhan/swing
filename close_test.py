import requests, json
r = requests.post(
    'https://api-fxpractice.oanda.com/v3/accounts/101-011-30754943-003/orders',
    headers={'Authorization': 'Bearer 78daf54cdf8b8448f2561d35c22efc06-561a50ea58490e6526f5bc6debe1665f', 'Content-Type': 'application/json'},
    json={'order': {'type': 'MARKET', 'instrument': 'NAS100_USD', 'units': '-1', 'timeInForce': 'FOK'}},
    timeout=15
)
d = r.json()
f = d.get('orderFillTransaction', {})
print(f"Closed at {f.get('price')} | P/L: {f.get('pl')} | Balance: {f.get('accountBalance')}")