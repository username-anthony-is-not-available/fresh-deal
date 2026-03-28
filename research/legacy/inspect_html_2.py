
from bs4 import BeautifulSoup

with open('/tmp/maxi_debug.html', 'r') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

target = soup.find(string=lambda text: text and "Beef T-Bone Steak" in text)
if target:
    print(f"Found in tag: {target.parent.name}")
    print(target.parent.text[:1000])
else:
    print("Text not found")
