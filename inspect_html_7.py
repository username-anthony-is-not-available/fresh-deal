
from bs4 import BeautifulSoup

with open('/tmp/maxi_debug.html', 'r') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

tag = soup.find(attrs={"data-testid": "iceberg-fulfillment-trigger"})
if tag:
    print(f"Found iceberg-fulfillment-trigger: {tag.name} - {tag.get_text()}")
else:
    print("Not found")
