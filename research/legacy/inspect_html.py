
from bs4 import BeautifulSoup

with open('/tmp/maxi_debug.html', 'r') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

target = soup.find(string=lambda text: text and "Beef T-Bone Steak" in text)
if target:
    print("Found text!")
    parent = target.parent
    for i in range(10):
        print(f"Level {i}: {parent.name} - {parent.get('class')} - {parent.get('data-testid')}")
        parent = parent.parent
else:
    print("Text not found")
