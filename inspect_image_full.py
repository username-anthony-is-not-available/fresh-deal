
from bs4 import BeautifulSoup

with open('/tmp/maxi_debug.html', 'r') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

images = soup.find_all(attrs={"data-testid": "product-image"})
if images:
    print(images[0])
