
from bs4 import BeautifulSoup

with open('/tmp/maxi_debug.html', 'r') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

prices = soup.find_all(attrs={"data-testid": "sale-price"})
if not prices:
    prices = soup.find_all(attrs={"data-testid": "regular-price"})

if prices:
    price = prices[0]
    print(f"Price text: {price.text}")
    print(f"Price HTML: {price}")
