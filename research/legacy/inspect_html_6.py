
from bs4 import BeautifulSoup

with open('/tmp/maxi_debug.html', 'r') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

# Look for anything related to "store" or "location" in button or div
for tag in soup.find_all(['button', 'div', 'span', 'p']):
    text = tag.get_text().lower()
    if 'store' in text or 'location' in text or 'postal' in text:
        if tag.name == 'button' or 'picker' in str(tag.get('class')):
            print(f"Tag: {tag.name} - Class: {tag.get('class')} - Text: {tag.get_text()[:50]}")
