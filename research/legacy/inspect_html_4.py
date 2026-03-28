
from bs4 import BeautifulSoup

with open('/tmp/maxi_debug.html', 'r') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

h3 = soup.find('h3', string=lambda t: t and "Beef T-Bone Steak" in t)
if h3:
    parent = h3.parent
    for i in range(5):
        print(f"Level {i}: {parent.name} - {parent.get('class')} - {parent.get('data-testid')}")
        parent = parent.parent
