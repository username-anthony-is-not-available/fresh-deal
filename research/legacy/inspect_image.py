
from bs4 import BeautifulSoup

with open('/tmp/maxi_debug.html', 'r') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

images = soup.find_all(attrs={"data-testid": "product-image"})
if images:
    img_tag = images[0].find('img')
    if img_tag:
        print(f"Image src: {img_tag.get('src')}")
        print(f"Image data-src: {img_tag.get('data-src')}")
