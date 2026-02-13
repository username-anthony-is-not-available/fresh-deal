
from bs4 import BeautifulSoup

with open('/tmp/maxi_debug.html', 'r') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

for tag in soup.find_all(True):
    if tag.name != 'script' and tag.string and "Beef T-Bone Steak" in tag.string:
        print(f"Found in {tag.name}: {tag.string.strip()} - classes: {tag.get('class')}")

# Also check for text in children if not directly in tag.string
for tag in soup.find_all(True):
    if tag.name != 'script' and any(string and "Beef T-Bone Steak" in string for string in tag.strings):
         if not any(child.name != 'script' and any(s and "Beef T-Bone Steak" in s for s in child.strings) for child in tag.find_all(recursive=False)):
             print(f"Found leaf container {tag.name}: classes: {tag.get('class')}")
