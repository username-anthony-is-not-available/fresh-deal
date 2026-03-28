
from bs4 import BeautifulSoup

with open('/tmp/maxi_debug.html', 'r') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

tiles = soup.select('div[class*="product-tile"], div[data-testid="product-tile"]')
print(f"Found {len(tiles)} tiles with native_tile_selector")

# Try to find any div that might be a tile
all_divs = soup.find_all('div')
print(f"Total divs: {len(all_divs)}")

# Look for the product names in the divs
for name in ["Beef T-Bone Steak", "Ah Caramel!", "Bacon"]:
    found = soup.find(string=lambda text: text and name in text)
    if found:
        print(f"Found {name} in {found.parent.name} with classes {found.parent.get('class')}")
    else:
        print(f"Did NOT find {name} as text in HTML")
