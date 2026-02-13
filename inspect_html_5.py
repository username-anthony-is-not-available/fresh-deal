
from bs4 import BeautifulSoup

with open('/tmp/maxi_debug.html', 'r') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

titles = soup.find_all(attrs={"data-testid": "product-title"})
print(f"Found {len(titles)} product titles")

if titles:
    title = titles[0]
    print(f"Title: {title.text}")
    parent = title.parent
    for i in range(10):
        print(f"Level {i}: {parent.name} - {parent.get('class')} - {parent.get('data-testid')}")
        if parent.find(attrs={"data-testid": "sale-price"}) or parent.find(attrs={"data-testid": "regular-price"}):
             print(f"  --- Found price at level {i}!")
        parent = parent.parent
